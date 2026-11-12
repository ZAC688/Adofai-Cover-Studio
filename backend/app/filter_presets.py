"""Portable, self-contained presets; no source images or object identities are exported."""
import base64
import hashlib
import io
import json
import re
import uuid
from copy import deepcopy
from typing import Literal
from PIL import Image
from pydantic import BaseModel,ConfigDict,Field,ValidationError
from .filter_schema import FilterSpec,CATALOG

MAX_PRESET_BYTES=100_000_000

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)

class SavePreset(Strict):
    name:str=Field(min_length=1,max_length=120)
    filters:list[FilterSpec]=Field(min_length=1,max_length=100)

class EmbeddedImage(Strict):
    kind:Literal['image','mask']
    sha256:str=Field(pattern=r'^[a-f0-9]{64}$')
    png:str=Field(max_length=44_000_000)

class PresetFile(SavePreset):
    format:Literal['adofai-filter-preset']='adofai-filter-preset'
    schemaVersion:Literal[1]=1
    assets:dict[str,EmbeddedImage]=Field(default_factory=dict)

def references(filters):
    refs={}
    for item in filters:
        for field in CATALOG[item['type']]['fields']:
            if field['type']=='texture' and item['params'].get(field['key']):refs.setdefault(item['params'][field['key']],[]).append(('image',None))
        for ratio,region in item['regions'].items():
            if region.get('maskAsset'):refs.setdefault(region['maskAsset'],[]).append(('mask',(1920 if ratio=='16:9' else 1440,1080)))
    return refs

def validate_file(raw):
    try:
        file=PresetFile.model_validate(raw).model_dump()
        file['name']=file['name'].strip()
        if not file['name']:raise ValueError('请填写预设名称')
        if len({f['id'] for f in file['filters']})!=len(file['filters']):raise ValueError('预设滤镜编号重复')
        if any(f['targets']!=['track'] for f in file['filters']):raise ValueError('预设目标格式无效')
        refs=references(file['filters'])
        if set(refs)!=set(file['assets']):raise ValueError('预设贴图或蒙版不完整')
        decoded={}
        for key,item in file['assets'].items():
            if not re.fullmatch('[a-f0-9]{32}',key):raise ValueError('预设素材编号无效')
            data=base64.b64decode(item['png'],validate=True)
            if len(data)>32_000_000 or hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('预设素材校验失败')
            with Image.open(io.BytesIO(data)) as image:
                if image.format!='PNG':raise ValueError('预设素材应为 PNG')
                image.load()
                if any(kind!=item['kind'] or size and image.size!=size for kind,size in refs[key]):raise ValueError('预设蒙版尺寸或素材类型不匹配')
                if item['kind']=='mask' and image.mode!='L':raise ValueError('预设蒙版格式无效')
                decoded[key]=image.copy()
        return file,decoded
    except (ValidationError,ValueError,OSError,Image.DecompressionBombError) as error:
        raise ValueError('无法读取滤镜预设：'+str(error)) from error

class Presets:
    def __init__(self,store):self.store=store
    def list(self):
        with self.store.connect() as db:
            return [{'id':row[0],'name':row[1],'count':len(json.loads(row[2])['filters'])} for row in db.execute('SELECT id,name,document FROM filter_presets ORDER BY rowid')]
    def get(self,key):
        if not re.fullmatch('[a-f0-9]{32}',key):raise ValueError('预设编号无效')
        with self.store.connect() as db:row=db.execute('SELECT document FROM filter_presets WHERE id=?',(key,)).fetchone()
        if row is None:raise FileNotFoundError('滤镜预设不存在')
        return json.loads(row[0])
    def put(self,file):
        file,_=validate_file(file);key=uuid.uuid4().hex
        payload=json.dumps(file,ensure_ascii=False,allow_nan=False)
        if len(payload.encode('utf-8'))>MAX_PRESET_BYTES:raise ValueError('滤镜预设不能超过 100 MB')
        with self.store.connect() as db:db.execute('INSERT INTO filter_presets VALUES(?,?,?)',(key,file['name'],payload))
        return {'id':key,'name':file['name'],'count':len(file['filters'])}
    def save(self,body):
        filters=[f.model_dump() for f in body.filters]
        for item in filters:item['targets']=['track']
        embedded={}
        for key in references(filters):
            info=self.store.asset_info(key);data=self.store.asset_path(key).read_bytes()
            embedded[key]={'kind':info['kind'],'sha256':hashlib.sha256(data).hexdigest(),'png':base64.b64encode(data).decode('ascii')}
        return self.put({'name':body.name,'filters':filters,'assets':embedded})
    def import_file(self,data):
        if len(data)>MAX_PRESET_BYTES:raise ValueError('滤镜预设不能超过 100 MB')
        try:raw=json.loads(data.decode('utf-8-sig'))
        except (UnicodeError,json.JSONDecodeError) as error:raise ValueError('无法读取滤镜预设文件') from error
        if not isinstance(raw,dict) or raw.get('format')!='adofai-filter-preset' or raw.get('schemaVersion')!=1:raise ValueError('滤镜预设格式或版本不支持')
        return self.put(raw)
    def prepare(self,key):
        file,images=validate_file(self.get(key));assets={}
        # Validate every resource before writing any files; applying changes the project only in the editor's undoable commit.
        for old,image in images.items():assets[old]=self.store.put_pixels(image,file['assets'][old]['kind'])
        filters=deepcopy(file['filters'])
        for item in filters:
            item['id']=uuid.uuid4().hex
            for field in CATALOG[item['type']]['fields']:
                if field['type']=='texture' and item['params'].get(field['key']):item['params'][field['key']]=assets[item['params'][field['key']]]['id']
            for region in item['regions'].values():
                if region.get('maskAsset'):region['maskAsset']=assets[region['maskAsset']]['id']
        return {'filters':filters,'assets':list(assets.values())}
