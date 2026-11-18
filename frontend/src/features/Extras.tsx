import type { Project } from '../domain/project';
import { useEffect, useRef, useState } from 'react';
import { dimensions } from '../domain/project';
import { drawComposition } from '../canvas/render';
import { exportName } from './exportName';
import {isAndroid,saveBlob} from '../services/downloads';

export { TrackControls } from './Recognition';
export { MaskEditor } from './MaskEditor';
export function ExportDialog({project,close,onError}: {project:Project;close:()=>void;onError:(error:string)=>void}) {
  const [snapshot] = useState(()=>structuredClone(project));
  const [name,setName] = useState(project.name);
  const [ready,setReady] = useState(false);
  const [busy,setBusy] = useState(false);
  const [failure,setFailure] = useState('');
  const canvas = useRef<HTMLCanvasElement>(null);
  const size = dimensions(snapshot.activeRatio);
  useEffect(()=>{
    let cancelled=false;
    if(canvas.current) void drawComposition(canvas.current,snapshot).then(()=>{if(!cancelled)setReady(true);}).catch(error=>{if(!cancelled)setFailure(String(error));});
    return ()=>{cancelled=true;};
  },[snapshot]);
  useEffect(()=>{const handler=(event:KeyboardEvent)=>{if(event.key==='Escape')close();};window.addEventListener('keydown',handler);return()=>window.removeEventListener('keydown',handler);},[close]);
  async function download(){
    if(!canvas.current||!ready)return;
    setBusy(true);setFailure('');
    try{
      const blob = await new Promise<Blob>((resolve,reject)=>canvas.current!.toBlob(value=>value?resolve(value):reject(new Error('图片生成失败，请重试')),'image/png'));
      await saveBlob(blob,exportName(name));
    }catch(error){const message=error instanceof Error?error.message:'导出失败';setFailure(message);onError(message);}finally{setBusy(false);}
  }
  return <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true" aria-label="导出图片">
    <div className="modal-header"><h2>导出封面</h2><button aria-label="关闭导出" onClick={close}>×</button></div>
    <canvas className="export-preview" aria-label="导出预览" ref={canvas}/>
    <div className="export-details"><span>PNG</span><span>{size.width} × {size.height}</span><input aria-label="导出文件名" value={name} maxLength={120} onChange={e=>setName(e.target.value)}/></div>
    {failure&&<p role="alert">{failure}</p>}
    <div className="modal-actions"><span className="micro">{ready?'完整分辨率 · 当前构图':'正在准备图片…'}</span><button onClick={close}>返回编辑</button><button className="primary" disabled={!ready||busy} onClick={()=>void download()}>{busy?'正在导出…':isAndroid()?'保存到手机':'导出到电脑'}</button></div>
  </section></div>;
}
