from importlib import metadata
from pathlib import Path
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'packaging/dependency-notices'
OUTPUT.mkdir(parents=True, exist_ok=True)
runtime = ['fastapi','starlette','pydantic','pydantic-core','uvicorn','python-multipart',
           'annotated-types','annotated-doc','typing-extensions','typing-inspection','anyio',
           'idna','click','colorama','h11','onnxruntime','numpy','pillow','opencv-python-headless',
           'protobuf','packaging','sympy','mpmath','coloredlogs','humanfriendly','flatbuffers',
           'pyreadline3','pyinstaller','opentelemetry-api','exceptiongroup','fonttools','brotli','zopfli',
           'PySide6','PySide6_Essentials','PySide6_Addons','PySide6_WebEngine','PySide6_Pdf','shiboken6']
lines = ['# Third-party notices', '', 'This folder records dependencies used by the bundled application and its build.',
         'Model: U²-Net small (u2netp), source https://github.com/xuebinqin/U-2-Net;',
         'ONNX export https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx.',
         'Full model source license is included as U2NET-LICENSE.txt.', '']
for name in runtime:
    dist = metadata.distribution(name)
    license_name = dist.metadata.get('License-Expression') or dist.metadata.get('License') or 'See included license files'
    lines.append(f'- {name} {dist.version}: {license_name.splitlines()[0]}')
    for file in dist.files or []:
        path = Path(str(file))
        if (any(term in path.name.upper() for term in ['LICENSE','COPYING','NOTICE']) or any(part.lower() in {'licenses','license'} for part in path.parts)) and path.suffix.lower() not in {'.py','.pyc'}:
            source = dist.locate_file(file)
            if source.is_file():
                target = OUTPUT / name / ('__'.join(path.parts[-3:]))
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
for name in ['react','react-dom','scheduler','pixi.js','pixi-filters','three','@pixi/colord','earcut','eventemitter3','ismobilejs','@xmldom/xmldom','parse-svg-path','tiny-lru','gifuct-js','js-binary-schema-parser']:
    package = ROOT / 'frontend/node_modules' / name
    version = json.loads((package/'package.json').read_text(encoding='utf-8'))['version']
    lines.append(f'- {name} {version}: MIT')
    destination = OUTPUT / name
    destination.mkdir(parents=True,exist_ok=True)
    candidates=[path for path in package.iterdir() if path.is_file() and path.name.lower().startswith(('license','copying'))]
    if not candidates and name=='@pixi/colord':candidates=[ROOT/'packaging/third-party/colord-LICENSE.txt']
    if not candidates:raise FileNotFoundError('Missing license: '+name)
    for path in candidates:shutil.copyfile(path,destination/path.name)
shutil.copyfile(ROOT/'models/U2NET-LICENSE.txt', OUTPUT/'U2NET-LICENSE.txt')
python_license = Path(sys.base_prefix) / 'LICENSE.txt'
if not python_license.is_file():
    raise FileNotFoundError('Python runtime license missing')
shutil.copyfile(python_license, OUTPUT/'PYTHON-LICENSE.txt')
(OUTPUT/'THIRD_PARTY_NOTICES.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
import subprocess
subprocess.run([sys.executable,str(ROOT/'packaging/export_webengine_credits.py')],check=True)
(OUTPUT/'QtWebEngine/RUNTIME-SOURCES.txt').write_text(
    'Unmodified Qt / PySide6 components are dynamically linked and may be replaced under their own licenses.\n'
    'Their license terms govern modification and debugging of these components; this application adds no restriction on those rights.\n'
    'Qt sources: https://code.qt.io/cgit/qt/ (Qt 6.12.0, Qt WebEngine 6.140.0).\n'
    'PySide6 sources: https://code.qt.io/cgit/pyside/pyside-setup.git/ (6.12.0).\n'
    'Licensing: https://doc.qt.io/qtforpython-6/licenses.html and https://doc.qt.io/qt-6/qtwebengine-licensing.html\n'
    'Chromium and other third-party license texts: Chromium-credits.html in this folder.\n',encoding='utf-8')
print(f'License notices collected in {OUTPUT}')
