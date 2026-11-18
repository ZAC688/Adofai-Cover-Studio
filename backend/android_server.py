"""Offline Android HTTP adapter for the same storage, schemas and algorithms.

Only a loopback socket is opened. All user files remain in the application data
directory; the runtime directory contains only bundled, read-only resources.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from email.parser import BytesParser
from email.policy import default as email_policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import mimetypes
from pathlib import Path
import re
import secrets
import sqlite3
import sys
import threading
from urllib.parse import unquote, urlsplit
import uuid

from PIL import Image


class PayloadTooLarge(ValueError):
    pass


class ThreadJobs:
    """Android cannot spawn Python processes; cancel invalidates the result."""
    def __init__(self, store, model):
        self.store, self.model = store, model
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='track-recognition')
        self.lock = threading.RLock()
        self.records = {}

    @staticmethod
    def public(record):
        return {key: record[key] for key in ('id', 'source', 'status', 'result', 'error')}

    def start(self, source):
        if self.store.asset_info(source)['kind'] != 'image':
            raise ValueError('识别输入必须是轨道原始图片')
        with self.lock:
            for key in list(self.records):
                if self.records[key]['status'] == 'running':
                    self.cancel(key)
            key = uuid.uuid4().hex
            record = {'id': key, 'source': source, 'status': 'running', 'result': None, 'error': None}
            self.records[key] = record
            record['future'] = self.executor.submit(self._run, record)
            return self.public(record)

    def _run(self, record):
        from .app.recognition import track_mask
        try:
            with Image.open(self.store.asset_path(record['source'])) as image:
                image.load()
                result = track_mask(image, self.model)
            with self.lock:
                if record['status'] != 'running':
                    return
                record['result'] = self.store.put_pixels(result.convert('L'), 'mask')
                record['status'] = 'succeeded'
        except Exception:
            with self.lock:
                if record['status'] == 'running':
                    record['status'] = 'failed'
                    record['error'] = '识别失败，请重试；原始图片与已有修正仍保留'

    def get(self, key):
        with self.lock:
            if key not in self.records:
                raise FileNotFoundError('识别任务不存在')
            return self.public(self.records[key])

    def latest(self, source):
        with self.lock:
            for record in reversed(list(self.records.values())):
                if record['source'] == source:
                    return self.public(record)
        return None

    def cancel(self, key):
        with self.lock:
            self.get(key)
            record = self.records[key]
            if record['status'] == 'running':
                record['status'] = 'cancelled'
                record['future'].cancel()
            return self.public(record)

    def close(self):
        with self.lock:
            for key in self.records:
                self.cancel(key)
        self.executor.shutdown(wait=False, cancel_futures=True)


class FileResult:
    def __init__(self, path, mime=None):
        self.path = Path(path)
        self.mime = mime or mimetypes.guess_type(str(path))[0] or 'application/octet-stream'


class Runtime:
    def __init__(self, root: Path, data: Path):
        from .app.storage import Store
        from .app.charts import Charts
        from .app.filter_presets import Presets
        from .app.text_presets import TextPresets
        from .app.stickers import StickerLibrary
        self.frontend = root / 'frontend/dist'
        self.store = Store(data)
        self.charts, self.presets, self.text_presets = Charts(self.store), Presets(self.store), TextPresets(self.store)
        self.stickers = StickerLibrary(root / 'Logos')
        self.jobs = ThreadJobs(self.store, root / 'models/u2netp.onnx')
        self.token = secrets.token_urlsafe(32)

    @staticmethod
    def mask(store, raw, size):
        if len(raw) > 32_000_000:
            raise ValueError('蒙版文件过大')
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            if image.size != size:
                raise ValueError('蒙版与画布或轨道尺寸不匹配')
            return store.put_pixels(image.convert('L'), 'mask')

    def route(self, method, path, body=None, upload=None):
        from .app.schema import SaveRequest, Title, ChartRecipe
        from .app.filter_presets import SavePreset
        from .app.text_presets import SaveTextPreset
        from .app.text_outline import text_outline
        if method == 'GET':
            if path == '/api/health':
                return {'application': 'adofai-cover-editor', 'ready': True, 'platform': 'android'}
            if path == '/api/session': return {'token': self.token}
            if path == '/api/project': return self.store.load()
            if path == '/api/fonts': return self.store.list_fonts()
            if path == '/api/stickers': return self.stickers.list()
            if path == '/api/filter-presets': return self.presets.list()
            if path == '/api/text-presets': return self.text_presets.list()
            if match := re.fullmatch('/api/assets/([a-f0-9]{32})', path):
                return FileResult(self.store.asset_path(match[1]), 'image/png')
            if match := re.fullmatch('/api/fonts/([a-f0-9]{32})', path):
                return FileResult(self.store.font_info(match[1])['path'])
            if match := re.fullmatch('/api/charts/([a-f0-9]{32})', path):
                return self.charts.info(match[1])
            if match := re.fullmatch('/api/(filter|text)-presets/([a-f0-9]{32})', path):
                return (self.presets if match[1] == 'filter' else self.text_presets).get(match[2])
            if match := re.fullmatch(r'/api/stickers/([a-f0-9]{32})/frames/(\d+)', path):
                return self.stickers.png(match[1], int(match[2])), 'image/png'
            if match := re.fullmatch('/api/jobs/active/([a-f0-9]{32})', path):
                self.store.asset_info(match[1])
                return {'job': self.jobs.latest(match[1])}
            if match := re.fullmatch('/api/jobs/([a-f0-9]{32})', path):
                return self.jobs.get(match[1])
            if not path.startswith('/api/'):
                target = (self.frontend / unquote(path).lstrip('/')).resolve()
                if not target.is_relative_to(self.frontend.resolve()):
                    raise ValueError('资源路径无效')
                if target.is_dir(): target = target / 'index.html'
                if target.is_file(): return FileResult(target)
        if method == 'PUT' and path == '/api/project':
            request = SaveRequest.model_validate(body)
            return self.store.save(request.baseRevision, request.project)
        if method == 'POST':
            if path == '/api/assets':
                self.limit_upload(upload, 10_000_000, '图片不能超过 10 MB')
                return self.store.put_image(upload[1])
            if path == '/api/fonts':
                self.limit_upload(upload, 50_000_000, '字体不能超过 50 MB')
                return self.store.put_font(upload[1])
            if path == '/api/charts':
                self.limit_upload(upload, 10_000_000, '谱面不能超过 10 MB')
                return self.charts.import_file(upload[1], upload[0])
            if path in ('/api/filter-presets', '/api/text-presets'):
                return self.presets.save(SavePreset.model_validate(body)) if path == '/api/filter-presets' else self.text_presets.save(SaveTextPreset.model_validate(body))
            if path in ('/api/filter-presets/import', '/api/text-presets/import'):
                self.limit_upload(upload, 100_000_000, '预设不能超过 100 MB')
                return (self.presets if '/filter-' in path else self.text_presets).import_file(upload[1])
            if match := re.fullmatch('/api/(filter|text)-presets/([a-f0-9]{32})/prepare', path):
                return (self.presets if match[1] == 'filter' else self.text_presets).prepare(match[2])
            if match := re.fullmatch('/api/charts/([a-f0-9]{32})/editor', path):
                recipe = ChartRecipe.model_validate(body) if body else None
                if recipe and recipe.sourceId != match[1]: raise ValueError('谱面参数不匹配')
                return {'html': self.charts.editor(match[1], recipe)}
            if path == '/api/charts/render': return self.charts.render(ChartRecipe.model_validate(body))
            if path == '/api/text-outline':
                title = Title.model_validate(body)
                return text_outline(title.text, title.fontId, self.store, self.frontend)
            if match := re.fullmatch('/api/stickers/([a-f0-9]{32})/import', path):
                if not isinstance(body, dict) or set(body) - {'frame'} or type(body.get('frame', 0)) is not int:
                    raise ValueError('贴纸帧参数无效')
                item = self.stickers.item(match[1])
                frame = body.get('frame', 0)
                return {'asset': self.store.put_pixels(self.stickers.frame(match[1], frame), 'image'),
                        'name': item['name'], 'presetId': match[1], 'frame': frame}
            if match := re.fullmatch('/api/masks/([a-f0-9]{32})', path):
                self.limit_upload(upload, 32_000_000, '蒙版文件过大')
                info = self.store.asset_info(match[1])
                return self.mask(self.store, upload[1], (info['width'], info['height']))
            if match := re.fullmatch('/api/filter-masks/(16-9|4-3)', path):
                self.limit_upload(upload, 32_000_000, '蒙版文件过大')
                return self.mask(self.store, upload[1], (1920 if match[1] == '16-9' else 1440, 1080))
            if path == '/api/jobs':
                if not isinstance(body, dict) or set(body) != {'source'}: raise ValueError('识别参数无效')
                return self.jobs.start(body['source'])
            if match := re.fullmatch('/api/jobs/([a-f0-9]{32})/cancel', path): return self.jobs.cancel(match[1])
            if path == '/api/shutdown': return {'stopping': True}
        raise FileNotFoundError('请求的内容不存在')

    @staticmethod
    def limit_upload(upload, limit, message):
        if upload is None: raise ValueError('请选择文件')
        if len(upload[1]) > limit: raise PayloadTooLarge(message)


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *_args):
        pass  # Do not log user filenames, content or session tokens.

    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def reject_session(self):
        # Closing a socket with unread POST bytes can reset the connection before
        # the caller receives the 403. Drain bounded bytes without parsing them.
        self.close_connection = True
        try:
            remaining = int(self.headers.get('Content-Length', '0'))
            if 0 <= remaining <= 101_000_000:
                while remaining:
                    chunk = self.rfile.read(min(remaining, 65536))
                    if not chunk: break
                    remaining -= len(chunk)
        except (OSError, ValueError):
            pass
        return self.respond(403, {'detail': '请求会话无效或不是本机访问'})

    def do_GET(self): self.handle_request('GET')
    def do_HEAD(self): self.handle_request('HEAD')
    def do_POST(self): self.handle_request('POST')
    def do_PUT(self): self.handle_request('PUT')

    def respond(self, status, content, mime='application/json'):
        if isinstance(content, FileResult):
            size, mime = content.path.stat().st_size, content.mime
        else:
            if mime == 'application/json': content = json.dumps(content, ensure_ascii=False, allow_nan=False).encode('utf-8')
            size = len(content)
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(size))
        if self.close_connection: self.send_header('Connection', 'close')
        self.send_header('Cache-Control', 'no-store' if mime == 'application/json' else 'private, max-age=3600')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        if self.command == 'HEAD': return
        if isinstance(content, FileResult):
            with content.path.open('rb') as stream:
                while chunk := stream.read(65536): self.wfile.write(chunk)
        else: self.wfile.write(content)

    def handle_request(self, method):
        from .app.storage import ConflictError
        runtime = self.server.runtime
        expected = f'127.0.0.1:{self.server.server_port}'
        try:
            if self.headers.get('Host') != expected or self.client_address[0] != '127.0.0.1':
                return self.reject_session()
            body, upload = None, None
            if method not in ('GET', 'HEAD'):
                self.close_connection = True
                if self.headers.get('Origin', 'http://' + expected) != 'http://' + expected or not secrets.compare_digest(self.headers.get('x-editor-token', ''), runtime.token):
                    return self.reject_session()
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 <= length <= 101_000_000:
                    return self.respond(413, {'detail': '文件过大'})
                raw = self.rfile.read(length)
                if len(raw) != length: raise ValueError('文件未完整读取，请重试')
                content_type = self.headers.get('Content-Type', '')
                if content_type.startswith('multipart/form-data'):
                    message = BytesParser(policy=email_policy).parsebytes(('Content-Type: ' + content_type + '\r\nMIME-Version: 1.0\r\n\r\n').encode() + raw)
                    parts = list(message.iter_parts()) if message.is_multipart() else []
                    files = [part for part in parts if part.get_param('name', header='content-disposition') == 'file']
                    if len(files) != 1: raise ValueError('请选择一个有效文件')
                    upload = (files[0].get_filename() or '', files[0].get_payload(decode=True))
                elif raw:
                    body = json.loads(raw)
            result = runtime.route('GET' if method == 'HEAD' else method, urlsplit(self.path).path, body, upload)
            if isinstance(result, tuple): self.respond(200, *result)
            else: self.respond(200, result)
        except ConflictError as error: self.respond(409, {'detail': str(error)})
        except PayloadTooLarge as error: self.respond(413, {'detail': str(error)})
        except FileNotFoundError as error: self.respond(404, {'detail': str(error)})
        except (ValueError, TypeError) as error: self.respond(400, {'detail': str(error)})
        except (sqlite3.Error, OSError): self.respond(503, {'detail': '本机读写失败，当前作品仍保留，请重试'})


_server = None


def start(root: str, data: str) -> int:
    global _server
    if _server is not None: return _server.server_port
    sys._MEIPASS = str(Path(root).resolve())
    runtime = Runtime(Path(root), Path(data))
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    server.runtime = runtime
    _server = server
    threading.Thread(target=server.serve_forever, name='offline-editor', daemon=True).start()
    return server.server_port


def stop():
    global _server
    if _server:
        _server.runtime.jobs.close()
        _server.shutdown()
        _server.server_close()
        _server = None
