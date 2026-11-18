from __future__ import annotations

from typing import Literal,Annotated
from .validation import BaseModel, ConfigDict, Field, model_validator
from .filter_schema import FilterSpec

TitleId=Literal['title1','title2','title3','title4','title5']
ExtraTitleId=Literal['title3','title4','title5']
ExtraTrackId=Literal['track2','track3','track4','track5']
StickerId=Annotated[str,Field(pattern=r'^sticker_[a-f0-9]{32}$')]
ObjectId=Literal['bg','track','track2','track3','track4','track5','title1','title2','title3','title4','title5']|StickerId


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Placement(Strict):
    x: float = Field(ge=-100000, le=100000)
    y: float = Field(ge=-100000, le=100000)
    scale: float = Field(gt=0, le=10000)
    rotation: float = Field(default=0,ge=-360,le=360)


class TextPlacement(Strict):
    x: float = Field(ge=-100000, le=100000)
    y: float = Field(ge=-100000, le=100000)
    fontSize: float = Field(ge=1, le=1080)
    rotation: float = Field(default=0,ge=-360,le=360)


class Layout(Strict):
    bg: Placement
    track: Placement
    title1: TextPlacement
    title2: TextPlacement
    extraTitles: dict[ExtraTitleId, TextPlacement] = Field(default_factory=dict)
    extraTracks: dict[ExtraTrackId, Placement] = Field(default_factory=dict)
    stickers: dict[StickerId,Placement] = Field(default_factory=dict)


class Effect(Strict):
    enabled: bool = False
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    color2: str = Field(default='#62bfff', pattern=r"^#[0-9a-fA-F]{6}$")
    intensity: float = Field(ge=0, le=100)
    radius: float = Field(ge=0, le=180)
    width: float = Field(ge=0, le=80)
    direction: float = Field(ge=0, le=360)
    blend: Literal['screen','add'] = 'screen'
    followGradient: bool = False


Effects = dict[Literal['outerGlow','innerGlow','bloom','stroke','gradient','bevel','horizontalBlur'], Effect]


class Shadow(Strict):
    enabled: bool = False
    color: str = Field(default='#000000',pattern=r'^#[0-9a-fA-F]{6}$')
    opacity: float = Field(default=55,ge=0,le=100)
    blur: float = Field(default=18,ge=0,le=180)
    distance: float = Field(default=20,ge=0,le=500)
    direction: float = Field(default=135,ge=0,le=360)


class Text3D(Strict):
    enabled: bool = False
    depth: float = Field(default=18,ge=0,le=200)
    bevel: float = Field(default=1,ge=0,le=10)
    rotationX: float = Field(default=12,ge=-180,le=180)
    rotationY: float = Field(default=-18,ge=-180,le=180)
    rotationZ: float = Field(default=0,ge=-180,le=180)
    perspective: float = Field(default=30,ge=0,le=100)
    sideColor: str = Field(default='#657080',pattern=r'^#[0-9a-fA-F]{6}$')
    lightDirection: float = Field(default=-35,ge=-180,le=180)
    lightElevation: float = Field(default=45,ge=-90,le=90)
    lightIntensity: float = Field(default=2,ge=0,le=8)
    ambientIntensity: float = Field(default=.7,ge=0,le=3)


class Title(Strict):
    text: str = Field(max_length=300)
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    glow: float = Field(ge=0, le=100)
    effects: Effects | None = None
    fontId: str = Field(default='system',pattern=r'^(system|noto-sans-sc|noto-serif-sc|inter|noto-serif|bebas-neue|russo-one|space-mono(?:-italic|-bold|-bold-italic)?|[a-f0-9]{32})$')
    shadow: Shadow | None = None
    text3d: Text3D | None = None


class Fusion(Strict):
    enabled: bool = True
    maskAsset: str | None = Field(default=None,pattern=r'^[a-f0-9]{32}$')
    mode: Literal['normal','multiply','screen','overlay','soft-light','add'] = 'normal'
    opacity: float = Field(default=100,ge=0,le=100)


class GradientFusion(Strict):
    kind: Literal['gradient']
    enabled: bool = True
    maskAsset: str | None = Field(default=None,pattern=r'^[a-f0-9]{32}$')
    position: float = Field(default=50,ge=0,le=100)
    width: float = Field(default=50,ge=1,le=200)
    angle: float = Field(default=0,ge=-180,le=180)
    reverse: bool = False


class ChartRecipe(Strict):
    sourceId: str = Field(pattern=r'^[a-f0-9]{32}$')
    start: int = Field(ge=0,le=20000)
    end: int = Field(ge=0,le=20000)
    style: Literal['gold','chart'] = 'gold'
    aspect: Literal['16:9','4:3','tight'] = 'tight'
    resolution: Literal[1920,2560,3840,4096] = 3840
    margin: int = Field(default=5,ge=2,le=20)
    icons: bool = True
    rotate: bool = True
    labels: bool = False
    crop: tuple[float,float,float,float] | None = None

    @model_validator(mode='after')
    def valid_range(self):
        if self.end<self.start:raise ValueError('结束砖块不能小于起始砖块')
        if self.crop and (self.crop[2]<=self.crop[0] or self.crop[3]<=self.crop[1] or any(abs(v)>100000 for v in self.crop)):
            raise ValueError('裁切范围无效')
        return self


class Track(Strict):
    trackAsset: str | None = None
    maskAsset: str | None = None
    baseMaskAsset: str | None = None
    removeBackground: bool = False
    trackColor: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    trackGlow: float = Field(ge=0, le=100)
    trackEffects: Effects | None = None
    trackShadow: Shadow | None = None
    fusion: GradientFusion | Fusion | None = None
    generatedTrack: ChartRecipe | None = Field(default=None,exclude_if=lambda value:value is None)


class Sticker(Strict):
    asset: str = Field(pattern=r'^[a-f0-9]{32}$')
    name: str = Field(max_length=300)
    presetId: str = Field(pattern=r'^[a-f0-9]{32}$')
    frame: int = Field(ge=0)
    shadow: Shadow | None = None


class Project(Track):
    schemaVersion: Literal[1] = 1
    name: str = Field(max_length=120)
    activeRatio: Literal["16:9", "4:3"]
    bgAsset: str | None = None
    titles: list[Title] = Field(min_length=2, max_length=5)
    layouts: dict[Literal["16:9", "4:3"], Layout | None]
    extraTracks: dict[ExtraTrackId,Track] = Field(default_factory=dict)
    stickers: dict[StickerId,Sticker] = Field(default_factory=dict)
    filters: list[FilterSpec] = Field(default_factory=list)
    layerOrder: list[ObjectId] = Field(default_factory=lambda:['title2','title1','track','bg'],min_length=1)

    @model_validator(mode='after')
    def validate_objects(self):
        if len(set(self.layerOrder))!=len(self.layerOrder) or self.layerOrder[-1]!='bg' or self.layerOrder.count('bg')!=1:
            raise ValueError('对象不能重复，底图必须固定在最底层')
        title_ids={f'title{i+1}' for i in range(len(self.titles))}
        track_ids={'track',*self.extraTracks}
        if any(value not in title_ids|track_ids|set(self.stickers)|{'bg'} for value in self.layerOrder):
            raise ValueError('对象数据缺失')
        if set(self.layouts)!={'16:9','4:3'} or self.layouts[self.activeRatio] is None:
            raise ValueError('当前画布布局不存在')
        for value in self.layouts.values():
            if value is not None and (set(value.extraTitles)!=title_ids-{'title1','title2'} or set(value.extraTracks)!=set(self.extraTracks)):
                raise ValueError('新增对象布局不完整')
            if value is not None and set(value.stickers)!=set(self.stickers):raise ValueError('贴纸布局不完整')
        if set(self.stickers)!={key for key in self.layerOrder if key.startswith('sticker_')}:raise ValueError('贴纸层序不完整')
        if len({item.id for item in self.filters})!=len(self.filters):raise ValueError('滤镜编号重复')
        available=title_ids|track_ids|set(self.stickers)|{'bg','canvas'}
        for item in self.filters:
            if len(set(item.targets))!=len(item.targets) or set(item.targets)-available:raise ValueError('滤镜目标不存在或重复')
            if 'canvas' in item.targets and len(item.targets)!=1:raise ValueError('整画布滤镜不能同时指定其他对象')
        return self


class SaveRequest(Strict):
    baseRevision: int = Field(ge=0)
    project: Project


def default_project() -> dict:
    return {
        "schemaVersion": 1, "name": "未命名封面", "activeRatio": "16:9",
        "bgAsset": None, "trackAsset": None, "maskAsset": None, "baseMaskAsset": None,
        "removeBackground": False, "trackColor": None, "trackGlow": 0, "trackEffects": None,"trackShadow":None,"fusion":None,
        "extraTracks": {}, "stickers":{}, "filters":[], "layerOrder": ['title2','title1','track','bg'],
        "titles": [{"text": "", "color": "#ffffff", "glow": 0, "effects": None,"fontId":"system","shadow":None,"text3d":None},
                   {"text": "", "color": "#69dcff", "glow": 0, "effects": None,"fontId":"system","shadow":None,"text3d":None}],
        "layouts": {"16:9": {
            "bg": {"x": 960, "y": 540, "scale": 1,"rotation":0},
            "track": {"x": 1200, "y": 540, "scale": 1,"rotation":0},
            "title1": {"x": 160, "y": 400, "fontSize": 120,"rotation":0},
            "title2": {"x": 160, "y": 570, "fontSize": 72,"rotation":0},"extraTitles":{},"extraTracks":{},"stickers":{}}, "4:3": None},
    }
