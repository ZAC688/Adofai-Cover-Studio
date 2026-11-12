import {describe,it,expect} from 'vitest';
import {captureTextStyle,applyTextStyle} from './textPresets';
import {addObject,removeObject,titlePosition} from './objects';
import {newFilter} from './filters';
import {defaultText3D} from './text3d';
import type {Project} from './project';

const initial=():Project=>({schemaVersion:1,name:'old',activeRatio:'16:9',bgAsset:null,trackAsset:null,maskAsset:null,baseMaskAsset:null,removeBackground:false,trackColor:null,trackGlow:0,titles:[{text:'source',color:'#123456',glow:15,fontId:'inter',text3d:{...defaultText3D(),enabled:true,depth:36}},{text:'keep me',color:'#abcdef',glow:0}],layouts:{'16:9':{bg:{x:960,y:540,scale:1},track:{x:960,y:540,scale:1},title1:{x:20,y:30,fontSize:100,rotation:12},title2:{x:300,y:600,fontSize:40,rotation:25}},'4:3':null}});

describe('text preset scope A',()=>{
  it('captures style without text or placement and preserves the target content and transform',()=>{
    const p=initial();const filter=newFilter('AdjustmentFilter','title1');filter.targets=['title1','track'];p.filters=[filter];
    const preset=captureTextStyle(p,'title1');expect(preset.style).not.toHaveProperty('text');expect(preset).not.toHaveProperty('rotation');
    const before=structuredClone(p);applyTextStyle(p,'title2',preset);
    expect(p.titles[1]).toEqual({...p.titles[0],text:'keep me'});
    expect(titlePosition(p.layouts['16:9']!,'title2')).toEqual({...before.layouts['16:9']!.title2,fontSize:100});
    expect(p.titles[0]).toEqual(before.titles[0]);expect(p.filters![0]).toEqual(filter);
    expect(p.filters![1].targets).toEqual(['title2']);expect(p.filters![1].id).not.toBe(filter.id);
    expect(p.layouts['4:3']).toBeNull();
  });
  it('restores both layout sizes and removes only the selected title filters when the preset is empty',()=>{
    const p=initial();p.layouts['4:3']=structuredClone(p.layouts['16:9']);p.layouts['4:3']!.title1.fontSize=75;p.layouts['4:3']!.title2.rotation=-42;
    const preset=captureTextStyle(p,'title1');const old=newFilter('AdjustmentFilter','title2');old.targets=['title2','track'];p.filters=[old];
    applyTextStyle(p,'title2',preset);
    expect(p.layouts['4:3']!.title2).toMatchObject({fontSize:75,rotation:-42,x:300,y:600});
    expect(p.filters).toEqual([{...old,targets:['track']}]);
  });
  it('rejects deleted targets without changing any state and supports all five title slots',()=>{
    const p=initial(),preset=captureTextStyle(p,'title1');addObject(p,'title');addObject(p,'title');addObject(p,'title');
    applyTextStyle(p,'title5',preset);expect(p.titles[4].color).toBe('#123456');expect(p.titles[4].text).toBe('');
    removeObject(p,'title5');const before=structuredClone(p);expect(()=>applyTextStyle(p,'title5',preset)).toThrow();expect(p).toEqual(before);
  });
});
