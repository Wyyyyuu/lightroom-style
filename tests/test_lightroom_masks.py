"""Native-mask contract tests with Lua 5.1 SDK mocks, not photographic acceptance."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import test_lightroom_commands as existing
import test_lightroom_round as round_fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lightroom-style/scripts'))
import lightroom_client as client
import lightroom_round as runner


class MaskTests(unittest.TestCase):
    def setUp(self):
        existing.CommandTests.setUp(self)
        self.lua.globals().digestMock = lambda s: hashlib.md5(s.encode()).hexdigest()
        self.lua.execute("""
            fields['set.Exposure2012']=nil; fields['expect.Exposure2012']=nil
            maskValues={old={local_Clarity=.1,local_Texture=.2,local_Exposure=.3,local_Amount=100}}
            maskList={old={tool='subject'}}; chosen='old'; currentModule='library'; created=0
            copy.values.MaskGroupBasedCorrections=maskValues
            function copy:getDevelopSettings()
                if self.values.MaskGroupBasedCorrections~=maskValues then return self.values end
                local out={};for k,v in pairs(self.values) do out[k]=v end
                local groups={}
                for id,values in pairs(maskValues) do
                    local group={CorrectionID=id,CorrectionMasks=maskList[id]}
                    for k,v in pairs(values) do group['Local'..k:sub(7)]=v end
                    groups[#groups+1]=group
                end
                table.sort(groups,function(a,b) return a.CorrectionID<b.CorrectionID end)
                out.MaskGroupBasedCorrections=groups
                return out
            end
            function choose(id) if maskList[id] then chosen=id end end
            develop={
                goToMasking=function() end, getSelectedTool=function() return wrongTool and 'crop' or 'masking' end,
                getAllMasks=function()
                    if malformedInventory then return {{tool='brush'}} end
                    if pendingInventory and pendingInventory>0 then pendingInventory=pendingInventory-1; return nil end
                    local out={}
                    for id,tools in pairs(maskList) do out[#out+1]={ID=id,Name=id,Hidden=false,Tools=tools} end
                    return out
                end,
                getSelectedMask=function() return chosen end,
                selectMask=choose,
                getRange=function(param) if param=='local_Amount' then return 0,200 end; return -1,1 end,
                getValue=function(param) return maskValues[chosen][param] end,
                resetToDefault=function(param)
                    if ignoredLocal then return end
                    maskValues[chosen][param]=param=='local_Amount' and 100 or 0
                    if driftSelection then selected={master} end
                end,
                setValue=function(param,value)
                    if ignoredLocal then return end
                    maskValues[chosen][param]=value
                    if floatSettling and param=='local_Texture' then maskValues[chosen].local_Clarity=maskValues[chosen].local_Clarity+0.0000001 end
                    if globalSideEffect then copy.values.Texture=40 end
                    if otherLocalSideEffect and param=='local_Clarity' then maskValues[chosen].local_Exposure=2 end
                    if changeTool then wrongTool=true end
                    if changeCatalog then mocks.LrApplication.activeCatalog=function() return {getPath=function() return 'C:/other.lrcat' end} end end
                    if driftSelection then selected={master} end
                end,
                createNewMask=function(kind,subtype)
                    assert(kind=='aiSelection'); assert(subtype=='background' or subtype=='subject' or subtype=='sky')
                    created=created+1
                    if neverCompletes then return end
                    chosen='new'
                    maskList.new={tool=subtype}; pendingInventory=2
                    maskValues.new={local_Clarity=.5,local_Texture=.5,local_Exposure=.8,local_Amount=20,
                        local_Maincurve={0,0,255,255}}
                    if nonlinearInherited then maskValues.new.local_Maincurve={0,0,128,100,255,255} end
                end
            }
            mocks.LrDevelopController=develop
            mocks.LrMD5={digest=digestMock}
            mocks.LrApplicationView={
                switchToModule=function(name) currentModule=name end,
                getCurrentModuleName=function() return currentModule end
            }
            progress={}
            function runMask() return commands.execute(fields,progress) end
            fields.action='mask-read'
        """)
        revision = self.lua.eval('runMask()')['mask_revision']
        self.lua.globals().fields['expected_mask_revision'] = revision
        self.lua.execute("fields.action='mask-create'; fields.mask_type='background'; fields.clarity='-30'; fields.texture='-45'")

    def test_create_softens_only_new_mask_and_neutralizes_inherited_defaults(self):
        result = self.lua.eval('runMask()')
        self.assertTrue(result['readback_verified'])
        self.assertEqual(result['mask_id'], 'new')
        self.assertAlmostEqual(result['mask_settings']['clarity'], -30)
        self.assertAlmostEqual(result['mask_settings']['texture'], -45)
        self.assertEqual(self.lua.eval('maskValues.new.local_Exposure'), 0)
        self.assertEqual(self.lua.eval('maskValues.new.local_Amount'), 100)
        self.assertEqual(self.lua.eval('maskValues.old.local_Exposure'), .3)
        self.assertEqual(self.lua.globals().snapshots, 1)
        self.assertEqual(self.lua.eval('copy.values.Exposure2012'), 0)

    def test_native_float_settling_is_not_an_unrelated_control_change(self):
        self.lua.execute('floatSettling=true')
        result=self.lua.eval('runMask()')
        self.assertTrue(result['readback_verified'])

    def test_adjust_existing_mask_keeps_other_local_effects(self):
        self.lua.execute("fields.action='mask-read'; fields.mask_type=nil; fields.mask_id='old'")
        revision = self.lua.eval('runMask()')['mask_revision']
        self.lua.globals().fields['expected_mask_revision'] = revision
        self.lua.execute("fields.action='mask-adjust'; fields.clarity='-15'; fields.texture=nil")
        result = self.lua.eval('runMask()')
        self.assertEqual(result['mask_id'], 'old')
        self.assertEqual(self.lua.globals().created, 0)
        self.assertEqual(self.lua.eval('maskValues.old.local_Exposure'), .3)
        self.assertEqual(self.lua.eval('maskValues.old.local_Texture'), .2)

    def test_stale_revision_and_snapshot_race_prevent_creation(self):
        for setup in ["copy.values.Exposure2012=1", "beforeWrite=function() copy.values.Exposure2012=2 end"]:
            self.setUp()
            self.lua.execute(setup)
            with self.assertRaisesRegex(Exception, 'Stale|context changed'):
                self.lua.eval('runMask()')
            self.assertEqual(self.lua.globals().created, 0)
            self.assertEqual(self.lua.globals().snapshots, 0)

    def test_original_and_unrelated_copy_are_protected(self):
        self.lua.execute("fields.photo_id='1'")
        with self.assertRaisesRegex(Exception, 'originals'):
            self.lua.eval('runMask()')
        self.assertEqual(self.lua.globals().created, 0)

    def test_unsupported_inputs_fail_before_snapshot(self):
        for setup, pattern in [
            ("fields.clarity='5'", 'Out-of-range'),
            ("fields.texture='nan'", 'Invalid numeric'),
            ("fields.mask_type='radialGradient'", 'Unsupported automatic'),
            ("fields['set.Exposure2012']='1'", 'cannot mix'),
            ("fields.mask_id='old'", 'must not specify'),
            ("copy.values.ProcessVersion='6.7'", 'process version'),
            ("develop.createNewMask=nil", 'unavailable'),
        ]:
            self.setUp()
            self.lua.execute(setup)
            with self.assertRaisesRegex(Exception, pattern):
                self.lua.eval('runMask()')
            self.assertEqual(self.lua.globals().created, 0)
            self.assertEqual(self.lua.globals().snapshots, 0)

    def test_no_completed_ai_selection_does_not_create_again(self):
        self.lua.execute('neverCompletes=true')
        with self.assertRaisesRegex(Exception, 'not confirmed'):
            self.lua.eval('runMask()')
        self.assertEqual(self.lua.globals().created, 1)
        self.assertTrue(self.lua.globals().progress['mask_creation_requested'])

    def test_selection_drift_stops_further_writes(self):
        self.lua.execute('driftSelection=true')
        with self.assertRaisesRegex(Exception, 'selection changed'):
            self.lua.eval('runMask()')
        self.assertEqual(self.lua.globals().created, 1)
        self.assertEqual(self.lua.globals().progress['created_mask_id'], 'new')

    def test_ignored_slider_and_global_side_effect_are_failures(self):
        for setup, pattern in [('ignoredLocal=true', 'neutralize|readback'), ('globalSideEffect=true', 'Global settings|context changed')]:
            self.setUp()
            self.lua.execute(setup)
            with self.assertRaisesRegex(Exception, pattern):
                self.lua.eval('runMask()')
            self.assertEqual(self.lua.globals().snapshots, 1)

    def test_non_neutral_inherited_curve_fails_without_raw_mask_writes(self):
        self.lua.execute('nonlinearInherited=true')
        with self.assertRaisesRegex(Exception, 'non-neutral local structure'):
            self.lua.eval('runMask()')
        self.assertEqual(self.lua.globals().created, 1)
        self.assertEqual(self.lua.eval('maskValues.new.local_Exposure'), .8)

    def test_other_local_control_and_tool_drift_fail(self):
        for flag, message in [('otherLocalSideEffect', 'Unrelated local control'),
                              ('changeTool', 'selection changed'), ('changeCatalog', 'catalog changed')]:
            self.setUp()
            self.lua.execute(flag + '=true')
            with self.assertRaisesRegex(Exception, message):
                self.lua.eval('runMask()')
            self.assertEqual(self.lua.globals().snapshots, 1)

    def test_unsupported_inventory_shape_fails_closed(self):
        self.lua.execute('malformedInventory=true')
        with self.assertRaisesRegex(Exception, 'representation'):
            self.lua.eval('runMask()')
        self.assertEqual(self.lua.globals().created, 0)

    def test_round_independently_checks_created_mask_before_export(self):
        fixture = round_fixture.RoundTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.plan['steps'] = [dict(action='mask-create', mask_type='background', clarity=-25, texture=-20)]
        def send(action, **kwargs):
            response = fixture.send(action, **kwargs)
            result = response['result']
            if action == 'mask-read':
                result.update(mask_revision='fresh', mask_settings={'clarity': -25, 'texture': -20})
            elif action == 'mask-create':
                self.assertEqual(kwargs['expected_mask_revision'], 'fresh')
                result.update(mask_id='new-native-id', readback_verified=True, snapshot_name='restore-mask')
            return response
        with patch.object(runner, 'send_command', side_effect=send):
            result = runner.run_round(fixture.plan, fixture.directory)
        self.assertTrue(result['ok'])
        self.assertEqual(result['masks']['new-native-id'], {'clarity': -25, 'texture': -20})
        self.assertEqual([a for a, _ in fixture.calls],
                         ['read', 'mask-read', 'mask-create', 'read', 'mask-read', 'export'])
        self.assertEqual(fixture.calls[-2][1]['mask_id'], 'new-native-id')

    def test_client_serializes_mask_data_and_rejects_invalid_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            kwargs = dict(catalog='C:/test.lrcat', path='C:/source.jpg', photo_id='2',
                          state_dir=Path(directory), expected_mask_revision='guard',
                          mask_type='background', mask_clarity=-30, mask_texture=-40)
            with patch.object(client, 'wait_result', return_value={'ok': True}):
                client.send_command('mask-create', **kwargs)
            text = next(Path(directory).glob('*.request')).read_text()
            self.assertIn('action=mask-create', text)
            self.assertIn('clarity=-30', text)
            with self.assertRaisesRegex(ValueError, 'between -100'):
                client.send_command('mask-create', **dict(kwargs, mask_clarity=5))
            with self.assertRaisesRegex(ValueError, 'mix'):
                client.send_command('mask-create', **dict(kwargs, settings={'Exposure2012': 1}, expected={'Exposure2012': 0}))
            plan = dict(catalog=str(Path(directory)/'test.lrcat'), path=str(Path(directory)/'test.jpg'), photo_id='2',
                        steps=[dict(action='mask-create', mask_type='background', clarity=-30, texture=-40)])
            runner.validate(plan)
            plan['steps'][0]['mask_type'] = 'people'
            with self.assertRaises(ValueError):
                runner.validate(plan)


class LuminanceMaskTests(unittest.TestCase):
    def setUp(self):
        MaskTests.setUp(self)
        self.lua.execute("""
            Lum=dofile(pluginPath .. '/Luminance.lua')
            local seq=0
            mocks.LrUUID={generateUUID=function() seq=seq+1; return 'native-id-'..seq end}
            mocks.LrApplication.versionString=function() return '13.0.2' end
            nativeOld={CorrectionID='old',CorrectionMasks={{What='Mask/AI',MaskID='keep'}},Other='preserve'}
            copy.values.MaskGroupBasedCorrections={nativeOld}
            local baseApply=copy.applyDevelopSettings
            copy.applyDevelopSettings=function(self,updates)
                baseApply(self,updates)
                if simulateMismatch then return end
                for _,group in ipairs(self.values.MaskGroupBasedCorrections) do
                    local id=group.CorrectionID
                    if not maskList[id] then
                        maskList[id]={tool='luminance'}
                        maskValues[id]={local_Clarity=0,local_Texture=0,local_Exposure=0,local_Amount=100}
                    end
                end
                if rangeSideEffect then self.values.MaskGroupBasedCorrections[1].Other='changed' end
            end
            fields.action='mask-read'; fields.mask_type=nil
        """)
        self.lua.globals().fields['expected_mask_revision'] = self.lua.eval('runMask()')['mask_revision']
        self.lua.execute("fields.action='mask-create'; fields.mask_type='luminance'; fields.luminance_range='40,60,100,100'")

    def test_luminance_create_and_range_only_adjustment_preserve_native_data(self):
        result = self.lua.eval('runMask()')
        mid = result['mask_id']
        self.assertEqual(result['luminance_range']['lower_full'], 60)
        self.assertEqual(self.lua.eval('copy.values.MaskGroupBasedCorrections[1].Other'), 'preserve')
        self.assertEqual(self.lua.globals().created, 0)  # no incomplete SDK sampling tool
        self.lua.execute("fields.action='mask-read'; fields.mask_type=nil; fields.luminance_range=nil")
        self.lua.globals().fields['mask_id'] = mid
        self.lua.globals().fields['expected_mask_revision'] = self.lua.eval('runMask()')['mask_revision']
        self.lua.execute("fields.action='mask-adjust'; fields.clarity=nil; fields.texture=nil; fields.luminance_range='0,0,20,40'")
        result = self.lua.eval('runMask()')
        self.assertEqual(result['mask_id'], mid)
        self.assertEqual(result['luminance_range']['upper_full'], 20)
        self.assertAlmostEqual(result['mask_settings']['clarity'], -30)
        self.assertEqual(self.lua.eval('#copy.values.MaskGroupBasedCorrections'), 2)

    def test_luminance_invalid_schema_version_and_bounds_fail_before_snapshot(self):
        for setup, pattern in [
            ("fields.luminance_range='60,40,100,100'", 'ordered'),
            ("fields.luminance_range='40,,60,100,100'", 'Invalid'),
            ("fields.luminance_range='0,0,0,0'", 'ordered'),
            ("fields.luminance_range='0,nan,100,100'", 'Invalid'),
            ("fields.luminance_range=nil", 'explicit range'),
            ("mocks.LrApplication.versionString=function() return '14.0' end", 'verified only'),
            ("fields.action='mask-adjust'; fields.mask_type=nil; fields.mask_id='old'", 'Stale|require one'),
        ]:
            self.setUp()
            self.lua.execute(setup)
            with self.assertRaisesRegex(Exception, pattern):
                self.lua.eval('runMask()')
            self.assertEqual(self.lua.globals().snapshots, 0)

    def test_luminance_ignored_apply_and_unrelated_geometry_changes_fail(self):
        for setup, pattern in [('simulateMismatch=true','not confirmed'), ('rangeSideEffect=true','Unrelated native correction')]:
            self.setUp()
            self.lua.execute(setup)
            with self.assertRaisesRegex(Exception, pattern):
                self.lua.eval('runMask()')
            self.assertEqual(self.lua.globals().snapshots, 1)

    def test_luminance_client_and_round_validate_before_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            kwargs=dict(catalog='C:/test.lrcat',path='C:/source.jpg',photo_id='2',
                        state_dir=Path(directory),expected_mask_revision='guard',mask_type='luminance',
                        luminance_range=[40,60,100,100],mask_clarity=-25)
            with patch.object(client,'wait_result',return_value={'ok':True}):
                client.send_command('mask-create',**kwargs)
            self.assertIn('luminance_range=40%2C60%2C100%2C100',next(Path(directory).glob('*.request')).read_text())
            for points in ([40,20,100,100],[0,0,0,0],[False,0,50,100],[0,0,101,101]):
                with self.assertRaises(ValueError):
                    client.send_command('mask-create',**dict(kwargs,luminance_range=points))

    def test_luminance_round_rejects_independent_range_mismatch_before_export(self):
        fixture=round_fixture.RoundTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.plan['steps']=[dict(action='mask-create',mask_type='luminance',luminance_range=[40,60,100,100],clarity=-25)]
        def send(action,**kwargs):
            response=fixture.send(action,**kwargs);result=response['result']
            if action=='mask-read':
                result.update(mask_revision='fresh',mask_settings={'clarity':-25},
                              luminance_range=dict(zip(client.LUMINANCE_KEYS,[0,0,100,100])))
            elif action=='mask-create':
                self.assertEqual(kwargs['luminance_range'],[40,60,100,100])
                result.update(mask_id='new-range',readback_verified=True)
            return response
        with patch.object(runner,'send_command',side_effect=send):
            result=runner.run_round(fixture.plan,fixture.directory)
        self.assertFalse(result['ok'])
        self.assertIn('Independent luminance',result['error'])
        self.assertNotIn('export',[a for a,_ in fixture.calls])

if __name__ == '__main__':
    unittest.main()
