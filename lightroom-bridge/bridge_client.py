"""Explicit Lightroom SDK command client. Never retries a mutation automatically."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import time
from urllib.parse import quote
import uuid


DEFAULT_STATE = Path(os.environ.get('APPDATA', '')) / 'Adobe/Lightroom/PhotoStyleMatchBridge'


def encode_curve(points: list) -> str:
    if not isinstance(points, (list, tuple)) or not 2 <= len(points) <= 16:
        raise ValueError('Point curve needs 2-16 input/output pairs')
    flat = []
    for pair in points:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError('Each curve point must contain input and output')
        for value in pair:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or int(value) != value or not 0 <= value <= 255:
                raise ValueError('Curve coordinates must be integers from 0 to 255')
            flat.append(int(value))
    if flat[0] != 0 or flat[-2] != 255:
        raise ValueError('Curve endpoint inputs must be 0 and 255')
    if any(flat[i] <= flat[i-2] or flat[i+1] < flat[i-1] for i in range(2, len(flat), 2)):
        raise ValueError('Curve inputs must increase and outputs must not decrease')
    return ','.join(map(str, flat))


LUMINANCE_KEYS = ("lower_none", "lower_full", "upper_full", "upper_none")


def encode_luminance(points: list) -> str:
    if (not isinstance(points, (list, tuple)) or len(points) != 4
        or any(isinstance(v, bool) or not isinstance(v, (int, float))
               or not math.isfinite(v) or not 0 <= v <= 100 for v in points)
        or any(points[i] > points[i+1] for i in range(3)) or points[0] == points[-1]):
        raise ValueError("Luminance range needs four ordered handles in 0..100 with nonzero width")
    return ",".join(str(v) for v in points)


def wait_result(state_dir: Path, request_id: str, timeout: float) -> dict:
    if not re.fullmatch(r'[a-f0-9]{32}', request_id):
        raise ValueError('Request ID must be 32 lowercase hexadecimal characters')
    stem = state_dir / ('command-' + request_id)
    deadline = time.monotonic() + timeout
    while True:
        result_path = Path(str(stem) + '.result.json')
        if Path(str(result_path) + '.ready').is_file():
            response = json.loads(result_path.read_text(encoding='utf-8'))
            if response.get('id') != request_id or response.get('protocol') != 1 or not isinstance(response.get('ok'), bool):
                raise ValueError('Mismatched or invalid Lightroom response')
            return response
        if time.monotonic() >= deadline:
            return {'id': request_id, 'ok': False, 'status': 'outcome_unknown',
                    'claimed': Path(str(stem) + '.running').exists(),
                    'error': 'No completed receipt yet. Use status with this ID; do not resend a mutation.'}
        time.sleep(0.2)


def send_command(action: str, *, catalog: str, path: str, photo_id: str | None = None,
                 settings: dict | None = None, expected: dict | None = None,
                 curve_points: list | None = None, curve_channel: str | None = None, expected_revision: str | None = None,
                 output_dir: str | None = None, state_dir: Path = DEFAULT_STATE,
                 timeout: float = 30, request_id: str | None = None,
                 mask_type: str | None = None, mask_id: str | None = None,
                 mask_clarity: float | None = None, mask_texture: float | None = None,
                 expected_mask_revision: str | None = None,
                 luminance_range: list | None = None) -> dict:
    if action not in {'import', 'read', 'copy', 'apply', 'export', 'curve', 'mask-read', 'mask-create', 'mask-adjust'}:
        raise ValueError('Unsupported action')
    if not 1 <= timeout <= 120:
        raise ValueError('Timeout must be between 1 and 120 seconds')
    if action != 'import' and not photo_id:
        raise ValueError('An explicit photo ID is required')
    if action == 'apply' and (not settings or set(settings) != set(expected or {})):
        raise ValueError('Every requested parameter needs exactly one expected current value')
    if action == 'export' and not output_dir:
        raise ValueError('A new absolute export directory is required')
    if curve_channel is not None and (action != 'curve' or curve_channel not in {'composite', 'red', 'green', 'blue'}):
        raise ValueError('Curve channel requires curve action and composite/red/green/blue')
    mask_action = action in {'mask-read', 'mask-create', 'mask-adjust'}
    mask_values = {'clarity': mask_clarity, 'texture': mask_texture}
    if luminance_range is not None:
        encode_luminance(luminance_range)
    if mask_action:
        if settings or expected or curve_points is not None or expected_revision is not None or output_dir:
            raise ValueError('Mask commands cannot mix global settings, curves, or export')
        if action == 'mask-read':
            if luminance_range is not None or mask_type is not None or expected_mask_revision is not None or any(v is not None for v in mask_values.values()):
                raise ValueError('mask-read does not accept write parameters')
        else:
            if not expected_mask_revision or not isinstance(expected_mask_revision, str):
                raise ValueError('Mask writes require a fresh mask revision')
            if luminance_range is None and all(v is None for v in mask_values.values()):
                raise ValueError('Mask writes need clarity, texture, or luminance range')
            for value in mask_values.values():
                if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                          or not math.isfinite(value) or not -100 <= value <= 0):
                    raise ValueError('Local softness values must be between -100 and 0')
            if action == 'mask-create' and (mask_type not in {'subject', 'sky', 'background', 'luminance'} or mask_id is not None):
                raise ValueError('New mask requires subject, sky, background, or luminance and no mask ID')
            if action == 'mask-create' and ((mask_type == 'luminance') != (luminance_range is not None)):
                raise ValueError('Only luminance creation requires an explicit luminance range')
            if action == 'mask-adjust' and (not mask_id or mask_type is not None):
                raise ValueError('Mask adjustment requires an existing mask ID')
        if mask_id is not None and (not isinstance(mask_id, str) or not mask_id or len(mask_id) > 256):
            raise ValueError('Invalid mask ID')
    elif any(v is not None for v in [mask_type, mask_id, mask_clarity, mask_texture, expected_mask_revision, luminance_range]):
        raise ValueError('Mask inputs require a mask action')
    request_id = request_id or uuid.uuid4().hex
    if not re.fullmatch(r'[a-f0-9]{32}', request_id):
        raise ValueError('Request ID must be 32 lowercase hexadecimal characters')
    fields = {'protocol': '1', 'id': request_id, 'action': action, 'catalog': catalog,
              'path': path, 'deadline': str(int(time.time() + timeout))}
    if photo_id is not None:
        fields['photo_id'] = str(photo_id)
    if output_dir is not None:
        fields['output_dir'] = output_dir
    if mask_action:
        for key, value in dict(mask_type=mask_type, mask_id=mask_id,
                               expected_mask_revision=expected_mask_revision, **mask_values).items():
            if value is not None:
                fields[key] = str(value)
    if luminance_range is not None:
        fields['luminance_range'] = encode_luminance(luminance_range)
    if action == 'curve':
        if settings or expected or not isinstance(expected_revision, str) or not expected_revision:
            raise ValueError('Curve writes require a fresh revision and cannot mix scalar changes')
        if curve_channel is not None:
            fields['curve_channel'] = curve_channel
        if curve_channel in {'red', 'green', 'blue'}:
            # Distinct wire action makes older plugins fail closed, never edit composite.
            fields['action'] = 'curve-channel'
        fields['curve_points'] = encode_curve(curve_points)
        fields['expected_revision'] = expected_revision
    elif curve_points is not None or expected_revision is not None:
        raise ValueError('Curve inputs require the curve action')
    for prefix, values in (('set', settings), ('expect', expected)):
        for key, value in (values or {}).items():
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9]*', key) or not math.isfinite(float(value)):
                raise ValueError('Invalid parameter name or value')
            fields[f'{prefix}.{key}'] = str(value)
    state_dir = Path(state_dir)
    if not state_dir.is_dir():
        raise ValueError('Bridge state directory is missing; initialize the Lightroom plugin first')
    if any(state_dir.glob(f'command-{request_id}.*')):
        raise ValueError('Request ID already exists; query status instead of resending')
    content = '\n'.join(key + '=' + quote(str(value), safe='') for key, value in fields.items()) + '\n'
    if len(content) > 65536:
        raise ValueError('Command too large')
    pending = state_dir / f'command-{request_id}.tmp'
    with pending.open('x', encoding='ascii', newline='\n') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    pending.rename(state_dir / f'command-{request_id}.request')
    return wait_result(state_dir, request_id, timeout)


def assignments(values: list[str]) -> dict:
    result = {}
    for item in values:
        key, value = item.split('=', 1)
        if key in result:
            raise ValueError('Repeated parameter: ' + key)
        result[key] = float(value)
    return result


def summarize(response: dict, *, include_settings: bool = False) -> dict:
    """Keep recovery evidence and useful results; omit duplicated photo baselines."""
    summary = {key: value for key, value in response.items() if key != 'result'}
    result = response.get('result')
    if isinstance(result, dict):
        summary['result'] = {key: value for key, value in result.items()
                             if key not in {'photo', 'source', 'before', 'local_controls', 'local_ranges'}}
        photo = result.get('photo')
        if isinstance(photo, dict):
            keys = ['photo_id', 'path', 'copy_name', 'is_virtual_copy']
            if include_settings:
                keys += ['settings', 'curve_state', 'curve_revision', 'grain_state']
            summary['result']['photo'] = {key: photo[key] for key in keys if key in photo}
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['import', 'read', 'copy', 'apply', 'export', 'curve', 'status', 'mask-read', 'mask-create', 'mask-adjust'])
    parser.add_argument('--catalog')
    parser.add_argument('--path')
    parser.add_argument('--photo-id')
    parser.add_argument('--set', action='append', default=[], metavar='KEY=VALUE')
    parser.add_argument('--expect', action='append', default=[], metavar='KEY=VALUE')
    parser.add_argument('--output-dir')
    parser.add_argument('--request-id')
    parser.add_argument('--curve-channel', choices=['composite', 'red', 'green', 'blue'])
    parser.add_argument('--curve-points', help='Channel points: "0,8;64,58;128,128;192,200;255,246"')
    parser.add_argument('--expected-revision-file', type=Path, help='UTF-8 file containing the exact curve_revision from a fresh read')
    parser.add_argument('--state-dir', type=Path, default=DEFAULT_STATE)
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--mask-type', choices=['subject', 'sky', 'background', 'luminance'])
    parser.add_argument('--mask-id')
    parser.add_argument('--luminance-range', help='Four ordered native handles, 0..100: lower-none,lower-full,upper-full,upper-none')
    parser.add_argument('--clarity', type=float, help='Local softness in UI units, -100 to 0')
    parser.add_argument('--texture', type=float, help='Local softness in UI units, -100 to 0')
    parser.add_argument('--expected-mask-revision-file', type=Path)
    parser.add_argument('--full', action='store_true', help='Print the full receipt instead of a compact summary')
    args = parser.parse_args()
    try:
        if args.action == 'status':
            if not args.request_id or not 0 <= args.timeout <= 120:
                parser.error('status needs --request-id and a timeout between 0 and 120')
            response = wait_result(args.state_dir, args.request_id, args.timeout)
        else:
            if not args.catalog or not args.path:
                parser.error('--catalog and --path are required')
            response = send_command(args.action, catalog=args.catalog, path=args.path,
                                    photo_id=args.photo_id, settings=assignments(args.set),
                                    expected=assignments(args.expect), output_dir=args.output_dir,
                                    curve_channel=args.curve_channel,
                                    curve_points=([list(map(float, pair.split(','))) for pair in args.curve_points.split(';')] if args.curve_points else None),
                                    expected_revision=(args.expected_revision_file.read_text(encoding='utf-8') if args.expected_revision_file else None),
                                    state_dir=args.state_dir, timeout=args.timeout,
                                    mask_type=args.mask_type, mask_id=args.mask_id,
                                    luminance_range=([float(v) for v in args.luminance_range.split(',')] if args.luminance_range else None),
                                    mask_clarity=args.clarity, mask_texture=args.texture,
                                    expected_mask_revision=(args.expected_mask_revision_file.read_text(encoding='utf-8').strip()
                                                            if args.expected_mask_revision_file else None))
        output = response if args.full else summarize(response, include_settings=args.action in {'read', 'import', 'copy'})
        if not args.full and response.get('id'):
            output['receipt_path'] = str(args.state_dir.resolve() / f"command-{response['id']}.result.json")
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0 if response.get('ok') else 2
    except (OSError, ValueError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
