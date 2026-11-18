"""Portable text styles, deliberately excluding content and object placement."""
import base64
from copy import deepcopy
import hashlib
import json
import re
import uuid
from typing import Annotated,Literal

from .validation import Field,ValidationError,model_validator

from .schema import Strict,Title,Effects,Shadow,Text3D
from .filter_schema import FilterSpec,CATALOG
from .filter_presets import EmbeddedImage,MAX_PRESET_BYTES,references,validate_file as validate_filters
from .fonts import BUILTIN_FONTS,inspect_font

Ratio=Literal['16:9','4:3']
FontSize=Annotated[float,Field(ge=1,le=1080)]


class TextStyle(Strict):
    color:str
    glow:float
    effects:Effects|None=None
    fontId:str='system'
    shadow:Shadow|None=None
    text3d:Text3D|None=None

    @model_validator(mode='after')
    def valid_title_attributes(self):
        Title.model_validate({'text':'',**self.model_dump()})
        return self


class SaveTextPreset(Strict):
    name:str=Field(min_length=1,max_length=120)
    style:TextStyle
    fontSize:FontSize
    fontSizes:dict[Ratio,FontSize]=Field(default_factory=dict)
    filters:list[FilterSpec]=Field(default_factory=list,max_length=100)


class EmbeddedFont(Strict):
    sha256:str=Field(pattern=r'^[a-f0-9]{64}$')
    data:str=Field(max_length=67_000_000)


class TextPresetFile(SaveTextPreset):
    format:Literal['adofai-text-preset']='adofai-text-preset'
    schemaVersion:Literal[1]=1
    assets:dict[str,EmbeddedImage]=Field(default_factory=dict)
    font:EmbeddedFont|None=None


def validate_file(raw):
    try:
        file=TextPresetFile.model_validate(raw).model_dump()
        file['name']=file['name'].strip()
        if not file['name']:raise ValueError('请填写预设名称')
        images={}
        if file['filters']:
            _,images=validate_filters({'name':file['name'],'filters':file['filters'],'assets':file['assets']})
        elif file['assets']:raise ValueError('预设含无关素材')
        font=None
        if file['style']['fontId'] in BUILTIN_FONTS:
            if file['font'] is not None:raise ValueError('内置字体不应携带额外字体文件')
        else:
            if file['font'] is None:raise ValueError('上传字体缺失，无法完整恢复文字样式')
            font=base64.b64decode(file['font']['data'],validate=True)
            if hashlib.sha256(font).hexdigest()!=file['font']['sha256']:raise ValueError('预设字体校验失败')
            inspect_font(font)
        return file,images,font
    except (ValidationError,ValueError,OSError,TypeError) as error:
        raise ValueError('无法读取文字预设：'+str(error)) from error


class TextPresets:
    def __init__(self,store):self.store=store

    def list(self):
        with self.store.connect() as db:
            return [{'id':r[0],'name':r[1],'count':len(json.loads(r[2])['filters'])} for r in db.execute('SELECT id,name,document FROM text_presets ORDER BY rowid')]

    def get(self,key):
        if not re.fullmatch('[a-f0-9]{32}',key):raise ValueError('文字预设编号无效')
        with self.store.connect() as db:row=db.execute('SELECT document FROM text_presets WHERE id=?',(key,)).fetchone()
        if not row:raise FileNotFoundError('文字预设不存在')
        return json.loads(row[0])

    def put(self,raw):
        file,_,_=validate_file(raw)
        payload=json.dumps(file,ensure_ascii=False,allow_nan=False)
        if len(payload.encode('utf-8'))>MAX_PRESET_BYTES:raise ValueError('文字预设不能超过 100 MB')
        key=uuid.uuid4().hex
        with self.store.connect() as db:db.execute('INSERT INTO text_presets VALUES(?,?,?)',(key,file['name'],payload))
        return {'id':key,'name':file['name'],'count':len(file['filters'])}

    def save(self,body):
        file=body.model_dump()
        for item in file['filters']:item['targets']=['track']
        file['assets']={}
        for key in references(file['filters']):
            info=self.store.asset_info(key);data=self.store.asset_path(key).read_bytes()
            file['assets'][key]={'kind':info['kind'],'sha256':hashlib.sha256(data).hexdigest(),'png':base64.b64encode(data).decode('ascii')}
        font_id=file['style']['fontId']
        if font_id not in BUILTIN_FONTS:
            data=self.store.font_info(font_id)['path'].read_bytes()
            file['font']={'sha256':hashlib.sha256(data).hexdigest(),'data':base64.b64encode(data).decode('ascii')}
        return self.put(file)

    def import_file(self,data):
        if len(data)>MAX_PRESET_BYTES:raise ValueError('文字预设不能超过 100 MB')
        try:raw=json.loads(data.decode('utf-8-sig'))
        except (UnicodeError,json.JSONDecodeError) as error:raise ValueError('无法读取文字预设文件') from error
        if not isinstance(raw,dict) or raw.get('format')!='adofai-text-preset' or raw.get('schemaVersion')!=1:raise ValueError('文字预设格式或版本不支持')
        return self.put(raw)

    def prepare(self,key):
        file,images,font=validate_file(self.get(key));assets={};fonts=[]
        # Decode and validate every resource first; no project write happens here.
        for old,image in images.items():assets[old]=self.store.put_pixels(image,file['assets'][old]['kind'])
        style=deepcopy(file['style'])
        if font is not None:
            with self.store.connect() as db:row=db.execute('SELECT id FROM fonts WHERE sha256=?',(file['font']['sha256'],)).fetchone()
            info=None
            if row:
                try:info={k:v for k,v in self.store.font_info(row[0]).items() if k!='path'}
                except FileNotFoundError:pass
            info=info or self.store.put_font(font);fonts.append(info);style['fontId']=info['id']
        filters=deepcopy(file['filters'])
        for item in filters:
            item['id']=uuid.uuid4().hex
            for field in CATALOG[item['type']]['fields']:
                if field['type']=='texture' and item['params'].get(field['key']):item['params'][field['key']]=assets[item['params'][field['key']]]['id']
            for region in item['regions'].values():
                if region.get('maskAsset'):region['maskAsset']=assets[region['maskAsset']]['id']
        return {'style':style,'fontSize':file['fontSize'],'fontSizes':file['fontSizes'],'filters':filters,'assets':list(assets.values()),'fonts':fonts}
