import {afterEach,describe,expect,it,vi} from 'vitest';
import {installDownloads,saveBlob} from './downloads';

function device(state='saved',broken=false){
  const chunks:Uint8Array[]=[],cancel=vi.fn();
  let written=0;
  const host=Object.assign(new EventTarget(),{
    AndroidDevice:{
      version:()=> '0.8.1-android.1',closeResult:vi.fn(),
      beginDownload:vi.fn(()=>JSON.stringify({id:'transfer-1'})),
      appendDownload:vi.fn((_id:string,offset:number,data:string)=>{
        expect(offset).toBe(written);
        const bytes=Uint8Array.from(atob(data),char=>char.charCodeAt(0));
        expect(bytes.length).toBeLessThanOrEqual(192*1024);chunks.push(bytes);written+=bytes.length;
        return JSON.stringify({written:broken?written-1:written});
      }),
      finishDownload:vi.fn(()=>{queueMicrotask(()=>window.adofaiDownloadResult!('transfer-1',state,state==='error'?'存储空间不足':''));return JSON.stringify({queued:true});}),
      cancelDownload:cancel,
    },
  });
  vi.stubGlobal('window',host);installDownloads();
  return {host,chunks,cancel};
}

afterEach(()=>vi.unstubAllGlobals());

describe('Android file transfer',()=>{
  it('transfers multiple bounded chunks without changing bytes or Unicode filenames',async()=>{
    const {host,chunks}=device();
    const bytes=Uint8Array.from({length:192*1024*2+7},(_,i)=>i%251);
    expect(await saveBlob(new Blob([bytes],{type:'image/png'}),'中文封面.png')).toBe('saved');
    expect(host.AndroidDevice.beginDownload).toHaveBeenCalledWith('中文封面.png','image/png',bytes.length);
    expect(chunks).toHaveLength(3);
    expect(new Uint8Array(chunks.flatMap(chunk=>[...chunk]))).toEqual(bytes);
    expect(host.AndroidDevice.finishDownload).toHaveBeenCalledTimes(1);
  });

  it('reports system cancellation without treating the file as saved',async()=>{
    const {cancel}=device('cancelled');
    expect(await saveBlob(new Blob(['{"style":1}'],{type:'application/json'}),'style.adofai-text.json')).toBe('cancelled');
    expect(cancel).not.toHaveBeenCalled();
  });

  it('never opens the save picker after a partial write and cancels private cache',async()=>{
    const {host,cancel}=device('saved',true);
    await expect(saveBlob(new Blob(['PNG'],{type:'image/png'}),'x.png')).rejects.toThrow('不完整');
    expect(host.AndroidDevice.finishDownload).not.toHaveBeenCalled();
    expect(cancel).toHaveBeenCalledWith('transfer-1');
  });

  it('returns a useful system write error and allows another export',async()=>{
    const {cancel}=device('error');
    await expect(saveBlob(new Blob(['PNG'],{type:'image/png'}),'x.png')).rejects.toThrow('存储空间不足');
    expect(cancel).toHaveBeenCalledWith('transfer-1');
    device();
    await expect(saveBlob(new Blob(['PNG'],{type:'image/png'}),'retry.png')).resolves.toBe('saved');
  });
});
