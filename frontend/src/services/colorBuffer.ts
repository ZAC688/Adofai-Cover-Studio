const active=new Set<()=>void>();
export function flushColorChanges(){for(const flush of active)flush();}
export class ColorBuffer {
  private pending:{value:string;commit:(value:string)=>void}|null=null;
  private timer:ReturnType<typeof setTimeout>|null=null;
  push(value:string,commit:(value:string)=>void){
    this.pending={value,commit};if(this.timer)clearTimeout(this.timer);
    this.timer=setTimeout(this.flush,120);
  }
  flush=()=>{
    if(this.timer)clearTimeout(this.timer);this.timer=null;
    const pending=this.pending;this.pending=null;if(pending)pending.commit(pending.value);
  };
  register(){active.add(this.flush);return()=>{this.flush();active.delete(this.flush);};}
}
