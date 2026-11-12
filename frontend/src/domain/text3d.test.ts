import {expect,it} from 'vitest';
import {defaultText3D} from './text3d';
import {addObject} from './objects';
import type {Project} from './project';
it('creates independent disabled 3D settings and keeps the five-title limit',()=>{
  const first=defaultText3D(),second=defaultText3D();first.depth=90;expect(second.depth).toBe(18);expect(second.enabled).toBe(false);
  const project={titles:[{text:'legacy',glow:37,color:'#ffffff'},{text:'',glow:0,color:'#ffffff'}],layouts:{'16:9':{extraTitles:{}},'4:3':null},activeRatio:'16:9',layerOrder:['title2','title1','bg']} as unknown as Project;
  project.titles[0].text3d={...defaultText3D(),enabled:true};
  for(let i=0;i<3;i++)expect(addObject(project,'title')).not.toBeNull();expect(addObject(project,'title')).toBeNull();
  expect(project.titles[0].text).toBe('legacy');expect(project.titles[0].glow).toBe(37);expect(project.titles[1].text3d).toBeUndefined();
});
