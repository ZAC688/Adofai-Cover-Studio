/** Coalesce immutable raster work and bound retained pixel memory across edits. */
export class RasterCache<T>{
  private entries=new Map<string,{promise:Promise<T>;bytes:number}>();
  private retained=0;
  constructor(private maxBytes:number,private sizeOf:(value:T)=>number,private maxEntries=32){}
  get bytes(){return this.retained;}
  get size(){return this.entries.size;}
  get(key:string,create:()=>Promise<T>):Promise<T>{
    const existing=this.entries.get(key);
    if(existing){this.entries.delete(key);this.entries.set(key,existing);return existing.promise;}
    const entry={promise:Promise.resolve().then(create),bytes:0};
    entry.promise=entry.promise.then(value=>{
      if(this.entries.get(key)===entry){entry.bytes=this.sizeOf(value);this.retained+=entry.bytes;this.trim();}
      return value;
    },error=>{if(this.entries.get(key)===entry)this.remove(key);throw error;});
    this.entries.set(key,entry);this.trim();return entry.promise;
  }
  private remove(key:string){const entry=this.entries.get(key);if(entry){this.retained-=entry.bytes;this.entries.delete(key);}}
  private trim(){while(this.retained>this.maxBytes||this.entries.size>this.maxEntries)this.remove(this.entries.keys().next().value!);}
}
