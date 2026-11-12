"""Original vector pictograms; shared by PNG, SVG and browser exports."""
import math


def ellipse(x, y, rx, ry, count=32):
    return [(x+rx*math.cos(i*math.tau/count), y+ry*math.sin(i*math.tau/count)) for i in range(count)]


def local_icon(kind, clockwise=True):
    parts = []
    def solid(points, color, stroke='#192536ff'):
        parts.append({'kind': 'polygon', 'points': points, 'fill': color, 'stroke': stroke, 'width': .012})
    def line(points, color, width=.035):
        parts.append({'kind': 'line', 'points': points, 'stroke': color, 'width': width})
    if kind == 'rabbit':
        color = '#ffb96bff'
        for args in [(-.17, .005, .039, .039), (-.035, -.025, .13, .087),
                     (.075, .055, .073, .074), (.065, .166, .024, .079),
                     (.128, .157, .025, .077), (-.055, -.105, .080, .025),
                     (.075, -.100, .072, .024)]:
            solid(ellipse(*args), color)
        solid(ellipse(.109, .077, .012, .012), '#192536ff')
        line([(.063, .135), (.065, .200)], '#d2606fff', .012)
        line([(.126, .130), (.128, .190)], '#d2606fff', .012)
    elif kind == 'turtle':
        color = '#9be693ff'
        for args in [(-.100, -.105, .037, .040), (.100, -.105, .037, .040),
                     (-.100, .105, .037, .040), (.100, .105, .037, .040),
                     (.190, .018, .044, .045)]:
            solid(ellipse(*args), color)
        solid([(-.15, -.025), (-.225, 0), (-.15, .025)], color)
        solid(ellipse(0, 0, .155, .107), '#60b47aff')
        solid(ellipse(0, 0, .073, .063, 6), '#9be693ff')
        for angle in range(0, 360, 60):
            a = math.radians(angle)
            line([(.075*math.cos(a), .060*math.sin(a)), (.149*math.cos(a), .100*math.sin(a))], '#25443aff', .012)
        solid(ellipse(.206, .030, .010, .010), '#192536ff')
    elif kind == 'twirl':
        sign = -1 if clockwise else 1
        spiral = []
        for i in range(97):
            angle = sign*i/96*math.tau*1.65
            radius = .012+i/96*.186
            spiral.append((radius*math.cos(angle), radius*math.sin(angle)))
        line(spiral, '#ff8acbff', .037)
        last, previous = spiral[-1], spiral[-2]
        dx, dy = last[0]-previous[0], last[1]-previous[1]
        length = math.hypot(dx, dy)
        dx, dy = dx/length, dy/length
        line([(last[0]-.075*dx-.040*dy, last[1]-.075*dy+.040*dx), last,
              (last[0]-.075*dx+.040*dy, last[1]-.075*dy-.040*dx)], '#ff8acbff', .037)
    elif kind == 'midspin':
        line([(-.09, -.12), (.10, 0), (-.09, .12)], '#ffd477ff', .040)
    elif kind == 'checkpoint':
        line([(-.10, -.17), (-.10, .18), (.14, .09), (-.10, .03)], '#8bffc3ff', .035)
    else:
        raise ValueError(f'Unknown icon: {kind}')
    return parts


def icon_layout(tile):
    kinds = []
    if tile.twirl:
        kinds.append('twirl')
    if tile.speed_icon:
        kinds.append(tile.speed_icon)
    if tile.midspin:
        kinds.append('midspin')
    if tile.checkpoint:
        kinds.append('checkpoint')
    angle = tile.outgoing if tile.outgoing is not None else (tile.incoming+180 if tile.incoming is not None else 0)
    if len(kinds) <= 1:
        locations, size = [(0, 0)], 1
    elif len(kinds) == 2:
        locations, size = [(-.12, 0), (.12, 0)], .54
    else:
        locations, size = [(-.11, .11), (.11, .11), (-.11, -.11), (.11, -.11)], .46
    return angle, [(kind, ox, oy, size) for kind, (ox, oy) in zip(kinds, locations)]


def icon_primitives(tile, rotate_icons=True, *, reference=False):
    angle, layout = icon_layout(tile)
    if not rotate_icons:
        angle = 0
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    result = []
    for kind, ox, oy, size in layout:
        if reference:
            from backend.app.chart_style import reference_icon
            artwork = reference_icon(kind, tile.twirl_clockwise)
        else:
            artwork = local_icon(kind, tile.twirl_clockwise)
        for primitive in artwork:
            points = []
            for x, y in primitive['points']:
                x, y = ox+x*size, oy+y*size
                points.append((tile.x+x*c-y*s, tile.y+x*s+y*c))
            result.append({**primitive, 'points': points, 'width': primitive['width']*size, 'icon_type': kind})
    return result


def color_rgba(value):
    value = (value or 'eaf2fc').lstrip('#')
    if len(value) not in (6, 8) or any(char not in '0123456789abcdefABCDEF' for char in value):
        raise ValueError('Track color must be RRGGBB or RRGGBBAA')
    return '#'+value.lower()+('ff' if len(value) == 6 else '')


def outline_color(fill):
    rgb = [int(fill[i:i+2], 16)/255 for i in (1, 3, 5)]
    bright = sum(a*b for a, b in zip(rgb, (.2126, .7152, .0722))) > .55
    return ('#263443' if bright else '#eaf2fc')+fill[-2:]


def svg_icon(icon, projected_points, scale):
    points = list(projected_points)
    coordinates = ' '.join(f'{x:.4f},{y:.4f}' for x, y in points)
    attrs = f'data-icon="{icon["icon_type"]}" stroke="{icon["stroke"]}" stroke-width="{icon["width"]*scale:.4f}" stroke-linejoin="round" stroke-linecap="round"'
    if icon['kind'] == 'polygon':
        path = 'M '+' L '.join(f'{x:.4f},{y:.4f}' for x, y in points)+' Z'
        return f'<path d="{path}" fill="{icon["fill"]}" {attrs}/>'
    return f'<polyline points="{coordinates}" fill="none" {attrs}/>'


def draw_icon(draw, icon, pixels, scale):
    width = max(1, round(icon['width']*scale))
    if icon['kind'] == 'polygon':
        draw.polygon(pixels, fill=icon['fill'])
        draw.line(pixels+[pixels[0]], fill=icon['stroke'], width=width, joint='curve')
    else:
        draw.line(pixels, fill=icon['stroke'], width=width, joint='curve')
