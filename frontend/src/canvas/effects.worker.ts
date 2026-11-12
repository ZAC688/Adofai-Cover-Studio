import {applyEffects} from './effects';
import type {Effects} from '../domain/effects';

type Request={id:number;bitmap:ImageBitmap;effects:Effects};
const scope=globalThis as unknown as {onmessage:(event:MessageEvent<Request>)=>void;postMessage:(value:unknown,transfer?:Transferable[])=>void};
scope.onmessage=({data:{id,bitmap,effects}})=>{
  try{
    const base=new OffscreenCanvas(bitmap.width,bitmap.height);
    base.getContext('2d',{willReadFrequently:true})!.drawImage(bitmap,0,0);
    const result=applyEffects(base,effects),output=(result.canvas as OffscreenCanvas).transferToImageBitmap();
    scope.postMessage({id,bitmap:output,padding:result.padding},[output]);
  }catch(error){scope.postMessage({id,error:String(error)});}
  finally{bitmap.close();}
};
