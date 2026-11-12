import {useEffect,useRef,useState} from 'react';
import type {EditorActions} from '../App';
import type {Asset,TitleId} from '../domain/project';
import {captureTextStyle,applyTextStyle,type TextPreset} from '../domain/textPresets';
import {registerFonts,type UploadedFont} from '../services/fonts';
import {api,jsonRequest} from '../services/api';
import {exportName} from './exportName';

type Item={id:string;name:string;count:number};
type Prepared=TextPreset&{assets:Asset[];fonts:UploadedFont[]};

export function TextPresets({actions,target,onError}:{actions:EditorActions;target:TitleId;onError:(message:string)=>void}){
  const [items,setItems]=useState<Item[]>([]),[chosen,setChosen]=useState(''),[name,setName]=useState(''),[busy,setBusy]=useState(false),[message,setMessage]=useState('');
  const input=useRef<HTMLInputElement>(null),alive=useRef(true);
  const selected=items.find(item=>item.id===chosen);
  useEffect(()=>{alive.current=true;void api<Item[]>('/text-presets').then(value=>{if(alive.current)setItems(value);}).catch(error=>{if(alive.current)onError(String(error));});return()=>{alive.current=false;};},[onError]);
  async function run(action:()=>Promise<void>){actions.end();setBusy(true);setMessage('');try{await action();}catch(error){if(alive.current)onError(String(error));}finally{if(alive.current)setBusy(false);}}
  function remember(item:Item){if(alive.current){setItems(previous=>[...previous,item]);setChosen(item.id);setMessage('文字预设已保存到本机');}}
  return <details className="text-presets filter-presets" open><summary>文字预设</summary><p className="asset-meta">保存字体、字号、颜色、光效、阴影、3D 和滤镜。应用时保留当前文案、位置和旋转角度，可撤销。</p>
    <label className="field">预设名称<input aria-label="文字预设名称" value={name} maxLength={120} disabled={busy} onChange={event=>setName(event.target.value)}/></label>
    <button disabled={busy||!name.trim()} onClick={()=>void run(async()=>{const project=actions.getProject?.()||actions.project;remember(await api<Item>('/text-presets',jsonRequest({name:name.trim(),...captureTextStyle(project,target)},'POST')));})}>保存为文字预设</button>
    <label className="field">本机文字预设<select aria-label="本机文字预设" value={chosen} disabled={busy} onChange={event=>setChosen(event.target.value)}><option value="">选择文字预设</option>{items.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    <div className="preset-actions"><button disabled={busy||!selected} onClick={()=>void run(async()=>{
      const value=await api<Prepared>('/text-presets/'+chosen+'/prepare',{method:'POST'});
      if(!alive.current)return;
      registerFonts(value.fonts);actions.addFonts?.(value.fonts);
      for(const asset of value.assets)actions.addAsset(asset);
      actions.end();actions.change(next=>applyTextStyle(next,target,value));setMessage('已应用文字预设，可撤销');
    })}>应用文字预设</button><button disabled={busy||!selected} onClick={()=>void run(async()=>{
      const file=await api<unknown>('/text-presets/'+chosen),url=URL.createObjectURL(new Blob([JSON.stringify(file,null,2)],{type:'application/json'}));
      if(!alive.current){URL.revokeObjectURL(url);return;}
      const link=document.createElement('a');link.href=url;link.download=exportName(selected!.name).slice(0,-4)+'.adofai-text.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),3000);
    })}>导出文字预设</button><button disabled={busy} onClick={()=>input.current?.click()}>导入文字预设</button></div>
    <input ref={input} aria-label="文字预设文件" hidden type="file" accept=".json,application/json" disabled={busy} onChange={event=>{const file=event.target.files?.[0];event.target.value='';if(file)void run(async()=>{if(file.size>100_000_000)throw new Error('文字预设不能超过 100 MB');const body=new FormData();body.append('file',file);remember(await api<Item>('/text-presets/import',{method:'POST',body}));});}}/>
    <p className="asset-meta" role="status">{busy?'正在处理文字预设…':message}</p>
  </details>;
}
