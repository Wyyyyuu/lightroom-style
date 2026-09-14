"""Command boundary tests with fake SDK, separate from real Lightroom acceptance."""
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import unquote

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('bridge_client', ROOT / 'lightroom-bridge/bridge_client.py')
CLIENT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLIENT)


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.globals().pluginPath = (ROOT / 'lightroom-bridge/PhotoStyleBridge.lrplugin').as_posix()
        self.lua.execute('''
            _PLUGIN={path=pluginPath}; applied=0; snapshots=0; copies=0
            local function makePhoto(id,isCopy,name)
                return {localIdentifier=id, raw={isVirtualCopy=isCopy,path='C:/source.jpg',virtualCopies={}},
                    values={ProcessVersion='15.4',Exposure2012=0,Contrast2012=0,Saturation=0},
                    getRawMetadata=function(self,k) return self.raw[k] end,
                    getFormattedMetadata=function(self,k) if k=='copyName' then return name else return 'source.jpg' end end,
                    getDevelopSettings=function(self) return self.values end,
                    createDevelopSnapshot=function() snapshots=snapshots+1; return true end,
                    applyDevelopSettings=function(self,values)
                        applied=applied+1
                        if not simulateMismatch then for k,v in pairs(values) do self.values[k]=v end end
                    end}
            end
            master=makePhoto(1,false,''); copy=makePhoto(2,true,'PhotoStyle-test')
            master.raw.virtualCopies={copy}; selected={master,copy}
            catalog={getPath=function() return 'C:/test.lrcat' end,
                findPhotoByPath=function(self,p) if p=='C:/source.jpg' then return master end end,
                withWriteAccessDo=function(self,name,f,options) if beforeWrite then beforeWrite() end; f(); return 'executed' end,
                getFolderByPath=function() return {} end,
                setActiveSources=function() return true end,
                getTargetPhoto=function() return selected[1] end,
                setSelectedPhotos=function(self,p,others) selected={p}; for _,v in ipairs(others) do table.insert(selected,v) end end,
                getTargetPhotos=function() return selected end,
                createVirtualCopies=function(self,name) copies=copies+1; assert(#selected==1); return {copy} end}
            mocks={LrApplication={activeCatalog=function() return catalog end},
                   LrTasks={pcall=pcall,sleep=function() end},
                   LrFileUtils={},LrPathUtils={parent=function(p) return 'C:/' end}}
            import=function(name) return assert(mocks[name]) end
            commands=dofile(pluginPath .. '/Commands.lua')
            fields={protocol='1',id=string.rep('a',32),catalog='C:/test.lrcat',path='C:/source.jpg',
                    photo_id='2',deadline=tostring(os.time()+60),action='apply',
                    ['set.Exposure2012']='0.7',['expect.Exposure2012']='0'}
            function run() return commands.execute(fields,{}) end
        ''')

    def test_apply_snapshot_and_readback(self):
        result = self.lua.eval('run()')
        self.assertTrue(result['readback_verified'])
        self.assertAlmostEqual(result['photo']['settings']['Exposure2012'], .7)
        self.assertEqual(self.lua.globals().snapshots, 1)
        self.assertEqual(self.lua.globals().master['values']['Exposure2012'], 0)

    def test_protected_original(self):
        self.lua.execute("fields.photo_id='1'")
        with self.assertRaisesRegex(Exception, 'originals'):
            self.lua.eval('run()')
        self.assertEqual(self.lua.globals().applied, 0)

    def test_white_balance_requires_custom_mode(self):
        self.lua.execute("copy.values.IncrementalTemperature=0; copy.values.WhiteBalance='As Shot'; fields['set.IncrementalTemperature']='8'; fields['expect.IncrementalTemperature']='0'")
        result=self.lua.eval('run()')
        self.assertEqual(result['photo']['settings']['WhiteBalance'],'Custom')
        self.assertEqual(result['photo']['settings']['IncrementalTemperature'],8)

    def test_stale_expected_and_gate_race(self):
        self.lua.execute("fields['expect.Exposure2012']='1'")
        with self.assertRaisesRegex(Exception, 'Stale'):
            self.lua.eval('run()')
        self.lua.execute("fields['expect.Exposure2012']='0'; beforeWrite=function() copy.values.Exposure2012=1 end")
        with self.assertRaisesRegex(Exception, 'changed before write'):
            self.lua.eval('run()')
        self.assertEqual(self.lua.globals().applied, 0)

    def test_identity_expiry_range_and_missing_expectation(self):
        for setup, error in [
            ("fields.catalog='C:/other.lrcat'", 'catalog changed'),
            ("fields.photo_id='3'", 'ID does not match'),
            ("fields.deadline='1'", 'expired'),
            ("fields['set.Exposure2012']='20'", 'Out-of-range'),
            ("fields['expect.Exposure2012']=nil", 'Missing field'),
            ("fields['set.Unknown']='1'", 'Unsupported develop'),
        ]:
            self.setUp()
            self.lua.execute(setup)
            with self.assertRaisesRegex(Exception, error):
                self.lua.eval('run()')
            self.assertEqual(self.lua.globals().applied, 0)

    def test_readback_mismatch_is_not_success(self):
        self.lua.execute('simulateMismatch=true')
        with self.assertRaisesRegex(Exception, 'readback did not match'):
            self.lua.eval('run()')
        self.assertEqual(self.lua.globals().snapshots, 1)

    def test_copy_restricts_selection(self):
        self.lua.execute("fields.action='copy'; fields.photo_id='1'")
        self.assertTrue(self.lua.eval('run()')['source_settings_unchanged'])
        self.assertEqual(self.lua.globals().copies, 1)

    def prepare_curve(self):
        self.lua.execute('''
            copy.values.EnableToneCurve=true
            copy.values.ParametricDarks=0; copy.values.ParametricLights=0
            copy.values.ParametricShadowSplit=25; copy.values.ParametricMidtoneSplit=50
            copy.values.ParametricHighlightSplit=75
            copy.values.ToneCurvePV2012={0,0,255,255}
            fields['set.Exposure2012']=nil; fields['expect.Exposure2012']=nil
            fields['set.ParametricDarks']='-12'; fields['expect.ParametricDarks']='0'
            fields['set.ParametricLights']='10'; fields['expect.ParametricLights']='0'
        ''')

    def test_parametric_curve_native_write_preserves_point_curve(self):
        self.prepare_curve()
        result=self.lua.eval('run()')
        self.assertTrue(result['readback_verified'])
        self.assertEqual(result['photo']['settings']['ParametricDarks'],-12)
        self.assertEqual(result['photo']['settings']['ParametricLights'],10)
        context=result['photo']['curve_state']
        self.assertEqual(context['ParametricMidtoneSplit'],50)
        self.assertEqual(context['ToneCurvePV2012']['4'],255)
        encoded=self.lua.eval("dofile(pluginPath .. '/Json.lua').encode")(result)
        self.assertEqual(json.loads(encoded)['photo']['curve_state']['ToneCurvePV2012']['4'],255)
        self.assertEqual(self.lua.globals().snapshots,1)
        self.assertIsNone(self.lua.globals().master['values']['ParametricDarks'])

    def test_curve_disabled_missing_or_stale_is_rejected(self):
        for setup,error in [
            ('copy.values.EnableToneCurve=false','verified enabled'),
            ('copy.values.EnableToneCurve=nil','verified enabled'),
            ('copy.values.ParametricDarks=nil','absent'),
            ("fields['set.ParametricDarks']='-101'",'Out-of-range'),
            ("fields['expect.ParametricDarks']='1'",'Stale'),
            ("fields['set.ToneCurvePV2012']='1'",'Unsupported develop'),
        ]:
            self.setUp(); self.prepare_curve(); self.lua.execute(setup)
            with self.assertRaisesRegex(Exception,error): self.lua.eval('run()')
            self.assertEqual(self.lua.globals().applied,0)

    def test_curve_context_race_stops_before_snapshot(self):
        self.prepare_curve()
        self.lua.execute('beforeWrite=function() copy.values.ParametricMidtoneSplit=60 end')
        with self.assertRaisesRegex(Exception,'Curve context changed'): self.lua.eval('run()')
        self.assertEqual(self.lua.globals().snapshots,0)
        self.assertEqual(self.lua.globals().applied,0)

    def test_curve_ignored_or_point_curve_changed_is_not_success(self):
        for setup in ['simulateMismatch=true', '''
            local original=copy.applyDevelopSettings
            copy.applyDevelopSettings=function(self,values)
                original(self,values); self.values.ToneCurvePV2012={0,8,255,255}
            end
        ''']:
            self.setUp(); self.prepare_curve(); self.lua.execute(setup)
            with self.assertRaisesRegex(Exception,'readback did not match'): self.lua.eval('run()')
            self.assertEqual(self.lua.globals().snapshots,1)

    def test_data_parser_rejects_duplicate_and_malformed_escapes(self):
        parse = self.lua.globals().commands['parse']
        prefix = 'protocol=1\nid=' + 'a' * 32 + '\n'
        self.assertEqual(parse(prefix + 'path=C%3A%2F%E4%B8%AD.jpg\n')['path'], 'C:/中.jpg')
        for tail in ['protocol=1', 'path=%QQ', 'path=%00', 'bad line']:
            with self.assertRaises(Exception):
                parse(prefix + tail)

    def prepare_point_curve(self):
        self.prepare_curve()
        self.lua.execute('''
            copy.values.ToneCurveName2012='Linear'; copy.values.HDREditMode=false
            copy.values.ExtendedToneCurvePV2012={0,0,255,255}
            copy.values.ToneCurvePV2012Blue={0,0,255,255}
            fields['set.ParametricDarks']=nil; fields['expect.ParametricDarks']=nil
            fields['set.ParametricLights']=nil; fields['expect.ParametricLights']=nil
            fields.action='read'; fields.expected_revision=run().photo.curve_revision
            fields.action='curve'; fields.curve_points='0,10,64,58,128,128,192,202,255,246'
        ''')

    def test_composite_points_update_both_representations_only(self):
        self.prepare_point_curve()
        result=self.lua.eval('run()')
        self.assertTrue(result['readback_verified'])
        curve=result['photo']['curve_state']
        self.assertEqual(curve['ToneCurvePV2012']['2'],10)
        self.assertEqual(curve['ExtendedToneCurvePV2012']['10'],246)
        self.assertEqual(curve['ToneCurvePV2012Blue']['2'],0)
        self.assertEqual(result['photo']['settings']['ParametricDarks'],0)
        self.assertEqual(curve['ToneCurveName2012'],'Custom')
        self.assertEqual(self.lua.globals().snapshots,1)

    def test_point_coordinates_rejected_before_mutation(self):
        for points in ['0,0,255','0,0,255,256','0,0,64,80,64,90,255,255',
                       '0,0,128,190,255,180','1,0,255,255','0,0,254,255',
                       '0,,255,255','0,0,255,255,','0,0,255,nan','0,0,255,2.5',
                       ',0,0,255,255','0,0;os.execute(1)']:
            self.setUp(); self.prepare_point_curve()
            self.lua.globals().fields['curve_points']=points
            with self.assertRaises(Exception): self.lua.eval('run()')
            self.assertEqual(self.lua.globals().applied,0)

    def test_point_guard_protects_source_stale_hdr_and_context(self):
        for setup,error,refresh in [
            ("fields.photo_id='1'",'originals',False),
            ("copy.values.ParametricLights=3",'Stale',False),
            ("copy.values.EnableToneCurve=false",'verified enabled',True),
            ("copy.values.HDREditMode=true",'HDR',True),
            ("copy.values.HDREditMode=1",'HDR',True),
            ("copy.values.ExtendedToneCurvePV2012={0,0,1024,1024}",'representations differ',True),
            ("fields['set.Exposure2012']='1'",'cannot mix',False),
            ("beforeWrite=function() copy.values.ToneCurvePV2012Blue={0,8,255,255} end",'changed before write',False),
        ]:
            self.setUp();self.prepare_point_curve();self.lua.execute(setup)
            if refresh: self.lua.execute("fields.action='read'; fields.expected_revision=run().photo.curve_revision; fields.action='curve'")
            with self.assertRaisesRegex(Exception,error): self.lua.eval('run()')
            self.assertEqual(self.lua.globals().applied,0)

    def test_point_readback_checks_curve_and_unrelated_settings(self):
        for setup in ['simulateMismatch=true', '''
            local old=copy.applyDevelopSettings
            copy.applyDevelopSettings=function(self,values) old(self,values); self.values.Exposure2012=1 end
        ''', '''
            local old=copy.applyDevelopSettings
            copy.applyDevelopSettings=function(self,values) old(self,values); self.values.ExtendedToneCurvePV2012={0,0,255,255} end
        ''']:
            self.setUp();self.prepare_point_curve();self.lua.execute(setup)
            with self.assertRaisesRegex(Exception,'readback did not match'): self.lua.eval('run()')
            self.assertEqual(self.lua.globals().snapshots,1)

    def test_queue_claim_is_at_most_once(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            rid = 'b' * 32
            request = folder / f'command-{rid}.request'
            request.write_text(f'protocol=1\nid={rid}\n', encoding='ascii')
            self.lua.globals().listFiles = lambda: self.lua.table_from([p.as_posix() for p in folder.iterdir()])
            self.lua.globals().exists = lambda p: Path(p).exists()
            self.lua.globals().move = lambda a,b: (Path(a).rename(b) is not None)
            self.lua.globals().read = lambda p: Path(p).read_text()
            self.lua.execute('''
                mocks.LrFileUtils.files=function() local all=listFiles(); local i=0; return function() i=i+1; return all[i] end end
                mocks.LrFileUtils.exists=exists; mocks.LrFileUtils.move=move; mocks.LrFileUtils.readFile=read
                mocks.LrPathUtils.child=function(a,b) return a .. '/' .. b end
                mocks.LrPathUtils.leafName=function(p) return p:match('[^/]+$') end
                executions=0; commands.execute=function() executions=executions+1; return {done=true} end
            ''')
            self.lua.globals().commands['poll'](folder.as_posix())
            request.write_text(f'protocol=1\nid={rid}\n', encoding='ascii')
            self.lua.globals().commands['poll'](folder.as_posix())
            self.assertEqual(self.lua.globals().executions, 1)
            self.assertTrue(json.loads((folder / f'command-{rid}.result.json').read_text())['ok'])


class ClientTests(unittest.TestCase):
    def test_point_client_validates_data_before_creating_request(self):
        self.assertEqual(CLIENT.encode_curve([[0,10],[64,58],[255,246]]),'0,10,64,58,255,246')
        invalid=[None,[],[[0,0]],[[0,0],[255,256]],[[0,0],[128,200],[255,190]],
                 [[0,0],[0,8],[255,255]],[[0,False],[255,255]],[[0,0],[255,float('nan')]],
                 [[0,0],[255,2.5]],[[0,0,1],[255,255]],[[1,0],[255,255]]]
        with tempfile.TemporaryDirectory() as directory:
            for points in invalid:
                with self.assertRaises(ValueError):
                    CLIENT.send_command('curve',catalog='C:/test.lrcat',path='C:/source.jpg',photo_id='2',
                                        curve_points=points,expected_revision='revision',state_dir=Path(directory))
            self.assertEqual(list(Path(directory).iterdir()),[])

    def test_point_revision_and_coordinates_are_encoded_as_data(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(CLIENT,'wait_result',return_value={'ok':True}):
                CLIENT.send_command('curve',catalog='C:/test.lrcat',path='C:/source.jpg',photo_id='2',
                                    curve_points=[[0,10],[255,246]],expected_revision='{"a":"x=y\\n"}',state_dir=Path(directory))
            content=next(Path(directory).glob('*.request')).read_text()
            fields={k:unquote(v) for k,v in (line.split('=',1) for line in content.splitlines())}
            self.assertEqual(fields['curve_points'],'0,10,255,246')
            self.assertEqual(fields['expected_revision'],'{"a":"x=y\\n"}')

    def test_native_receipt_correlates_and_encodes_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            def respond():
                while not list(state.glob('*.request')):
                    time.sleep(.01)
                path = next(state.glob('*.request'))
                fields = dict(line.split('=',1) for line in path.read_text().splitlines())
                self.assertEqual(unquote(fields['path']), 'C:/中 space.jpg')
                rid = fields['id']
                result = state / f'command-{rid}.result.json'
                result.write_text(json.dumps({'protocol':1,'id':rid,'ok':True,'result':{}}))
                Path(str(result)+'.ready').touch()
            thread = threading.Thread(target=respond)
            thread.start()
            response = CLIENT.send_command('read',catalog='C:/test.lrcat',path='C:/中 space.jpg',photo_id='1',state_dir=state,timeout=3)
            thread.join()
            self.assertTrue(response['ok'])

    def test_timeout_reports_unknown_without_resubmitting(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            response = CLIENT.send_command('copy',catalog='C:/test.lrcat',path='C:/source.jpg',photo_id='1',state_dir=state,timeout=1)
            self.assertEqual(response['status'], 'outcome_unknown')
            self.assertEqual(len(list(state.glob('*.request'))),1)
            self.assertEqual(CLIENT.wait_result(state,response['id'],0)['status'],'outcome_unknown')


if __name__ == '__main__':
    unittest.main()
