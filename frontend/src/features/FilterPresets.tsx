import {useEffect,useRef,useState} from 'react';
import type {EditorActions} from '../App';
import type {ObjectId,Asset} from '../domain/project';
import type {FilterSpec} from '../domain/filters';
import {replaceTargetFilters} from '../domain/filterPresets';
import {api,jsonRequest} from '../services/api';
import {exportName} from './exportName';
type Preset={id:string;name:string;count:number};
export function FilterPresets({actions,target,onError}:{actions:EditorActions;target:ObjectId|'canvas';onError:(message:string)=>void}){
  const [items,setItems]=useState<Preset[]>([]),[chosen,setChosen]=useState(''),[name,setName]=useState(''),[busy,setBusy]=useState(false),[message,setMessage]=useState('');
  const input=useRef<HTMLInputElement>(null),alive=useRef(true);
  useEffect(()=>{alive.current=true;void api<Preset[]>('/filter-presets').then(value=>{if(alive.current)setItems(value);}).catch(error=>{if(alive.current)onError(String(error));});return()=>{alive.current=false;};},[onError]);
  const selected=items.find(item=>item.id===chosen);
  async function run(action:()=>Promise<void>){actions.end();setBusy(true);setMessage('');try{await action();}catch(error){onError(String(error));}finally{if(alive.current)setBusy(false);}}
  function remember(preset:Preset){if(alive.current){setItems(previous=>[...previous,preset]);setChosen(preset.id);setMessage('预设已保存到本机');}}
  return <details className="filter-presets" open><summary>滤镜预设</summary><p className="asset-meta">整套滤镜、顺序及局部范围一起保存。应用会替换当前目标的滤镜，可撤销。</p>
    <label className="field">预设名称<input aria-label="滤镜预设名称" value={name} maxLength={120} disabled={busy} onChange={event=>setName(event.target.value)}/></label>
    <button disabled={busy||!name.trim()||!actions.project.filters?.some(f=>f.targets.includes(target))} onClick={()=>void run(async()=>{const project=actions.getProject?.()||actions.project;const preset=await api<Preset>('/filter-presets',jsonRequest({name:name.trim(),filters:project.filters!.filter(f=>f.targets.includes(target))},'POST'));remember(preset);})}>保存为滤镜预设</button>
    <label className="field">本机预设<select aria-label="本机滤镜预设" value={chosen} disabled={busy} onChange={event=>setChosen(event.target.value)}><option value="">选择预设</option>{items.map(item=><option key={item.id} value={item.id}>{item.name} · {item.count} 个滤镜</option>)}</select></label>
    <div className="preset-actions"><button disabled={busy||!selected} onClick={()=>void run(async()=>{
      const value=await api<{filters:FilterSpec[];assets:Asset[]}>('/filter-presets/'+chosen+'/prepare',{method:'POST'});
      for(const asset of value.assets)actions.addAsset(asset);
      actions.end();actions.change(next=>replaceTargetFilters(next,target,value.filters));if(alive.current)setMessage('已应用预设，可撤销');
    })}>应用滤镜预设</button>
    <button disabled={busy||!selected} onClick={()=>void run(async()=>{
      const file=await api<unknown>('/filter-presets/'+chosen),url=URL.createObjectURL(new Blob([JSON.stringify(file,null,2)],{type:'application/json'}));
      const link=document.createElement('a');link.href=url;link.download=exportName(selected!.name).slice(0,-4)+'.adofai-filters.json';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),3000);
    })}>导出滤镜预设</button><button disabled={busy} onClick={()=>input.current?.click()}>导入滤镜预设</button></div>
    <input ref={input} aria-label="滤镜预设文件" hidden type="file" accept=".json,application/json" disabled={busy} onChange={event=>{const file=event.target.files?.[0];event.target.value='';if(file)void run(async()=>{if(file.size>100_000_000)throw new Error('滤镜预设不能超过 100 MB');const body=new FormData();body.append('file',file);remember(await api<Preset>('/filter-presets/import',{method:'POST',body}));});}}/>
    <p className="asset-meta" role="status">{busy?'正在处理预设…':message}</p>
  </details>;
}
