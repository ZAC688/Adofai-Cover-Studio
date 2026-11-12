from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager

from PIL import Image
from experiments.p0 import decode_image
from .schema import Project, default_project
from .fonts import inspect_font,BUILTIN_FONTS


class ConflictError(Exception):
    pass


class Store:
    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        (directory / "assets").mkdir(exist_ok=True)
        (directory / "fonts").mkdir(exist_ok=True)
        (directory / "charts").mkdir(exist_ok=True)
        self.lock = threading.RLock()
        self.database = directory / "project.sqlite3"
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS assets (id TEXT PRIMARY KEY, width INT, height INT, kind TEXT, sha256 TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS fonts (id TEXT PRIMARY KEY,label TEXT,extension TEXT,sha256 TEXT)")
            db.execute('CREATE TABLE IF NOT EXISTS charts (id TEXT PRIMARY KEY,name TEXT NOT NULL,sha256 TEXT NOT NULL,tile_count INT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS filter_presets (id TEXT PRIMARY KEY,name TEXT NOT NULL,document TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS text_presets (id TEXT PRIMARY KEY,name TEXT NOT NULL,document TEXT NOT NULL)')
            db.execute("CREATE TABLE IF NOT EXISTS project (id INT PRIMARY KEY, revision INT NOT NULL, document TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO project VALUES(1,0,?)", (json.dumps(default_project()),))

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.database, timeout=15)
        connection.execute("PRAGMA synchronous=FULL")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def asset_path(self, asset_id: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{32}", asset_id):
            raise ValueError("Invalid asset ID")
        path = self.directory / "assets" / f"{asset_id}.png"
        if not path.is_file():
            raise FileNotFoundError("素材文件缺失，请保留数据目录并重试")
        return path

    def asset_info(self, asset_id: str) -> dict:
        self.asset_path(asset_id)
        with self.connect() as db:
            row = db.execute("SELECT width,height,kind FROM assets WHERE id=?", (asset_id,)).fetchone()
        if not row:
            raise FileNotFoundError("素材索引缺失")
        return {"id": asset_id, "width": row[0], "height": row[1], "kind": row[2]}

    def put_image(self, raw: bytes) -> dict:
        image = decode_image(raw)
        return self.put_pixels(image, "image", raw)

    def put_pixels(self, image: Image.Image, kind: str, original: bytes | None = None) -> dict:
        asset_id = uuid.uuid4().hex
        target = self.directory / "assets" / f"{asset_id}.png"
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        payload = buffer.getvalue()
        temporary = target.with_suffix(".tmp")
        try:
            with temporary.open("wb") as file:
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, target)
            if original is not None:
                with target.with_suffix(".original").open("wb") as file:
                    file.write(original)
                    file.flush()
                    os.fsync(file.fileno())
            with self.connect() as db:
                db.execute("INSERT INTO assets VALUES(?,?,?,?,?)", (
                    asset_id, image.width, image.height, kind, hashlib.sha256(payload).hexdigest()))
        finally:
            temporary.unlink(missing_ok=True)
        return {"id": asset_id, "width": image.width, "height": image.height, "kind": kind}

    def validate_references(self, document: dict) -> dict:
        assets = {}
        for title in document['titles']:
            if title.get('fontId','system') not in BUILTIN_FONTS:self.font_info(title['fontId'])
        if document.get('bgAsset'):assets[document['bgAsset']]=self.asset_info(document['bgAsset'])
        for item in document.get('stickers',{}).values():assets[item['asset']]=self.asset_info(item['asset'])
        for item in document.get('filters',[]):
            from .filter_schema import CATALOG
            for field in CATALOG[item['type']]['fields']:
                asset_id=item['params'].get(field['key']) if field['type']=='texture' else None
                if asset_id:assets[asset_id]=self.asset_info(asset_id)
            for ratio,region in item['regions'].items():
                if region.get('maskAsset'):
                    info=self.asset_info(region['maskAsset']);assets[info['id']]=info
                    if info['kind']!='mask' or (info['width'],info['height'])!=(1920 if ratio=='16:9' else 1440,1080):raise ValueError('滤镜蒙版与画布尺寸不匹配')
        for item in [document,*document.get('extraTracks',{}).values()]:
            recipe=item.get('generatedTrack')
            if recipe:
                from .charts import Charts
                info=Charts(self).info(recipe['sourceId'])
                if recipe['end']>=info['tileCount']:raise ValueError('选段超出源谱面')
                if not item.get('trackAsset'):raise ValueError('生成轨道素材缺失')
            for key in ("trackAsset", "maskAsset", "baseMaskAsset"):
                asset_id = item.get(key)
                if asset_id:assets[asset_id] = self.asset_info(asset_id)
            fusion_mask=(item.get('fusion') or {}).get('maskAsset')
            if fusion_mask:assets[fusion_mask]=self.asset_info(fusion_mask)
            if item.get("removeBackground") and not item.get("maskAsset"):
                raise ValueError("去背景结果尚未生成")
            track = assets.get(item.get("trackAsset"))
            for key in ("maskAsset", "baseMaskAsset"):
                if item.get(key):
                    mask = assets[item[key]]
                    if not track or mask["kind"] != "mask" or (mask["width"], mask["height"]) != (track["width"], track["height"]):
                        raise ValueError("蒙版与轨道尺寸不匹配")
            if fusion_mask:
                mask=assets[fusion_mask]
                if not track or mask['kind']!='mask' or (mask['width'],mask['height'])!=(track['width'],track['height']):raise ValueError('融合蒙版与轨道尺寸不匹配')
        if set(document["layouts"]) != {"16:9", "4:3"} or not document["layouts"][document["activeRatio"]]:
            raise ValueError("当前画布布局不存在")
        return assets

    def list_fonts(self)->list[dict]:
        with self.connect() as db:
            return [{'id':row[0],'label':row[1],'extension':row[2]} for row in db.execute('SELECT id,label,extension FROM fonts ORDER BY label,id')]

    def font_info(self,font_id:str)->dict:
        if not re.fullmatch('[a-f0-9]{32}',font_id):raise ValueError('字体编号无效')
        with self.connect() as db:row=db.execute('SELECT label,extension FROM fonts WHERE id=?',(font_id,)).fetchone()
        if not row:raise FileNotFoundError('上传字体不存在，请保留字体数据目录')
        path=self.directory/'fonts'/f'{font_id}.{row[1]}'
        if not path.is_file():raise FileNotFoundError('字体文件缺失，请恢复原字体数据')
        return {'id':font_id,'label':row[0],'extension':row[1],'path':path}

    def put_font(self,raw:bytes)->dict:
        extension,label=inspect_font(raw);font_id=uuid.uuid4().hex
        target=self.directory/'fonts'/f'{font_id}.{extension}'
        temporary=target.with_suffix('.tmp')
        try:
            with temporary.open('wb') as file:file.write(raw);file.flush();os.fsync(file.fileno())
            os.replace(temporary,target)
            with self.connect() as db:db.execute('INSERT INTO fonts VALUES(?,?,?,?)',(font_id,label,extension,hashlib.sha256(raw).hexdigest()))
        finally:temporary.unlink(missing_ok=True)
        return {'id':font_id,'label':label,'extension':extension}

    def load(self) -> dict:
        with self.lock, self.connect() as db:
            revision, raw = db.execute("SELECT revision,document FROM project WHERE id=1").fetchone()
        document = Project.model_validate_json(raw).model_dump()
        return {"revision": revision, "project": document, "assets": self.validate_references(document)}

    def save(self, base_revision: int, project: Project) -> dict:
        document = project.model_dump()
        assets = self.validate_references(document)
        payload = json.dumps(document, ensure_ascii=False, allow_nan=False)
        with self.lock, self.connect() as db:
            cursor = db.execute("UPDATE project SET revision=revision+1,document=? WHERE id=1 AND revision=?", (payload, base_revision))
            if cursor.rowcount != 1:
                raise ConflictError("作品已被另一个窗口修改；当前修改仍在页面中，请先保留再重新打开")
        return {"revision": base_revision + 1, "project": document, "assets": assets}
