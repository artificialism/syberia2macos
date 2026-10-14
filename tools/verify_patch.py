#!/usr/bin/env python3
"""Verify resource conversion and an install/restore cycle in an isolated fixture."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.local/dependencies/python'))
from fontTools.ttLib import TTFont

package = ROOT / 'patch'
manifest = json.loads((package / 'manifest.json').read_text())
report = json.loads((package / 'report.json').read_text())
resources = Path(report['app']) / 'Contents/Resources'
encoding = 'cp1251' if report['encoding'].startswith('legacy') else 'utf-8'
relative = 'texts/PC-MacOSX-Android-iPhone-iPad/en.xml'
old = (resources / relative).read_bytes().decode('cp1252')
new = (package / 'Resources' / relative).read_bytes().decode(encoding)
pattern = re.compile(r'<value name="([^"]+)" value="(.*?)"\s*/>', re.S)
assert [k for k, _ in pattern.findall(old)] == [k for k, _ in pattern.findall(new)], 'Changed text identifiers/order'
old_values = dict(pattern.findall(old))
assert all(value == old_values[key] for key, value in pattern.findall(new) if key.endswith('_R')), 'Changed Mac dialogue selectors'
ET.fromstring('<root>' + new + '</root>')
inventory = (package / 'Resources/Inventory/Objects/Objects_en.xml').read_bytes().decode(encoding)
assert re.findall(r'id="([^"]+)"', inventory) == re.findall(r'id="([^"]+)"', (resources / 'Inventory/Objects/Objects_en.xml').read_bytes().decode('cp1252'))
assert not report['untranslated'] and not report['inventory_untranslated']
font_count = 0
for path in (package / 'Resources/Common/Fonts').iterdir():
    font = TTFont(path)
    cmap = font.getBestCmap()
    for char in 'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя':
        assert ord(char) in cmap, (path, char)
        if encoding == 'cp1251':
            assert cmap[char.encode('cp1251')[0]] == cmap[ord(char)], (path, char)
    font_count += 1
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
with tempfile.TemporaryDirectory(prefix='syberia-install-test-') as temp:
    fixture = Path(temp) / 'Syberia 2.app'
    for item in manifest['files']:
        dest = fixture / 'Contents/Resources' / item['path']
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(resources / item['path'], dest)
    backup = Path(temp) / 'backup'
    def run(*args, ok=True):
        result = subprocess.run([sys.executable, str(package / 'install.py'), *args, '--app', str(fixture)], capture_output=True, text=True)
        assert (result.returncode == 0) == ok, result.stdout + result.stderr
    run('check')
    # A changed original must cause refusal before creating a backup.
    victim = fixture / 'Contents/Resources' / manifest['files'][0]['path']
    original_bytes = victim.read_bytes()
    victim.write_bytes(original_bytes + b'test')
    run('install', '--backup', str(backup), ok=False)
    assert not backup.exists()
    victim.write_bytes(original_bytes)
    run('install', '--backup', str(backup))
    assert all(sha(fixture / 'Contents/Resources' / i['path']) == i['sha256'] for i in manifest['files'])
    run('restore', '--backup', str(backup))
    assert all(sha(fixture / 'Contents/Resources' / i['path']) == i['original_sha256'] for i in manifest['files'])
result = {'text_records': len(pattern.findall(new)), 'inventory_objects': len(re.findall(r'id="', inventory)),
          'fonts_verified': font_count, 'resources_install_restore_verified': len(manifest['files']),
          'modified_original_refused': True, 'native_gameplay_verified': False}
report_dir = ROOT / '.local/reports'
report_dir.mkdir(parents=True, exist_ok=True)
(report_dir / 'package-validation.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
