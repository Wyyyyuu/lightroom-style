"""Validate an explicit source allowlist and build new, private-data-free release folders."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'release-manifest.json'
FORBIDDEN_PARTS = {
    '.git', '.codex', '.agents', '__pycache__', 'photo-sessions', 'validation-output',
    '.validation-deps', '.plot-deps', 'private-notes', 'photo-style-match-workspace', 'lightroom-style-workspace',
    'dist', '.venv', 'venv', '.test-artifacts', 'experiments', 'evals',
}
PRIVATE_DOCUMENTS = {'VALIDATION.md', 'docs/DEVELOPMENT.md', 'docs/EVALUATION.md'}
LICENSE_FILES = {'LICENSE', 'lightroom-style/LICENSE'}
EXTENSIONS = {'.md', '.py', '.lua', '.json', '.yaml', '.yml', '.txt'}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_tool_catalog(entries: list[str], metadata: dict) -> None:
    """Check declaration consistency; this does not grant runtime permissions."""
    catalog_entry = 'lightroom-style/tools.yaml'
    if catalog_entry not in entries:
        raise ValueError('Tool catalog must be packaged')
    extra = metadata.get('metadata')
    if not isinstance(extra, dict) or extra.get('tool-catalog') != 'tools.yaml':
        raise ValueError('metadata.tool-catalog must point to tools.yaml')
    catalog = yaml.safe_load((ROOT / catalog_entry).read_text(encoding='utf-8'))
    if not isinstance(catalog, dict) or catalog.get('schema_version') != 1 or catalog.get('host') != 'codex':
        raise ValueError('Unsupported tool catalog schema or host')
    names = []
    for section, key in [('host_tools', 'name'), ('cli_helpers', 'id'), ('optional_capabilities', 'id')]:
        rows = catalog.get(section)
        if not isinstance(rows, list) or not rows:
            raise ValueError(f'Tool catalog needs a nonempty {section} list')
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f'Invalid tool catalog row in {section}')
            ident = row.get(key)
            if not isinstance(ident, str) or not ident or any(c.isspace() for c in ident) or ident in seen:
                raise ValueError(f'Invalid or duplicate tool identifier in {section}')
            seen.add(ident)
            if not isinstance(row.get('purpose'), str) or not row['purpose'].strip():
                raise ValueError(f'Tool purpose is required: {ident}')
            if section == 'host_tools':
                names.append(ident)
            if section == 'cli_helpers':
                for field, folder, suffix in [('entrypoint', 'scripts', '.py'), ('guide', 'references', '.md')]:
                    value = row.get(field)
                    if not isinstance(value, str):
                        raise ValueError(f'Tool {field} is required: {ident}')
                    path = PurePosixPath(value)
                    if (len(path.parts) != 2 or path.parts[0] != folder or path.suffix != suffix
                            or '\\' in value or f'lightroom-style/{value}' not in entries):
                        raise ValueError(f'Tool {field} is unsafe or not packaged: {value}')
    declared = metadata.get('allowed-tools')
    if not isinstance(declared, str) or declared.split() != names:
        raise ValueError('allowed-tools must match tools.yaml host_tools in order')


def checked_files() -> list[str]:
    entries = json.loads(MANIFEST.read_text(encoding='utf-8'))['files']
    if not entries or len(entries) != len(set(entries)):
        raise ValueError('The release manifest must contain unique paths')
    if not LICENSE_FILES.issubset(entries):
        raise ValueError('Both repository and standalone skill licenses must be packaged')
    for entry in entries:
        relative = PurePosixPath(entry)
        if (relative.is_absolute() or '..' in relative.parts or '\\' in entry
                or any(part in FORBIDDEN_PARTS for part in relative.parts)
                or entry in PRIVATE_DOCUMENTS):
            raise ValueError(f'Unsafe release path: {entry}')
        path = ROOT.joinpath(*relative.parts)
        if not path.resolve().is_relative_to(ROOT) or not path.is_file():
            raise ValueError(f'Missing or escaping file: {entry}')
        if any(parent.is_symlink() for parent in [path, *path.parents] if parent != ROOT):
            raise ValueError(f'Symlinks are not packaged: {entry}')
        if path.suffix not in EXTENSIONS and path.name != '.gitignore' and entry not in LICENSE_FILES:
            raise ValueError(f'Unsupported release file type: {entry}')
        source = path.read_text(encoding='utf-8')
        if source.startswith('\ufeff'):
            raise ValueError(f'UTF-8 BOM must be removed: {entry}')
        # Heuristics supplement the explicit allowlist; they are not a complete PII detector.
        if re.search(r'[A-Za-z]:[/\\]Users[/\\][^\s"\'<>]+', source, re.I):
            raise ValueError(f'Personal absolute Windows profile path in {entry}')
        if re.search(r'codex-clipboard-[0-9a-f]{8}-', source, re.I):
            raise ValueError(f'Private attachment identifier in {entry}')
        if path.suffix == '.md':
            for link in re.findall(r'\]\(([^)]+)\)', source):
                target = link.split('#', 1)[0].strip('<>')
                if not target or re.match(r'[A-Za-z][A-Za-z0-9+.-]*:', target):
                    continue
                resolved = (path.parent / target).resolve()
                if not resolved.is_relative_to(ROOT):
                    raise ValueError(f'Escaping document link: {entry}: {link}')
                rel = resolved.relative_to(ROOT).as_posix()
                if rel not in entries:
                    raise ValueError(f'Document link not packaged: {entry}: {link}')

    skill_text = (ROOT / 'lightroom-style/SKILL.md').read_text(encoding='utf-8')
    if not skill_text.startswith('---\n'):
        raise ValueError('SKILL.md needs YAML frontmatter at the beginning')
    metadata = yaml.safe_load(skill_text.split('---', 2)[1])
    if metadata.get('name') != 'lightroom-style' or not metadata.get('description'):
        raise ValueError('Invalid skill name/description')
    if metadata.get('license') != 'MIT':
        raise ValueError('The skill must declare the MIT license')
    if digest(ROOT / 'LICENSE') != digest(ROOT / 'lightroom-style/LICENSE'):
        raise ValueError('Repository and standalone skill license mismatch')
    if len(skill_text.splitlines()) >= 500:
        raise ValueError('Keep the entrypoint under 500 lines; move detail to references')
    check_tool_catalog(entries, metadata)
    interface = yaml.safe_load((ROOT / 'lightroom-style/agents/openai.yaml').read_text(encoding='utf-8'))['interface']
    if not 25 <= len(interface['short_description']) <= 64:
        raise ValueError('short_description must have 25–64 characters')
    if '$lightroom-style' not in interface['default_prompt']:
        raise ValueError('default_prompt must explicitly invoke the skill')
    pairs = [
        ('lightroom-bridge/bridge_client.py', 'lightroom-style/scripts/lightroom_client.py'),
        ('lightroom-bridge/bridge_probe.py', 'lightroom-style/scripts/lightroom_probe.py'),
    ]
    pairs.extend((entry, entry.replace('lightroom-bridge/', 'lightroom-style/assets/', 1))
                 for entry in entries if entry.startswith('lightroom-bridge/PhotoStyleBridge.lrplugin/'))
    for source, packaged in pairs:
        if packaged not in entries or digest(ROOT / source) != digest(ROOT / packaged):
            raise ValueError(f'Bridge source/package mismatch: {source} -> {packaged}')
    return sorted(entries)


def write_zip(source: Path, files: list[str], destination: Path, prefix: str) -> None:
    with ZipFile(destination, 'x', compression=ZIP_DEFLATED) as archive:
        for entry in files:
            archive.write(source / entry, f'{prefix}/{entry}')
    with ZipFile(destination) as archive:
        expected = {f'{prefix}/{entry}' for entry in files}
        if set(archive.namelist()) != expected or archive.testzip() is not None:
            raise ValueError(f'Archive verification failed: {destination}')


def build(entries: list[str]) -> Path:
    # Exclusive creation: no recursive deletion or replacement of previous releases.
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = ROOT / 'dist' / f'release-{stamp}'
    repository = output / 'lightroom-style-repository'
    repository.mkdir(parents=True, exist_ok=False)
    for entry in entries:
        destination = repository / entry
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / entry, destination)
        if digest(destination) != digest(ROOT / entry):
            raise ValueError(f'Copy hash mismatch: {entry}')
    write_zip(repository, entries, output / 'lightroom-style-repository.zip', 'lightroom-style-repository')
    skill_entries = [entry.removeprefix('lightroom-style/') for entry in entries
                     if entry.startswith('lightroom-style/')]
    write_zip(repository / 'lightroom-style', skill_entries,
              output / 'lightroom-style-skill.zip', 'lightroom-style')
    hashes = {entry: digest(repository / entry) for entry in entries}
    for filename in ('lightroom-style-repository.zip', 'lightroom-style-skill.zip'):
        hashes[filename] = digest(output / filename)
    (output / 'SHA256SUMS.json').write_text(json.dumps(hashes, indent=2) + '\n', encoding='utf-8')
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Validate without creating files')
    args = parser.parse_args()
    entries = checked_files()
    print(f'Validated {len(entries)} explicitly allowed source files.')
    if not args.check:
        print(build(entries))


if __name__ == '__main__':
    main()
