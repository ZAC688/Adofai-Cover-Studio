import {expect,it} from 'vitest';
import {distances,horizontalPass,resolveEffects,gradientFraction} from './effects';
it('initializes independent effects without losing legacy glow',()=>{
  const first=resolveEffects(null,40,'#ff0000'),second=resolveEffects(null,0,'#ffffff');
  expect(first.outerGlow.enabled).toBe(true);expect(first.outerGlow.intensity).toBe(40);
  first.bloom.enabled=true;expect(second.bloom.enabled).toBe(false);
  expect(Object.values(second).every(effect=>!effect.enabled)).toBe(true);
  expect(second.outerGlow.intensity).toBeGreaterThan(0);
});
it('horizontal blur never leaks into adjacent rows',()=>{
  const input=new Float32Array([0,0,0,0,255,0,0,0,0]);
  expect(Array.from(horizontalPass(input,3,3,1))).toEqual([0,0,0,85,85,85,0,0,0]);
});
it('distance fields distinguish exterior and interior edges',()=>{
  const alpha=new Uint8ClampedArray(25);for(let y=1;y<4;y++)for(let x=1;x<4;x++)alpha[y*5+x]=255;
  const outside=distances(alpha,5,5,true),inside=distances(alpha,5,5,false);
  expect(outside[12]).toBe(0);expect(outside[0]).toBeCloseTo(Math.SQRT2);
  expect(inside[12]).toBe(2);expect(inside[0]).toBe(0);
});
it('aligns a shared gradient across the body and clamps light outside it',()=>{
  expect(gradientFraction(-50,0,100,20,0)).toBe(0);expect(gradientFraction(50,0,100,20,0)).toBe(1);
  expect(gradientFraction(0,-10,100,20,90)).toBeCloseTo(0);expect(gradientFraction(0,10,100,20,90)).toBeCloseTo(1);
  expect(gradientFraction(0,0,100,20,45)).toBe(.5);expect(gradientFraction(-500,0,100,20,0)).toBe(0);
  expect(resolveEffects(null,20,'#fff').bloom.followGradient).toBe(false);
});
