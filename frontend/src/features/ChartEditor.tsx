import {useEffect,useRef,useState} from 'react';
import {api,jsonRequest} from '../services/api';
import type {Asset,ChartRecipe} from '../domain/project';
import type {ChartInfo} from '../domain/chartTitles';
import {saveURL} from '../services/downloads';

export function ChartEditor({initial,close,apply,availableTitles}:{initial?:ChartRecipe|null;close:()=>void;availableTitles:number;apply:(asset:Asset,recipe:ChartRecipe,texts:string[])=>void}){
  const [source,setSource]=useState(initial?.sourceId||'');
  const [html,setHtml]=useState(''),[busy,setBusy]=useState(false),[failure,setFailure]=useState('');
  const [result,setResult]=useState<{asset:Asset;recipe:ChartRecipe}|null>(null);
  const [info,setInfo]=useState<ChartInfo|null>(null),[song,setSong]=useState(false),[artist,setArtist]=useState(false);
  const texts=[song?info?.song:'',artist?info?.artist:''].filter((text):text is string=>!!text);
  const full=texts.length>availableTitles;
  const frame=useRef<HTMLIFrameElement>(null),input=useRef<HTMLInputElement>(null),alive=useRef(true);
  const initialRef=useRef(initial),busyRef=useRef(false),closeRef=useRef(close);closeRef.current=close;
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
  useEffect(()=>{
    if(!source)return;let cancelled=false;
    setBusy(true);setFailure('');setInfo(null);setSong(false);setArtist(false);
    void Promise.all([api<{html:string}>('/charts/'+source+'/editor',jsonRequest(initialRef.current?.sourceId===source?initialRef.current:null,'POST')),api<ChartInfo>('/charts/'+source)]).then(([data,metadata])=>{if(!cancelled){setHtml(data.html);setInfo(metadata);}}).catch(error=>{if(!cancelled)setFailure(String(error));}).finally(()=>{if(!cancelled)setBusy(false);});
    return()=>{cancelled=true;};
  },[source]);
  useEffect(()=>{
    const receive=(event:MessageEvent)=>{
      if(event.origin!==location.origin||event.source!==frame.current?.contentWindow||event.data?.type!=='adofai-chart-apply'||event.data.sourceId!==source||busyRef.current)return;
      busyRef.current=true;setBusy(true);setFailure('');
      void api<{asset:Asset;recipe:ChartRecipe}>('/charts/render',jsonRequest(event.data.recipe,'POST')).then(data=>{if(alive.current)setResult(data);}).catch(error=>{if(alive.current)setFailure(String(error));}).finally(()=>{busyRef.current=false;if(alive.current)setBusy(false);});
    };
    window.addEventListener('message',receive);return()=>window.removeEventListener('message',receive);
  },[source]);
  useEffect(()=>{const handler=(event:KeyboardEvent)=>{if(event.key==='Escape'&&!busy){event.preventDefault();closeRef.current();}};window.addEventListener('keydown',handler);return()=>window.removeEventListener('keydown',handler);},[busy]);
  async function upload(file?:File){
    if(!file)return;setBusy(true);setFailure('');setResult(null);
    try{const body=new FormData();body.append('file',file);const item=await api<{id:string}>('/charts',{method:'POST',body});initialRef.current=null;setHtml('');setSource(item.id);}
    catch(error){setFailure(String(error));}finally{setBusy(false);}
  }
  async function downloadTrack(){
    if(!result)return;
    try{await saveURL('/api/assets/'+result.asset.id,`轨道-${result.recipe.start}-${result.recipe.end}-${result.recipe.resolution}.png`);}
    catch(error){if(alive.current)setFailure(String(error));}
  }
  return <div className="modal-backdrop"><section className="modal chart-editor" role="dialog" aria-modal="true" aria-label="从谱面生成轨道">
    <div className="modal-header"><h2>从谱面生成轨道</h2><button disabled={busy} onClick={()=>input.current?.click()}>{source?'更换谱面':'导入 .adofai'}</button><button aria-label="关闭谱面生成" disabled={busy} onClick={close}>×</button></div>
    <input ref={input} aria-label="谱面文件" type="file" accept=".adofai" hidden onChange={event=>{void upload(event.target.files?.[0]);event.target.value='';}}/>
    {!source&&<div className="chart-empty"><p>导入本机 .adofai 谱面，选择轨道段并预览。</p><p>只读取轨道数据，不需要音乐、背景或其他媒体；谱面上限 10 MB。</p><button disabled={busy} onClick={()=>input.current?.click()}>选择谱面文件</button></div>}
    {info&&<fieldset className="chart-metadata" disabled={busy}><legend>曲目信息 · 可选白色标题</legend><label><input type="checkbox" aria-label="生成音乐名称标题" checked={song} disabled={!info.song} onChange={event=>setSong(event.target.checked)}/>音乐名称：{info.song||'谱面未填写'}</label><label><input type="checkbox" aria-label="生成音乐作者标题" checked={artist} disabled={!info.artist} onChange={event=>setArtist(event.target.checked)}/>音乐作者：{info.artist||'谱面未填写'}</label><p>应用轨道时新增所选标题，可继续编辑；剩余 {availableTitles} 个标题名额。</p>{full&&<p role="alert">标题名额不足，请减少勾选项或先删除不需要的标题。现有内容将保留。</p>}</fieldset>}
    {html&&<iframe ref={frame} title="轨道选段工具" srcDoc={html} hidden={!!result} />}
    {result&&<div className="chart-result"><h3>生成结果预览 · {result.asset.width} × {result.asset.height}</h3><div className="chart-result-image"><img alt="生成轨道预览" src={'/api/assets/'+result.asset.id}/></div><p>应用后成为轨道对象，可继续添加光效、滤镜、旋转和排序。</p><div className="modal-actions"><button onClick={downloadTrack}>导出轨道 PNG</button><button disabled={busy} onClick={()=>setResult(null)}>返回调整</button><button className="primary" disabled={busy||full} onClick={()=>{try{apply(result.asset,result.recipe,texts);close();}catch(error){setFailure(String(error));}}}>应用到封面</button></div></div>}
    {failure&&<p role="alert">{failure} 可保留当前草稿重试。</p>}{busy&&<div className="chart-busy" role="status">正在读取或生成轨道，请稍候…</div>}
  </section></div>;
}
