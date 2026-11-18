export type DownloadResult='saved'|'cancelled'|'started';
const CHUNK_BYTES=192*1024;
const pending=new Map<string,{resolve:(result:DownloadResult)=>void;reject:(error:Error)=>void}>();

declare global {
  interface Window {
    adofaiDownloadResult?:(id:string,state:string,message:string)=>void;
    adofaiSaveBlob?:(blob:Blob,name:string)=>Promise<DownloadResult>;
  }
}

export function isAndroid(){return !!window.AndroidDevice;}

export function installDownloads(){
  window.adofaiSaveBlob=saveBlob;
  window.adofaiDownloadResult=(id,state,message)=>{
    const task=pending.get(id);if(!task)return;pending.delete(id);
    if(state==='saved'||state==='cancelled')task.resolve(state);
    else task.reject(new Error(message||'文件保存失败，请重试'));
  };
}

function response(raw:string):Record<string,unknown>{
  const value:unknown=JSON.parse(raw);
  if(!value||typeof value!=='object')throw new Error('手机文件接口返回无效数据');
  const result=value as Record<string,unknown>;
  if(typeof result.error==='string')throw new Error(result.error);
  return result;
}

function encoded(bytes:Uint8Array){
  let value='';for(let offset=0;offset<bytes.length;offset+=4096)value+=String.fromCharCode(...bytes.subarray(offset,offset+4096));
  return btoa(value);
}

export async function saveBlob(blob:Blob,name:string):Promise<DownloadResult>{
  const device=window.AndroidDevice;
  if(!device){
    const address=URL.createObjectURL(blob),anchor=document.createElement('a');
    anchor.href=address;anchor.download=name;document.body.append(anchor);anchor.click();anchor.remove();
    setTimeout(()=>URL.revokeObjectURL(address),3000);
    return 'started';
  }
  if(blob.size<=0||blob.size>100_000_000)throw new Error('导出文件大小无效或超过 100 MB');
  if(!window.adofaiDownloadResult)installDownloads();
  let id:string|undefined;
  const notice=(message:string)=>window.dispatchEvent(new CustomEvent('adofai-download-status',{detail:message}));
  try{
    const created=response(device.beginDownload(name,blob.type||'application/json',blob.size));
    if(typeof created.id!=='string')throw new Error('无法创建手机导出文件');
    id=created.id;notice('正在准备手机导出文件…');
    for(let offset=0;offset<blob.size;offset+=CHUNK_BYTES){
      const bytes=new Uint8Array(await blob.slice(offset,offset+CHUNK_BYTES).arrayBuffer());
      if(response(device.appendDownload(id,offset,encoded(bytes))).written!==offset+bytes.length)throw new Error('手机导出数据不完整，请重试');
      await new Promise<void>(resolve=>setTimeout(resolve,0));
    }
    const result=await new Promise<DownloadResult>((resolve,reject)=>{
      pending.set(id!,{resolve,reject});
      try{
        if(response(device.finishDownload(id!)).queued!==true)throw new Error('无法打开手机保存界面');
      }catch(error){pending.delete(id!);reject(error instanceof Error?error:new Error(String(error)));}
    });
    notice(result==='saved'?'文件已保存到所选位置':'已取消保存，作品仍保留');
    return result;
  }catch(error){
    if(id){pending.delete(id);device.cancelDownload(id);}
    notice('导出失败，作品仍保留，可重新导出');
    throw error;
  }
}

export async function saveURL(url:string,name:string){
  const result=await fetch(url);if(!result.ok)throw new Error('导出文件读取失败，请重试');
  return saveBlob(await result.blob(),name);
}
