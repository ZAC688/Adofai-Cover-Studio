import {expect,it} from 'vitest';
import {compareStickers,compareCategoryStickers} from './stickerOrder';
it('sorts names naturally across folders with a deterministic tie break',()=>{
  const items=['轨道10','Logo 10','轨道2','Logo 2','Logo 1'].map((name,i)=>({name,id:String(i),category:[String(5-i)]}));
  // zh-CN places Chinese names before Latin names; both groups use numeric order.
  expect([...items].sort(compareStickers).map(x=>x.name)).toEqual(['轨道2','轨道10','Logo 1','Logo 2','Logo 10']);
  expect(compareStickers({name:'a',id:'2',category:['B']},{name:'A',id:'1',category:['A']})).toBeGreaterThan(0);
});
it('puts P files first and crazy last only within the new-level category',()=>{
  const items=['crazy','U10','G10','P10','m21','p2','G2','U2'].map((name,i)=>({name,id:String(i),category:['TUF','新等级']}));
  expect([...items].sort((a,b)=>compareCategoryStickers(a,b,['TUF','新等级'])).map(v=>v.name)).toEqual(['p2','P10','G2','G10','m21','U2','U10','crazy']);
  for(const category of [[],['TUF'],['旧等级']])expect([...items].sort((a,b)=>compareCategoryStickers(a,b,category))).toEqual([...items].sort(compareStickers));
});
