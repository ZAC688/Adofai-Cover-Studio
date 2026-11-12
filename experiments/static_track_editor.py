"""Build a self-contained offline HTML editor and four high-resolution samples."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from PIL import Image, ImageDraw

from experiments.static_track_probe import ROOT, build_track, dark_preview, get_font, main_charts, read_chart, tile_polygon
from experiments.static_track_export import render_selection
from experiments.static_track_icons import icon_layout, local_icon, outline_color

OUTPUT = ROOT / 'artifacts/static-track-editor'
SAMPLE_RANGES = {"Heaven's Gateway": (1020, 1099), 'The Limit Does Not Exist': (640, 719),
                 'Inferno': (90, 169), 'Crystallized': (300, 379)}


def rounded(value):
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, (list, tuple)):
        return [rounded(v) for v in value]
    if isinstance(value, dict):
        return {k: rounded(v) for k, v in value.items()}
    return value


def browser_chart(track, name, identifier, sample_range, *, reference=False):
    from backend.app.chart_style import reference_polygon,surface_edges
    tiles = []
    for tile in track.tiles:
        angle, layout = icon_layout(tile)
        polygon=reference_polygon(tile) if reference else tile_polygon(tile)
        tiles.append({'floor': tile.floor, 'center': [tile.x, tile.y], 'polygon': polygon,
                      'surface':surface_edges(tile,polygon) if reference else [],
                      'angle': angle, 'bpm': tile.bpm, 'icons': [
                          {'type': kind, 'template': ('twirl-cw' if tile.twirl_clockwise else 'twirl-ccw') if kind == 'twirl' else kind,
                           'offset': [ox, oy], 'scale': size} for kind, ox, oy, size in layout]})
    return rounded({'id': identifier, 'name': name, 'color': track.color, 'outline': outline_color(track.color),
                    'notes': track.notes, 'sample_range': sample_range, 'tiles': tiles})


def make_sample_overview(output, charts):
    image = Image.new('RGB', (1600, 1100), '#0c1018')
    draw = ImageDraw.Draw(image)
    draw.text((25, 18), '静态轨道选段 · 默认颜色与矢量图标 · 4K 输出样图', font=get_font(28), fill='white')
    for i, chart in enumerate(charts):
        x, y = 20+(i%2)*790, 85+(i//2)*500
        draw.rounded_rectangle((x, y, x+770, y+480), radius=12, fill='#171e29')
        draw.text((x+18, y+12), chart['name'], font=get_font(22), fill='white')
        a, b = chart['sample_range']
        draw.text((x+18, y+45), f'砖块 {a}—{b} · 3840 × 2160 PNG / SVG', font=get_font(16), fill='#b4c7dd')
        with Image.open(output / chart['id'] / 'thumbnail-4k.png') as track:
            track.thumbnail((730, 390), Image.Resampling.LANCZOS)
            image.paste(track, (x+(770-track.width)//2, y+80+(390-track.height)//2), track)
    image.save(output / 'samples-overview.png')


def generate_editor(input_dir: Path, output: Path, *, make_samples=True):
    files = sorted(input_dir.rglob('*.adofai'))
    before = {str(p.relative_to(input_dir)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    templates = {kind: local_icon(kind) for kind in ('rabbit', 'turtle', 'midspin', 'checkpoint')}
    templates['twirl-cw'], templates['twirl-ccw'] = local_icon('twirl', True), local_icon('twirl', False)
    charts, samples = [], []
    output.mkdir(parents=True, exist_ok=True)
    for i, path in enumerate(main_charts(input_dir)):
        chart = read_chart(path)
        track = build_track(chart)
        name = re.sub(r'<[^>]+>', '', chart.get('settings', {}).get('song', '')).strip() or ("Heaven's Gateway" if 'heaven' in str(path).lower() else path.stem)
        identifier = f'{i+1:02d}-'+re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        a, b = SAMPLE_RANGES.get(name, (0, min(79, len(track.tiles)-1)))
        a, b = min(a, len(track.tiles)-1), min(b, len(track.tiles)-1)
        charts.append(browser_chart(track, name, identifier, (a, b)))
        if make_samples:
            target = output / identifier / 'thumbnail-4k.png'
            result = render_selection(track, target, start_floor=a, end_floor=b, width=3840, height=2160, padding=108)
            dark_preview(target, target.with_name('thumbnail-4k-preview.png'))
            samples.append({'id': identifier, 'name': name, 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), **result})
        print(f'{name}: {len(track.tiles)} selectable bricks; sample {a}..{b}')
    if not charts:
        raise ValueError('No chart groups found')
    after = {str(p.relative_to(input_dir)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    if before != after:
        raise RuntimeError('Input charts changed during generation')
    payload = rounded({'version': 1, 'fingerprint': hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest(),
                       'templates': templates, 'charts': charts})
    data = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('&', '\\u0026')
    template = Path(__file__).with_suffix('.html').read_text(encoding='utf-8')
    (output / 'index.html').write_text(template.replace('/*__TRACK_DATA__*/', data), encoding='utf-8')
    (output / 'manifest.json').write_text(json.dumps({'source_files_unchanged': True, 'source_hashes': before,
        'visual_match_status': 'NOT_VERIFIED_AGAINST_GAME', 'samples': samples}, ensure_ascii=False, indent=2), encoding='utf-8')
    if make_samples:
        make_sample_overview(output, charts)
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT/'generate_test')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    generate_editor(args.input, args.output)
