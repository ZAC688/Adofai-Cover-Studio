import {NumberField} from '../App';
import {ColorInput} from './ColorInput';
import {defaultText3D,type Text3D} from '../domain/text3d';
export function Text3DPanel({value,onChange,begin,end}:{value?:Text3D|null;onChange:(next:Text3D)=>void;begin:()=>void;end:()=>void}){
  const settings=value||defaultText3D(),edit=(part:Partial<Text3D>)=>onChange({...settings,...part});
  return <section className="text3d-panel"><button className="mode3d-toggle" aria-label="3D文字模式" aria-pressed={settings.enabled} onClick={()=>{end();edit({enabled:!settings.enabled});}}>{settings.enabled?'切回普通文字':'一键生成 3D 文字'}</button>
    {settings.enabled&&<details open><summary>3D 配置</summary><p className="asset-meta">文字颜色作为正面颜色。厚度与倒角以字号的百分比计算，随画幅缩放。</p>
      <label className="color-field">侧面颜色<ColorInput label="3D侧面颜色" value={settings.sideColor} begin={begin} end={end} onChange={sideColor=>edit({sideColor})}/></label>
      {([
        ['depth','3D厚度 (%)',0,200,.1],['bevel','3D倒角 (%)',0,10,.1],
        ['rotationX','3D旋转 X',-180,180,.1],['rotationY','3D旋转 Y',-180,180,.1],['rotationZ','3D旋转 Z',-180,180,.1],
        ['perspective','3D透视强度',0,100,1],['lightDirection','3D光照方向',-180,180,1],['lightElevation','3D光照高度',-90,90,1],
        ['lightIntensity','3D光照强度',0,8,.01],['ambientIntensity','3D环境光强度',0,3,.01],
      ] as const).map(([key,label,min,max,step])=><NumberField key={key} label={label} value={settings[key]} min={min} max={max} step={step} begin={begin} end={end} onChange={value=>edit({[key]:value})}/>)}
      <button onClick={()=>{end();onChange({...defaultText3D(),enabled:true});}}>恢复默认3D配置</button>
    </details>}
  </section>;
}
