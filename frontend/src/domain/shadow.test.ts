import {it,expect} from 'vitest';
import {resolveShadow,shadowOffset} from './shadow';
it('defaults old objects to no shadow and maps light direction to an offset',()=>{
  const old=resolveShadow();expect(old.enabled).toBe(false);
  expect(shadowOffset({...old,distance:30,direction:0})).toEqual({x:30,y:0});
  expect(shadowOffset({...old,distance:30,direction:90}).y).toBeCloseTo(30);
  expect(shadowOffset({...old,distance:30,direction:180}).x).toBeCloseTo(-30);
});
