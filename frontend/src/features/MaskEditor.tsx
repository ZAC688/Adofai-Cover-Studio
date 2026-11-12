import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';
import type { EditorActions } from '../App';
import type { Asset } from '../domain/project';
import { screenPoint } from '../domain/project';
import { alphaMask, assetImage } from '../canvas/render';
import { api } from '../services/api';

export function MaskEditor(props: EditorActions & {close:()=>void;onError:(error:string)=>void}){
  const [tool,setTool]=useState<'keep'|'erase'|'pan'>('erase');
  const [brush,setBrush]=useState(45);
  const [zoom,setZoom]=useState(.5);
  const [pan,setPan]=useState({x:0,y:0});
  const [original,setOriginal]=useState(false);
  const [ready,setReady]=useState(false);
  const [busy,setBusy]=useState(false);
  const [dirty,setDirty]=useState(false);
  const [notice,setNotice]=useState('正在载入轨道…');
  const [,refresh]=useState(0);
  const visible=useRef<HTMLCanvasElement>(null), wrapper=useRef<HTMLDivElement>(null);
  const mask=useRef<HTMLCanvasElement|null>(null), source=useRef<HTMLImageElement|null>(null);
  const first=useRef(true),painting=useRef(false);
  const previousPoint=useRef<{x:number;y:number}|null>(null);
  const panning=useRef<{x:number;y:number;pan:{x:number;y:number}}|null>(null);
  const history=useRef<{past:string[];future:string[]}>({past:[],future:[]});
  const latest=useRef(props);latest.current=props;
  const sourceId=props.project.trackAsset!;

  function render(showOriginal=original){
    if(!visible.current||!source.current||!mask.current)return;
    const canvas=visible.current,ctx=canvas.getContext('2d')!;
    canvas.width=source.current.naturalWidth;canvas.height=source.current.naturalHeight;
    ctx.drawImage(source.current,0,0);
    if(!showOriginal){ctx.globalCompositeOperation='destination-in';ctx.drawImage(mask.current,0,0);ctx.globalCompositeOperation='source-over';}
  }
  useEffect(()=>{
    let cancelled=false;setReady(false);
    void Promise.all([assetImage(sourceId),assetImage(props.project.maskAsset!)]).then(([image,reference])=>{
      if(cancelled)return;
      source.current=image;mask.current=alphaMask(reference);render(original);
      if(first.current&&wrapper.current){setZoom(Math.min(wrapper.current.clientWidth/image.naturalWidth,wrapper.current.clientHeight/image.naturalHeight)*.9);first.current=false;}
      setReady(true);setNotice('修正已保存');
    }).catch(error=>{if(!cancelled){setNotice(String(error));props.onError(String(error));}});
    return()=>{cancelled=true;};
  },[sourceId,props.project.maskAsset]);

  async function persist(){
    if(!mask.current||busy)return;
    setBusy(true);setNotice('正在保存修正…');
    const copy=document.createElement('canvas');copy.width=mask.current.width;copy.height=mask.current.height;
    const ctx=copy.getContext('2d')!,pixels=mask.current.getContext('2d')!.getImageData(0,0,copy.width,copy.height);
    for(let i=0;i<pixels.data.length;i+=4){const alpha=pixels.data[i+3];pixels.data[i]=pixels.data[i+1]=pixels.data[i+2]=alpha;pixels.data[i+3]=255;}
    ctx.putImageData(pixels,0,0);
    try{
      const blob=await new Promise<Blob>((resolve,reject)=>copy.toBlob(value=>value?resolve(value):reject(new Error('蒙版生成失败')),'image/png'));
      const form=new FormData();form.append('file',blob,'mask.png');
      const asset=await api<Asset>('/masks/'+sourceId,{method:'POST',body:form});
      if(latest.current.project.trackAsset!==sourceId)throw new Error('轨道素材已更换，当前修正未覆盖新素材');
      const previous=latest.current.project.maskAsset;
      if(previous)history.current.past.push(previous);
      if(history.current.past.length>40)history.current.past.shift();history.current.future=[];
      latest.current.addAsset(asset);latest.current.change(next=>{next.maskAsset=asset.id;next.removeBackground=true;});
      setDirty(false);setNotice('修正已保存');refresh(n=>n+1);
    }catch(error){setNotice('修正保存失败，请重试');props.onError(String(error));}finally{setBusy(false);}
  }
  function undo(redo=false){
    if(busy||dirty)return;
    const state=history.current,from=redo?state.future:state.past,to=redo?state.past:state.future;
    const id=from.pop();if(!id)return;
    if(latest.current.project.maskAsset)to.push(latest.current.project.maskAsset);
    latest.current.change(next=>{next.maskAsset=id;});refresh(n=>n+1);
  }
  useEffect(()=>{
    const handler=(event:KeyboardEvent)=>{
      if(!(event.ctrlKey||event.metaKey)||event.isComposing||(event.target as HTMLElement).closest('input,textarea'))return;
      if(event.key.toLowerCase()==='z'||event.key.toLowerCase()==='y'){event.preventDefault();undo(event.shiftKey||event.key.toLowerCase()==='y');}
    };
    window.addEventListener('keydown',handler);return()=>window.removeEventListener('keydown',handler);
  });
  function point(event:ReactPointerEvent<HTMLCanvasElement>){return screenPoint({x:event.clientX,y:event.clientY},event.currentTarget.getBoundingClientRect(),{width:event.currentTarget.width,height:event.currentTarget.height});}
  function stroke(at:{x:number;y:number}){
    if(!mask.current)return;const ctx=mask.current.getContext('2d')!;
    ctx.globalCompositeOperation=tool==='erase'?'destination-out':'source-over';ctx.fillStyle='#ffffff';ctx.strokeStyle='#ffffff';ctx.lineWidth=brush;ctx.lineCap='round';
    const last=previousPoint.current||at;ctx.beginPath();ctx.moveTo(last.x,last.y);ctx.lineTo(at.x,at.y);ctx.stroke();ctx.beginPath();ctx.arc(at.x,at.y,brush/2,0,Math.PI*2);ctx.fill();ctx.globalCompositeOperation='source-over';
    previousPoint.current=at;setDirty(true);setNotice('修正尚未保存');render();
  }
  function down(event:ReactPointerEvent<HTMLCanvasElement>){
    if(!ready||busy||dirty)return;
    event.currentTarget.setPointerCapture(event.pointerId);
    if(tool==='pan'){panning.current={x:event.clientX,y:event.clientY,pan};return;}
    if(original)return;painting.current=true;stroke(point(event));
  }
  function move(event:ReactPointerEvent<HTMLCanvasElement>){
    if(panning.current){const start=panning.current;setPan({x:start.pan.x+event.clientX-start.x,y:start.pan.y+event.clientY-start.y});}
    else if(painting.current)stroke(point(event));
  }
  function up(){panning.current=null;if(painting.current){painting.current=false;previousPoint.current=null;void persist();}}
  return <section className="mask-workspace" role="dialog" aria-modal="true" aria-label="轨道修正工作区">
    <div className="mask-toolbar"><h2>轨道修正</h2>
      <button aria-pressed={tool==='keep'} onClick={()=>setTool('keep')}>保留画笔</button><button aria-pressed={tool==='erase'} onClick={()=>setTool('erase')}>擦除画笔</button><button aria-pressed={tool==='pan'} onClick={()=>setTool('pan')}>平移</button>
      <button aria-label="撤销画笔" disabled={busy||dirty||!history.current.past.length} onClick={()=>undo()}>↶</button><button aria-label="重做画笔" disabled={busy||dirty||!history.current.future.length} onClick={()=>undo(true)}>↷</button>
      <button aria-pressed={original} onClick={()=>{setOriginal(!original);render(!original);}}>{original?'查看处理结果':'对照原图'}</button><span className="spacer"/>
      {dirty&&!busy&&<button onClick={()=>void persist()}>重试保存修正</button>}
      <button className="primary" disabled={busy||dirty} onClick={props.close}>返回构图</button>
    </div>
    <div className="mask-stage-wrap" ref={wrapper}><canvas aria-label="轨道修正画布" ref={visible} style={{left:'50%',top:'50%',transform:`translate(-50%,-50%) translate(${pan.x}px,${pan.y}px) scale(${zoom})`}} onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up} onLostPointerCapture={up}/></div>
    <div className="mask-footer"><label>画笔大小 <input aria-label="画笔大小" type="range" min="1" max="200" value={brush} onChange={e=>setBrush(Number(e.target.value))}/></label><span>{brush} px</span>
      <label>缩放 <input aria-label="修正缩放" type="range" min="10" max="300" value={zoom*100} onChange={e=>setZoom(Number(e.target.value)/100)}/></label><span>{Math.round(zoom*100)}%</span><span className="spacer"/><span role="status">{notice}</span></div>
  </section>;
}
