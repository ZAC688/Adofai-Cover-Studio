import {effectNames,resolveEffects,type EffectKind,type Effects,type Effect} from '../domain/effects';
import {NumberField} from '../App';
import {ColorInput} from './ColorInput';
import {useState,type ReactNode} from 'react';

export function CollapsibleSettings({label,children}:{label:string;children:ReactNode}){
  const [expanded,setExpanded]=useState(true);
  return <section className="collapsible-settings"><button className="settings-toggle" aria-expanded={expanded} onClick={()=>setExpanded(!expanded)}>{label}<span>{expanded?'−':'+'}</span></button>{expanded&&children}</section>;
}

export function EffectsPanel({value,glow,color,onChange,begin,end}:{value?:Effects|null;glow:number;color:string;
  onChange:(value:Effects)=>void;begin:()=>void;end:()=>void}){
  const settings=resolveEffects(value,glow,color);
  const [collapsed,setCollapsed]=useState<Partial<Record<EffectKind,boolean>>>({});
  function update(kind:EffectKind,change:Partial<Effect>){const next=structuredClone(settings);Object.assign(next[kind],change);onChange(next);}
  return <details className="effects-panel"><summary>光效模块 · 可叠加</summary>
    {(Object.keys(effectNames) as EffectKind[]).map(kind=>{const effect=settings[kind],name=effectNames[kind];return <div className="effect-module" key={kind} data-effect={kind}>
      <div className="effect-heading"><label className="effect-switch">{name}<input aria-label={name+'开关'} type="checkbox" checked={effect.enabled} onChange={event=>{update(kind,{enabled:event.target.checked});if(event.target.checked)setCollapsed(previous=>({...previous,[kind]:false}));}}/></label>
        {effect.enabled&&<button className="settings-toggle" aria-label={name+'参数'} aria-expanded={!collapsed[kind]} onClick={()=>{end();setCollapsed(previous=>({...previous,[kind]:!previous[kind]}));}}>{collapsed[kind]?'展开':'折叠'}</button>}</div>
      {effect.enabled&&!collapsed[kind]&&<div className="effect-options">
        {kind!=='gradient'&&<label className="effect-switch">跟随渐变填充<input aria-label={name+'跟随渐变填充'} type="checkbox" checked={!!effect.followGradient} onChange={event=>update(kind,{followGradient:event.target.checked})}/></label>}
        {kind!=='gradient'&&effect.followGradient?<p className="asset-meta">使用渐变填充的方向和两端颜色，填充关闭时仍生效。</p>:<label className="color-field">{name}颜色<ColorInput label={name+'颜色'} value={effect.color} begin={begin} end={end} onChange={color=>update(kind,{color})}/></label>}
        {kind==='gradient'&&<label className="color-field">渐变终点颜色<ColorInput label="渐变终点颜色" value={effect.color2} begin={begin} end={end} onChange={color2=>update(kind,{color2})}/></label>}
        <NumberField label={name+'强度'} value={effect.intensity} min={0} max={100} begin={begin} end={end} onChange={intensity=>update(kind,{intensity})}/>
        {kind!=='gradient'&&<NumberField label={name+'半径'} value={effect.radius} min={0} max={180} begin={begin} end={end} onChange={radius=>update(kind,{radius})}/>}
        {kind==='stroke'&&<NumberField label="描边宽度" value={effect.width} min={0} max={80} begin={begin} end={end} onChange={width=>update(kind,{width})}/>}
        {(kind==='gradient'||kind==='bevel')&&<NumberField label={kind==='gradient'?'渐变方向':'高光方向'} value={effect.direction} min={0} max={360} begin={begin} end={end} onChange={direction=>update(kind,{direction})}/>}
        {kind!=='gradient'&&<label className="field">混合模式<select aria-label={name+'混合模式'} value={effect.blend} onChange={event=>update(kind,{blend:event.target.value as Effect['blend']})}><option value="screen">Screen · 滤色</option><option value="add">Add · 叠加发光</option></select></label>}
      </div>}
    </div>;})}
  </details>;
}
