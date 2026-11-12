import {it,expect} from 'vitest';
import {LatestRenderer} from './latestRenderer';
it('renders intermediate feedback and the latest snapshot without accumulating stale work',async()=>{
  const started:number[]=[],shown:number[]=[],busy:boolean[]=[],pending:((value:number)=>void)[]=[];
  const runner=new LatestRenderer<number,number>(value=>{started.push(value);return new Promise(resolve=>pending.push(resolve));},value=>shown.push(value),value=>busy.push(value),error=>{throw error;});
  runner.request(1);for(let n=2;n<=50;n++)runner.request(n);
  expect(started).toEqual([1]);pending.shift()!(1);await Promise.resolve();
  expect(started).toEqual([1,50]);expect(shown).toEqual([1]);
  pending.shift()!(50);await Promise.resolve();expect(shown).toEqual([1,50]);expect(busy.at(-1)).toBe(false);
});
it('recovers after errors and never presents work after disposal',async()=>{
  const shown:number[]=[],errors:unknown[]=[];let finish!:(value:number)=>void;
  const runner=new LatestRenderer<number,number>(async n=>{if(n===1)throw Error('failed');return new Promise(resolve=>{finish=resolve;});},value=>shown.push(value),()=>{},error=>errors.push(error));
  runner.request(1);await Promise.resolve();runner.request(2);expect(errors).toHaveLength(1);
  runner.dispose();finish(2);await Promise.resolve();await Promise.resolve();expect(shown).toEqual([]);
});
