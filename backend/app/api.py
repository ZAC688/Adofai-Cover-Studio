from __future__ import annotations

from contextlib import asynccontextmanager
import io
from pathlib import Path
import secrets
import sqlite3

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image

from .schema import SaveRequest,Title,ChartRecipe
from .charts import Charts,MAX_CHART_BYTES
from .text_outline import text_outline
from .filter_presets import Presets,SavePreset,MAX_PRESET_BYTES
from .text_presets import TextPresets,SaveTextPreset
from .storage import Store, ConflictError
from .jobs import Jobs
from pydantic import BaseModel
from .stickers import StickerLibrary
from experiments.p0 import resource_root


class RecognitionRequest(BaseModel):
    source: str

class StickerImport(BaseModel):
    frame: int = 0


def create_app(data_dir: Path, frontend: Path | None = None, model: Path | None = None, sticker_dir:Path|None=None) -> FastAPI:
    store = Store(data_dir)
    presets=Presets(store)
    text_presets=TextPresets(store)
    charts=Charts(store)
    session = secrets.token_urlsafe(32)
    stickers=StickerLibrary(sticker_dir or resource_root()/'Logos')

    @asynccontextmanager
    async def lifespan(app):
        yield
        if hasattr(app.state, "jobs"):
            app.state.jobs.close()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.store = store
    app.state.session = session
    app.state.jobs = Jobs(store, model)

    @app.middleware("http")
    async def local_requests_only(request: Request, call_next):
        if request.url.hostname not in {"127.0.0.1", "localhost", "testserver"}:
            return JSONResponse({"detail": "仅允许本机访问"}, status_code=403)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            expected = f"{request.url.scheme}://{request.url.netloc}"
            if (origin and origin != expected) or not secrets.compare_digest(
                    request.headers.get("x-editor-token", ""), session):
                return JSONResponse({"detail": "请求会话无效，请重新打开页面"}, status_code=403)
        try:
            return await call_next(request)
        except (sqlite3.Error, OSError):
            return JSONResponse({"detail": "本机读写失败；当前内容仍在页面中，请检查数据目录并重试"}, status_code=503)

    @app.exception_handler(ValueError)
    async def invalid_value(_request, error):
        return JSONResponse({"detail": str(error)}, status_code=400)

    @app.exception_handler(FileNotFoundError)
    async def missing_file(_request, error):
        return JSONResponse({"detail": str(error)}, status_code=404)

    @app.exception_handler(ConflictError)
    async def save_conflict(_request, error):
        return JSONResponse({"detail": str(error)}, status_code=409)

    @app.get("/api/health")
    def health():
        return {"application": "adofai-cover-editor", "ready": True,
                "instance": getattr(app.state, "instance", "development")}

    @app.get("/api/session")
    def get_session():
        response = JSONResponse({"token": session})
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/project")
    def get_project():
        return store.load()

    @app.put("/api/project")
    def save_project(body: SaveRequest):
        return store.save(body.baseRevision, body.project)

    @app.post("/api/assets")
    async def upload_asset(file: UploadFile = File(...)):
        raw = await file.read(10_000_001)
        if len(raw) > 10_000_000:
            raise HTTPException(413, "图片不能超过 10 MB")
        return store.put_image(raw)

    @app.get("/api/assets/{asset_id}")
    def get_asset(asset_id: str):
        return FileResponse(store.asset_path(asset_id), media_type="image/png")

    @app.post('/api/charts')
    async def import_chart(file:UploadFile=File(...)):
        raw=await file.read(MAX_CHART_BYTES+1)
        if len(raw)>MAX_CHART_BYTES:raise HTTPException(413,'谱面不能超过 10 MB')
        return charts.import_file(raw,file.filename or '')

    @app.get('/api/charts/{source_id}')
    def get_chart(source_id:str):return charts.info(source_id)

    @app.post('/api/charts/{source_id}/editor')
    def chart_editor(source_id:str,body:ChartRecipe|None=None):
        if body and body.sourceId!=source_id:raise ValueError('谱面参数不匹配')
        return {'html':charts.editor(source_id,body)}

    @app.post('/api/charts/render')
    def render_chart(body:ChartRecipe):
        return charts.render(body)

    @app.get('/api/filter-presets')
    def list_filter_presets():return presets.list()

    @app.post('/api/filter-presets')
    def save_filter_preset(body:SavePreset):return presets.save(body)

    @app.post('/api/filter-presets/import')
    async def import_filter_preset(file:UploadFile=File(...)):
        return presets.import_file(await file.read(MAX_PRESET_BYTES+1))

    @app.get('/api/filter-presets/{preset_id}')
    def export_filter_preset(preset_id:str):return presets.get(preset_id)

    @app.post('/api/filter-presets/{preset_id}/prepare')
    def prepare_filter_preset(preset_id:str):return presets.prepare(preset_id)

    @app.get('/api/text-presets')
    def list_text_presets():return text_presets.list()

    @app.post('/api/text-presets')
    def save_text_preset(body:SaveTextPreset):return text_presets.save(body)

    @app.post('/api/text-presets/import')
    async def import_text_preset(file:UploadFile=File(...)):
        return text_presets.import_file(await file.read(MAX_PRESET_BYTES+1))

    @app.get('/api/text-presets/{preset_id}')
    def export_text_preset(preset_id:str):return text_presets.get(preset_id)

    @app.post('/api/text-presets/{preset_id}/prepare')
    def prepare_text_preset(preset_id:str):return text_presets.prepare(preset_id)

    @app.get('/api/fonts')
    def get_fonts():
        return store.list_fonts()

    @app.post('/api/fonts')
    async def upload_font(file:UploadFile=File(...)):
        raw=await file.read(50_000_001)
        if len(raw)>50_000_000:raise HTTPException(413,'字体不能超过 50 MB')
        return store.put_font(raw)

    @app.get('/api/fonts/{font_id}')
    def get_font(font_id:str):
        info=store.font_info(font_id)
        return FileResponse(info['path'],media_type='font/'+info['extension'])

    @app.post('/api/text-outline')
    def outline(body:Title):
        return text_outline(body.text,body.fontId,store,frontend or resource_root()/'frontend/dist')

    @app.post("/api/masks/{track_id}")
    async def save_mask(track_id: str, file: UploadFile = File(...)):
        track = store.asset_info(track_id)
        raw = await file.read(32_000_001)
        if len(raw) > 32_000_000:
            raise HTTPException(413, "蒙版文件过大")
        try:
            with Image.open(io.BytesIO(raw)) as image:
                image.load()
                if image.size != (track["width"], track["height"]):
                    raise ValueError("蒙版与轨道尺寸不匹配")
                return store.put_pixels(image.convert("L"), "mask")
        except OSError as error:
            raise ValueError("无法读取蒙版") from error

    @app.get('/api/stickers')
    def sticker_catalog():return stickers.list()

    @app.get('/api/stickers/{preset_id}/frames/{frame}')
    def sticker_frame(preset_id:str,frame:int):return Response(stickers.png(preset_id,frame),media_type='image/png',headers={'Cache-Control':'public, max-age=3600'})

    @app.post('/api/stickers/{preset_id}/import')
    def import_sticker(preset_id:str,body:StickerImport):
        info=stickers.item(preset_id)
        return {'asset':store.put_pixels(stickers.frame(preset_id,body.frame),'image'),'name':info['name'],'presetId':preset_id,'frame':body.frame}

    @app.post('/api/filter-masks/{ratio}')
    async def filter_mask(ratio:str,file:UploadFile=File(...)):
        sizes={'16-9':(1920,1080),'4-3':(1440,1080)}
        if ratio not in sizes:raise ValueError('画幅无效')
        raw=await file.read(32_000_001)
        if len(raw)>32_000_000:raise HTTPException(413,'蒙版文件过大')
        try:
            with Image.open(io.BytesIO(raw)) as image:
                image.load()
                if image.size!=sizes[ratio]:raise ValueError('滤镜蒙版与画布尺寸不匹配')
                return store.put_pixels(image.convert('L'),'mask')
        except OSError as error:raise ValueError('无法读取滤镜蒙版') from error

    @app.post("/api/shutdown")
    def shutdown():
        if hasattr(app.state, "shutdown"):
            app.state.shutdown()
        return {"stopping": True}

    @app.post("/api/jobs")
    def start_job(body: RecognitionRequest):
        return app.state.jobs.start(body.source)

    @app.get("/api/jobs/active/{source_id}")
    def active_job(source_id: str):
        store.asset_info(source_id)
        return {"job": app.state.jobs.latest(source_id)}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        return app.state.jobs.get(job_id)

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str):
        return app.state.jobs.cancel(job_id)

    if frontend and frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app
