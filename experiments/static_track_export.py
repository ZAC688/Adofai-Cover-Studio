"""Selection, crop and fitted export for the independent static-track probe."""
from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw
import numpy as np

from experiments.static_track_probe import tile_polygon
from experiments.static_track_icons import draw_icon, icon_primitives, outline_color, svg_icon


def select_tiles(track, start_floor=0, end_floor=None):
    """Both endpoints are inclusive and retain the original chart geometry."""
    if end_floor is None:
        end_floor = len(track.tiles)-1
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (start_floor, end_floor)):
        raise ValueError("Brick endpoints must be integers")
    if not 0 <= start_floor <= end_floor < len(track.tiles):
        raise ValueError("Brick range must satisfy 0 <= start <= end <= last floor")
    return track.tiles[start_floor:end_floor+1]


def fit_bounds(world, width, height, padding):
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (width, height, padding)):
        raise ValueError("Export dimensions and padding must be integers")
    if not (64 <= width <= 8192 and 64 <= height <= 8192) or width*height > 20_000_000:
        raise ValueError("Export must be 64..8192 pixels per side, at most 20 megapixels")
    if not 4 <= padding < min(width, height)/2:
        raise ValueError("Padding must leave a positive drawing area, at least 4 pixels")
    if len(world) != 4 or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in world):
        raise ValueError("Crop requires four finite coordinates")
    left, bottom, right, top = world
    if right-left <= 1e-9 or top-bottom <= 1e-9:
        raise ValueError("Crop must have a positive width and height")
    scale = min((width-2*padding)/(right-left), (height-2*padding)/(top-bottom))
    used_w, used_h = (right-left)*scale, (top-bottom)*scale
    x, y = (width-used_w)/2, (height-used_h)/2
    return {"world": list(world), "width": width, "height": height, "padding": padding,
            "scale": scale, "offset_x": x-left*scale, "offset_y": y+top*scale,
            "clip": [x, y, x+used_w, y+used_h]}


def selection_scene(track, start_floor=0, end_floor=None, *, rotate_icons=True, style='chart', reference=False):
    tiles = select_tiles(track, start_floor, end_floor)
    from backend.app.chart_style import reference_polygon, surface_edges, GOLD_EDGE
    polygons = [reference_polygon(tile) if reference else tile_polygon(tile) for tile in tiles]
    points = [p for polygon in polygons for p in polygon]
    return {"start_floor": tiles[0].floor, "end_floor": tiles[-1].floor,
            "bounds": [min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)], "tiles": [
                {"floor": tile.floor, "center": [tile.x, tile.y],
                 "polygon": polygon, "fill": '#c3a66eff' if style=='gold' else track.color,
                 "surface": surface_edges(tile,polygon) if reference and style=='gold' else [],
                 "outline": GOLD_EDGE if reference and style=='gold' else '#8f7c50ff' if style=='gold' else outline_color(track.color),
                 "icons": icon_primitives(tile, rotate_icons, reference=reference)}
                for tile,polygon in zip(tiles,polygons)]}


def render_selection(track, target: Path, *, start_floor=0, end_floor=None,
                     width=3840, height=2160, padding=96, crop=None, rotate_icons=True,
                     style='chart', reference=False, show_icons=True, labels=False):
    if style not in ('gold','chart'):
        raise ValueError('Unknown track style')
    scene = selection_scene(track, start_floor, end_floor, rotate_icons=rotate_icons, style=style, reference=reference)
    world = crop if crop is not None else [scene['bounds'][0]-.04, scene['bounds'][1]-.04,
                                          scene['bounds'][2]+.04, scene['bounds'][3]+.04]
    view = fit_bounds(world, width, height, padding)
    ss = 2
    image = Image.new('RGBA', (width*ss, height*ss))
    draw = ImageDraw.Draw(image)
    texture = None
    if style == 'gold':
        from backend.app.chart_style import stone_texture, TEXTURE_UNITS
        unit = max(1, min(2048, round(view['scale']*ss*TEXTURE_UNITS)))
        pattern = np.asarray(stone_texture().resize((unit,unit), Image.Resampling.BILINEAR))
        xs = (np.arange(width*ss)-round(view['offset_x']*ss)) % unit
        ys = (round(view['offset_y']*ss)-np.arange(height*ss)) % unit
        texture = Image.fromarray(pattern[ys[:,None],xs[None,:]])
    def project(point, factor=1):
        return ((point[0]*view['scale']+view['offset_x'])*factor,
                (view['offset_y']-point[1]*view['scale'])*factor)
    x1, y1, x2, y2 = view['clip']
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           f'<defs><clipPath id="crop"><rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}"/></clipPath></defs><g clip-path="url(#crop)">']
    if style=='gold':
        from backend.app.chart_style import stone_data_url, TEXTURE_UNITS
        unit=view['scale']*TEXTURE_UNITS
        svg.insert(1,f'<defs><pattern id="stone" patternUnits="userSpaceOnUse" width="{unit}" height="{unit}" x="{view["offset_x"]}" y="{view["offset_y"]}"><image href="{stone_data_url()}" width="{unit}" height="{unit}" transform="translate(0,{unit}) scale(1,-1)"/></pattern></defs>')
    def coords(points):
        return ' '.join(f'{x:.4f},{y:.4f}' for x, y in (project(p) for p in points))
    for item in reversed(scene['tiles']):
        pixels = [project(p, ss) for p in item['polygon']]
        line_width = max(.45 if reference else .65, (.012 if reference else .025)*view['scale'])
        if texture is not None:
            box = (max(0,math.floor(min(p[0] for p in pixels))),max(0,math.floor(min(p[1] for p in pixels))),
                   min(image.width,math.ceil(max(p[0] for p in pixels))+1),min(image.height,math.ceil(max(p[1] for p in pixels))+1))
            if box[2]>box[0] and box[3]>box[1]:
                tile_mask=Image.new('L',(box[2]-box[0],box[3]-box[1]))
                ImageDraw.Draw(tile_mask).polygon([(x-box[0],y-box[1]) for x,y in pixels],fill=255)
                image.paste(texture.crop(box),box,tile_mask)
        else:
            draw.polygon(pixels, fill=item['fill'])
        draw.line(pixels+[pixels[0]], fill=item['outline'], width=max(1, round(line_width*ss)), joint='curve')
        svg_fill='url(#stone)' if style=='gold' else item['fill']
        svg.append(f'<polygon data-floor="{item["floor"]}" points="{coords(item["polygon"])}" fill="{svg_fill}" stroke="{item["outline"]}" stroke-width="{line_width}" stroke-linejoin="round"/>')
        for edge in item['surface']:
            draw.line([project(p,ss) for p in edge['points']],fill=edge['stroke'],width=max(1,round(edge['width']*view['scale']*ss)))
            svg.append(f'<polyline data-detail="bevel" points="{coords(edge["points"])}" fill="none" stroke="{edge["stroke"]}" stroke-width="{edge["width"]*view["scale"]}"/>')
        for icon in item['icons'] if show_icons else []:
            draw_icon(draw, icon, [project(p, ss) for p in icon['points']], view['scale']*ss)
            svg.append(svg_icon(icon, (project(p) for p in icon['points']), view['scale']))
    mask = Image.new('L', image.size)
    ImageDraw.Draw(mask).rectangle((round(x1*ss), round(y1*ss), round(x2*ss), round(y2*ss)), fill=255)
    image.putalpha(ImageChops.multiply(image.getchannel('A'), mask))
    if labels:
        from experiments.static_track_probe import get_font
        font=get_font(14*ss)
        for tile in select_tiles(track,start_floor,end_floor):
            if len(scene['tiles'])<=160 or tile.floor%10==0:
                point=project((tile.x,tile.y+.16),ss)
                draw.text(point,str(tile.floor),font=font,anchor='mm',fill='white',stroke_width=2,stroke_fill='black')
        image.putalpha(ImageChops.multiply(image.getchannel('A'),mask))
    target.parent.mkdir(parents=True, exist_ok=True)
    image.resize((width, height), Image.Resampling.LANCZOS).save(target)
    target.with_suffix('.svg').write_text('\n'.join(svg+['</g></svg>']), encoding='utf-8')
    result = {"start_floor": scene['start_floor'], "end_floor": scene['end_floor'],
              "tile_count": len(scene['tiles']), "crop": list(crop) if crop is not None else None,
              "view": view, "png": target.name, "svg": target.with_suffix('.svg').name}
    target.with_suffix('.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result
