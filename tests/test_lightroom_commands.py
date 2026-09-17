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


    def calibration_fixture(self):
        self.lua.execute("""
            fields['set.Exposure2012']=nil; fields['expect.Exposure2012']=nil
            copy.values.RedHue=0; copy.values.GreenHue=0; copy.values.BlueHue=0
            copy.values.EnableCalibration=true;copy.values.RedSaturation=4;copy.values.GreenSaturation=5
            copy.values.BlueSaturation=6;copy.values.ShadowTint=2;copy.values.CameraProfile='Embedded'
            copy.values.HueAdjustmentRed=7
            fields['set.RedHue']='12';fields['expect.RedHue']='0'
            fields['set.GreenHue']='-8';fields['expect.GreenHue']='0'
            fields['set.BlueHue']='-15';fields['expect.BlueHue']='0'
        """)

    def test_calibration_hues_preserve_hsl_profile_process_and_other_calibration(self):
        self.calibration_fixture()
        result=self.lua.eval('run()')
        self.assertTrue(result['readback_verified'])
        settings=result['photo']['settings']
        self.assertEqual([settings[k] for k in ('RedHue','GreenHue','BlueHue')],[12,-8,-15])
        self.assertEqual(settings['HueAdjustmentRed'],7)
        self.assertEqual(settings['ProcessVersion'],'15.4')
        self.assertEqual(result['photo']['curve_state']['CameraProfile'],'Embedded')
        self.assertEqual(result['photo']['calibration_state']['RedSaturation'],4)
        self.assertEqual(result['photo']['calibration_state']['ShadowTint'],2)

    def test_calibration_disabled_absent_range_and_context_race_fail_before_write(self):
        cases=[
            ("copy.values.EnableCalibration=false",'verified enabled'),
            ("copy.values.RedHue=nil",'absent'),
            ("fields['set.BlueHue']='101'",'Out-of-range'),
            ("fields['expect.RedHue']='1'",'Stale'),
            ("beforeWrite=function() copy.values.CameraProfile='Changed' end",'context changed'),
            ("beforeWrite=function() copy.values.BlueSaturation=8 end",'context changed'),
        ]
        for setup,message in cases:
            self.setUp();self.calibration_fixture();self.lua.execute(setup)
            with self.assertRaisesRegex(Exception,message): self.lua.eval('run()')
            self.assertEqual(self.lua.globals().applied,0)
            self.assertEqual(self.lua.globals().snapshots,0)

    def test_calibration_unrequested_side_effect_fails_readback(self):
        for side_effect in ("self.values.RedSaturation=50","self.values.CameraProfile='Changed'",
                            "self.values.HueAdjustmentRed=42","self.values.ProcessVersion='6.7'"):
            self.setUp();self.calibration_fixture()
            self.lua.execute("local old=copy.applyDevelopSettings;copy.applyDevelopSettings=function(self,v) old(self,v);"+side_effect+" end")
            with self.assertRaisesRegex(Exception,'readback'): self.lua.eval('run()')
            self.assertEqual(self.lua.globals().snapshots,1)

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

    def prepare_grain(self):
        self.lua.execute("""
            copy.values.GrainAmount=0; copy.values.GrainSize=25; copy.values.GrainFrequency=50
            copy.values.EnableGrain=true; copy.values.EnableEffects=true
            copy.values.ToneCurvePV2012={0,8,128,128,255,247}
            fields['set.Exposure2012']=nil; fields['expect.Exposure2012']=nil
            fields['set.GrainAmount']='22'; fields['expect.GrainAmount']='0'
            fields['set.GrainSize']='28'; fields['expect.GrainSize']='25'
            fields['set.GrainFrequency']='55'; fields['expect.GrainFrequency']='50'
        """)

    def test_grain_read_apply_and_disable_preserve_baseline(self):
        self.prepare_grain()
        result=self.lua.eval('run()')
        self.assertTrue(result['readback_verified'])
        for key,value in [('GrainAmount',22),('GrainSize',28),('GrainFrequency',55)]:
            self.assertEqual(result['photo']['settings'][key],value)
        self.assertTrue(result['photo']['grain_state']['EnableGrain'])
        self.assertEqual(result['photo']['curve_state']['ToneCurvePV2012']['2'],8)
        self.assertEqual(result['photo']['settings']['Exposure2012'],0)
        self.assertIsNone(self.lua.globals().master['values']['GrainAmount'])
        self.lua.execute("fields['set.GrainAmount']='0'; fields['expect.GrainAmount']='22'; fields['expect.GrainSize']='28'; fields['expect.GrainFrequency']='55'")
        self.assertEqual(self.lua.eval('run()')['photo']['settings']['GrainAmount'],0)

    def test_grain_rejects_invalid_missing_stale_disabled_and_races(self):
        for setup,error in [
            ("fields['set.GrainAmount']='101'",'Out-of-range'),
            ("fields['set.GrainSize']='-1'",'Out-of-range'),
            ("fields['set.GrainFrequency']='101'",'Out-of-range'),
            ("fields['set.GrainAmount']='nan'",'Invalid numeric'),
            ("fields['expect.GrainSize']=nil",'Missing field'),
            ("copy.values.GrainFrequency=nil",'absent'),
            ("fields['expect.GrainAmount']='1'",'Stale'),
            ("copy.values.EnableGrain=false",'disabled'),
            ("copy.values.EnableEffects=false",'disabled'),
            ("beforeWrite=function() copy.values.EnableGrain=false end",'Grain context changed'),
            ("beforeWrite=function() copy.values.GrainAmount=9 end",'Parameter changed'),
            ("fields.photo_id='1'",'originals'),
        ]:
            with self.subTest(setup=setup):
                self.setUp(); self.prepare_grain(); self.lua.execute(setup)
                with self.assertRaisesRegex(Exception,error): self.lua.eval('run()')
                self.assertEqual(self.lua.globals().applied,0)
                self.assertEqual(self.lua.globals().snapshots,0)

    def test_grain_readback_mismatch_retains_recovery_snapshot(self):
        for setup in ['simulateMismatch=true', "local original=copy.applyDevelopSettings; copy.applyDevelopSettings=function(self,v) original(self,v); self.values.EnableGrain=false end"]:
            self.setUp(); self.prepare_grain(); self.lua.execute(setup)
            with self.assertRaisesRegex(Exception,'readback did not match'): self.lua.eval('run()')
            self.assertEqual(self.lua.globals().snapshots,1)

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

    def prepare_channels(self, channel):
        self.prepare_point_curve()
        self.lua.execute("""
            for _,suffix in ipairs({'Red','Green','Blue'}) do
                copy.values['ToneCurvePV2012'..suffix]={0,0,255,255}
                copy.values['ExtendedToneCurvePV2012'..suffix]={0,0,255,255}
            end
            fields.action='read'; fields.expected_revision=run().photo.curve_revision
            fields.action='curve-channel'
        """)
        self.lua.globals().fields['curve_channel']=channel

    def test_rgb_channels_preserve_composite_and_other_channels(self):
        for channel in ('red','green','blue'):
            self.setUp();self.prepare_channels(channel)
            r=self.lua.eval('run()');c=r['photo']['curve_state']
            self.assertEqual(r['curve_channel'],channel)
            self.assertTrue(r['readback_verified'])
            for suffix in ('Red','Green','Blue'):
                expected=10 if suffix.lower()==channel else 0
                self.assertEqual(c['ToneCurvePV2012'+suffix]['2'],expected)
                self.assertEqual(c['ExtendedToneCurvePV2012'+suffix]['2'],expected)
            self.assertEqual(c['ToneCurvePV2012']['2'],0)
            self.assertEqual(c['ExtendedToneCurvePV2012']['2'],0)
            self.assertEqual(self.lua.globals().master['values']['Exposure2012'],0)

    def test_channel_invalid_missing_stale_and_ambiguous_fail_before_write(self):
        cases=[("fields.curve_channel='cyan'",'Invalid',False),
               ("fields.curve_channel=nil",'Invalid',False),
               ("fields.action='curve'",'Invalid',False),
               ("copy.values.ToneCurvePV2012Red=nil",'absent',True),
               ("copy.values.ExtendedToneCurvePV2012Red={0,2,255,255}",'representations differ',True),
               ("copy.values.ToneCurvePV2012Green={0,2,255,255}",'Stale',False),
               ("beforeWrite=function() copy.values.ToneCurvePV2012Blue={0,2,255,255} end",'changed before write',False)]
        for setup,error,refresh in cases:
            self.setUp();self.prepare_channels('red');self.lua.execute(setup)
            if refresh:self.lua.execute("fields.action='read'; fields.expected_revision=run().photo.curve_revision;fields.action='curve-channel'")
            with self.assertRaisesRegex(Exception,error):self.lua.eval('run()')
            self.assertEqual(self.lua.globals().applied,0)
            self.assertEqual(self.lua.globals().snapshots,0)

    def test_channel_readback_rejects_wrong_channel_or_preservation_failure(self):
        for change in ('ToneCurvePV2012','ToneCurvePV2012Green','ExtendedToneCurvePV2012Red'):
            self.setUp();self.prepare_channels('red')
            self.lua.execute("local old=copy.applyDevelopSettings;copy.applyDevelopSettings=function(self,v) old(self,v);self.values['"+change+"']={0,3,255,255} end")
            with self.assertRaisesRegex(Exception,'readback did not match'):self.lua.eval('run()')
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

    def test_channel_client_routes_fail_closed_and_rejects_invalid_channels(self):
        for channel in ('red','green','blue'):
            with tempfile.TemporaryDirectory() as directory:
                with patch.object(CLIENT,'wait_result',return_value={'ok':True}):
                    CLIENT.send_command('curve',catalog='C:/test.lrcat',path='C:/source.jpg',photo_id='2',
                        curve_points=[[0,0],[255,245]],curve_channel=channel,expected_revision='fresh',state_dir=Path(directory))
                fields=dict(line.split('=',1) for line in next(Path(directory).glob('*.request')).read_text().splitlines())
                self.assertEqual(fields['action'],'curve-channel')
                self.assertEqual(fields['curve_channel'],channel)
        with tempfile.TemporaryDirectory() as directory:
            for action,channel in [('curve','cyan'),('read','red'),('apply','blue')]:
                with self.assertRaises(ValueError):
                    CLIENT.send_command(action,catalog='C:/test.lrcat',path='C:/source.jpg',photo_id='2',
                        curve_channel=channel,state_dir=Path(directory))
            self.assertEqual(list(Path(directory).iterdir()),[])

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
