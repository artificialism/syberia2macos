#!/usr/bin/env python3
"""Build an experimental resource patch from the supplied Windows localization."""
import argparse
import concurrent.futures
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import io

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APP = Path.home() / 'Library/Application Support/Steam/steamapps/common/Syberia 2/Syberia 2.app'
VALUE = re.compile(r'<value name="([^"]+)" value="(.*?)"\s*/>', re.S)

def archive(path):
    data = path.read_bytes()
    if data[:4] != b'VXBG':
        raise ValueError(f'Unknown archive: {path}')
    end = 8 + struct.unpack_from('<I', data, 4)[0]
    pos, entries = 8, []
    while pos < end:
        zero = data.index(0, pos, end)
        name = data[pos:zero].decode('cp1251')
        if Path(name).name != name or '\\' in name:
            raise ValueError(f'Unsafe archive member: {name}')
        size = struct.unpack_from('<I', data, zero + 1)[0]
        entries.append((name, size))
        pos = zero + 5
    if pos != end or end + sum(s for _, s in entries) != len(data):
        raise ValueError(f'Invalid archive index: {path}')
    result = {}
    for name, size in entries:
        result[name.lower()] = memoryview(data)[end:end + size]
        end += size
    return result

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--app', type=Path, default=DEFAULT_APP)
    ap.add_argument('--output', type=Path, default=ROOT / 'build/macos-ru')
    ap.add_argument('--audio', action='store_true')
    ap.add_argument('--encoding', choices=['utf8', 'legacy'], default='legacy', help='legacy: CP1251 bytes with Latin glyph aliases; utf8: Unicode trial')
    ap.add_argument('--video-audio', action='store_true', help='Experimental cinematic dubbing; native subtitle timing is retained')
    args = ap.parse_args()
    resources = args.app / 'Contents/Resources'
    out = args.output / 'Resources'
    out.mkdir(parents=True, exist_ok=True)
    if (args.output / 'manifest.json').exists():
        raise SystemExit('Output already contains a patch. Use a fresh --output directory.')
    parts = (ROOT / '.local/source/app/data/string.dat').read_bytes().decode('cp1251').split('\0')
    while parts and parts[-1] == '':
        parts.pop()
    if len(parts) % 2:
        raise ValueError('Invalid string.dat pairs')
    strings = dict(zip(parts[::2], parts[1::2]))
    lower = {k.lower(): v for k, v in strings.items()}
    overrides = json.loads((ROOT / 'translations/ui_ru.json').read_text())
    report = {'app': str(args.app), 'encoding': args.encoding + ' (native runtime verification required)',
              'text_from_windows': 0, 'text_manual': 0, 'control_records_preserved': 0, 'untranslated': [], 'inventory_untranslated': [],
              'dialog_audio': 0, 'cinematic_audio': 0, 'cinematic_duration_checks': [],
              'limitations': ['Help/objective texts and images containing text are not translated.',
                              'Cinematic SRT timings are not retimed for Russian dubbing.',
                              'Native rendering, audio scheduling and gameplay have not been verified.']}
    def write(rel, data):
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    rel = 'texts/PC-MacOSX-Android-iPhone-iPad/en.xml'
    original = (resources / rel).read_bytes().decode('cp1252')
    def translate(match):
        key, old = match.groups()
        if key.endswith('_R'):
            # These are random-dialogue selectors, not displayed text. The
            # Windows version uses a different '#' convention; retain Mac logic.
            report['control_records_preserved'] += 1
            return match.group(0)
        if key.lower() in lower:
            value = lower[key.lower()]
            report['text_from_windows'] += 1
        elif key in overrides:
            value = overrides[key]
            report['text_manual'] += 1
        else:
            value = html.unescape(old)
            if value.strip(): report['untranslated'].append({'key': key, 'text': value})
        # Keep engine directives (such as # and $ references) verbatim inside values.
        return f'<value name="{key}" value="{html.escape(value, quote=True)}"/>'
    encoding = 'cp1251' if args.encoding == 'legacy' else 'utf-8'
    write(rel, VALUE.sub(translate, original).encode(encoding))
    rel = 'Inventory/Objects/Objects_en.xml'
    original = (resources / rel).read_bytes().decode('cp1252')
    aliases = {'rouleau': 'rouleau1', 'bonbonoval': 'bonbonrond', 'bougie_ronce': 'bougieronce', 'bougie_sansronce': 'bougiesansronce'}
    inventory_extra = {'appeau4': 'Коричневый манок', 'bonbonoval': 'Леденцы «Катала»', 'bougie_ronce': 'Свеча с травами', 'bougie_sansronce': 'Свеча'}
    def inventory(match):
        key, old = match.groups()
        suffix = key.removeprefix('Inventory_obj_').lower()
        value = inventory_extra.get(suffix, lower.get(('TT_obj_' + aliases.get(suffix, suffix)).lower()))
        if value is None:
            report['inventory_untranslated'].append({'key': key, 'text': old})
            value = html.unescape(old)
        return f'id="{key}" name="{html.escape(value, quote=True)}"'
    write(rel, re.sub(r'id="([^"]+)" name="([^"]*)"', inventory, original).encode(encoding))
    # Use the Cyrillic-capable font already shipped with this game.
    sys.path.insert(0, str(ROOT / '.local/dependencies/python'))
    from fontTools.ttLib import TTFont
    font_rel = 'Common/Fonts/arial.ttf'
    font = TTFont(resources / font_rel)
    required = {ord(c) for c in 'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя'}
    if not required.issubset(font.getBestCmap()): raise ValueError('Arial lacks Russian glyphs')
    for name in ['BULLN___.TTF', 'Colaborate-Regular.otf', 'CHAUCER.TTF', 'Argh.ttf', 'ProDisplay.ttf', 'ComicRelief.ttf', 'arial.ttf']:
        original_font = TTFont(resources / 'Common/Fonts' / name)
        chosen = resources / 'Common/Fonts' / name if required.issubset(original_font.getBestCmap()) else resources / font_rel
        patched = TTFont(chosen)
        cmap = patched.getBestCmap()
        if args.encoding == 'legacy':
            # The shipped text is single-byte Western text. Cover both byte ->
            # Latin-1 and byte -> Windows-1252 rendering while retaining Unicode glyphs.
            for char in map(chr, sorted(required)):
                byte = char.encode('cp1251')[0]
                for table in patched['cmap'].tables:
                    if table.isUnicode():
                        table.cmap[byte] = cmap[ord(char)]
                        table.cmap[ord(bytes([byte]).decode('cp1252'))] = cmap[ord(char)]
        buffer = io.BytesIO()
        patched.save(buffer)
        # FreeType identifies the font by signature, including at .otf paths.
        write('Common/Fonts/' + name, buffer.getvalue())
    if args.audio or args.video_audio:
        ffmpeg = ROOT / '.local/dependencies/python/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1'
        if not ffmpeg.is_file(): raise ValueError('Bundled ffmpeg not found')
        def convert(source, dest):
            dest.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([str(ffmpeg), '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                            '-i', str(source), '-map', '0:a:0', '-vn', '-c:a', 'libvorbis', '-q:a', '5',
                            str(dest)], check=True)
        if args.audio:
            members = archive(ROOT / '.local/source/app/data/MinimalRes.syb')
            targets = sorted((resources / 'sounds/Dialogs/en').glob('*.ogg'))
            missing = [p.name for p in targets if (p.stem + '.mp3').lower() not in members]
            if missing: raise ValueError(f'Missing Russian audio: {missing}')
            with tempfile.TemporaryDirectory(prefix='syberia-ru-') as temp:
                jobs = []
                for target in targets:
                    source = Path(temp) / (target.stem + '.mp3')
                    source.write_bytes(members[source.name.lower()])
                    jobs.append((source, out / target.relative_to(resources)))
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                    for count, _ in enumerate(pool.map(lambda job: convert(*job), jobs), 1):
                        if count % 250 == 0: print(f'Dialogs: {count}/{len(jobs)}', flush=True)
            report['dialog_audio'] = len(targets)
        if args.video_audio:
            def duration(path):
                output = subprocess.run([str(ffmpeg), '-hide_banner', '-i', str(path)], capture_output=True, text=True).stderr
                match = re.search(r'Duration: (\d+):(\d+):([\d.]+)', output)
                if not match: raise ValueError(f'Cannot read duration: {path}')
                hour, minute, second = map(float, match.groups())
                return hour * 3600 + minute * 60 + second
            names = {'CIN00001_SybRecap': 'CINRecap', **{f'CINNY0{x}': f'CINNY_{x}' for x in [1, 3, 4, 7]}}
            for source in sorted((ROOT / '.local/source/app/video').glob('*.bik')):
                stem = names.get(source.stem, source.stem.split('_')[0])
                rel = Path('videos/en') / (stem + '.ogg')
                if not (resources / rel).is_file(): raise ValueError(f'Unknown cinematic target: {rel}')
                convert(source, out / rel)
                picture_stem = 'CIN00001' if stem == 'CINRecap' else stem
                picture_seconds = duration(resources / 'videos/PC-MacOSX' / (picture_stem + '.ogv'))
                russian_seconds = duration(out / rel)
                difference = round(russian_seconds - picture_seconds, 2)
                report['cinematic_duration_checks'].append({'file': rel.name, 'picture_seconds': picture_seconds,
                    'russian_seconds': russian_seconds, 'russian_vs_picture_seconds': difference})
                if abs(difference) > 0.1:
                    raise ValueError(f'Cinematic duration differs from picture: {rel}: {difference}s')
                report['cinematic_audio'] += 1
    files = []
    for path in sorted(out.rglob('*')):
        if path.is_file():
            rel = path.relative_to(out).as_posix()
            original = resources / rel
            files.append({'path': rel, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                          'original_sha256': hashlib.sha256(original.read_bytes()).hexdigest()})
    (args.output / 'manifest.json').write_text(json.dumps({'format': 1, 'files': files}, indent=2))
    (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k not in ['limitations','cinematic_duration_checks']}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
