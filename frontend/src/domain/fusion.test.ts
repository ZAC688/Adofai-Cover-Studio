import {expect,it} from 'vitest';
import {resolveFusion,blendOperation,newGradientFusion,gradientAlpha} from './fusion';
it('preserves independent blend configuration and keeps old tracks neutral',()=>{
  expect(resolveFusion()).toEqual({enabled:true,maskAsset:null,mode:'normal',opacity:100});
  expect(blendOperation('normal')).toBe('source-over');expect(blendOperation('add')).toBe('lighter');expect(blendOperation('screen')).toBe('screen');
  expect(resolveFusion({enabled:false,maskAsset:'mask',mode:'multiply',opacity:37}).enabled).toBe(false);
});
it('produces a smooth oriented reversible gradient without blurring the endpoints',()=>{
  const s={...newGradientFusion(),width:100};
  expect(gradientAlpha(0,50,200,100,s)).toBe(0);expect(gradientAlpha(200,50,200,100,s)).toBe(255);
  expect(gradientAlpha(100,50,200,100,s)).toBe(128);
  const ramp=Array.from({length:201},(_,x)=>gradientAlpha(x,50,200,100,s));
  expect(ramp.every((v,i)=>!i||v>=ramp[i-1]&&v-ramp[i-1]<=2)).toBe(true);
  expect(gradientAlpha(25,50,200,100,{...s,reverse:true})).toBe(255-gradientAlpha(25,50,200,100,s));
  expect(gradientAlpha(100,0,200,100,{...s,angle:90})).toBe(0);expect(gradientAlpha(100,100,200,100,{...s,angle:90})).toBe(255);
  expect(gradientAlpha(100,50,200,100,{...s,position:75,width:20})).toBe(0);
});
