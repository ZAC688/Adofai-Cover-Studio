import {expect,it} from 'vitest';
import {filterCatalog} from './filters';
import {filterSlider,fineSlider} from './filterSlider';
it('provides bounded practical ranges for every numeric slider without changing storage limits',()=>{
  for(const filter of filterCatalog)for(const field of filter.fields.filter(f=>['number','point'].includes(f.type))){
    const range=filterSlider(filter.type,field);expect(range.min).toBeGreaterThanOrEqual(field.min);expect(range.max).toBeLessThanOrEqual(field.max);expect(range.max).toBeGreaterThan(range.min);expect(range.step).toBeGreaterThan(0);
    if(field.step>=1)expect(range.step).toBe(field.step);
  }
  const brightness=filterCatalog[0].fields.find(f=>f.key==='brightness')!;
  expect(filterSlider('AdjustmentFilter',brightness)).toEqual({min:0,max:5,step:.01});expect(brightness.max).toBe(10000);
});
it('zooms around the actual value, including numbers outside the normal slider range',()=>{
  expect(fineSlider(1,{min:0,max:5,step:.01},{min:-10000,max:10000})).toEqual({min:.75,max:1.25,step:.001});
  const large=fineSlider(999,{min:0,max:5,step:.01},{min:-10000,max:10000});expect(large.min).toBeLessThan(999);expect(large.max).toBeGreaterThan(999);
});
