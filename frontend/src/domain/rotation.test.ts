import {expect,it} from 'vitest';
import {rotatePoint,boxContains,normalizeDegrees} from './rotation';
it('rotates and inverts around the same pivot',()=>{
  const point={x:130,y:50},pivot={x:100,y:50};
  const rotated=rotatePoint(point,pivot,90);
  expect(rotated.x).toBeCloseTo(100);expect(rotated.y).toBeCloseTo(80);
  const inverse=rotatePoint(rotated,pivot,-90);expect(inverse.x).toBeCloseTo(point.x);expect(inverse.y).toBeCloseTo(point.y);
});
it('hit testing follows rotated text and angles wrap at full turns',()=>{
  const box={x:100,y:100,width:200,height:40};
  expect(boxContains(box,{x:200,y:200},90)).toBe(true);
  expect(boxContains(box,{x:110,y:120},90)).toBe(false);
  expect(normalizeDegrees(450)).toBe(90);expect(normalizeDegrees(-450)).toBe(-90);
});
