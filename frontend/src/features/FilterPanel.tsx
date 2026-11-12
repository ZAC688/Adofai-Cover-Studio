import {useState} from 'react';
import type {EditorActions} from '../App';
import {NumberField} from '../App';
import {filterCatalog,newFilter,defaultParameters,defaultRegion,parameterLabels,type FilterSpec,type Parameter,type Value} from '../domain/filters';
import {order,objectName,isTitle} from '../domain/objects';
import type {ObjectId} from '../domain/project';
import {upload} from '../services/api';
import {FilterRangeEditor} from './FilterRangeEditor';
import {ColorInput} from './ColorInput';
import {filterSlider} from '../domain/filterSlider';
import {FilterPresets} from './FilterPresets';
import {TextPresets} from './TextPresets';

function StructuredField({label,value,onChange}:{label:string;value:Value;onChange:(value:Value)=>void}){
  const [raw,setRaw]=useState(JSON.stringify(value)),[error,setError]=useState('');
  return <label className="field">{label}<textarea aria-label={label} rows={4} value={raw} onChange={event=>setRaw(event.target.value)} onBlur={()=>{try{const parsed=JSON.parse(raw);if(!Array.isArray(parsed))throw new Error('请填写数组');onChange(parsed);setError('');}catch{setError('请填写有效的参数数组');}}}/>{error&&<small role="alert">{error}</small>}</label>;
}
function ParameterField({type,field,value,onChange,actions,onError}:{type:string;field:Parameter;value:Value;onChange:(value:Value)=>void;actions:EditorActions;onError:(value:string)=>void}){
  const [uploading,setUploading]=useState(false);
  const label=parameterLabels[field.key]||field.key,{begin,end}=actions;
  if(field.type==='boolean')return <label className="effect-switch">{label}<input aria-label={label} type="checkbox" checked={!!value} onChange={event=>{end();onChange(event.target.checked);}}/></label>;
  if(field.type==='number')return <NumberField label={label} value={Number(value)} min={field.min} max={field.max} step={field.step} slider={filterSlider(type,field)} begin={begin} end={end} onChange={value=>onChange(field.step>=1?Math.min(field.max,Math.max(field.min,field.min+Math.round((value-field.min)/field.step)*field.step)):value)}/>;
  if(field.type==='color')return <label className="color-field">{label}<ColorInput label={label} value={String(value)} begin={begin} end={end} onChange={onChange}/></label>;
  if(field.type==='select'||field.type==='enum')return <label className="field">{label}<select aria-label={label} value={String(value)} onChange={event=>onChange(field.type==='enum'?Number(event.target.value):event.target.value)}>{field.options!.map(option=><option key={option} value={option}>{field.key==='type'?['线性','径向','锥形'][Number(option)]:field.key==='fillMode'?['透明','原图','循环','限制边缘','镜像'][Number(option)]:option}</option>)}</select></label>;
  if(field.type==='point'){const point=value as {x:number;y:number};return <div className="filter-point"><NumberField label={label+' X'} value={point.x} min={field.min} max={field.max} step={.01} slider={filterSlider(type,field)} begin={begin} end={end} onChange={x=>onChange({...point,x})}/><NumberField label={label+' Y'} value={point.y} min={field.min} max={field.max} step={.01} slider={filterSlider(type,field)} begin={begin} end={end} onChange={y=>onChange({...point,y})}/></div>;}
  if(field.type==='texture')return <label className="field">{label}<input aria-label={label+'图片'} aria-busy={uploading} disabled={uploading} type="file" accept="image/png,image/jpeg" onChange={event=>{const file=event.target.files?.[0];if(file){setUploading(true);void upload(file).then(asset=>{if(field.key==='colorMap'&&asset.width!==asset.height**2)throw new Error('色彩查找表应为 N² × N，例如 256 × 16');actions.addAsset(asset);onChange(asset.id);}).catch(error=>onError(String(error))).finally(()=>setUploading(false));}event.target.value='';}}/><small>{uploading?'正在保存贴图…':value?'已选择本机图片':'使用内置示例贴图'} · 最大 10 MB</small>{value&&<button onClick={()=>onChange(null)}>恢复示例贴图</button>}</label>;
  if(field.key==='stops'){
    const stops=value as {offset:number;color:number|string;alpha:number}[];
    const color=(value:number|string)=>typeof value==='number'?'#'+value.toString(16).padStart(6,'0'):value;
    const edit=(index:number,part:Partial<typeof stops[number]>)=>onChange(stops.map((stop,i)=>i===index?{...stop,...part}:stop));
    return <div className="filter-stops">{stops.map((stop,index)=><div key={index}><label className="color-field">色标 {index+1}<ColorInput label={'色标'+(index+1)+'颜色'} value={color(stop.color)} begin={begin} end={end} onChange={value=>edit(index,{color:value})}/></label><NumberField label={'色标'+(index+1)+'位置'} value={stop.offset} min={0} max={1} step={.01} begin={begin} end={end} onChange={offset=>edit(index,{offset})}/><NumberField label={'色标'+(index+1)+'浓度'} value={stop.alpha} min={0} max={1} step={.01} begin={begin} end={end} onChange={alpha=>edit(index,{alpha})}/><button disabled={stops.length<=2} onClick={()=>{end();onChange(stops.filter((_,i)=>i!==index));}}>删除色标</button></div>)}<button disabled={stops.length>=32} onClick={()=>{end();onChange([...stops,{offset:.5,color:'#ffffff',alpha:1}]);}}>添加色标</button></div>;
  }
  if(field.key==='replacements'){
    const pairs=value as (string|number)[][];const color=(value:number|string)=>typeof value==='number'?'#'+value.toString(16).padStart(6,'0'):value;
    return <div>{pairs.map((pair,index)=><div key={index}>{pair.map((part,side)=><label className="color-field" key={side}>{side?'替换为':'原颜色'}<ColorInput label={'替换组'+(index+1)+(side?'目标':'原色')} value={color(part)} begin={begin} end={end} onChange={color=>onChange(pairs.map((value,i)=>i===index?value.map((old,j)=>j===side?color:old):value))}/></label>)}<button disabled={pairs.length<=1} onClick={()=>onChange(pairs.filter((_,i)=>i!==index))}>删除替换组</button></div>)}<button disabled={pairs.length>=32} onClick={()=>onChange([...pairs,['#ffffff','#000000']])}>添加替换组</button></div>;
  }
  if(Array.isArray(value)&&value.length&&value.every(part=>typeof part==='number'))return <div className="filter-vector">{value.map((part,index)=><label key={index}>{label} {index+1}<input aria-label={label+' '+(index+1)} type="number" min={-10000} max={10000} step={.1} value={Number(part)} onFocus={begin} onBlur={end} onChange={event=>{const next=Number(event.target.value);if(event.target.value!==''&&Number.isFinite(next))onChange(value.map((old,i)=>i===index?next:old));}}/></label>)}</div>;
  return <StructuredField key={field.key+JSON.stringify(value)} label={label} value={value} onChange={onChange}/>;
}
export function FilterPanel({actions,selected,onError}:{actions:EditorActions;selected:ObjectId;onError:(value:string)=>void}){
  const [type,setType]=useState(filterCatalog[0].type),[editing,setEditing]=useState<string|null>(null);
  const [scope,setScope]=useState<'object'|'canvas'>('object'),[expanded,setExpanded]=useState(true),[collapsed,setCollapsed]=useState<Record<string,boolean>>({});
  const {project,change,end}=actions,list=project.filters||[];
  const target=scope==='canvas'?'canvas':selected;
  const visible=list.filter(filter=>filter.targets.includes(target));
  const update=(id:string,mutate:(filter:FilterSpec)=>void)=>change(next=>{const filter=next.filters?.find(filter=>filter.id===id);if(filter)mutate(filter);});
  function move(index:number,delta:number){end();change(next=>{const filters=next.filters!,a=filters.findIndex(item=>item.id===visible[index].id),b=filters.findIndex(item=>item.id===visible[index+delta].id);[filters[a],filters[b]]=[filters[b],filters[a]];});}
  const active=list.find(filter=>filter.id===editing);
  return <section className="filters-panel"><p className="asset-meta">38 种 PixiJS 滤镜 · 离线处理 · 按列表从上到下叠加</p>
    <label className="field">管理范围<select aria-label="滤镜管理范围" value={scope} onChange={event=>{end();setCollapsed({});setScope(event.target.value as typeof scope);}}><option value="object">当前对象 · {objectName(project,selected)}</option><option value="canvas">整张画布</option></select></label>
    {isTitle(selected)&&target===selected&&<TextPresets key={'text-'+target} actions={actions} target={selected} onError={onError}/>}
    <FilterPresets key={target} actions={actions} target={target} onError={onError}/>
    <label className="field">选择滤镜<select aria-label="选择滤镜" value={type} onChange={event=>setType(event.target.value)}>{filterCatalog.map(entry=><option key={entry.type} value={entry.type}>{entry.label} · {entry.type}</option>)}</select></label>
    <button className="primary" onClick={()=>{end();setExpanded(true);const filter=newFilter(type,target);setCollapsed(previous=>({...previous,[filter.id]:false}));change(next=>{(next.filters??=[]).push(filter);});}}>添加滤镜</button>
    <button className="settings-toggle filter-list-toggle" aria-label="滤镜列表" aria-expanded={expanded} onClick={()=>{end();setExpanded(!expanded);}}>滤镜列表 · {visible.length}<span>{expanded?'−':'+'}</span></button>
    {expanded&&visible.map((filter,index)=>{const entry=filterCatalog.find(entry=>entry.type===filter.type)!;const region=filter.regions[project.activeRatio]||defaultRegion();return <details className="filter-entry" key={filter.id} data-filter-id={filter.id} open={collapsed[filter.id]===false} onToggle={event=>{const closed=!event.currentTarget.open;setCollapsed(previous=>previous[filter.id]===closed?previous:{...previous,[filter.id]:closed});}}><summary>{entry.label}<span>{index+1} {collapsed[filter.id]===false?'−':'+'}</span></summary>
      <label className="effect-switch">启用滤镜<input aria-label="启用滤镜" type="checkbox" checked={filter.enabled} onChange={event=>{end();update(filter.id,filter=>{filter.enabled=event.target.checked;});}}/></label>
      <div className="filter-actions"><button aria-label="上移滤镜" disabled={!index} onClick={()=>move(index,-1)}>↑</button><button aria-label="下移滤镜" disabled={index===visible.length-1} onClick={()=>move(index,1)}>↓</button><button onClick={()=>{end();update(filter.id,filter=>{filter.params=defaultParameters(filter.type);});}}>恢复默认参数</button><button onClick={()=>{end();change(next=>{next.filters=next.filters!.filter(item=>item.id!==filter.id);});}}>删除滤镜</button></div>
      <label className="field">作用范围<select aria-label="滤镜作用范围" value={filter.targets.includes('canvas')?'canvas':'objects'} onChange={event=>{end();const canvas=event.target.value==='canvas';update(filter.id,filter=>{filter.targets=canvas?['canvas']:[selected];});setScope(canvas?'canvas':'object');}}><option value="canvas">整张画布</option><option value="objects">指定对象</option></select></label>
      {!filter.targets.includes('canvas')&&<div className="filter-targets">{order(project).map(id=><label key={id}><input aria-label={'滤镜目标 '+objectName(project,id)} type="checkbox" checked={filter.targets.includes(id)} disabled={filter.targets.length===1&&filter.targets[0]===id} onChange={event=>update(filter.id,filter=>{filter.targets=event.target.checked?[...filter.targets,id]:filter.targets.filter(target=>target!==id);})}/>{objectName(project,id)}</label>)}</div>}
      <label className="field">局部区域<select aria-label="滤镜局部区域" value={region.mode} onChange={event=>update(filter.id,filter=>{filter.regions[project.activeRatio]={...region,mode:event.target.value as typeof region.mode};})}><option value="all">整个目标</option><option value="rect">矩形框选</option><option value="paint">柔边涂抹</option></select></label>
      {region.mode!=='all'&&<button onClick={()=>{end();setEditing(filter.id);}}>编辑滤镜范围</button>}
      <div className="filter-parameters">{entry.fields.map(field=><ParameterField key={field.key} type={filter.type} field={field} value={filter.params[field.key]??field.value} onChange={value=>update(filter.id,filter=>{filter.params[field.key]=value;})} actions={actions} onError={onError}/>)}</div>
    </details>;})}
    {active&&<FilterRangeEditor project={project} filter={active} close={()=>setEditing(null)} onError={onError} apply={(region,asset)=>{if(asset)actions.addAsset(asset);update(active.id,filter=>{filter.regions[project.activeRatio]=region;});}}/>}
  </section>;
}
