import {afterEach,expect,it,vi} from 'vitest';
import {ColorBuffer,flushColorChanges} from './colorBuffer';
afterEach(()=>vi.useRealTimers());
it('coalesces bursts and commits the exact latest value after a pause',()=>{
  vi.useFakeTimers();const b=new ColorBuffer(),commit=vi.fn();
  for(let i=0;i<60;i++){b.push(String(i),commit);vi.advanceTimersByTime(8);}
  expect(commit).not.toHaveBeenCalled();vi.advanceTimersByTime(120);
  expect(commit).toHaveBeenCalledExactlyOnceWith('59');
});
it('flushes synchronously for export/undo/blur and cannot replay stale colors',()=>{
  vi.useFakeTimers();const b=new ColorBuffer(),commit=vi.fn(),unregister=b.register();
  b.push('#aabbcc',commit);flushColorChanges();expect(commit).toHaveBeenCalledExactlyOnceWith('#aabbcc');
  vi.advanceTimersByTime(500);expect(commit).toHaveBeenCalledTimes(1);unregister();
});
it('retains the original target callback and saves pending edits on unmount',()=>{
  vi.useFakeTimers();const b=new ColorBuffer(),oldTarget=vi.fn(),newTarget=vi.fn(),unregister=b.register();
  b.push('#123456',oldTarget);unregister();expect(oldTarget).toHaveBeenCalledExactlyOnceWith('#123456');
  b.push('#abcdef',newTarget);b.flush();vi.advanceTimersByTime(500);
  expect(oldTarget).toHaveBeenCalledTimes(1);expect(newTarget).toHaveBeenCalledExactlyOnceWith('#abcdef');
});
