import {useEffect,useState} from 'react';
import {api,jsonRequest} from '../services/api';
import type {Asset,Sticker} from '../domain/project';
import {compareStickers,compareCategoryStickers} from '../domain/stickerOrder';

type Preset={id:string;name:string;category:string[];frames:number;width:number;height:number};
export function StickerPicker({close,add,onError}:{close:()=>void;add:(item:Sticker,asset:Asset)=>void;onError:(message:string)=>void}){
  const [items,setItems]=useState<Preset[]>([]),[category,setCategory]=useState<string[]>([]),[selected,setSelected]=useState<Preset|null>(null),[frame,setFrame]=useState(0),[busy,setBusy]=useState(false),[failure,setFailure]=useState('');
  useEffect(()=>{let cancelled=false;void api<Preset[]>('/stickers').then(value=>{if(!cancelled)setItems([...value].sort(compareStickers));}).catch(error=>{if(!cancelled)setFailure(String(error));});return()=>{cancelled=true;};},[]);
  const groups=new Map<string,string[]>();for(const item of items)for(let depth=1;depth<=item.category.length;depth++){const value=item.category.slice(0,depth);groups.set(value.join('/'),value);}
  const shown=items.filter(item=>category.every((part,index)=>item.category[index]===part)).sort((a,b)=>compareCategoryStickers(a,b,category));
  async function confirm(){
    if(!selected)return;setBusy(true);setFailure('');
    try{const value=await api<{asset:Asset;name:string;presetId:string;frame:number}>('/stickers/'+selected.id+'/import',jsonRequest({frame},'POST'));add({...value,asset:value.asset.id,shadow:null},value.asset);close();}
    catch(error){setFailure(String(error));onError(String(error));}finally{setBusy(false);}
  }
  return <div className="modal-backdrop"><section className="modal sticker-picker" role="dialog" aria-modal="true" aria-label="选择贴纸"><div className="modal-header"><h2>预设贴纸</h2><button aria-label="关闭贴纸选择" disabled={busy} onClick={close}>×</button></div>
    <div className="sticker-browser"><nav aria-label="贴纸分类"><button aria-pressed={!category.length} onClick={()=>setCategory([])}>全部素材 <small>{items.length}</small></button>{[...groups].map(([key,value])=><button key={key} aria-label={'分类 '+value.join(' / ')} aria-pressed={category.join('/')===key} style={{paddingLeft:12+(value.length-1)*14}} onClick={()=>setCategory(value)}>{value.at(-1)}</button>)}</nav>
      <div className="sticker-grid" aria-label="贴纸素材">{shown.map(item=><button key={item.id} data-preset-id={item.id} aria-label={'选择贴纸 '+item.name} aria-pressed={selected?.id===item.id} onClick={()=>{setSelected(item);setFrame(0);}}><img loading="lazy" src={'/api/stickers/'+item.id+'/frames/0'} alt=""/><span>{item.name}</span>{item.frames>1&&<small>GIF · {item.frames} 帧</small>}</button>)}</div>
      <div className="sticker-detail">{selected?<><img aria-label="贴纸帧预览" src={'/api/stickers/'+selected.id+'/frames/'+frame} alt={selected.name}/><strong>{selected.name}</strong><p>{selected.category.join(' / ')} · {selected.width} × {selected.height}</p>
        {selected.frames>1&&<label>选择静态帧 <input aria-label="贴纸帧" type="range" min={0} max={selected.frames-1} value={frame} onChange={event=>setFrame(Number(event.target.value))}/><span>第 {frame+1} / {selected.frames} 帧</span></label>}</>:<p>按文件夹选择素材，再添加到画布。</p>}</div>
    </div>{failure&&<p role="alert">{failure}</p>}<div className="modal-actions"><button disabled={busy} onClick={close}>取消</button><button className="primary" disabled={!selected||busy} onClick={()=>void confirm()}>{busy?'正在添加…':'添加贴纸'}</button></div></section></div>;
}
