from __future__ import annotations
from functools import lru_cache
import hashlib
import io
from pathlib import Path
from PIL import Image


@lru_cache(maxsize=4)
def _catalog(directory: str):
    root=Path(directory);items={}
    if not root.is_dir():raise FileNotFoundError('预设贴纸资源缺失，请使用完整程序包')
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in {'.png','.gif'}:continue
        relative=path.relative_to(root)
        with Image.open(path) as image:
            key=hashlib.sha256(relative.as_posix().encode('utf-8')).hexdigest()[:32]
            items[key]={'id':key,'name':path.stem,'category':list(relative.parts[:-1]) or ['未分类'],'frames':getattr(image,'n_frames',1),'width':image.width,'height':image.height,'path':path}
    return items


class StickerLibrary:
    def __init__(self,directory:Path):self.directory=str(directory.resolve())
    def list(self):return [{k:v for k,v in item.items() if k!='path'} for item in _catalog(self.directory).values()]
    def item(self,key):
        item=_catalog(self.directory).get(key)
        if not item:raise FileNotFoundError('贴纸不存在')
        return item
    def frame(self,key,index:int):
        item=self.item(key)
        if index<0 or index>=item['frames']:raise ValueError('贴纸帧超出范围')
        with Image.open(item['path']) as image:
            image.seek(index)
            return image.convert('RGBA').copy()
    def png(self,key,index):
        output=io.BytesIO();self.frame(key,index).save(output,'PNG');return output.getvalue()
