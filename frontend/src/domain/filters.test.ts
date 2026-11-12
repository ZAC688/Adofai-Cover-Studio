import {expect,it} from 'vitest';
import * as upstream from 'pixi-filters';
import {filterCatalog,newFilter,defaultParameters,defaultRegion} from './filters';
it('covers every exported upstream filter without duplicates or undefined defaults',()=>{
  const names=Object.entries(upstream).filter(([name,value])=>name.endsWith('Filter')&&typeof value==='function').map(([name])=>name).sort();
  expect(filterCatalog.map(entry=>entry.type).sort()).toEqual(names);
  for(const entry of filterCatalog)for(const field of entry.fields)expect(field.value,entry.type+'.'+field.key).not.toBeUndefined();
});
it('resets every filter to independent original defaults including nested arrays',()=>{
  for(const entry of filterCatalog){
    const filter=newFilter(entry.type,'title1'),original=structuredClone(filter.params);
    for(const key of Object.keys(filter.params))filter.params[key]=null;
    filter.params=defaultParameters(filter.type);
    expect(filter.params).toEqual(original);
    expect(filter.targets).toEqual(['title1']);
    expect(filter.params).not.toBe(defaultParameters(filter.type));
  }
  const a=defaultParameters('ColorGradientFilter'),b=defaultParameters('ColorGradientFilter');
  (a.stops as unknown[]).push({});expect(a).not.toEqual(b);
});
it('creates independent deterministic parameter data and neutral region defaults',()=>{
  const first=newFilter('GlitchFilter','track'),second=newFilter('GlitchFilter','canvas');
  expect(first.id).not.toBe(second.id);first.params.seed=.3;expect(second.params.seed).toBe(0);
  expect(defaultRegion()).toEqual({mode:'all',x:.25,y:.25,width:.5,height:.5,feather:0,maskAsset:null});
});
