from __future__ import annotations
import json
import math
import re
from pathlib import Path
from typing import Literal
from .validation import BaseModel,ConfigDict,Field,JsonValue,model_validator
from experiments.p0 import resource_root

root=resource_root()
catalog_path=root/'frontend/public/filter-catalog.json'
if not catalog_path.is_file():catalog_path=root/'frontend/dist/filter-catalog.json'
CATALOG={entry['type']:entry for entry in json.loads(catalog_path.read_text(encoding='utf-8'))['filters']}

class Region(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    mode:Literal['all','rect','paint']='all'
    x:float=Field(default=.25,ge=0,le=1)
    y:float=Field(default=.25,ge=0,le=1)
    width:float=Field(default=.5,gt=0,le=1)
    height:float=Field(default=.5,gt=0,le=1)
    feather:float=Field(default=0,ge=0,le=180)
    maskAsset:str|None=Field(default=None,pattern=r'^[a-f0-9]{32}$')

class FilterSpec(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    id:str=Field(pattern=r'^[a-f0-9]{32}$')
    type:str
    enabled:bool=True
    targets:list[str]=Field(min_length=1)
    params:dict[str,JsonValue]
    regions:dict[Literal['16:9','4:3'],Region]=Field(default_factory=dict)

    @model_validator(mode='after')
    def valid_parameters(self):
        if self.type not in CATALOG:raise ValueError('未知滤镜')
        fields={field['key']:field for field in CATALOG[self.type]['fields']}
        if set(self.params)-set(fields):raise ValueError('未知滤镜参数')
        def finite(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and abs(value)<=10000
        def check_nested(value):
            if isinstance(value,float) and not math.isfinite(value):raise ValueError('滤镜数值无效')
            if isinstance(value,list):
                if len(value)>64:raise ValueError('滤镜数组过长')
                for part in value:check_nested(part)
            if isinstance(value,dict):
                for part in value.values():check_nested(part)
        for key,value in self.params.items():
            field=fields[key];kind=field['type'];valid=True
            if kind=='number':valid=finite(value) and field['min']<=value<=field['max'] and (field['step']<1 or value==int(value) and (value-field['min'])%field['step']==0)
            elif kind=='boolean':valid=isinstance(value,bool)
            elif kind=='color':valid=isinstance(value,str) and bool(re.fullmatch(r'#[a-fA-F0-9]{6}',value))
            elif kind=='point':valid=isinstance(value,dict) and set(value)=={'x','y'} and all(finite(part) and field['min']<=part<=field['max'] for part in value.values())
            elif kind=='texture':valid=value is None or isinstance(value,str) and bool(re.fullmatch(r'[a-f0-9]{32}',value))
            elif kind in {'select','enum'}:valid=value in field['options']
            elif kind=='array':valid=isinstance(value,list)
            if not valid:raise ValueError('滤镜参数无效：'+key)
            check_nested(value)
            if key=='matrix' and (len(value)!=9 or not all(finite(part) for part in value)):raise ValueError('卷积需要9个有效数值')
            if key=='stops':
                if len(value)<2 or any(not isinstance(stop,dict) or set(stop)!={'offset','color','alpha'} or not finite(stop['offset']) or not 0<=stop['offset']<=1 or not finite(stop['alpha']) or not 0<=stop['alpha']<=1 or not isinstance(stop['color'],(int,str)) for stop in value):raise ValueError('渐变色标无效')
            if key=='replacements' and (not value or any(not isinstance(pair,list) or len(pair)!=2 or any(not isinstance(color,(int,str)) for color in pair) for pair in value)):raise ValueError('替换色组无效')
        return self
