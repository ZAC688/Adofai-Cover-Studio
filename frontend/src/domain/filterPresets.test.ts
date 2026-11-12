import {expect,it} from 'vitest';
import {replaceTargetFilters} from './filterPresets';
import {newFilter} from './filters';
import type {Project} from './project';
it('replaces a target in order while retaining shared filters for all other objects',()=>{
  const shared=newFilter('GrayscaleFilter','title1');shared.targets.push('title2');
  const other=newFilter('EmbossFilter','canvas'),own=newFilter('AdjustmentFilter','title1');
  const project={layerOrder:['title2','title1','bg'],filters:[other,shared,own]} as Project;
  const preset=[newFilter('ColorOverlayFilter','track'),newFilter('GlitchFilter','track')];preset[1].enabled=false;
  const original=structuredClone(preset);replaceTargetFilters(project,'title1',preset);
  expect(project.filters!.map(f=>f.type)).toEqual(['EmbossFilter','ColorOverlayFilter','GlitchFilter','GrayscaleFilter']);
  expect(project.filters![3]).toEqual({...shared,targets:['title2']});expect(project.filters![0]).toBe(other);
  expect(project.filters!.slice(1,3).every(f=>f.targets.join()==='title1')).toBe(true);
  expect(project.filters![1].id).not.toBe(preset[0].id);expect(project.filters![2].enabled).toBe(false);expect(preset).toEqual(original);
});
it('never resurrects deleted targets or damages the existing project',()=>{
  const project={layerOrder:['bg'],filters:[newFilter('EmbossFilter','canvas')]} as Project,old=structuredClone(project);
  expect(()=>replaceTargetFilters(project,'title1',[newFilter('GrayscaleFilter','track')])).toThrow('已删除');expect(project).toEqual(old);
});
