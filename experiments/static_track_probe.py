"""Offline static-track experiment, separate from the production editor.

Reads chart text only. Meshes and icons are original schematic artwork, not
game assets. See docs/STATIC_TRACK_VALIDATION.md for fidelity limitations.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
import hashlib
from html import escape
import json
import math
from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageFont
from experiments.static_track_icons import color_rgba, draw_icon, icon_primitives, outline_color, svg_icon

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/static-track-validation"
PATH_ANGLES = dict(zip("RpJEToUqGQHWLxNZFVDYBCMA", range(0, 360, 15)))
PATH_ANGLES["!"] = 999


def _remove_json_extras(text: str) -> str:
    """Two string-aware passes: comments first, then trailing commas."""
    clean = []
    quoted = escaped = False
    i = 0
    while i < len(text):
        char = text[i]
        if quoted:
            clean.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            i += 1
        elif char == '"':
            quoted = True
            clean.append(char)
            i += 1
        elif text.startswith("//", i):
            end = text.find("\n", i + 2)
            i = len(text) if end < 0 else end
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0:
                raise ValueError("Unterminated chart comment")
            clean.append(" ")
            i = end + 2
        else:
            clean.append(char)
            i += 1
    text = "".join(clean)
    clean = []
    quoted = escaped = False
    for i, char in enumerate(text):
        if quoted:
            clean.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        if char == ",":
            j = i + 1
            while j < len(text) and text[j].isspace():
                j += 1
            if j < len(text) and text[j] in "]}":
                continue
        clean.append(char)
    return "".join(clean)


def _reject_constant(value: str):
    raise ValueError("Nonfinite JSON constant: " + value)


def read_chart(path: Path) -> dict:
    text = path.read_bytes().decode("utf-8-sig")
    # Older charts may contain literal line breaks in metadata strings.
    data = json.loads(_remove_json_extras(text), strict=False, parse_constant=_reject_constant)
    if not isinstance(data, dict):
        raise ValueError("Chart root must be an object")
    return data


def main_charts(directory: Path) -> list[Path]:
    result = []
    for folder in sorted(p for p in directory.iterdir() if p.is_dir()):
        candidates = sorted(p for p in folder.rglob("*.adofai") if p.stem.lower() != "backup")
        if candidates:
            mains = [p for p in candidates if p.name == "main.adofai"]
            if len(mains) > 1:
                raise ValueError(f"Ambiguous main charts: {folder}")
            result.append(mains[0] if mains else candidates[0])
    return result


def decode_angles(chart: dict) -> tuple[list[float], list[bool]]:
    if "angleData" in chart:
        raw = chart["angleData"]
        if not isinstance(raw, list):
            raise ValueError("angleData must be an array")
    elif isinstance(chart.get("pathData"), str):
        raw = []
        for index, char in enumerate(chart["pathData"]):
            if char not in PATH_ANGLES:
                raise ValueError(f"Unsupported pathData character {char!r} at {index}")
            raw.append(PATH_ANGLES[char])
    else:
        raise ValueError("Chart needs angleData or pathData")
    if not raw:
        raise ValueError("Empty track")
    angles, midspins = [], []
    for index, value in enumerate(raw):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"Invalid angle at {index}")
        if value in (555, 666, 777, 888):
            raise ValueError(f"Relative angle encoding {value} is outside this probe's scope")
        midspin = value == 999
        if midspin and not angles:
            raise ValueError("Midspin has no previous direction at floor 0")
        # Midspin reverses the previous resolved direction, not another step
        # along the incoming direction. Consecutive midspins alternate.
        angles.append((angles[-1] + 180 if midspin else value) % 360)
        midspins.append(midspin)
    return angles, midspins


def enabled(value) -> bool:
    return value is True or value == "Enabled"


def number(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid {label}: {value!r}")
    return float(value)


def direction(angle: float) -> tuple[float, float]:
    return math.cos(math.radians(angle)), math.sin(math.radians(angle))


@dataclass(frozen=True)
class Tile:
    floor: int
    x: float
    y: float
    incoming: float | None
    outgoing: float | None
    midspin: bool = False
    twirl: bool = False
    checkpoint: bool = False
    speed_icon: str | None = None
    bpm: float = 100
    twirl_clockwise: bool = True


@dataclass
class Track:
    tiles: list[Tile]
    notes: list[str]
    position_events_applied: int
    color: str = '#eaf2fcff'


def build_track(chart: dict, *, apply_offsets: bool = True) -> Track:
    """Unit-step centers and optional PositionTrack translations.

    Nontranslation transforms and ScaleRadius are audited, not approximated as
    validated game behavior. A separate no-event render provides a comparison.
    """
    angles, midspins = decode_angles(chart)
    actions = chart.get("actions", [])
    if not isinstance(actions, list):
        raise ValueError("actions must be an array")
    events = defaultdict(list)
    for event in actions:
        if not isinstance(event, dict):
            raise ValueError("Invalid event")
        floor = event.get("floor", 0)
        if isinstance(floor, bool) or not isinstance(floor, int) or not 0 <= floor <= len(angles):
            raise ValueError(f"Invalid event floor {floor!r}")
        events[floor].append(event)
    notes = []
    counts = Counter(e.get("eventType", "UNKNOWN") for e in actions)
    if counts["ScaleRadius"]:
        notes.append(f"ScaleRadius ({counts['ScaleRadius']}) not applied: orbit/spacing semantics need game comparison.")
    transforms = [e for e in actions if e.get("eventType") == "PositionTrack"
                  and not enabled(e.get("editorOnly"))
                  and (e.get("scale", 100) != 100 or e.get("opacity", 100) != 100
                       or e.get("rotation", 0) != 0
                       or e.get("relativeTo", [0, "ThisTile"]) != [0, "ThisTile"])]
    if transforms:
        notes.append(f"PositionTrack non-default transform ({len(transforms)}) not applied; only translations are tested.")
    if counts["PositionTrack"] and enabled(chart.get("settings", {}).get("stickToFloors")):
        notes.append("stickToFloors is enabled; final game geometry is not verified by this translation-only probe.")
    x = y = shift_x = shift_y = 0.0
    bpm = number(chart.get('settings', {}).get('bpm', 100), 'initial BPM')
    if bpm <= 0:
        raise ValueError('BPM must be positive')
    clockwise = True
    tiles = []
    applied = 0
    for floor in range(len(angles) + 1):
        local_x = local_y = 0.0
        previous_bpm = bpm
        for event in events[floor]:
            if event.get('eventType') == 'SetSpeed':
                kind = event.get('speedType', 'Bpm')
                if kind == 'Multiplier':
                    bpm *= number(event.get('bpmMultiplier', 1), 'BPM multiplier')
                elif kind == 'Bpm':
                    bpm = number(event.get('beatsPerMinute', bpm), 'BPM')
                else:
                    raise ValueError(f'Unsupported speed type: {kind}')
                if not math.isfinite(bpm) or bpm <= 0:
                    raise ValueError('BPM must remain positive and finite')
            if event.get('eventType') == 'Twirl':
                clockwise = not clockwise
        speed_icon = None if math.isclose(previous_bpm, bpm, rel_tol=1e-9) else ('rabbit' if bpm > previous_bpm else 'turtle')
        for event in events[floor]:
            if (not apply_offsets or event.get("eventType") != "PositionTrack"
                    or enabled(event.get("editorOnly"))):
                continue
            if (event.get("relativeTo", [0, "ThisTile"]) != [0, "ThisTile"]
                    or event.get("rotation", 0) != 0):
                raise ValueError(f"Unsupported PositionTrack reference/rotation at floor {floor}")
            offset = event.get("positionOffset", [0, 0])
            if not isinstance(offset, list) or len(offset) != 2:
                raise ValueError("PositionTrack offset needs two numbers")
            dx, dy = (number(v, "positionOffset") for v in offset)
            if enabled(event.get("justThisTile")):
                local_x += dx
                local_y += dy
            else:
                shift_x += dx
                shift_y += dy
            applied += 1
        tiles.append(Tile(floor, x + shift_x + local_x, y + shift_y + local_y,
                          (angles[floor-1]+180) % 360 if floor else None,
                          angles[floor] if floor < len(angles) else None,
                          midspins[floor] if floor < len(angles) else False,
                          any(e.get("eventType") == "Twirl" for e in events[floor]),
                          any(e.get("eventType") == "Checkpoint" for e in events[floor]),
                          speed_icon, bpm, clockwise))
        if floor < len(angles):
            dx, dy = direction(angles[floor])
            x += dx
            y += dy
    return Track(tiles, notes, applied, color_rgba(chart.get('settings', {}).get('trackColor')))


def convex_hull(points):
    points = sorted(set(points))
    def cross(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
    lower, upper = [], []
    for point in points:
        while len(lower) > 1 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    for point in reversed(points):
        while len(upper) > 1 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def tile_polygon(tile: Tile):
    # Original simplified mesh, not a reproduction of the game's tile skin.
    # Ports follow the angles: no invented bridges across PositionTrack jumps.
    radius = .29
    points = [(radius*math.cos(i*math.tau/48), radius*math.sin(i*math.tau/48)) for i in range(48)]
    for angle in (tile.incoming, tile.outgoing):
        if angle is not None:
            dx, dy = direction(angle)
            for side in (-1, 1):
                points.append((.5*dx-side*radius*dy, .5*dy+side*radius*dx))
    return [(tile.x+x, tile.y+y) for x, y in convex_hull(points)]


def bounds(tiles):
    points = [p for tile in tiles for p in tile_polygon(tile)]
    return min(x for x, _ in points), min(y for _, y in points), max(x for x, _ in points), max(y for _, y in points)


def get_font(size):
    for path in (Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/arial.ttf")):
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def render_track(track, png_path: Path, *, start=0, end=None, max_side=2200, labels=False):
    """Paired transparent PNG and SVG using the same polygon geometry."""
    tiles = track.tiles[start:end]
    if not tiles:
        raise ValueError("Empty render range")
    left, bottom, right, top = bounds(tiles)
    margin = .8
    world_w, world_h = right-left+2*margin, top-bottom+2*margin
    # World-unit margins alone collapse below one pixel on very long charts.
    # Keep a fixed pixel border as well, including the downsampling kernel.
    if max_side < 64:
        raise ValueError("max_side must be at least 64 pixels")
    padding = 16
    scale = (max_side-2*padding-2) / max(world_w, world_h)
    width = max(2, math.ceil(world_w*scale)+2*padding)
    height = max(2, math.ceil(world_h*scale)+2*padding)
    ss = 2
    image = Image.new("RGBA", (width*ss, height*ss), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    def project(p, factor=1):
        return (((p[0]-left+margin)*scale+padding)*factor,
                ((top+margin-p[1])*scale+padding)*factor)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           '<title>Static track probe: simplified tiles, no game-time effects</title>']
    outline = max(.7, .025*scale)
    for tile in reversed(tiles):
        polygon = tile_polygon(tile)
        pixels = [project(p, ss) for p in polygon]
        draw.polygon(pixels, fill=track.color)
        edge = outline_color(track.color)
        draw.line(pixels+[pixels[0]], fill=edge, width=max(1, round(outline*ss)), joint="curve")
        coords = " ".join(f"{x:.3f},{y:.3f}" for x, y in (project(p) for p in polygon))
        svg.append(f'<polygon data-floor="{tile.floor}" points="{coords}" fill="{track.color}" stroke="{edge}" stroke-width="{outline:.3f}" stroke-linejoin="round"/>')
        for icon in icon_primitives(tile):
            draw_icon(draw, icon, [project(p, ss) for p in icon['points']], scale*ss)
            svg.append(svg_icon(icon, (project(p) for p in icon['points']), scale))
    if labels:
        font = get_font(max(9, round(min(13, scale*.2)))*ss)
        for tile in tiles:
            if tile.floor % 10 == 0 or tile == tiles[0] or tile == tiles[-1]:
                x, y = project((tile.x, tile.y+.39), ss)
                draw.text((x, y), str(tile.floor), font=font, anchor="mm", fill="#8fdfff", stroke_width=1, stroke_fill="#07111e")
    svg.append("</svg>")
    png_path.parent.mkdir(parents=True, exist_ok=True)
    image.resize((width, height), Image.Resampling.LANCZOS).save(png_path)
    png_path.with_suffix(".svg").write_text("\n".join(svg), encoding="utf-8")
    return {"width": width, "height": height, "floor_start": tiles[0].floor,
            "floor_end": tiles[-1].floor, "tile_count": len(tiles),
            "bounds": [left, bottom, right, top], "pixels_per_unit": scale,
            "png": png_path.name, "svg": png_path.with_suffix(".svg").name}


def dark_preview(source: Path, target: Path):
    with Image.open(source) as image:
        result = Image.new("RGBA", image.size, "#10151d")
        result.alpha_composite(image.convert("RGBA"))
        result.convert("RGB").save(target)


def create_overview(output: Path, records):
    canvas = Image.new("RGB", (1600, 1400), "#080d14")
    draw = ImageDraw.Draw(canvas)
    draw.text((32, 18), "ADOFAI 静态轨道验证 · 四组主谱", font=get_font(30), fill="white")
    draw.text((32, 62), "基础布局与静态位移试算；简化砖块样式，不含动画、镜头、装饰和特效", font=get_font(19), fill="#b6c7db")
    for i, record in enumerate(records):
        col, row = i % 2, i // 2
        x, y = 20+col*790, 105+row*640
        draw.rounded_rectangle((x, y, x+770, y+620), radius=12, fill="#10151d", outline="#39465a")
        draw.text((x+18, y+12), record["display_name"], font=get_font(23), fill="#eaf2fc")
        draw.text((x+18, y+50), f'{record["angle_count"]} 段 / {record["tile_count"]} 个节点 · 中旋 {record["midspin_count"]}', font=get_font(17), fill="#acbdd2")
        with Image.open(output / record["id"] / "track.png") as image:
            image.thumbnail((725, 485), Image.Resampling.LANCZOS)
            canvas.paste(image, (x+(770-image.width)//2, y+84+(485-image.height)//2), image)
        caption = "含未核实的静态变换：请先检查对照图" if record["notes"] else "基础静态布局：待与游戏截图人工核对"
        draw.text((x+18, y+580), caption, font=get_font(17), fill="#ffd477" if record["notes"] else "#93b5dc")
    canvas.save(output / "overview.png")


def run(input_dir: Path, output: Path):
    charts = main_charts(input_dir)
    if not charts:
        raise ValueError("No chart groups found")
    output.mkdir(parents=True, exist_ok=True)
    all_files = sorted(input_dir.rglob("*.adofai"))
    before = {str(p.relative_to(input_dir)): hashlib.sha256(p.read_bytes()).hexdigest() for p in all_files}
    records, sections = [], []
    for i, path in enumerate(charts):
        chart = read_chart(path)
        base, positioned = build_track(chart, apply_offsets=False), build_track(chart)
        name = re.sub(r"<[^>]+>", "", chart.get("settings", {}).get("song", "")).strip()
        if not name:
            name = "Heaven's Gateway" if "heaven" in str(path).lower() else path.stem
        identifier = f"{i+1:02d}-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        folder = output / identifier
        main = render_track(positioned, folder / "track.png")
        base_render = render_track(base, folder / "base-layout.png")
        dark_preview(folder / "track.png", folder / "preview.png")
        ranges = [(0, min(80, len(positioned.tiles))),
                  (max(0, len(positioned.tiles)//2-40), min(len(positioned.tiles), len(positioned.tiles)//2+40))]
        position_floor = next((e["floor"] for e in chart.get("actions", [])
                               if e.get("eventType") == "PositionTrack" and not enabled(e.get("editorOnly"))), None)
        midspin_floor = next((t.floor for t in positioned.tiles if t.midspin), None)
        for floor in (position_floor, midspin_floor):
            if floor is not None:
                pair = (max(0, floor-10), min(len(positioned.tiles), floor+45))
                if pair not in ranges:
                    ranges.append(pair)
        details = []
        for j, (start, end) in enumerate(ranges):
            filename = f"detail-{j+1:02d}-{start}-{end-1}.png"
            result = render_track(positioned, folder / filename, start=start, end=end, max_side=1600, labels=True)
            dark_preview(folder / filename, folder / filename.replace(".png", "-preview.png"))
            details.append(result)
        actions = chart.get("actions", [])
        record = {"id": identifier, "display_name": name, "input": str(path.resolve()),
                  "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "version": chart.get("settings", {}).get("version"),
                  "encoding": "angleData" if "angleData" in chart else "pathData",
                  "angle_count": len(positioned.tiles)-1, "tile_count": len(positioned.tiles),
                  "midspin_count": sum(t.midspin for t in positioned.tiles),
                  "event_counts": dict(sorted(Counter(e.get("eventType", "UNKNOWN") for e in actions).items())),
                  "position_events_applied": positioned.position_events_applied,
                  "editor_only_position_events_ignored": sum(e.get("eventType") == "PositionTrack" and enabled(e.get("editorOnly")) for e in actions),
                  "notes": positioned.notes, "main": main, "base": base_render, "details": details}
        (folder / "geometry.json").write_text(json.dumps({"metadata": record, "tiles": [asdict(t) for t in positioned.tiles]}, ensure_ascii=False, indent=2), encoding="utf-8")
        records.append(record)
        detail_links = " ".join(f'<a href="{identifier}/{d["png"].replace(".png", "-preview.png")}">局部 {d["floor_start"]}–{d["floor_end"]}</a>' for d in details)
        notes = "<br>".join(escape(n) for n in record["notes"]) or "需与游戏截图核对；测试通过不等于游戏画面一致。"
        sections.append(f'<section><h2>{escape(name)}</h2><p>{record["angle_count"]} 段 / {record["tile_count"]} 个节点 / 中旋 {record["midspin_count"]}</p><p class="note">{notes}</p><p><a href="{identifier}/track.png" download>透明 PNG</a> <a href="{identifier}/track.svg">矢量 SVG</a> <a href="{identifier}/base-layout.png">未应用位移的基础布局</a> {detail_links}</p><a href="{identifier}/preview.png"><img src="{identifier}/preview.png" alt="{escape(name)} 静态布局"></a></section>')
        print(f'{name}: {record["angle_count"]} directions -> {record["tile_count"]} nodes, {main["width"]}x{main["height"]}; {len(record["notes"])} notes')
    after = {str(p.relative_to(input_dir)): hashlib.sha256(p.read_bytes()).hexdigest() for p in all_files}
    if before != after:
        raise RuntimeError("Input charts changed during validation")
    manifest = {"scope": "Static schematic, no animation/camera/decoration/effects",
                "visual_match_status": "NOT_VERIFIED_AGAINST_GAME", "all_chart_sha256_before": before,
                "all_chart_sha256_after": after, "source_files_unchanged": before == after, "charts": records}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    html = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>静态轨道验证</title><style>body{background:#080d14;color:#eaf2fc;font:16px system-ui;max-width:1200px;margin:30px auto;padding:20px}a{color:#91ccff;margin-right:14px}section{background:#10151d;padding:20px;margin:25px 0;border:1px solid #39465a;border-radius:12px}img{display:block;max-width:100%;max-height:850px;margin:auto}.note{color:#ffd477}</style><h1>静态轨道生成验证</h1><p>实验结果，尚未接入封面编辑器。使用简化砖块和自绘图标；不读取音乐、背景图片或装饰。</p><p>track.png 应用了非 editorOnly 的 PositionTrack 位移；base-layout.png 仅使用方向数据。缩放与粘性轨道语义仍需核对，完整忽略项见 manifest.json。</p>' + "".join(sections) + '</html>'
    (output / "index.html").write_text(html, encoding="utf-8")
    create_overview(output, records)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "generate_test")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    run(args.input, args.output)
