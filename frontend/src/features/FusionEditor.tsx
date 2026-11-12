import {useEffect,useRef,useState} from 'react';
import {NumberField} from '../App';
import {api} from '../services/api';
import {assetImage,drawComposition} from '../canvas/render';
import {maskBlob} from '../canvas/feather';
import {gradientMask} from '../canvas/gradientMask';
import {trackFor} from '../domain/objects';
import {type Project,type TrackId,type Asset} from '../domain/project';
import {newGradientFusion,type Fusion,type GradientFusion} from '../domain/fusion';

export function FusionEditor({project,trackId,close,apply,onError}:{project:Project;trackId:TrackId;close:()=>void;apply:(settings:Fusion,asset?:Asset)=>void;onError:(message:string)=>void}){
  const [snapshot]=useState(()=>structuredClone(project)),item=trackFor(snapshot,trackId);
  const [settings,setSettings]=useState<GradientFusion>(()=>item.fusion?.kind==='gradient'?{...item.fusion}:newGradientFusion());
  const [changed,setChanged]=useState(!item.fusion||item.fusion.kind==='gradient');
  const [ready,setReady]=useState(false),[busy,setBusy]=useState(false),[failure,setFailure]=useState('');
  const preview=useRef<HTMLCanvasElement>(null),maskPreview=useRef<HTMLCanvasElement>(null),mask=useRef<HTMLCanvasElement|null>(null),size=useRef({width:0,height:0});
  const update=(patch:Partial<GradientFusion>)=>{setChanged(true);setSettings(value=>({...value,...patch,maskAsset:null}));};
  useEffect(()=>{
    let cancelled=false;
    void assetImage(item.trackAsset!).then(image=>{if(!cancelled){size.current={width:image.naturalWidth,height:image.naturalHeight};setReady(true);}}).catch(error=>{if(!cancelled)setFailure(String(error));});
    return()=>{cancelled=true;};
  },[item.trackAsset]);
  useEffect(()=>{
    if(!ready||!preview.current)return;let cancelled=false;
    const target=preview.current;target.setAttribute('aria-busy','true');
    const layer=gradientMask(size.current.width,size.current.height,settings);mask.current=layer;
    if(maskPreview.current){maskPreview.current.width=layer.width;maskPreview.current.height=layer.height;maskPreview.current.getContext('2d')!.drawImage(layer,0,0);}
    const draft=structuredClone(snapshot);if(changed)trackFor(draft,trackId).fusion=settings;
    const stage=document.createElement('canvas');
    void drawComposition(stage,draft,changed?{fusionMasks:{[trackId]:layer}}:{}).then(()=>{if(cancelled)return;target.width=stage.width;target.height=stage.height;target.getContext('2d')!.drawImage(stage,0,0);target.setAttribute('aria-busy','false');}).catch(error=>{if(!cancelled){target.setAttribute('aria-busy','false');setFailure(String(error));}});
    return()=>{cancelled=true;};
  },[ready,settings,changed,snapshot,trackId]);
  useEffect(()=>{const handle=(event:KeyboardEvent)=>{if(event.key==='Escape'&&!busy)close();};window.addEventListener('keydown',handle);return()=>window.removeEventListener('keydown',handle);},[busy,close]);
  async function save(){
    if(!ready||!mask.current||busy)return;
    if(!changed){close();return;}
    setBusy(true);setFailure('');
    try{
      const body=new FormData();body.append('file',await maskBlob(mask.current),'fusion-gradient.png');
      const asset=await api<Asset>('/masks/'+item.trackAsset,{method:'POST',body});
      apply({...settings,maskAsset:asset.id},asset);close();
    }catch(error){setFailure('融合保存失败，草稿仍保留，可重试');onError(String(error));}finally{setBusy(false);}
  }
  return <div className="modal-backdrop"><section className="modal fusion-editor" role="dialog" aria-modal="true" aria-label="图片融合"><div className="modal-header"><h2>图片融合</h2><button aria-label="关闭融合" disabled={busy} onClick={close}>×</button></div>
    <div className="fusion-layout"><div className="fusion-pictures"><section><h3>整幅构图预览</h3><canvas ref={preview} aria-label="融合效果预览" aria-busy="true"/></section><section><h3>渐变蒙版 · 白色保留，透明处淡出</h3><div className="fusion-source"><canvas ref={maskPreview} aria-label="渐变融合蒙版"/></div></section></div>
    <aside className="fusion-controls">
      {!changed&&<p>当前保留旧融合效果。调整参数并应用后替换为渐变蒙版。</p>}
      <label>启用融合<input aria-label="启用融合" type="checkbox" checked={settings.enabled} onChange={event=>update({enabled:event.target.checked})}/></label>
      <NumberField label="过渡位置 (%)" value={settings.position} min={0} max={100} begin={()=>{}} end={()=>{}} onChange={position=>update({position})}/>
      <NumberField label="过渡宽度 (%)" value={settings.width} min={1} max={200} begin={()=>{}} end={()=>{}} onChange={width=>update({width})}/>
      <NumberField label="过渡角度" value={settings.angle} min={-180} max={180} begin={()=>{}} end={()=>{}} onChange={angle=>update({angle})}/>
      <label>反转渐变<input aria-label="反转渐变" type="checkbox" checked={settings.reverse} onChange={event=>update({reverse:event.target.checked})}/></label>
      <button disabled={!ready||busy} onClick={()=>{setChanged(true);setSettings(newGradientFusion());}}>重置融合</button>
    </aside></div>{failure&&<p role="alert">{failure}</p>}<div className="modal-actions"><span className="micro">{busy?'正在保存…':ready?'原图保留 · 应用后保存到作品':'正在载入…'}</span><button disabled={busy} onClick={close}>取消</button><button className="primary" disabled={!ready||busy} onClick={()=>void save()}>应用融合</button></div>
  </section></div>;
}
