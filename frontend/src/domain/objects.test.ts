import {describe,it,expect} from 'vitest';
import {addObject,removeObject,reorderObject,order,isTitle,isTrack,titleFor,titlePosition,imagePosition,changeTrack,addSticker,isSticker} from './objects';
import {changeRatio,layout,type Project} from './project';

function initial():Project{return {schemaVersion:1,name:'legacy',activeRatio:'16:9',bgAsset:null,trackAsset:null,maskAsset:null,baseMaskAsset:null,removeBackground:false,trackColor:null,trackGlow:25,
  titles:[{text:'one',color:'#ffffff',glow:25},{text:'two',color:'#ffffff',glow:20}],layouts:{'16:9':{bg:{x:960,y:540,scale:1},track:{x:1200,y:540,scale:1},title1:{x:160,y:400,fontSize:120},title2:{x:160,y:570,fontSize:72}},'4:3':null}};}
describe('independent object catalogs and stacking',()=>{
  it('does not inherit the first track generation recipe into a regular extra track',()=>{
    const p=initial();p.generatedTrack={sourceId:'a'.repeat(32),start:0,end:9,style:'gold',aspect:'tight',resolution:3840,margin:5,icons:true,rotate:true,labels:false,crop:null};
    addObject(p,'track');delete p.extraTracks!.track2!.generatedTrack;
    changeTrack(p,'track2',view=>{view.trackGlow=40;});
    expect(p.extraTracks!.track2!.generatedTrack).toBeNull();
    expect(p.generatedTrack.sourceId).toBe('a'.repeat(32));expect(p.trackGlow).toBe(25);
  });
  it('adds and re-adds every title and track with zero glow while preserving old slots',()=>{
    const p=initial();
    for(let i=0;i<3;i++){const id=addObject(p,'title')!;expect(titleFor(p,id as 'title3').glow).toBe(0);}
    for(let i=0;i<4;i++){const id=addObject(p,'track')!;expect(id==='track'?p.trackGlow:p.extraTracks![id as 'track2']!.trackGlow).toBe(0);}
    expect(p.titles[0].glow).toBe(25);expect(p.titles[1].glow).toBe(20);expect(p.trackGlow).toBe(25);
    removeObject(p,'title1');addObject(p,'title');expect(p.titles[0].glow).toBe(0);
    removeObject(p,'track');addObject(p,'track');expect(p.trackGlow).toBe(0);
  });
  it('adds many independent stickers without consuming title or track slots',()=>{
    const p=initial(),asset={id:'a'.repeat(32),width:128,height:128,kind:'image'};
    for(let i=0;i<100;i++)addSticker(p,{asset:asset.id,name:'logo',presetId:'b'.repeat(32),frame:1},asset);
    expect(order(p).filter(isSticker)).toHaveLength(100);expect(order(p).filter(isTitle)).toHaveLength(2);expect(order(p).filter(isTrack)).toHaveLength(1);
    const id=order(p).find(isSticker)!;imagePosition(layout(p),id).rotation=27;
    const other=changeRatio(p,'4:3',{});expect(imagePosition(layout(other),id).rotation).toBe(27);
    removeObject(other,id);expect(other.stickers![id]).toBeUndefined();expect(other.layouts['16:9']!.stickers![id]).toBeUndefined();expect(other.layouts['4:3']!.stickers![id]).toBeUndefined();
    expect(p.stickers![id]).toBeDefined();
  });
  it('keeps legacy stacking and enforces five of each, deletion and re-addition',()=>{
    const p=initial();expect(order(p)).toEqual(['title2','title1','track','bg']);
    for(let i=0;i<3;i++)expect(addObject(p,'title')).not.toBeNull();
    for(let i=0;i<4;i++)expect(addObject(p,'track')).not.toBeNull();
    expect(addObject(p,'title')).toBeNull();expect(addObject(p,'track')).toBeNull();
    expect(order(p).filter(isTitle)).toHaveLength(5);expect(order(p).filter(isTrack)).toHaveLength(5);
    removeObject(p,'bg');expect(order(p).at(-1)).toBe('bg');
    removeObject(p,'title3');expect(addObject(p,'title')).toBe('title3');expect(titleFor(p,'title3').text).toBe('');
  });
  it('reorders mixed objects while locking background and changes only the intended track',()=>{
    const p=initial();addObject(p,'track');reorderObject(p,'track2','title1');
    expect(order(p)).toEqual(['title2','track2','title1','track','bg']);
    reorderObject(p,'bg','title2');expect(order(p).at(-1)).toBe('bg');
    changeTrack(p,'track2',view=>{view.trackColor='#ff0000';view.maskAsset='mask2';});
    expect(p.trackColor).toBeNull();expect(p.maskAsset).toBeNull();expect(p.extraTracks!.track2!.maskAsset).toBe('mask2');
  });
  it('creates and remembers extra placements in both ratios without resetting rotations',()=>{
    const p=initial();addObject(p,'title');addObject(p,'track');
    titlePosition(layout(p),'title3').rotation=37;imagePosition(layout(p),'track2').rotation=-21;
    const other=changeRatio(p,'4:3',{});
    expect(titlePosition(layout(other),'title3').fontSize).toBe(54);expect(titlePosition(layout(other),'title3').rotation).toBe(37);
    expect(imagePosition(layout(other),'track2').x).toBe(720);expect(imagePosition(layout(other),'track2').rotation).toBe(-21);
    titlePosition(layout(other),'title3').x=999;
    const back=changeRatio(other,'16:9',{});expect(titlePosition(layout(back),'title3').x).toBe(160);
    expect(titlePosition(layout(changeRatio(back,'4:3',{})),'title3').x).toBe(999);
    addObject(other,'title');expect(titlePosition(other.layouts['16:9']!,'title4')).toBeDefined();expect(titlePosition(other.layouts['4:3']!,'title4')).toBeDefined();
  });
});
