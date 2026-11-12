import {NumberField} from '../App';
import {ColorInput} from './ColorInput';
import {CollapsibleSettings} from './EffectsPanel';
import {resolveShadow,type Shadow} from '../domain/shadow';

export function ShadowPanel({value,onChange,begin,end}:{value?:Shadow|null;onChange:(value:Shadow)=>void;begin:()=>void;end:()=>void}){
  const settings=resolveShadow(value);const update=(change:Partial<Shadow>)=>onChange({...settings,...change});
  return <section className="shadow-panel"><label className="effect-switch">阴影<input aria-label="阴影开关" type="checkbox" checked={settings.enabled} onChange={event=>{end();update({enabled:event.target.checked});}}/></label>
    {settings.enabled&&<CollapsibleSettings label="阴影参数"><label className="color-field">阴影颜色<ColorInput label="阴影颜色" value={settings.color} begin={begin} end={end} onChange={color=>update({color})}/></label>
      <NumberField label="阴影不透明度" value={settings.opacity} min={0} max={100} onChange={opacity=>update({opacity})} begin={begin} end={end}/>
      <NumberField label="阴影模糊" value={settings.blur} min={0} max={180} onChange={blur=>update({blur})} begin={begin} end={end}/>
      <NumberField label="阴影距离" value={settings.distance} min={0} max={500} onChange={distance=>update({distance})} begin={begin} end={end}/>
      <NumberField label="阴影方向" value={settings.direction} min={0} max={360} onChange={direction=>update({direction})} begin={begin} end={end}/>
    </CollapsibleSettings>}
  </section>;
}
