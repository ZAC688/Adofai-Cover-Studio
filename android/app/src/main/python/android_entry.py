import os


def start(root, data):
    os.environ['ADOFAI_ANDROID'] = '1'
    from backend.android_server import start as start_server
    return start_server(root, data)


def stop():
    from backend.android_server import stop as stop_server
    stop_server()


def diagnostics():
    import json
    import sys
    import numpy
    import PIL
    import cv2
    import pydantic
    import brotli
    import fontTools
    return json.dumps({'python':list(sys.version_info[:3]),'numpy':numpy.__version__,
                       'pillow':PIL.__version__,'opencv':cv2.__version__,
                       'pydantic':pydantic.VERSION,'brotli':brotli.__version__,
                       'fonttools':fontTools.__version__})
