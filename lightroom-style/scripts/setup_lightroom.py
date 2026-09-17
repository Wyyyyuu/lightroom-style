#!/usr/bin/env python3
"""Install bundled Windows plugin files; Lightroom UI must load them separately."""
import argparse
import json
import os
from pathlib import Path
import sys
import uuid

PLUGIN_NAME = 'PhotoStyleBridge.lrplugin'
PLUGIN_FILES = ('Bridge.lua', 'Commands.lua', 'Diagnostics.lua', 'Info.lua',
                'Init.lua', 'Json.lua', 'Luminance.lua', 'LuminanceSeed.lua', 'Masks.lua', 'PluginInfoProvider.lua', 'Shutdown.lua')


def install_plugin(source, destination):
    if source.is_symlink() or not source.is_dir():
        raise ValueError('Bundled plugin directory is missing or linked')
    payload = {}
    for name in PLUGIN_FILES:
        item = source / name
        if item.is_symlink() or not item.is_file():
            raise ValueError(f'Missing or linked bundled plugin file: {name}')
        payload[name] = item.read_bytes()
    if destination.name != PLUGIN_NAME:
        raise ValueError(f'Destination must end in {PLUGIN_NAME}')
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise ValueError('Destination is linked or is not a directory')
    if destination.exists():
        matches = all((destination / name).is_file()
                      and not (destination / name).is_symlink()
                      and (destination / name).read_bytes() == data
                      for name, data in payload.items())
        status = 'already_installed' if matches else 'existing_installation_differs'
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = destination.parent / f'PhotoStyleBridge-{uuid.uuid4().hex}.installing'
        staging.mkdir()
        try:
            for name, data in payload.items():
                with (staging / name).open('xb') as handle:
                    handle.write(data)
            # Windows rename refuses an existing destination, including a racing installer.
            if destination.exists():
                raise FileExistsError(destination)
            staging.rename(destination)
        except OSError as error:
            raise OSError(f'Installation incomplete; staged files retained at {staging}: {error}') from error
        status = 'installed'
    return {
        'status': status,
        'plugin_directory': str(destination.resolve()),
        'connection_verified': False,
        'next_step': (
            'Inspect the actually loaded path; back up before any deliberate update.'
            if status == 'existing_installation_differs' else
            'In Lightroom Plug-in Manager, Add this folder if absent, enable if needed, '
            'run the read-only connection check, close the manager, then run lightroom_probe.py.'
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plugin-dir', type=Path, help='Verified destination plugin folder')
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('Automatic installation is Windows-only; use verified native setup elsewhere')
    destination = args.plugin_dir
    if destination is None:
        appdata = os.environ.get('APPDATA')
        if not appdata:
            parser.error('APPDATA is unavailable; specify --plugin-dir')
        destination = Path(appdata) / 'Adobe' / 'Lightroom' / 'Modules' / PLUGIN_NAME
    if not destination.is_absolute():
        parser.error('--plugin-dir must be an absolute path')
    source = Path(__file__).resolve().parents[1] / 'assets' / PLUGIN_NAME
    try:
        result = install_plugin(source, destination)
    except (OSError, ValueError) as error:
        print(json.dumps({'status': 'error', 'connection_verified': False, 'error': str(error)}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result['status'] == 'existing_installation_differs' else 0


if __name__ == '__main__':
    sys.exit(main())
