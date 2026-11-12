import { describe, expect, it } from 'vitest';
import { changeRatio, dimensions, fitScale, History, screenPoint, type Project } from './project';
const project = (): Project => ({schemaVersion: 1, name:'test', activeRatio:'16:9', bgAsset:null, trackAsset:null, maskAsset:null, baseMaskAsset:null, removeBackground:false,trackColor:null,trackGlow:20,
  titles:[{text:'one',color:'#ffffff',glow:10},{text:'two',color:'#ffffff',glow:20}],
  layouts:{'16:9':{bg:{x:960,y:540,scale:1},track:{x:1200,y:540,scale:.5},title1:{x:200,y:400,fontSize:100},title2:{x:200,y:600,fontSize:60}},'4:3':null}});
describe('composition layout', () => {
  it('converts first ratio once and restores independent positions and font sizes', () => {
    const first = project();
    const second = changeRatio(first, '4:3', {});
    expect(second.layouts['4:3']!.track.x).toBe(900);
    expect(second.layouts['4:3']!.title1.fontSize).toBe(75);
    second.layouts['4:3']!.title1.x = 400;
    const back = changeRatio(second, '16:9', {});
    expect(back.layouts['16:9']!.title1.x).toBe(200);
    expect(changeRatio(back, '4:3', {}).layouts['4:3']!.title1.x).toBe(400);
    expect(first.layouts['4:3']).toBeNull();
  });
  it('keeps cover proportions and maps pointer coordinates through preview scaling', () => {
    expect(fitScale({width:1000,height:1000},dimensions('16:9'))).toBe(1.92);
    expect(screenPoint({x:510,y:290},{left:30,top:20,width:960,height:540},dimensions('16:9'))).toEqual({x:960,y:540});
  });
  it('never reuses an abandoned redo branch', () => {
    const history = new History<{value:number}>();
    history.remember({value:1}); history.remember({value:2});
    expect(history.undo({value:3})).toEqual({value:2});
    history.remember({value:2});
    expect(history.redo({value:4})).toBeNull();
    expect(history.undo({value:4})).toEqual({value:2});
  });
});
