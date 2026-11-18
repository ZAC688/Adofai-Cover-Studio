import os


def start(root, data):
    os.environ['ADOFAI_ANDROID'] = '1'
    from backend.android_server import start as start_server
    return start_server(root, data)


def stop():
    from backend.android_server import stop as stop_server
    stop_server()
