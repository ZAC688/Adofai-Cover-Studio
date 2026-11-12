import io
import struct
import zlib
from fontTools.ttLib import TTFont,TTLibError

BUILTIN_FONTS={'system','noto-sans-sc','noto-serif-sc','inter','noto-serif',
               'bebas-neue','russo-one','space-mono','space-mono-italic','space-mono-bold','space-mono-bold-italic'}
MAX_FONT_BYTES=50_000_000


def inspect_font(raw:bytes)->tuple[str,str]:
    if len(raw)>MAX_FONT_BYTES:raise ValueError('字体不能超过 50 MB')
    formats={b'\x00\x01\x00\x00':'ttf',b'OTTO':'otf',b'wOFF':'woff',b'wOF2':'woff2'}
    extension=formats.get(raw[:4])
    if not extension:raise ValueError('仅支持有效的 TTF、OTF、WOFF、WOFF2 字体')
    try:
        with TTFont(io.BytesIO(raw),lazy=False,checkChecksums=2) as font:
            if not font.getBestCmap() or not font.getGlyphOrder():raise ValueError('Empty font')
            for required in ['head','hhea','hmtx','maxp','name']:font[required]
            if 'glyf' not in font and 'CFF ' not in font and 'CFF2' not in font:raise ValueError('Missing glyph outlines')
            names=[record.toUnicode() for record in font['name'].names if record.nameID in {1,4}]
            label=next((value for value in names if value.strip()),'上传字体')[:100]
    except (TTLibError,KeyError,ValueError,AssertionError,struct.error,zlib.error,EOFError,UnicodeError) as error:
        raise ValueError('字体文件损坏或不受支持') from error
    return extension,label
