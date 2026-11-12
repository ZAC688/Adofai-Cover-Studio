import { useEffect, useRef, useState } from 'react';
import type { EditorActions } from '../App';
import type { Asset } from '../domain/project';
import { api } from '../services/api';

type Job = {id: string; source: string; status: 'running'|'succeeded'|'failed'|'cancelled'; result: Asset|null; error: string|null};

export function TrackControls(props: EditorActions & {openMask:()=>void;onError:(error:string)=>void}) {
  const latest = useRef(props); latest.current=props;
  const [job,setJob]=useState<Job|null>(null);
  const [starting,setStarting]=useState(false);
  const generation=useRef(0);
  const timer=useRef<ReturnType<typeof setTimeout>|null>(null);

  function accept(value:Job, version:number){
    if(version!==generation.current||latest.current.project.trackAsset!==value.source)return;
    setJob(value);
    if(value.status==='succeeded'&&value.result){
      const handled='adofai-job-'+(latest.current.objectKey||'track')+'-'+value.id;
      if(sessionStorage.getItem(handled)!=='handled'&&latest.current.project.baseMaskAsset!==value.result.id){
        const asset=value.result;latest.current.addAsset(asset);
        latest.current.change(next=>{if(next.trackAsset===value.source){next.baseMaskAsset=asset.id;next.maskAsset=asset.id;next.removeBackground=true;}});
      }
      sessionStorage.setItem(handled,'handled');
    }
    if(value.status==='running')timer.current=setTimeout(()=>void poll(value.id,version),250);
  }
  async function poll(id:string,version:number){
    try{accept(await api<Job>('/jobs/'+id),version);}catch(error){
      if(version===generation.current){setJob(previous=>previous?{...previous,status:'failed',error:String(error)}:null);latest.current.onError(String(error));}
    }
  }
  useEffect(()=>{
    const version=++generation.current;setJob(null);
    if(props.project.trackAsset)void api<{job:Job|null}>('/jobs/active/'+props.project.trackAsset).then(value=>{if(value.job)accept(value.job,version);}).catch(error=>{if(version===generation.current)latest.current.onError(String(error));});
    return ()=>{generation.current++;if(timer.current)clearTimeout(timer.current);};
  },[props.project.trackAsset]);

  async function start(replace=false){
    const source=props.project.trackAsset;if(!source)return;
    if(replace&&props.project.maskAsset&&!window.confirm('重新识别会替换当前手工修正结果。是否继续？'))return;
    const version=++generation.current;if(timer.current)clearTimeout(timer.current);
    setStarting(true);
    try{const value=await api<Job>('/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source})});accept(value,version);}
    catch(error){if(version===generation.current){latest.current.onError(String(error));setJob(null);}}
    finally{if(version===generation.current)setStarting(false);}
  }
  async function cancel(){
    generation.current++;if(timer.current)clearTimeout(timer.current);
    setStarting(false);
    if(job){try{setJob(await api<Job>('/jobs/'+job.id+'/cancel',{method:'POST'}));}catch(error){props.onError(String(error));}}
  }
  const busy=starting||job?.status==='running';
  return <div className="track-controls">
    <label>自动去除背景<input aria-label="自动去除背景" type="checkbox" disabled={!props.project.trackAsset||starting} checked={props.project.removeBackground||!!busy}
      onChange={event=>{if(!event.target.checked){if(busy)void cancel();props.change(next=>{next.removeBackground=false;});}else if(props.project.maskAsset)props.change(next=>{next.removeBackground=true;});else void start();}}/></label>
    {busy?<><p role="status">正在识别轨道…</p><button onClick={()=>void cancel()}>取消识别</button></>:<>
      <p>适用于纯色或暗色低对比纹理背景。复杂背景仅提供候选结果；可用保留／擦除画笔修正。</p>
      {job?.status==='failed'&&<p role="alert">{job.error||'识别失败，原始素材已保留。'}</p>}
      <button disabled={!props.project.maskAsset} onClick={props.openMask}>修正轨道</button>
      <button disabled={!props.project.trackAsset} onClick={()=>void start(true)}>{job?.status==='failed'?'重试识别':'重新识别'}</button>
    </>}
  </div>;
}
