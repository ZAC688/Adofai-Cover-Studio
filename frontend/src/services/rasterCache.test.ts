import {it,expect,vi} from 'vitest';
import {RasterCache} from './rasterCache';

it('coalesces in-flight work, reuses immutable pixels and retries rejected work',async()=>{
  const cache=new RasterCache<{bytes:number}>(100,value=>value.bytes);
  const create=vi.fn(async()=>({bytes:40}));
  const first=cache.get('body',create),second=cache.get('body',create);
  expect(first).toBe(second);expect(await first).toBe(await second);expect(create).toHaveBeenCalledTimes(1);
  const failing=vi.fn(async()=>{throw Error('worker unavailable');});
  await expect(cache.get('failed',failing)).rejects.toThrow('worker unavailable');
  await expect(cache.get('failed',create)).resolves.toEqual({bytes:40});expect(create).toHaveBeenCalledTimes(2);
});
it('evicts least recently used pixels by bytes and does not retain oversized results',async()=>{
  const cache=new RasterCache<number>(100,n=>n);
  await cache.get('a',async()=>40);await cache.get('b',async()=>40);
  await cache.get('a',async()=>{throw Error('a must remain cached');});
  await cache.get('c',async()=>40);expect(cache.bytes).toBe(80);
  const rebuild=vi.fn(async()=>40);await cache.get('b',rebuild);expect(rebuild).toHaveBeenCalledOnce();
  await cache.get('huge',async()=>200);expect(cache.bytes).toBe(0);expect(cache.size).toBe(0);
});
it('bounds pending entries without resurrecting an evicted completion',async()=>{
  const cache=new RasterCache<number>(100,n=>n,1);let finish!:(value:number)=>void;
  const first=cache.get('a',()=>new Promise(resolve=>{finish=resolve;}));await Promise.resolve();
  await cache.get('b',async()=>20);finish(90);await first;
  expect(cache.bytes).toBe(20);expect(cache.size).toBe(1);
  expect(await cache.get('b',async()=>{throw Error('evicted completion must not disturb b');})).toBe(20);
});
