"""Persistent local chart sources and static rendering; no media/event execution."""
from functools import lru_cache
import hashlib
import html
import io
import json
import math
import os
import re
from pathlib import Path
import threading
import uuid

from PIL import Image

from .schema import ChartRecipe
from .chart_style import reference_icon,stone_data_url,TEXTURE_UNITS,GOLD_EDGE
from experiments.static_track_probe import build_track,decode_angles,read_chart
from experiments.p0 import resource_root
from experiments.static_track_editor import browser_chart,rounded
from experiments.static_track_export import render_selection,selection_scene

MAX_CHART_BYTES=10_000_000
RENDER_LOCK=threading.Lock()


@lru_cache(maxsize=8)
def loaded_chart(path,sha):
    source=Path(path)
    if hashlib.sha256(source.read_bytes()).hexdigest()!=sha:raise ValueError('源谱面校验失败，请重新导入')
    return read_chart(source)


@lru_cache(maxsize=8)
def loaded_track(path,sha):
    return build_track(loaded_chart(path,sha))


def metadata_text(value):
    if not isinstance(value,str):return ''
    value=re.sub(r'<[^>]*>','',html.unescape(value))
    value=re.sub(r'[\x00-\x1f\x7f]+',' ',value)
    return re.sub(r'\s+',' ',value).strip()[:300]


class Charts:
    def __init__(self,store):self.store=store

    def path(self,source_id):
        import re
        if not re.fullmatch('[a-f0-9]{32}',source_id):raise ValueError('谱面编号无效')
        path=self.store.directory/'charts'/f'{source_id}.adofai'
        if not path.is_file():raise FileNotFoundError('源谱面缺失，请恢复本机数据目录')
        return path

    def info(self,source_id):
        self.path(source_id)
        with self.store.connect() as db:row=db.execute('SELECT name,sha256,tile_count FROM charts WHERE id=?',(source_id,)).fetchone()
        if not row:raise FileNotFoundError('谱面记录缺失')
        settings=loaded_chart(str(self.path(source_id)),row[1]).get('settings',{})
        return {'id':source_id,'name':row[0],'sha256':row[1],'tileCount':row[2],
                'song':metadata_text(settings.get('song')),'artist':metadata_text(settings.get('artist'))}

    def import_file(self,raw,name):
        if len(raw)>MAX_CHART_BYTES:raise ValueError('谱面不能超过 10 MB')
        if not name.lower().endswith('.adofai'):raise ValueError('请选择 .adofai 谱面文件')
        source_id=uuid.uuid4().hex
        target=self.store.directory/'charts'/f'{source_id}.adofai'
        temporary=target.with_suffix('.tmp')
        try:
            with temporary.open('wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
            try:data=read_chart(temporary)
            except (UnicodeError,ValueError) as error:raise ValueError('谱面格式无法读取：'+str(error)) from error
            angles,_=decode_angles(data)
            if len(angles)>20000:raise ValueError('本版支持不超过 20000 段的谱面')
            track=build_track(data)
            if any(abs(t.x)>100000 or abs(t.y)>100000 for t in track.tiles):raise ValueError('谱面坐标超出支持范围')
            os.replace(temporary,target)
            sha=hashlib.sha256(raw).hexdigest()
            name=Path(name.replace('\\','/')).name[:300]
            with self.store.connect() as db:db.execute('INSERT INTO charts VALUES(?,?,?,?)',(source_id,name,sha,len(track.tiles)))
            return self.info(source_id)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        finally:temporary.unlink(missing_ok=True)

    def track(self,source_id):
        info=self.info(source_id)
        return loaded_track(str(self.path(source_id)),info['sha256'])

    def editor(self,source_id,recipe=None):
        info=self.info(source_id);track=self.track(source_id)
        templates={kind:reference_icon(kind) for kind in ('rabbit','turtle','midspin','checkpoint')}
        templates['twirl-cw'],templates['twirl-ccw']=reference_icon('twirl',True),reference_icon('twirl',False)
        payload=rounded({'version':1,'embedded':True,'sourceId':source_id,'fingerprint':info['sha256'],
                         'defaultStyle':'gold','defaultAspect':'tight','texture':stone_data_url(),'textureUnits':TEXTURE_UNITS,'reference':True,'goldEdge':GOLD_EDGE,'templates':templates,
                         'initialRecipe':recipe.model_dump(exclude={'sourceId'}) if recipe else None,
                         'charts':[browser_chart(track,info['name'],source_id,(0,min(79,len(track.tiles)-1)),reference=True)]})
        template=(resource_root()/'experiments/static_track_editor.html').read_text(encoding='utf-8')
        data=json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('&','\\u0026')
        return template.replace('/*__TRACK_DATA__*/',data)

    def render(self,recipe:ChartRecipe):
        track=self.track(recipe.sourceId)
        scene=selection_scene(track,recipe.start,recipe.end,reference=True)
        b=scene['bounds']
        world=recipe.crop or (b[0]-.04,b[1]-.04,b[2]+.04,b[3]+.04)
        ratio=(world[2]-world[0])/(world[3]-world[1])
        n=recipe.resolution
        if recipe.aspect=='16:9':width,height=n,round(n*9/16)
        elif recipe.aspect=='4:3':width,height=n,round(n*3/4)
        elif ratio>=1:width,height=n,max(64,round(n/ratio))
        else:width,height=max(64,round(n*ratio)),n
        target=self.store.directory/'charts'/f'{uuid.uuid4().hex}.png'
        try:
            with RENDER_LOCK:
                render_selection(track,target,start_floor=recipe.start,end_floor=recipe.end,width=width,height=height,
                    padding=max(4,round(min(width,height)*recipe.margin/100)),crop=recipe.crop,
                    rotate_icons=recipe.rotate,style=recipe.style,reference=True,show_icons=recipe.icons,labels=recipe.labels)
                with Image.open(target) as image:asset=self.store.put_pixels(image.convert('RGBA'),'image')
            return {'asset':asset,'recipe':recipe.model_dump()}
        finally:
            for extension in ('.png','.svg','.json'):target.with_suffix(extension).unlink(missing_ok=True)
