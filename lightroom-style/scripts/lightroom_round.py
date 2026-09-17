"""Execute one planned adjustment round; stop before visual acceptance."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import uuid

from lightroom_client import DEFAULT_STATE, LUMINANCE_KEYS, encode_curve, encode_luminance, send_command, summarize


def save(path: Path, value: dict) -> None:
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def validate(plan: dict) -> None:
    if not isinstance(plan, dict) or set(plan) != {'catalog', 'path', 'photo_id', 'steps'}:
        raise ValueError('Plan requires exactly catalog, path, photo_id, and steps')
    for key in ('catalog', 'path'):
        if not isinstance(plan[key], str) or not Path(plan[key]).is_absolute():
            raise ValueError(f'{key} must be an absolute path')
    if not isinstance(plan['photo_id'], str) or not plan['photo_id']:
        raise ValueError('photo_id must be an explicit string ID')
    if not isinstance(plan['steps'], list) or not plan['steps']:
        raise ValueError('steps must be a nonempty list')
    for step in plan['steps']:
        if not isinstance(step, dict):
            raise ValueError('Each step must be an object')
        action = step.get('action')
        if action == 'apply' and set(step) == {'action', 'settings'}:
            values = step['settings']
            if not isinstance(values, dict) or not values:
                raise ValueError('apply needs nonempty settings')
            for key, value in values.items():
                if (not re.fullmatch(r'[A-Za-z][A-Za-z0-9]*', key)
                        or isinstance(value, bool) or not isinstance(value, (int, float))
                        or not math.isfinite(value)):
                    raise ValueError('Settings must contain finite numeric slider values')
        elif action == 'curve' and {'action', 'points'} <= set(step) <= {'action', 'points', 'channel'}:
            if step.get('channel', 'composite') not in {'composite', 'red', 'green', 'blue'}:
                raise ValueError('Unsupported curve channel')
            encode_curve(step['points'])
        elif action in {'mask-create', 'mask-adjust'}:
            selector = 'mask_type' if action == 'mask-create' else 'mask_id'
            if not {'action', selector} <= set(step) or set(step) - {'action', selector, 'clarity', 'texture', 'luminance_range'}:
                raise ValueError('Mask step has invalid fields')
            if action == 'mask-create' and step[selector] not in {'subject', 'sky', 'background', 'luminance'}:
                raise ValueError('Unsupported automatic mask type')
            if action == 'mask-adjust' and (not isinstance(step[selector], str) or not step[selector] or len(step[selector]) > 256):
                raise ValueError('Existing mask needs an explicit ID')
            if 'luminance_range' in step:
                encode_luminance(step['luminance_range'])
            if action == 'mask-create' and ((step[selector] == 'luminance') != ('luminance_range' in step)):
                raise ValueError('Only luminance creation requires an explicit range')
            values = [step[k] for k in ('clarity', 'texture') if k in step]
            if (not values and 'luminance_range' not in step) or any(isinstance(v, bool) or not isinstance(v, (int, float))
                                 or not math.isfinite(v) or not -100 <= v <= 0 for v in values):
                raise ValueError('Mask softness needs finite values between -100 and 0')
        else:
            raise ValueError('Unsupported round step')


class RoundStopped(Exception):
    def __init__(self, summary: dict):
        self.summary = summary


def run_round(plan: dict, directory: Path, *, state_dir: Path = DEFAULT_STATE,
              timeout: float = 30) -> dict:
    """Never replay a directory, retry a command, or decide aesthetic acceptance."""
    validate(plan)
    if not 1 <= timeout <= 120:
        raise ValueError('Timeout must be between 1 and 120 seconds')
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    save(directory / 'plan.json', plan)
    identity = {key: plan[key] for key in ('catalog', 'path', 'photo_id')}
    requests = []
    snapshots = []

    def command(action: str, **kwargs) -> dict:
        request_id = uuid.uuid4().hex
        label = f'{len(requests) + 1:02d}-{action}'
        requests.append(request_id)
        # Persist identity and ID BEFORE dispatch, including interrupted/unknown writes.
        intent = dict(action=action, request_id=request_id, **identity, **kwargs)
        save(directory / f'{label}-request.json', intent)
        try:
            response = send_command(action, **identity, **kwargs, state_dir=state_dir,
                                    timeout=timeout, request_id=request_id)
        except (OSError, ValueError) as error:
            response = {'id': request_id, 'ok': False, 'status': 'outcome_unknown',
                        'error': str(error)}
        receipt = directory / f'{label}-receipt.json'
        save(receipt, response)
        if not response.get('ok'):
            raise RoundStopped(dict(summarize(response), receipt_path=str(receipt), action=action))
        return response['result']

    def photo_read() -> dict:
        photo = command('read')['photo']
        if (str(photo.get('photo_id')) != plan['photo_id']
                or os.path.normcase(os.path.normpath(photo.get('path', ''))) != os.path.normcase(os.path.normpath(plan['path']))
                or photo.get('is_virtual_copy') is not True
                or not photo.get('copy_name', '').startswith('PhotoStyle-')):
            raise ValueError('Round requires the exact PhotoStyle- virtual copy')
        return photo

    try:
        first = photo_read()
        desired = {}
        desired_curve = None
        desired_calibration = None
        desired_masks = {}
        for index, step in enumerate(plan['steps']):
            current = first if index == 0 else photo_read()
            if step['action'] == 'apply':
                values = step['settings']
                if set(values) & {'RedHue', 'GreenHue', 'BlueHue'}:
                    desired_calibration = current.get('calibration_state')
                    if not desired_calibration or desired_calibration.get('EnableCalibration') is not True:
                        raise ValueError('Calibration context missing or disabled')
                expected = {key: current['settings'][key] for key in values}
                result = command('apply', settings=values, expected=expected)
                desired.update(values)
                if set(values) & {'Temperature', 'Tint', 'IncrementalTemperature', 'IncrementalTint'}:
                    desired['WhiteBalance'] = 'Custom'
            elif step['action'] == 'curve':
                result = command('curve', curve_channel=step.get('channel', 'composite'), curve_points=step['points'],
                                 expected_revision=current['curve_revision'])
            else:
                mask_id = step.get('mask_id')
                mask_before = command('mask-read', **({'mask_id': mask_id} if mask_id else {}))
                kwargs = {'expected_mask_revision': mask_before['mask_revision']}
                if mask_id:
                    kwargs['mask_id'] = mask_id
                else:
                    kwargs['mask_type'] = step['mask_type']
                for key in ('clarity', 'texture'):
                    if key in step:
                        kwargs['mask_' + key] = step[key]
                if 'luminance_range' in step:
                    kwargs['luminance_range'] = step['luminance_range']
                result = command(step['action'], **kwargs)
                mask_id = result['mask_id']
                desired_masks.setdefault(mask_id, {}).update({k: step[k] for k in ('clarity', 'texture') if k in step})
                if 'luminance_range' in step:
                    desired_masks[mask_id]['luminance_range'] = dict(zip(LUMINANCE_KEYS, step['luminance_range']))
            if result.get('snapshot_name'):
                snapshots.append(result['snapshot_name'])
            if result.get('readback_verified') is not True:
                raise ValueError('Mutation lacks verified native readback')
            desired_curve = result['photo'].get('curve_state')
        final = photo_read()
        for key, value in desired.items():
            actual = final['settings'].get(key)
            if isinstance(value, (int, float)):
                if not isinstance(actual, (int, float)) or not math.isfinite(actual) or abs(actual - value) > 0.0001:
                    raise ValueError(f'Independent final readback mismatch: {key}')
            elif actual != value:
                raise ValueError(f'Independent final readback mismatch: {key}')
        if desired_curve is not None and final.get('curve_state') != desired_curve:
            raise ValueError('Independent final curve readback mismatch')
        if desired_calibration is not None and (
                final.get('calibration_state') != desired_calibration
                or final['settings'].get('ProcessVersion') != first['settings'].get('ProcessVersion')):
            raise ValueError('Independent calibration context readback mismatch')
        for mask_id, targets in desired_masks.items():
            mask_final = command('mask-read', mask_id=mask_id)
            for key, value in targets.items():
                if key == 'luminance_range':
                    actual_range = mask_final.get('luminance_range', {})
                    if any(not isinstance(actual_range.get(k), (int, float)) or not math.isfinite(actual_range[k])
                           or abs(actual_range[k] - v) > .00011 for k, v in value.items()):
                        raise ValueError('Independent luminance range readback mismatch')
                    continue
                actual = mask_final['mask_settings'].get(key)
                if not isinstance(actual, (int, float)) or not math.isfinite(actual) or abs(actual - value) > 0.0001:
                    raise ValueError(f'Independent mask readback mismatch: {mask_id}/{key}')
        exported = command('export', output_dir=str(directory / 'render'))
        summary = {
            'ok': True, 'status': 'needs_visual_review', 'photo_id': plan['photo_id'],
            'copy_name': final['copy_name'], 'files': exported['files'],
            'settings_delta': {key: {'before': first['settings'].get(key), 'after': value}
                               for key, value in desired.items()},
            'curve_changed': first.get('curve_state') != final.get('curve_state'),
            'independent_readback_verified': True,
            'masks': desired_masks,
        }
    except RoundStopped as error:
        summary = error.summary
    except (OSError, ValueError, KeyError, TypeError) as error:
        summary = {'ok': False, 'status': 'stopped', 'error': str(error)}
    summary.update(round_dir=str(directory), request_ids=requests, snapshots=snapshots)
    save(directory / 'summary.json', summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--round-dir', type=Path, required=True, help='New directory; existing rounds are never replayed')
    parser.add_argument('--state-dir', type=Path, default=DEFAULT_STATE)
    parser.add_argument('--timeout', type=float, default=30, help='Per-command timeout, not a whole-round deadline')
    args = parser.parse_args()
    try:
        plan = json.loads(args.plan.read_text(encoding='utf-8-sig'))
        summary = run_round(plan, args.round_dir, state_dir=args.state_dir, timeout=args.timeout)
    except (OSError, ValueError) as error:
        summary = {'ok': False, 'error': str(error)}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary.get('ok') else 2


if __name__ == '__main__':
    raise SystemExit(main())
