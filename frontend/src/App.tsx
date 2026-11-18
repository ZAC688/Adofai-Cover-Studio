import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';
import { changeRatio, dimensions, fitScale, History, layout, screenPoint, type Asset, type Assets, type Loaded, type ObjectId, type Project, type Ratio,type TrackId,type TitleId,type Track,type GraphicId,type Sticker } from './domain/project';
import { api, initSession, jsonRequest, upload } from './services/api';
import { SaveQueue, type SaveStatus } from './services/saveQueue';
import { compose, presentComposition, objectBounds } from './canvas/render';
import './styles.css';
import './mobile.css';
import {useCompactLayout,useMobileButtons,type MobilePanel} from './services/mobile';
import {EffectsPanel,CollapsibleSettings} from './features/EffectsPanel';
import {ShadowPanel} from './features/ShadowPanel';
import {StickerPicker} from './features/StickerPicker';
import {FusionEditor} from './features/FusionEditor';
import {FilterPanel} from './features/FilterPanel';
import {ColorInput} from './features/ColorInput';
import {Text3DPanel} from './features/Text3DPanel';
import {InfoDialog} from './features/InfoDialog';
import {ChartEditor} from './features/ChartEditor';
import {addChartTitles,titleCapacity} from './domain/chartTitles';
import {flushColorChanges} from './services/colorBuffer';
import {LatestRenderer} from './services/latestRenderer';
import {fineSlider,type SliderRange} from './domain/filterSlider';
import {builtinFonts,registerFonts,type UploadedFont} from './services/fonts';
import {getTrackGeometry,trackBounds,trackContains,trackPivot,type TrackGeometry} from './canvas/selection';
import {center,rotatePoint,boxContains,normalizeDegrees,type Point} from './domain/rotation';
import {order,isTitle as titleObject,isTrack,isSticker,isGraphic,titleFor,trackFor,position,titlePosition,imagePosition,objectName,graphicAsset,graphicView,addSticker,addObject,removeObject,reorderObject,selectedTrackView,changeTrack,titleIds} from './domain/objects';

export type EditorActions = {
  project: Project; assets: Assets;
  change: (mutate: (project: Project) => void) => void;
  addAsset: (asset: Asset) => void;
  addFonts?: (fonts:UploadedFont[]) => void;
  begin: () => void; end: () => void;
  objectKey?:string;
  getProject?:()=>Project;
};

export function NumberField({label, value, min, max, step = 1, slider, onChange, begin, end}: {
  label: string; value: number; min: number; max: number; step?: number;
  slider?:SliderRange;
  onChange: (value: number) => void; begin: () => void; end: () => void;
}) {
  const [fine,setFine]=useState<SliderRange|null>(null),range=fine||slider||{min,max:Math.max(max,value),step};
  const change = (raw: string) => { const next = Number(raw); if (raw !== '' && Number.isFinite(next)) onChange(Math.max(min, Math.min(max, next))); };
  return <div className="field number-field"><label>{label}<input aria-label={label} type="number" value={slider?Number(value.toFixed(6)):Math.round(value*100)/100} min={min} max={max} step={step}
    onFocus={begin} onBlur={end} onChange={e => change(e.target.value)} /></label>
    <input aria-label={label+'滑块'} aria-valuetext={String(value)} type="range" min={range.min} max={range.max} step={range.step} value={Math.max(range.min,Math.min(range.max,value))}
      onPointerDown={begin} onPointerUp={end} onKeyDown={begin} onKeyUp={end} onBlur={end} onChange={e => change(e.target.value)} />
    {slider&&<div className="slider-precision"><span>{Number(range.min.toFixed(3))}—{Number(range.max.toFixed(3))}</span><button aria-label={'精细调节 '+label} aria-pressed={!!fine} onClick={()=>{end();setFine(fine?null:fineSlider(value,slider,{min,max}));}}>{fine?'常用范围':'精细调节'}</button></div>}</div>;
}

export default function App() {
  const compact=useCompactLayout();
  useMobileButtons(compact);
  const [mobilePanel,setMobilePanel]=useState<MobilePanel>('properties');
  const [project, setProject] = useState<Project | null>(null);
  const [assets, setAssets] = useState<Assets>({});
  const [fonts,setFonts]=useState<UploadedFont[]>([]);
  const [,refreshSelection]=useState(0);
  const [selectedId, setSelected] = useState<ObjectId>('title1');
  const selected=project&&!order(project).includes(selectedId)?order(project)[0]:selectedId;
  const [geometries,setGeometries]=useState<Partial<Record<GraphicId,TrackGeometry>>>({});
  const geometry=isGraphic(selected)?geometries[selected]:null;
  const [stickerOpen,setStickerOpen]=useState(false);
  const [propertyTab,setPropertyTab]=useState<'object'|'filters'>('object');
  const [fusionTarget,setFusionTarget]=useState<TrackId|null>(null),[trackMenu,setTrackMenu]=useState<TrackId|null>(null);
  const [status, setStatus] = useState<SaveStatus>({kind:'saved', message:'正在恢复本机作品…'});
  const [error, setError] = useState('');
  const [loadingError, setLoadingError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [closing, setClosing] = useState(false);
  const [closed, setClosed] = useState(false);
  const [view, setView] = useState<'editor' | 'mask'>('editor');
  const [exportOpen, setExportOpen] = useState(false);
  const [infoOpen,setInfoOpen]=useState(false);
  const [chartTarget,setChartTarget]=useState<TrackId|'new'|null>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const renderer=useRef<LatestRenderer<Project,HTMLCanvasElement>|null>(null);
  const current = useRef<Project | null>(null);
  const queue = useRef<SaveQueue<Project> | null>(null);
  const history = useRef(new History<Project>());
  const group = useRef<Project | null>(null);
  const backgroundInput = useRef<HTMLInputElement>(null), trackInput = useRef<HTMLInputElement>(null);
  const fontInput=useRef<HTMLInputElement>(null);
  const [historyVersion, refreshHistory] = useState(0);
  const [feature, setFeature] = useState<null | typeof import('./features/Extras')>(null);
  const layerDrag=useRef<{source:ObjectId;target:ObjectId}|null>(null);
  const [layerTarget,setLayerTarget]=useState<ObjectId|null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        await initSession(); const [loaded,fontList] = await Promise.all([api<Loaded>('/project'),api<UploadedFont[]>('/fonts')]);
        if (cancelled) return;
        registerFonts(fontList);setFonts(fontList);
        current.current = loaded.project; setProject(loaded.project); setAssets(loaded.assets);
        queue.current = new SaveQueue(loaded.revision,
          (baseRevision, snapshot) => api<Loaded>('/project', jsonRequest({baseRevision, project:snapshot})), setStatus);
        setStatus({kind:'saved', message:'已保存到本机'});
      } catch (problem) { if (!cancelled) setLoadingError(problem instanceof Error ? problem.message : '恢复失败'); }
    })();
    return () => {cancelled = true; queue.current?.dispose();};
  }, []);

  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      flushColorChanges();
      if (queue.current?.isDirty()) { event.preventDefault(); event.returnValue = ''; }
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, []);

  const commit = useCallback((next: Project, remember = true) => {
    if (!current.current || JSON.stringify(current.current) === JSON.stringify(next)) return;
    if (remember && !group.current) history.current.remember(current.current);
    current.current = next; setProject(next); queue.current?.update(next); refreshHistory(n => n+1);
  }, []);
  const change = useCallback((mutate: (project: Project) => void) => {
    if (!current.current) return;
    const next = structuredClone(current.current); mutate(next); commit(next);
  }, [commit]);
  const begin = useCallback(() => { if (!group.current && current.current) group.current = structuredClone(current.current); }, []);
  const end = useCallback(() => {
    flushColorChanges();
    if (group.current && current.current && JSON.stringify(group.current) !== JSON.stringify(current.current)) {
      history.current.remember(group.current); refreshHistory(n => n+1);
    }
    group.current = null;
  }, []);
  const undo = useCallback((redo = false) => {
    end(); if (!current.current) return;
    const next = redo ? history.current.redo(current.current) : history.current.undo(current.current);
    if (next) commit(next, false);
  }, [commit, end]);
  useEffect(()=>{
    const host=window as Window&{adofaiCloseRequest?:()=>Promise<boolean>};
    host.adofaiCloseRequest=async()=>{end();try{await queue.current?.flush();return !queue.current?.isDirty();}catch(problem){setError(String(problem));return false;}};
    return()=>{delete host.adofaiCloseRequest;};
  },[end]);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.defaultPrevented||event.isComposing||view === 'mask'||fusionTarget||stickerOpen||exportOpen||document.querySelector('[role="dialog"][aria-modal="true"]')) return;
      const target=event.target;
      if (target instanceof HTMLElement&&(target.closest('input,textarea,select')||target.isContentEditable)) return;
      if(event.key==='Delete'&&!event.ctrlKey&&!event.metaKey&&!event.altKey){
        if(!event.repeat&&selected!=='bg'){event.preventDefault();end();change(next=>removeObject(next,selected));}
        return;
      }
      if (!(event.ctrlKey || event.metaKey)) return;
      if (event.key.toLowerCase() === 'z' || event.key.toLowerCase() === 'y') {
        event.preventDefault(); undo(event.shiftKey || event.key.toLowerCase() === 'y');
      }
    };
    window.addEventListener('keydown', handler); return () => window.removeEventListener('keydown', handler);
  }, [undo,end,change,selected,view,fusionTarget,stickerOpen,exportOpen]);

  useEffect(() => {
    if (!project || !canvas.current) return;
    renderer.current??=new LatestRenderer(async snapshot=>{
      // Give controls a paint opportunity before raster work and GPU readback.
      await new Promise<void>(resolve=>requestAnimationFrame(()=>setTimeout(resolve,0)));
      return compose(snapshot);
    },(stage,snapshot)=>{
      const target=canvas.current;if(!target||snapshot.activeRatio!==current.current?.activeRatio)return;
      presentComposition(target,stage);refreshSelection(value=>value+1);
    },busy=>canvas.current?.setAttribute('aria-busy',String(busy)),problem=>setError(String(problem)));
    renderer.current.request(project);
  }, [project]);
  useEffect(()=>()=>{renderer.current?.dispose();renderer.current=null;},[]);

  const drag = useRef<null | {id:ObjectId;x:number;y:number;initial:Project;mode:'move'|'resize'|'rotate';pivot:Point;startAngle:number}>(null);
  const [manipulating,setManipulating]=useState(false);
  const trackSources=project?order(project).filter(isGraphic).map(id=>{const t=graphicView(project,id);return [id,t.trackAsset,t.maskAsset,t.removeBackground,JSON.stringify(t.fusion)].join(':');}).join('|'):'';
  useEffect(()=>{
    let cancelled=false;setGeometries({});
    if(project)void Promise.all(order(project).filter(isGraphic).filter(id=>graphicAsset(project,id)).map(async id=>[id,await getTrackGeometry(graphicView(project,id))] as const)).then(values=>{if(!cancelled)setGeometries(Object.fromEntries(values));}).catch(error=>{if(!cancelled)setError(String(error));});
    return()=>{cancelled=true;};
  },[trackSources]);
  function boundsFor(id:ObjectId){
    if(!project)return null;
    return isGraphic(id)?(geometries[id]?trackBounds(geometries[id]!,imagePosition(layout(project),id)):null):objectBounds(project,assets,id);
  }
  function pointerDown(event: ReactPointerEvent<HTMLCanvasElement>) {
    if (!project) return;
    // Finish the focused field before starting a canvas gesture. Its later blur
    // must not split a single drag into separate undo entries.
    if(document.activeElement instanceof HTMLElement)document.activeElement.blur();
    end();
    const size = dimensions(project.activeRatio);
    const point = screenPoint({x:event.clientX,y:event.clientY},event.currentTarget.getBoundingClientRect(),size);
    const selectedBox = boundsFor(selected);
    const tolerance = (event.pointerType==='touch'?22:14) * size.width / event.currentTarget.getBoundingClientRect().width;
    const pivot=isGraphic(selected)&&geometry?trackPivot(geometry,imagePosition(layout(project),selected)):selectedBox?center(selectedBox):position(layout(project),selected);
    const angle=position(layout(project),selected).rotation||0;
    const corner=selectedBox?rotatePoint({x:selectedBox.x+selectedBox.width,y:selectedBox.y+selectedBox.height},pivot,angle):null;
    const knob=selectedBox?rotatePoint({x:selectedBox.x+selectedBox.width/2,y:selectedBox.y-24*size.width/event.currentTarget.getBoundingClientRect().width},pivot,angle):null;
    const rotating=selected!=='bg'&&!!knob&&Math.hypot(point.x-knob.x,point.y-knob.y)<tolerance;
    const resize=!rotating&&!titleObject(selected)&&!!corner&&Math.hypot(point.x-corner.x,point.y-corner.y)<tolerance;
    const id = rotating||resize ? selected : order(project).find(id => {
      if(isGraphic(id))return geometries[id]?trackContains(geometries[id]!,imagePosition(layout(project),id),point):false;
      const box = boundsFor(id);
      return box&&boxContains(box,point,position(layout(project),id).rotation||0);
    });
    if (!id) return;
    setSelected(id); begin(); drag.current = {id,x:point.x,y:point.y,initial:structuredClone(project),mode:rotating?'rotate':resize?'resize':'move',pivot,startAngle:Math.atan2(point.y-pivot.y,point.x-pivot.x)};
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function pointerMove(event: ReactPointerEvent<HTMLCanvasElement>) {
    const data = drag.current; if (!data || !project) return;
    setManipulating(true);
    const point = screenPoint({x:event.clientX,y:event.clientY},event.currentTarget.getBoundingClientRect(),dimensions(project.activeRatio));
    const initial = position(layout(data.initial),data.id);
    change(next => {
      const placement = position(layout(next),data.id);
      if(data.mode==='rotate'){
        placement.rotation=normalizeDegrees((initial.rotation||0)+(Math.atan2(point.y-data.pivot.y,point.x-data.pivot.x)-data.startAngle)*180/Math.PI);
      }else if (data.mode==='resize' && !titleObject(data.id)) {
        const old = imagePosition(layout(data.initial),data.id);
        const radius = Math.max(1,Math.hypot(data.x-data.pivot.x,data.y-data.pivot.y));
        const scale=Math.max(.001,Math.min(10000,old.scale*Math.hypot(point.x-data.pivot.x,point.y-data.pivot.y)/radius));
        imagePosition(layout(next),data.id).scale=scale;
        placement.x=data.pivot.x-(data.pivot.x-old.x)/old.scale*scale;
        placement.y=data.pivot.y-(data.pivot.y-old.y)/old.scale*scale;
      } else {placement.x=initial.x+point.x-data.x; placement.y=initial.y+point.y-data.y;}
    });
  }
  function pointerEnd() { setManipulating(false);if (drag.current) {drag.current=null; end();} }

  async function uploadObject(file: File | undefined, id: 'bg' | TrackId) {
    if (!file || !current.current) return;
    end(); setUploading(true); setError('');
    try {
      const asset = await upload(file); setAssets(previous => ({...previous,[asset.id]:asset}));
      change(next => {
        if(!order(next).includes(id))return;
        if(id==='bg')next.bgAsset=asset.id;else trackFor(next,id).trackAsset=asset.id;
        for (const ratio of ['16:9','4:3'] as Ratio[]) {
          const positions = next.layouts[ratio]; if (!positions) continue;
          const size = dimensions(ratio);
          Object.assign(imagePosition(positions,id),{x:size.width/2,y:size.height/2,scale:fitScale(asset,size,id==='bg')*(isTrack(id)?.8:1),rotation:0});
        }
        if (isTrack(id)) {const t=trackFor(next,id);t.maskAsset=null;t.baseMaskAsset=null;t.removeBackground=false;t.fusion=null;t.generatedTrack=null;}
      }); setSelected(id);
    } catch(problem) {setError(problem instanceof Error ? problem.message : '上传失败');}
    finally {setUploading(false);}
  }
  function uploadTrack(file:File|undefined){
    if(!file||!current.current)return;
    let id=isTrack(selected)&&order(current.current).includes(selected)?selected:order(current.current).find(isTrack);
    if(!id){end();change(next=>{id=addObject(next,'track') as TrackId;});}
    if(id)void uploadObject(file,id);
  }
  async function loadExtras() {
    if (feature) return feature;
    const loaded = await import('./features/Extras'); setFeature(loaded); return loaded;
  }

  async function uploadFont(file:File|undefined){
    if(!file||!current.current)return;
    if(!titleObject(selected))return;
    const id=selected;end();setUploading(true);setError('');
    try{
      if(file.size>50_000_000)throw new Error('字体不能超过 50 MB');
      const body=new FormData();body.append('file',file);
      const font=await api<UploadedFont>('/fonts',{method:'POST',body});registerFonts([font]);setFonts(previous=>[...previous,font]);
      change(next=>{if(order(next).includes(id))titleFor(next,id).fontId=font.id;});
    }catch(problem){setError(problem instanceof Error?problem.message:'字体上传失败');}finally{setUploading(false);}
  }

  function add(kind:'title'|'track'){
    end();let id:ObjectId|null=null;change(next=>{id=addObject(next,kind);});if(id)setSelected(id);
  }
  function deleteSelected(){end();change(next=>removeObject(next,selected));}
  function openFusion(id:TrackId){end();setSelected(id);setTrackMenu(null);setFusionTarget(id);}
  function shiftSelected(delta:number){
    end();const values=[...order(project!)],index=values.indexOf(selected),target=index+delta;
    if(selected==='bg'||target<0||target>=values.length-1)return;
    [values[index],values[target]]=[values[target],values[index]];change(next=>{next.layerOrder=values;});
  }

  async function shutdownApp() {
    end(); setClosing(true);
    try { await queue.current?.flush(); await api('/shutdown', {method:'POST'}); setClosed(true);Object.assign(window,{adofaiShutdownComplete:true}); }
    catch(problem) {setError(problem instanceof Error ? problem.message : '退出失败，请先保存后重试');}
    finally {setClosing(false);}
  }

  if (closed) return <main className="boot"><div className="brand-mark">A</div><h1>ADOFAI 封面制作器</h1><p>作品已保存，本地程序已退出。再次双击启动程序即可继续。</p></main>;

  if (!project) return <main className="boot"><div className="brand-mark">A</div><h1>ADOFAI 封面制作器</h1>
    <p>{loadingError || '正在恢复本机作品…'}</p>{loadingError && <button onClick={() => window.location.reload()}>重新读取</button>}</main>;
  const size = dimensions(project.activeRatio), positions = layout(project);
  const box = boundsFor(selected);
  const titleIndex = titleIds.indexOf(selected as TitleId);
  const isTitle = titleObject(selected),track=isTrack(selected)?trackFor(project,selected):null;
  const selectedAsset = assets[(selected === 'bg' ? project.bgAsset : isGraphic(selected)?graphicAsset(project,selected):null) || ''];
  const nameFor=(id:ObjectId)=>objectName(project,id);
  const placement=position(positions,selected);
  const pivot=isGraphic(selected)&&geometry?trackPivot(geometry,imagePosition(positions,selected)):box?center(box):placement;
  const editTrack=(mutate:(track:Track)=>void)=>change(next=>{if(isTrack(selected))mutate(trackFor(next,selected));});
  const actions: EditorActions = {project:isTrack(selected)?selectedTrackView(project,selected):project, assets,
    change:mutate=>change(next=>{if(isTrack(selected))changeTrack(next,selected,mutate);}), objectKey:selected,begin, end, addAsset: asset => setAssets(previous => ({...previous,[asset.id]:asset}))};
  void historyVersion;
  return <div className={'app-shell'+(compact?' mobile-layout':'')} data-mobile-panel={mobilePanel} data-ratio={project.activeRatio}>
    <header className="topbar"><div className="identity"><span className="brand-mark">A</span><div><h1>ADOFAI 封面制作器</h1><span className="eyebrow">COVER STUDIO · LOCAL</span></div></div>
      <div className="toolbar-imports"><button className="upload-card toolbar-upload" aria-label="上传底图" title="PNG / JPEG · 最大 10 MB" disabled={uploading} onClick={()=>backgroundInput.current?.click()}><span>▧</span><strong>上传底图</strong></button>
        <button className="upload-card toolbar-upload" aria-label="上传轨道" title="透明 PNG 或游戏截图 · 最大 10 MB" disabled={uploading} onClick={()=>trackInput.current?.click()}><span>◈</span><strong>上传轨道</strong></button>
        <button className="toolbar-chart" disabled={order(project).filter(isTrack).length>=5&&!order(project).filter(isTrack).some(id=>!trackFor(project,id).trackAsset)} onClick={()=>{end();setChartTarget('new');}}>从谱面生成</button></div>
      <input className="project-name" aria-label="作品名称" maxLength={120} value={project.name} onFocus={begin} onBlur={end} onChange={e => change(next => {next.name=e.target.value;})}/>
      <div className={'save-state '+status.kind} role="status">{status.message}{status.kind==='error' && <button onClick={() => void queue.current?.flush().catch(()=>{})}>重试保存</button>}</div>
      <div className="history-buttons"><button aria-label="撤销" disabled={!history.current.canUndo()} onClick={() => undo()}>↶</button><button aria-label="重做" disabled={!history.current.canRedo()} onClick={() => undo(true)}>↷</button></div>
      <button className="primary export-trigger" onClick={() => {end();void loadExtras().then(()=>setExportOpen(true)).catch(e=>setError(String(e)));}}>导出图片 <span>↗</span></button>
      <button className="info-trigger" aria-label="信息" onClick={()=>{end();setInfoOpen(true);}}>ⓘ 信息</button>
    </header>
    {error && <div className="error-banner" role="alert">{error}<button aria-label="关闭提示" onClick={()=>setError('')}>×</button></div>}
    <div className="editor-layout">
      <aside id="objects-panel" className="objects-panel"><div className="panel-heading"><span>作品对象</span><span className="micro">{order(project).length} LAYERS</span></div>
        <div className="object-list" aria-label="对象图层列表">{order(project).map((id,index) => <div key={id} data-layer-id={id} className={'object-entry'+(layerTarget===id?' reorder-target':'')}>
          {compact&&id!=='bg'&&<button className="touch-reorder" aria-label={'拖动排序 '+nameFor(id)}
            onPointerDown={event=>{end();layerDrag.current={source:id,target:id};event.currentTarget.setPointerCapture(event.pointerId);}}
            onPointerMove={event=>{if(!layerDrag.current)return;const key=document.elementFromPoint(event.clientX,event.clientY)?.closest('[data-layer-id]')?.getAttribute('data-layer-id') as ObjectId|null;if(key&&order(project).includes(key)){layerDrag.current.target=key;setLayerTarget(key);}}}
            onPointerUp={event=>{const pending=layerDrag.current;layerDrag.current=null;setLayerTarget(null);if(event.currentTarget.hasPointerCapture(event.pointerId))event.currentTarget.releasePointerCapture(event.pointerId);if(pending&&pending.source!==pending.target)change(next=>reorderObject(next,pending.source,pending.target));}}
            onPointerCancel={()=>{layerDrag.current=null;setLayerTarget(null);}}>⠿</button>}
          <button data-object-id={id} className={'object-row '+(id===selected?'selected':'')} aria-pressed={id===selected} draggable={!compact&&id!=='bg'}
          onDragStart={event=>{end();event.dataTransfer.setData('text/plain',id);event.dataTransfer.effectAllowed='move';}}
          onDragOver={event=>{event.preventDefault();event.dataTransfer.dropEffect='move';}}
          onDrop={event=>{event.preventDefault();const source=event.dataTransfer.getData('text/plain');if(order(project).includes(source as ObjectId)){end();change(next=>reorderObject(next,source as ObjectId,id));}}}
          onClick={()=>{end();setSelected(id);setTrackMenu(null);}}>
          <span className={'object-symbol '+id}>{titleObject(id)?'T':isSticker(id)?'◇':isTrack(id)?'◈':'▧'}</span><span><strong>{nameFor(id)}</strong><small>{titleObject(id) ? titleFor(project,id).text || '点击输入文字' : isSticker(id)?'静态贴纸 · 可拖动排序':(id==='bg'?project.bgAsset:trackFor(project,id).trackAsset)?'已上传素材':'尚未上传'}</small></span><span className="layer-index">{id==='bg'?'锁定':String(index+1).padStart(2,'0')}</span></button>
          {isTrack(id)&&<><button className="object-menu-trigger" aria-label={nameFor(id)+'操作'} aria-expanded={trackMenu===id} onClick={()=>setTrackMenu(trackMenu===id?null:id)}>⋯</button>{trackMenu===id&&<div className="object-menu" role="menu"><button role="menuitem" disabled={!trackFor(project,id).trackAsset||trackFor(project,id).removeBackground} onClick={()=>openFusion(id)}>融合</button>{trackFor(project,id).generatedTrack&&<button role="menuitem" onClick={()=>{end();setTrackMenu(null);setChartTarget(id);}}>编辑谱面选段</button>}</div>}</>}
        </div>)}</div>
        <div className="object-actions"><button disabled={order(project).filter(titleObject).length>=5} onClick={()=>add('title')}>添加标题 <small>{order(project).filter(titleObject).length}/5</small></button>
          <button disabled={order(project).filter(isTrack).length>=5} onClick={()=>add('track')}>添加轨道 <small>{order(project).filter(isTrack).length}/5</small></button>
          <button onClick={()=>{end();setStickerOpen(true);}}>选择贴纸</button>
          <button aria-label="上移一层" disabled={selected==='bg'||order(project).indexOf(selected)===0} onClick={()=>shiftSelected(-1)}>↑</button><button aria-label="下移一层" disabled={selected==='bg'||order(project).indexOf(selected)>=order(project).length-2} onClick={()=>shiftSelected(1)}>↓</button>
          <button disabled={selected==='bg'} onClick={deleteSelected}>删除对象</button></div><p className="layer-help">拖动对象排序 · 上方覆盖下方 · 底图固定</p>
        <div className="local-note"><span className="local-dot"/>完全离线 · 保存在本机<button className="text-button" disabled={closing} onClick={()=>void shutdownApp()}>{closing?'正在退出…':'退出程序'}</button></div>
      </aside>
      <main className="workspace">
        <div className="canvas-toolbar"><div><span className="micro">CANVAS</span><span className="canvas-caption">画布预览</span></div><div className="ratio-switch">{(['16:9','4:3'] as Ratio[]).map(ratio=><button key={ratio} aria-pressed={project.activeRatio===ratio} onClick={()=>{end();commit(changeRatio(current.current!,ratio,assets));}}>{ratio}</button>)}</div><span className="dimensions">{size.width} × {size.height}</span></div>
        <div className="canvas-area"><div className={'canvas-stage'+(manipulating?' manipulating':'')} style={{aspectRatio:`${size.width}/${size.height}`,maxWidth:`calc((100vh - 235px) * ${size.width/size.height})`}}>
          <canvas ref={canvas} aria-label="封面画布" width={size.width} height={size.height} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerEnd} onPointerCancel={pointerEnd} onLostPointerCapture={pointerEnd}/>
          {box && !isGraphic(selected)&&<div className="selection-box" style={{left:box.x/size.width*100+'%',top:box.y/size.height*100+'%',width:box.width/size.width*100+'%',height:box.height/size.height*100+'%',transform:`rotate(${placement.rotation||0}deg)`}}><span className="selection-label">{nameFor(selected)}</span>{selected==='bg'?<span className="resize-handle"/>:<span className="rotation-handle" aria-label="旋转手柄"/>}</div>}
          {isGraphic(selected)&&geometry?.path&&<svg className="track-selection" aria-label={isSticker(selected)?'贴纸选中轮廓':'轨道选中轮廓'} viewBox={`0 0 ${size.width} ${size.height}`}><g transform={`rotate(${placement.rotation||0} ${pivot.x} ${pivot.y})`}><g transform={`translate(${placement.x-geometry.width*imagePosition(positions,selected).scale/2} ${placement.y-geometry.height*imagePosition(positions,selected).scale/2}) scale(${geometry.width/geometry.outlineWidth*imagePosition(positions,selected).scale} ${geometry.height/geometry.outlineHeight*imagePosition(positions,selected).scale})`}>
            <path d={geometry.path} fill="none" stroke="#000" strokeWidth="3" vectorEffect="non-scaling-stroke"/><path d={geometry.path} fill="none" stroke="#fff" strokeWidth="1.2" vectorEffect="non-scaling-stroke"/></g></g></svg>}
          {isGraphic(selected)&&box&&<div className="track-handles" aria-label="轨道缩放手柄" style={{left:box.x/size.width*100+'%',top:box.y/size.height*100+'%',width:box.width/size.width*100+'%',height:box.height/size.height*100+'%',transformOrigin:`${(pivot.x-box.x)/box.width*100}% ${(pivot.y-box.y)/box.height*100}%`,transform:`rotate(${placement.rotation||0}deg)`}}><span className="resize-handle"/><span className="rotation-handle" aria-label="旋转手柄"/></div>}
          {!project.bgAsset && !order(project).some(id=>titleObject(id)?titleFor(project,id).text:isGraphic(id)&&graphicAsset(project,id)) && <div className="empty-canvas"><span>◈</span><h2>从一张底图开始</h2><p>上传素材，制作你的下一张音游封面</p><button onClick={()=>backgroundInput.current?.click()}>选择底图</button></div>}
        </div></div>
        <footer className="canvas-footer"><span>{nameFor(selected)} · 拖动调整位置</span><span>{compact?'点击对象选择 · 拖动手柄缩放 / 旋转':'Ctrl + Z 撤销 · Ctrl + Shift + Z 重做'}</span></footer>
      </main>
      <aside id="properties-panel" className="properties-panel"><div className="panel-heading"><span>{propertyTab==='filters'?'PixiJS 滤镜':nameFor(selected)}</span><span className="micro">PROPERTIES</span></div>
        <div className="property-tabs"><button aria-pressed={propertyTab==='object'} onClick={()=>{end();setPropertyTab('object');}}>对象属性</button><button aria-pressed={propertyTab==='filters'} onClick={()=>{end();setPropertyTab('filters');}}>滤镜</button></div>
        <div className="properties-content">
          {compact&&mobilePanel==='effects'&&selected==='bg'&&<p className="mobile-effects-note">底图效果可在“滤镜”中调整。选择文字、轨道或贴纸可设置对应光效与阴影。</p>}
          {propertyTab==='filters'?<FilterPanel key={selected} actions={{project,assets,change,begin,end,getProject:()=>current.current!,addAsset:asset=>setAssets(previous=>({...previous,[asset.id]:asset})),addFonts:list=>setFonts(previous=>Array.from(new Map([...previous,...list].map(font=>[font.id,font])).values()))}} selected={selected} onError={setError}/>:<>
          {isTitle ? <><label className="field">标题内容<textarea aria-label="标题内容" rows={3} maxLength={300} placeholder={titleIndex===0?'输入曲名或主标题':'输入作者、难度或副标题'} value={project.titles[titleIndex].text} onFocus={begin} onBlur={end} onChange={e=>change(next=>{next.titles[titleIndex].text=e.target.value.replace(/[\r\n]+/g,' ');})}/></label>
            <label className="field">字体<select aria-label="字体" value={project.titles[titleIndex].fontId||'system'} onChange={event=>change(next=>{next.titles[titleIndex].fontId=event.target.value;})}>
              <optgroup label="内置离线字体">{builtinFonts.map(font=><option key={font.id} value={font.id}>{font.label}</option>)}</optgroup>
              {fonts.length>0&&<optgroup label="本机上传字体">{fonts.map(font=><option key={font.id} value={font.id}>{font.label}</option>)}</optgroup>}
            </select></label><button className="font-upload" disabled={uploading} onClick={()=>fontInput.current?.click()}>上传字体</button><p className="asset-meta">TTF / OTF / WOFF / WOFF2 · 最大 50 MB</p>
            <Text3DPanel key={'3d:'+selected} value={project.titles[titleIndex].text3d} begin={begin} end={end} onChange={value=>change(next=>{next.titles[titleIndex].text3d=value;})}/>
            <label className="color-field">文字颜色<ColorInput label="文字颜色" value={project.titles[titleIndex].color} begin={begin} end={end} onChange={value=>change(next=>{next.titles[titleIndex].color=value;})}/><span>{project.titles[titleIndex].color.toUpperCase()}</span></label>
            <NumberField label="字号" value={titlePosition(positions,selected as TitleId).fontSize} min={1} max={400} begin={begin} end={end} onChange={value=>change(next=>{titlePosition(layout(next),selected as TitleId).fontSize=value;})}/>
            <CollapsibleSettings key={selected} label="基础发光设置"><NumberField label="发光强度" value={project.titles[titleIndex].glow} min={0} max={100} begin={begin} end={end} onChange={value=>change(next=>{const title=next.titles[titleIndex];title.glow=value;if(title.effects){title.effects.outerGlow.intensity=value;title.effects.outerGlow.enabled=value>0;}})}/></CollapsibleSettings>
            <EffectsPanel value={project.titles[titleIndex].effects} glow={project.titles[titleIndex].glow} color={project.titles[titleIndex].color} begin={begin} end={end} onChange={effects=>change(next=>{next.titles[titleIndex].effects=effects;next.titles[titleIndex].glow=effects.outerGlow.enabled?effects.outerGlow.intensity:0;})}/>
            <ShadowPanel value={project.titles[titleIndex].shadow} begin={begin} end={end} onChange={shadow=>change(next=>{next.titles[titleIndex].shadow=shadow;})}/></> : <>
            {!isSticker(selected)&&<button className="replace-button" disabled={uploading} onClick={()=>(selected==='bg'?backgroundInput:trackInput).current?.click()}>{selectedAsset?'替换图片':'上传图片'}</button>}
            {selectedAsset && <p className="asset-meta">{selectedAsset.width} × {selectedAsset.height} px · 原始素材保留</p>}
            {isSticker(selected)&&<ShadowPanel value={project.stickers![selected].shadow} begin={begin} end={end} onChange={shadow=>change(next=>{next.stickers![selected].shadow=shadow;})}/>}
            {track && <><label className="color-field">图形颜色<ColorInput label="图形颜色" value={track.trackColor||'#ffffff'} begin={begin} end={end} onChange={value=>editTrack(next=>{next.trackColor=value;})}/><button className="text-button" onClick={()=>editTrack(next=>{next.trackColor=null;})}>恢复原色</button></label>
              <CollapsibleSettings key={'basic-glow:'+selected} label="基础发光设置"><NumberField label="发光强度" value={track.trackGlow} min={0} max={100} begin={begin} end={end} onChange={value=>editTrack(next=>{next.trackGlow=value;if(next.trackEffects){next.trackEffects.outerGlow.intensity=value;next.trackEffects.outerGlow.enabled=value>0;}})}/></CollapsibleSettings>
              <EffectsPanel value={track.trackEffects} glow={track.trackGlow} color={track.trackColor||'#ffffff'} begin={begin} end={end} onChange={effects=>editTrack(next=>{next.trackEffects=effects;next.trackGlow=effects.outerGlow.enabled?effects.outerGlow.intensity:0;})}/>
              <ShadowPanel value={track.trackShadow} begin={begin} end={end} onChange={shadow=>editTrack(next=>{next.trackShadow=shadow;})}/>
              <button className="fusion-open" disabled={!track.trackAsset||track.removeBackground} onClick={()=>{if(isTrack(selected))openFusion(selected);}}>融合图片</button>{track.removeBackground&&<p className="asset-meta">关闭自动去除背景后可融合原图。</p>}
              {feature ? <feature.TrackControls key={'track-controls:'+selected} {...actions} openMask={()=>setView('mask')} onError={setError}/> : <button disabled={!track.trackAsset} onClick={()=>void loadExtras().catch(e=>setError(String(e)))}>去背景与轨道修正</button>}
            </>}
            {selectedAsset && <><NumberField label="缩放 (%)" value={imagePosition(positions,selected as 'bg'|GraphicId).scale*100} min={.1} max={Math.max(500,imagePosition(positions,selected as 'bg'|GraphicId).scale*100)} step={.1} begin={begin} end={end} onChange={value=>change(next=>{imagePosition(layout(next),selected as 'bg'|GraphicId).scale=value/100;})}/>
              {isSticker(selected)&&<><NumberField label="贴纸宽度" value={selectedAsset.width*imagePosition(positions,selected).scale} min={1} max={5000} begin={begin} end={end} onChange={width=>change(next=>{imagePosition(layout(next),selected).scale=width/selectedAsset.width;})}/><NumberField label="贴纸高度" value={selectedAsset.height*imagePosition(positions,selected).scale} min={1} max={5000} begin={begin} end={end} onChange={height=>change(next=>{imagePosition(layout(next),selected).scale=height/selectedAsset.height;})}/></>}
              {selected==='bg' && <button onClick={()=>change(next=>{layout(next).bg={x:size.width/2,y:size.height/2,scale:fitScale(selectedAsset,size)};})}>铺满画布</button>}</>}
          </>}
          {selected!=='bg'&&<NumberField label="旋转角度" value={placement.rotation||0} min={-180} max={180} begin={begin} end={end} onChange={value=>change(next=>{position(layout(next),selected).rotation=value;})}/>}
          <div className="section-label">位置 <span>画布像素</span></div>
          <NumberField label="水平位置" value={placement.x} min={-5000} max={5000} begin={begin} end={end} onChange={value=>change(next=>{position(layout(next),selected).x=value;})}/>
          <NumberField label="垂直位置" value={placement.y} min={-5000} max={5000} begin={begin} end={end} onChange={value=>change(next=>{position(layout(next),selected).y=value;})}/>
          <p className="property-note">所有调整实时预览，保存成功后可在下次打开时继续编辑。</p>
          </>}
        </div>
      </aside>
    </div>
    <nav className="mobile-tabs" role="tablist" aria-label="手机编辑栏目">{([['objects','对象'],['properties','属性'],['effects','光效'],['filters','滤镜']] as const).map(([panel,label])=><button key={panel} role="tab" aria-selected={mobilePanel===panel} aria-controls={panel==='objects'?'objects-panel':'properties-panel'} onClick={()=>{if(document.activeElement instanceof HTMLElement)document.activeElement.blur();end();setMobilePanel(panel);setPropertyTab(panel==='filters'?'filters':'object');}}>{label}</button>)}</nav>
    <input ref={backgroundInput} aria-label="底图文件" type="file" accept="image/png,image/jpeg" hidden onChange={e=>{void uploadObject(e.target.files?.[0],'bg');e.target.value='';}}/>
    <input ref={trackInput} aria-label="轨道文件" type="file" accept="image/png,image/jpeg" hidden onChange={e=>{uploadTrack(e.target.files?.[0]);e.target.value='';}}/>
    <input ref={fontInput} aria-label="字体文件" type="file" accept=".ttf,.otf,.woff,.woff2" hidden onChange={event=>{void uploadFont(event.target.files?.[0]);event.target.value='';}}/>
    {uploading && <div className="busy-toast" role="status">正在读取并保存素材…</div>}
    {feature && view==='mask' && <feature.MaskEditor key={selected} {...actions} close={()=>setView('editor')} onError={setError}/>}
    {feature && exportOpen && <feature.ExportDialog project={project} close={()=>setExportOpen(false)} onError={setError}/>}
    {stickerOpen&&<StickerPicker close={()=>setStickerOpen(false)} onError={setError} add={(item:Sticker,asset:Asset)=>{setAssets(previous=>({...previous,[asset.id]:asset}));let id:ObjectId|null=null;change(next=>{id=addSticker(next,item,asset);});if(id)setSelected(id);}}/>}
    {fusionTarget&&<FusionEditor project={project} trackId={fusionTarget} close={()=>setFusionTarget(null)} onError={setError} apply={(fusion,asset)=>{if(asset)setAssets(previous=>({...previous,[asset.id]:asset}));change(next=>{if(order(next).includes(fusionTarget))trackFor(next,fusionTarget).fusion=fusion;});}}/>}
    {infoOpen&&<InfoDialog close={()=>setInfoOpen(false)}/>}
    {chartTarget&&<ChartEditor availableTitles={titleCapacity(project)} initial={chartTarget==='new'?null:trackFor(project,chartTarget).generatedTrack} close={()=>setChartTarget(null)} apply={(asset,recipe,texts)=>{
      if(texts.length>titleCapacity(current.current!))throw new Error('标题名额不足，现有内容已保留');
      end();
      setAssets(previous=>({...previous,[asset.id]:asset}));let target:TrackId|null=null;
      change(next=>{
        target=chartTarget==='new'?(order(next).filter(isTrack).find(id=>!trackFor(next,id).trackAsset)||addObject(next,'track') as TrackId|null):chartTarget;
        if(!target||!order(next).includes(target))throw new Error('轨道名额不足，现有内容已保留');
        addChartTitles(next,texts);
        const item=trackFor(next,target),old=assets[item.trackAsset||''];
        item.trackAsset=asset.id;item.generatedTrack=recipe;item.maskAsset=null;item.baseMaskAsset=null;item.removeBackground=false;item.fusion=null;
        for(const ratio of ['16:9','4:3'] as Ratio[]){const places=next.layouts[ratio];if(!places)continue;const size=dimensions(ratio),p=imagePosition(places,target);
          if(chartTarget==='new'){Object.assign(p,{x:size.width/2,y:size.height/2,scale:fitScale(asset,size,false)*.8,rotation:0});}
          else if(old)p.scale*=Math.max(old.width,old.height)/Math.max(asset.width,asset.height);
        }
      });if(target)setSelected(target);
    }}/>}
  </div>;
}
