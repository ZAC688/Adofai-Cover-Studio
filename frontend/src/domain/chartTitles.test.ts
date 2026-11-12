import {describe,it,expect} from 'vitest';
import {addChartTitles,titleCapacity} from './chartTitles';
import {addObject,order,isTitle,removeObject,titlePosition} from './objects';
import {changeRatio,type Project} from './project';

const initial=():Project=>({schemaVersion:1,name:'old',activeRatio:'16:9',bgAsset:null,trackAsset:null,maskAsset:null,baseMaskAsset:null,removeBackground:false,trackColor:null,trackGlow:0,titles:[{text:'keep1',color:'#123456',glow:20},{text:'keep2',color:'#abcdef',glow:15}],layouts:{'16:9':{bg:{x:960,y:540,scale:1},track:{x:960,y:540,scale:1},title1:{x:20,y:30,fontSize:60},title2:{x:50,y:100,fontSize:40}},'4:3':null}});

describe('optional chart labels',()=>{
  it('adds independent white unlit titles in both layouts without changing old titles',()=>{
    const project=changeRatio(initial(),'4:3',{}),before=structuredClone(project);
    const ids=addChartTitles(project,['曲名','Composer']);
    expect(ids).toEqual(['title3','title4']);expect(project.titles.slice(0,2)).toEqual(before.titles);
    for(const title of project.titles.slice(2))expect(title).toMatchObject({color:'#ffffff',glow:0,effects:null,fontId:'system'});
    for(const ratio of ['16:9','4:3'] as const){
      expect(project.layouts[ratio]!.title1).toEqual(before.layouts[ratio]!.title1);
      expect(titlePosition(project.layouts[ratio]!,'title3').y).toBeLessThan(titlePosition(project.layouts[ratio]!,'title4').y);
    }
  });
  it('checks capacity before any write and supports independent single selection',()=>{
    const p=initial();addObject(p,'title');addObject(p,'title');const before=structuredClone(p);
    expect(titleCapacity(p)).toBe(1);expect(()=>addChartTitles(p,['song','artist'])).toThrow('标题名额不足');expect(p).toEqual(before);
    addChartTitles(p,['artist']);expect(order(p).filter(isTitle)).toHaveLength(5);expect(p.titles[4].text).toBe('artist');
  });
  it('reuses a deleted slot and handles unchecked labels as a no-op',()=>{
    const p=initial();removeObject(p,'title1');addChartTitles(p,['song']);expect(p.titles[0].text).toBe('song');
    const before=structuredClone(p);expect(addChartTitles(p,[])).toEqual([]);expect(p).toEqual(before);
  });
});
