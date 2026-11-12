"""Local vector outlines from the same preset/uploaded fonts used by titles."""
from contextlib import ExitStack
from pathlib import Path
import os
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from .fonts import BUILTIN_FONTS


def text_outline(text:str,font_id:str,store,frontend:Path):
    fonts=frontend/'fonts'
    system=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Fonts'/'msyhbd.ttc'
    if not system.is_file():system=fonts/'noto-sans-sc.ttf'
    path=system if font_id=='system' else fonts/f'{font_id}.ttf' if font_id in BUILTIN_FONTS else store.font_info(font_id)['path']
    weight=700 if font_id.startswith('space-mono-bold') else 400 if font_id.startswith(('space-mono','bebas','russo')) else 900
    with ExitStack() as stack:
        def load(source,weight):
            font=stack.enter_context(TTFont(source,fontNumber=0,lazy=True))
            location={'wght':weight} if 'fvar' in font and any(a.axisTag=='wght' for a in font['fvar'].axes) else None
            return font,font.getBestCmap(),font.getGlyphSet(location=location)
        font,cmap,glyphs=load(path,weight)
        fallback=None;cursor=0.;paths=[];substitutions=[];missing=[]
        ascent=font['hhea'].ascent/font['head'].unitsPerEm*1000
        height=(font['hhea'].ascent-font['hhea'].descent)/font['head'].unitsPerEm*1000
        for char in text:
            use_font,use_map,use_glyphs=font,cmap,glyphs
            if ord(char) not in cmap:
                if fallback is None:fallback=load(system,900)
                use_font,use_map,use_glyphs=fallback
                if ord(char) in use_map:substitutions.append(char)
                else:missing.append(char)
            name=use_map.get(ord(char),'.notdef')
            if name not in use_glyphs:continue
            scale=1000/use_font['head'].unitsPerEm
            pen=SVGPathPen(use_glyphs,ntos=lambda value:format(value,'.5f').rstrip('0').rstrip('.') or '0')
            use_glyphs[name].draw(TransformPen(pen,(scale,0,0,-scale,cursor,ascent)))
            commands=pen.getCommands()
            if commands:paths.append(commands)
            cursor+=use_glyphs[name].width*scale
        return {'paths':paths,'width':cursor,'height':height,'fallbackCharacters':list(dict.fromkeys(substitutions)),'missingCharacters':list(dict.fromkeys(missing))}
