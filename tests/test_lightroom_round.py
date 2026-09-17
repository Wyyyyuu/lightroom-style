"""Round orchestration tests. SDK boundaries remain covered by command tests."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lightroom-style/scripts'))
import lightroom_round as runner
import lightroom_client as client


class RoundTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / 'round'
        self.plan = dict(catalog=str(self.root / 'catalog.lrcat'),
                         path=str(self.root / 'source.jpg'), photo_id='2',
                         steps=[dict(action='apply', settings={'Exposure2012': .4}),
                                dict(action='apply', settings={'Saturation': -12})])
        self.photo = dict(photo_id='2', path=self.plan['path'], copy_name='PhotoStyle-test',
                          is_virtual_copy=True,
                          settings={'Exposure2012': 0, 'Saturation': 0, 'WhiteBalance': 'As Shot',
                                    'IncrementalTemperature': 0},
                          curve_revision='fresh', curve_state={'ToneCurvePV2012': {'1': 0, '2': 0, '3': 255, '4': 255}})
        self.calls = []
        self.fail_action = None
        self.read_count = 0
        self.drift = False

    def send(self, action, **kwargs):
        self.calls.append((action, kwargs))
        # Crash recovery must not depend on getting a receipt back.
        intents = [json.loads(p.read_text(encoding='utf-8')) for p in self.directory.glob('*-request.json')]
        self.assertTrue(any(p['request_id'] == kwargs['request_id'] for p in intents))
        if action == self.fail_action:
            return {'id': kwargs['request_id'], 'ok': False, 'status': 'outcome_unknown',
                    'progress': {'snapshot_name': 'recover-me'}, 'error': 'timeout'}
        result = {}
        if action == 'read':
            self.read_count += 1
            if self.drift and self.read_count == 3:
                self.photo['settings']['Exposure2012'] = 2
        elif action == 'apply':
            for key, value in kwargs['expected'].items():
                self.assertEqual(value, self.photo['settings'][key])
            self.photo['settings'].update(kwargs['settings'])
            if 'IncrementalTemperature' in kwargs['settings']:
                self.photo['settings']['WhiteBalance'] = 'Custom'
            result.update(readback_verified=True, snapshot_name='snapshot-' + kwargs['request_id'])
        elif action == 'curve':
            self.assertEqual(kwargs['expected_revision'], self.photo['curve_revision'])
            self.photo['curve_state'] = {'points': kwargs['curve_points']}
            self.photo['curve_revision'] = 'new'
            result.update(readback_verified=True, snapshot_name='snapshot-' + kwargs['request_id'])
        elif action == 'export':
            result['files'] = {'1': str(self.directory / 'render' / 'source.jpg')}
        result['photo'] = copy.deepcopy(self.photo)
        return {'id': kwargs['request_id'], 'protocol': 1, 'ok': True, 'result': result}

    def run_plan(self):
        with patch.object(runner, 'send_command', side_effect=self.send):
            return runner.run_round(self.plan, self.directory)

    def test_calibration_requires_context_before_dispatch(self):
        self.plan['steps']=[dict(action='apply',settings={'RedHue':12})]
        self.photo['settings']['RedHue']=0
        result=self.run_plan()
        self.assertFalse(result['ok'])
        self.assertEqual([a for a,_ in self.calls],['read'])

    def test_calibration_independent_context_drift_blocks_export(self):
        self.plan['steps']=[dict(action='apply',settings={'RedHue':12})]
        self.photo['settings'].update(RedHue=0,ProcessVersion='15.4')
        self.photo['calibration_state']={'EnableCalibration':True,'RedSaturation':0}
        def send(action,**kwargs):
            if action=='read' and self.read_count==1:
                self.photo['calibration_state']['RedSaturation']=40
            return self.send(action,**kwargs)
        with patch.object(runner,'send_command',side_effect=send):
            result=runner.run_round(self.plan,self.directory)
        self.assertFalse(result['ok'])
        self.assertIn('calibration context',result['error'])
        self.assertNotIn('export',[a for a,_ in self.calls])

    def test_groups_one_export_and_independent_read(self):
        result = self.run_plan()
        self.assertTrue(result['ok'])
        self.assertEqual(result['status'], 'needs_visual_review')
        self.assertEqual([a for a, _ in self.calls], ['read', 'apply', 'read', 'apply', 'read', 'export'])
        self.assertEqual(result['settings_delta']['Exposure2012'], {'before': 0, 'after': .4})
        self.assertNotIn('settings', result)
        self.assertEqual(len(list(self.directory.glob('*-receipt.json'))), 6)

    def test_unknown_stops_without_export_or_replay(self):
        self.fail_action = 'apply'
        result = self.run_plan()
        self.assertFalse(result['ok'])
        self.assertEqual(result['status'], 'outcome_unknown')
        self.assertEqual(result['progress']['snapshot_name'], 'recover-me')
        self.assertEqual([a for a, _ in self.calls], ['read', 'apply'])
        with self.assertRaises(FileExistsError):
            self.run_plan()
        self.assertEqual(len(self.calls), 2)

    def test_final_drift_stops_before_export(self):
        self.drift = True
        result = self.run_plan()
        self.assertFalse(result['ok'])
        self.assertIn('readback mismatch', result['error'])
        self.assertNotIn('export', [a for a, _ in self.calls])

    def test_original_unrelated_copy_and_wrong_identity_are_rejected(self):
        for field, value in [('is_virtual_copy', False), ('copy_name', 'Other-copy'),
                             ('photo_id', '3'), ('path', str(self.root / 'other.jpg'))]:
            with self.subTest(field=field):
                previous = self.photo[field]
                self.photo[field] = value
                self.directory = self.root / field
                result = self.run_plan()
                self.assertFalse(result['ok'])
                self.photo[field] = previous
        self.assertTrue(all(action == 'read' for action, _ in self.calls))

    def test_invalid_later_step_rejected_before_any_command(self):
        for bad in [{'action': 'apply', 'settings': {'Saturation': float('nan')}},
                    {'action': 'copy'}, {'action': 'curve', 'points': [[1, 0], [255, 255]]}]:
            self.plan['steps'][-1] = bad
            with self.assertRaises(ValueError):
                self.run_plan()
        self.assertEqual(self.calls, [])
        self.assertFalse(self.directory.exists())

    def test_rgb_curves_forward_channels_and_export_once(self):
        self.plan['steps']=[dict(action='curve',channel=c,points=[[0,3],[255,249]]) for c in ('red','green','blue')]
        result=self.run_plan()
        self.assertTrue(result['ok'])
        self.assertTrue(result['independent_readback_verified'])
        self.assertEqual([kw['curve_channel'] for a,kw in self.calls if a=='curve'],['red','green','blue'])
        self.assertEqual([a for a,_ in self.calls].count('export'),1)
        self.assertEqual([a for a,_ in self.calls],['read','curve','read','curve','read','curve','read','export'])

    def test_curve_and_white_balance_use_current_guards(self):
        self.plan['steps'] = [
            dict(action='curve', points=[[0, 4], [255, 250]]),
            dict(action='apply', settings={'IncrementalTemperature': -4})]
        result = self.run_plan()
        self.assertTrue(result['ok'])
        self.assertTrue(result['curve_changed'])
        self.assertEqual(result['settings_delta']['WhiteBalance']['after'], 'Custom')

    def test_exception_retains_dispatched_id(self):
        def crash(action, **kwargs):
            if action == 'apply':
                raise OSError('lost connection')
            return self.send(action, **kwargs)
        with patch.object(runner, 'send_command', side_effect=crash):
            result = runner.run_round(self.plan, self.directory)
        self.assertEqual(result['status'], 'outcome_unknown')
        intent = json.loads((self.directory / '02-apply-request.json').read_text())
        self.assertEqual(result['id'], intent['request_id'])

    def test_compact_receipt_keeps_recovery_evidence_and_read_settings(self):
        receipt = dict(ok=False, id='a' * 32, status='outcome_unknown',
                       progress={'parameters_applied': True, 'snapshot_name': 'restore'},
                       result={'photo': self.photo, 'before': {'large': [1] * 1000}})
        small = client.summarize(receipt)
        self.assertEqual(small['progress'], receipt['progress'])
        self.assertNotIn('settings', small['result']['photo'])
        self.assertNotIn('before', small['result'])
        self.assertEqual(client.summarize(receipt, include_settings=True)['result']['photo']['settings'],
                         self.photo['settings'])

    def test_supplied_id_persists_and_cannot_be_dispatched_twice(self):
        request_id = 'a' * 32
        with patch.object(client, 'wait_result', return_value={'ok': True}) as wait:
            client.send_command('read', catalog=self.plan['catalog'], path=self.plan['path'],
                                photo_id='2', state_dir=self.root, request_id=request_id)
            self.assertIn('id=' + request_id, (self.root / f'command-{request_id}.request').read_text())
            wait.assert_called_once_with(self.root, request_id, 30)
            with self.assertRaisesRegex(ValueError, 'already exists'):
                client.send_command('read', catalog=self.plan['catalog'], path=self.plan['path'],
                                    photo_id='2', state_dir=self.root, request_id=request_id)


if __name__ == '__main__':
    unittest.main()
