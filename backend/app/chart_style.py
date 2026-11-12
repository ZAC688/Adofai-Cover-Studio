"""Offline reference-matched stone relief and vector pictograms."""
import base64
import io
import math
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from experiments.static_track_icons import local_icon, ellipse

TEXTURE_UNITS = 4
GOLD_EDGE = '#59482eff'


@lru_cache(maxsize=1)
def stone_texture():
    rng = np.random.default_rng(688)
    coarse = Image.fromarray(rng.integers(70, 190, (32, 32), dtype='uint8')).resize((512, 512), Image.Resampling.BICUBIC)
    grain = rng.normal(0, 5.6, (512, 512)) + (np.asarray(coarse).astype(float)-128)/14
    pits = rng.random((512, 512)) < .043
    grain[pits] -= rng.uniform(18, 56, pits.sum())
    rgb = np.clip(np.array([195, 166, 110])+grain[:, :, None], 0, 255).astype('uint8')
    image = Image.fromarray(rgb).convert('RGBA')
    cracks = Image.new('RGBA', image.size)
    draw = ImageDraw.Draw(cracks)
    for _ in range(65):
        x, y = rng.integers(0, 512, 2)
        points = [(int(x), int(y))]
        direction = rng.uniform(-math.pi, math.pi)
        for _ in range(int(rng.integers(4, 13))):
            direction += rng.uniform(-.8, .8)
            x += math.cos(direction)*rng.uniform(2, 7)
            y += math.sin(direction)*rng.uniform(2, 7)
            points.append((int(x), int(y)))
        draw.line([(x+1, y-1) for x, y in points], fill=(255, 231, 169, 125), width=1)
        draw.line(points, fill=(90, 72, 39, 110), width=1)
        if len(points)>7:
            x, y = points[4]
            draw.line([(x, y), (x-4, y+6), (x-3, y+11)], fill=(90, 72, 39, 80), width=1)
    return Image.alpha_composite(image, cracks.filter(ImageFilter.GaussianBlur(.25)))


def stone_data_url():
    stream = io.BytesIO(); stone_texture().save(stream, format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(stream.getvalue()).decode('ascii')


def reference_icon(kind, clockwise=True):
    if kind == 'rabbit':
        body=curve((-.19,-.025), [
            ((-.24,.04),(-.16,.09),(-.135,.025)),
            ((-.12,.13),(-.025,.14),(.025,.08)),
            ((.005,.16),(-.025,.25),(.007,.255)),
            ((.05,.26),(.062,.16),(.068,.13)),
            ((.075,.18),(.10,.27),(.128,.25)),
            ((.16,.23),(.12,.14),(.115,.115)),
            ((.22,.105),(.225,.04),(.143,.015)),
            ((.095,-.015),(.10,-.065),(.165,-.08)),
            ((.20,-.14),(.035,-.14),(.015,-.095)),
            ((-.04,-.13),(-.165,-.14),(-.17,-.10)),
            ((-.12,-.055),(-.075,-.075),(-.09,-.035)),
            ((-.13,-.065),(-.17,-.065),(-.19,-.025))])
        return [{'kind':'polygon','points':body,'fill':'#df493cff','stroke':'#fff1cfff','width':.019},
                {'kind':'polygon','points':ellipse(.137,.075,.008,.01),'fill':'#4d2725ff','stroke':'#4d2725ff','width':.003},
                {'kind':'line','points':[(.014,.19),(.029,.125)],'stroke':'#9f343aff','width':.008}]
    original = local_icon(kind, clockwise)
    if kind == 'twirl':
        spiral, arrow = original
        return [{**spiral,'stroke':'#704051ff','width':.069},
                {**spiral,'stroke':'#efacc7ff','width':.049},
                {**spiral,'stroke':'#8552a9ff','width':.024},
                {**arrow,'stroke':'#704051ff','width':.066},
                {**arrow,'stroke':'#4477d5ff' if clockwise else '#df493cff','width':.046}]
    result = []
    for part in original:
        part = dict(part)
        if part['kind'] == 'polygon' and part.get('fill') != '#192536ff':
            part['stroke'] = '#fff1cfff'; part['width'] = .016
        result.append(part)
    return result


def curve(start, segments):
    result = [start]
    for c1, c2, end in segments:
        x, y = result[-1]
        for i in range(1, 13):
            t=i/12; s=1-t
            result.append((s**3*x+3*s*s*t*c1[0]+3*s*t*t*c2[0]+t**3*end[0],
                           s**3*y+3*s*s*t*c1[1]+3*s*t*t*c2[1]+t**3*end[1]))
    return result


def reference_polygon(tile):
    """Mitered corners and round exposed caps, with unchanged half-step ports."""
    from experiments.static_track_probe import tile_polygon
    if tile.incoming is None or tile.outgoing is None:
        return tile_polygon(tile)
    a, b = (math.radians(v) for v in (tile.incoming, tile.outgoing))
    u, v = (math.cos(a), math.sin(a)), (math.cos(b), math.sin(b))
    if u[0]*v[0]+u[1]*v[1] > .3:
        return tile_polygon(tile)
    n0, n1 = (u[1], -u[0]), (-v[1], v[0])
    nx, ny = n0[0]+n1[0], n0[1]+n1[1]
    denominator = nx*n0[0]+ny*n0[1]
    if denominator < 1e-8:
        return tile_polygon(tile)
    r = .29
    join = (r*nx/denominator, r*ny/denominator)
    p, q = (.5*u[0], .5*u[1]), (.5*v[0], .5*v[1])
    points = [(p[0]+r*n0[0], p[1]+r*n0[1]), join,
              (q[0]+r*n1[0], q[1]+r*n1[1]), (q[0]-r*n1[0], q[1]-r*n1[1]),
              (-join[0], -join[1]), (p[0]-r*n0[0], p[1]-r*n0[1])]
    return [(round(tile.x+x,12), round(tile.y+y,12)) for x, y in points]


def surface_edges(tile, polygon):
    edges=[]
    points=[(tile.x+(x-tile.x)*.968, tile.y+(y-tile.y)*.968) for x,y in polygon]
    for a,b in zip(points,points[1:]+points[:1]):
        mx,my=(a[0]+b[0])/2-tile.x,(a[1]+b[1])/2-tile.y
        edges.append({'points':[a,b],'stroke':'#f2d898ff' if -mx+my>0 else '#a18a56ff','width':.009})
    return edges
