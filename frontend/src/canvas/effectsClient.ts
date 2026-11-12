import type {Effects} from '../domain/effects';

let worker:Worker|null=null,sequence=0;
const requests=new Map<number,{resolve:(value:{canvas:HTMLCanvasElement;padding:number})=>void;reject:(error:Error)=>void}>();
export async function renderEffects(base:HTMLCanvasElement,effects:Effects){
  if(!worker){
    worker=new Worker(new URL('./effects.worker.ts',import.meta.url),{type:'module'});
    worker.onmessage=({data}:{data:{id:number;bitmap?:ImageBitmap;padding:number;error?:string}})=>{
      const request=requests.get(data.id);requests.delete(data.id);
      if(!request){data.bitmap?.close();return;}
      if(data.error){request.reject(new Error(data.error));return;}
      const bitmap=data.bitmap!,canvas=document.createElement('canvas');canvas.width=bitmap.width;canvas.height=bitmap.height;
      canvas.getContext('2d',{willReadFrequently:true})!.drawImage(bitmap,0,0);bitmap.close();
      request.resolve({canvas,padding:data.padding});
    };
    worker.onerror=event=>{
      for(const item of requests.values())item.reject(new Error(event.message||'光效渲染线程失败，请重试'));
      requests.clear();worker?.terminate();worker=null;
    };
  }
  const bitmap=await createImageBitmap(base),id=++sequence;
  return new Promise<{canvas:HTMLCanvasElement;padding:number}>((resolve,reject)=>{
    requests.set(id,{resolve,reject});
    try{worker!.postMessage({id,bitmap,effects},[bitmap]);}catch(error){bitmap.close();requests.delete(id);reject(error);}
  });
}
