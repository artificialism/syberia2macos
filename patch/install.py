#!/usr/bin/env python3
"""Check, install, or restore the experimental Syberia 2 resource patch."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from datetime import datetime

DEFAULT_APP = Path.home() / 'Library/Application Support/Steam/steamapps/common/Syberia 2/Syberia 2.app'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def atomic_copy(source, target):
    fd, temp = tempfile.mkstemp(prefix='.syberia-ru-', dir=target.parent)
    os.close(fd)
    try:
        shutil.copy2(source, temp)
        os.replace(temp, target)
    finally:
        Path(temp).unlink(missing_ok=True)

def safe_target(base, relative):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError(f'Unsafe path: {relative}')
    target = base / path
    if not target.resolve().is_relative_to(base.resolve()):
        raise ValueError(f'Target escapes resource directory: {relative}')
    return target

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'install', 'restore'])
    parser.add_argument('--app', type=Path, default=DEFAULT_APP)
    parser.add_argument('--package', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--backup', type=Path, help='Required for restore; optional destination for install')
    args = parser.parse_args()
    resources = args.app / 'Contents/Resources'
    if not resources.is_dir(): raise SystemExit(f'Game resources not found: {resources}')
    package = args.package.resolve()
    manifest = json.loads((package / 'manifest.json').read_text())
    if args.action == 'restore':
        if args.backup is None: raise SystemExit('Pass --backup PATH from the install output.')
        backup = args.backup.resolve()
        record = json.loads((backup / 'backup.json').read_text())
        if Path(record['app']).resolve() != args.app.resolve(): raise SystemExit('Backup belongs to another app.')
        for item in record['files']:
            target = safe_target(resources, item['path'])
            original = safe_target(backup / 'Resources', item['path'])
            if digest(original) != item['original_sha256']: raise SystemExit(f'Damaged backup: {original}')
            if digest(target) not in [item['sha256'], item['original_sha256']]:
                raise SystemExit(f'Game file changed since installation; restore stopped: {target}')
        for item in record['files']:
            atomic_copy(backup / 'Resources' / item['path'], resources / item['path'])
        print('Original resources restored. Backup retained: ' + str(backup))
        return
    files = manifest['files']
    if len({x['path'] for x in files}) != len(files): raise SystemExit('Duplicate manifest entries')
    for item in files:
        source = safe_target(package / 'Resources', item['path'])
        target = safe_target(resources, item['path'])
        if digest(source) != item['sha256']: raise SystemExit(f'Damaged package: {source}')
        if not target.is_file() or digest(target) != item['original_sha256']:
            raise SystemExit(f'Original game file does not match tested build: {target}. Restore any earlier patch first.')
    if args.action == 'check':
        print(f'Package and original resources match: {len(files)} files. No files changed.')
        return
    backup = (args.backup or package / 'backups' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')).resolve()
    if backup.exists(): raise SystemExit('Backup destination already exists; choose a new path.')
    if backup.is_relative_to(resources.resolve()): raise SystemExit('Backup must be outside game resources.')
    backup.mkdir(parents=True)
    # Complete and verify all backups before changing the first game resource.
    for item in files:
        target = safe_target(resources, item['path'])
        saved = safe_target(backup / 'Resources', item['path'])
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, saved)
        if digest(saved) != item['original_sha256']: raise SystemExit(f'Backup failed: {saved}')
    (backup / 'backup.json').write_text(json.dumps({'app': str(args.app.resolve()), 'files': files}, indent=2))
    changed = []
    try:
        for item in files:
            changed.append(item)
            atomic_copy(package / 'Resources' / item['path'], resources / item['path'])
            if digest(resources / item['path']) != item['sha256']: raise RuntimeError('Installed hash mismatch')
    except BaseException:
        for item in reversed(changed):
            atomic_copy(backup / 'Resources' / item['path'], resources / item['path'])
        raise
    print(f'Installed {len(files)} resources. Keep Steam language set to English.\nBackup: {backup}')

if __name__ == '__main__':
    main()
