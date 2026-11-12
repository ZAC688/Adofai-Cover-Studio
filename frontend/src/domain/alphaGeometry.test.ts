import {it,expect} from 'vitest';
import {alphaBounds,alphaContour} from './alphaGeometry';
it('bounds exclude transparent padding and an empty image has no outline',()=>{
  const alpha=new Uint8ClampedArray(64);alpha[3*8+2]=255;alpha[4*8+4]=200;
  expect(alphaBounds(alpha,8,8)).toEqual({x:2,y:3,width:3,height:2});
  expect(alphaBounds(new Uint8ClampedArray(9),3,3)).toBeNull();
  expect(alphaContour(new Uint8ClampedArray(9),3,3)).toBe('');
});
it('traces concavity rather than the bounding rectangle',()=>{
  const alpha=new Uint8ClampedArray([255,0,0,255,0,0,255,255,255]);
  const path=alphaContour(alpha,3,3);
  expect(path).toContain('1,2');expect(path.match(/L/g)!.length).toBeGreaterThan(3);
});
it('keeps interior holes as separate closed contours',()=>{
  const alpha=new Uint8ClampedArray(25).fill(255);alpha[12]=0;
  expect(alphaContour(alpha,5,5).match(/M/g)).toHaveLength(2);
});
