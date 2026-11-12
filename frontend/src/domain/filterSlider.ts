import type {Parameter} from './filters';
export type SliderRange={min:number;max:number;step:number};
/** Common editing ranges are independent of the full validated numeric range. */
export function filterSlider(type:string,field:Parameter):SliderRange{
  const key=field.key,value=typeof field.value==='number'?field.value:0;
  let min=field.min,max=field.max,step=field.step;
  if(field.max-field.min>25){
    if(/^(rotation|direction|hue|angle)$/.test(key)){min=-180;max=180;step=.1;}
    else if(/^(gamma|contrast|saturation|brightness|red|green|blue|bloomScale|resolution|gain|lacunarity|scale|curvature)$/.test(key)){min=0;max=5;step=.01;}
    else if(/^(noise|lineContrast|vignetting|vignettingBlur|sepia|scratch|scratchDensity|lightness)$/.test(key)){min=0;max=1;step=.01;}
    else if(/^(outerStrength|innerStrength|strength)$/.test(key)){min=0;max=20;step=.01;}
    else if(/^(thickness|lineWidth|noiseSize|scratchWidth|minSize)$/.test(key)){min=0;max=20;step=.1;}
    else if(key==='time'){min=0;max=5;step=.01;}
    else if(key==='step'){min=-1;max=1;step=.01;}
    else if(key==='offset'||key.startsWith('offset')){min=-200;max=200;step=.1;}
    else if(key==='radius'||key==='innerRadius'){min=-1;max=600;step=1;}
    else if(/blur/i.test(key)){min=0;max=Math.max(40,value*2);step=.1;}
    else if(key==='slices'||key==='maxColors'){min=field.min;max=32;step=1;}
    else if(key==='sampleSize'){min=1;max=512;step=1;}
    else{min=0;max=Math.max(40,Math.abs(value)*2);step=.1;}
  }
  if(type==='HslAdjustmentFilter'&&/^(saturation|lightness)$/.test(key)){min=-1;max=1;step=.01;}
  if(type==='TwistFilter'&&key==='angle'){min=-8;max=8;step=.01;}
  if(type==='ZoomBlurFilter'&&key==='strength'){min=0;max=1;step=.001;}
  if(field.type==='point'){
    min=field.min===0&&field.max===1?0:key==='size'?.01:-100;
    max=field.max===1?1:key==='size'?80:100;step=field.max===1?.001:.1;
  }
  return {min:Math.max(field.min,min),max:Math.min(field.max,max),step:field.step>=1?field.step:step};
}
export function fineSlider(value:number,range:SliderRange,limits:{min:number;max:number}):SliderRange{
  const span=Math.max(range.step*20,(range.max-range.min)/10);
  return {min:Math.max(limits.min,Number((value-span/2).toFixed(6))),max:Math.min(limits.max,Number((value+span/2).toFixed(6))),step:range.step>=1?range.step:range.step/10};
}
