/** Keep one render in flight and one newest snapshot, rather than a queue of stale frames. */
export class LatestRenderer<T,R>{
  private latest:{value:T}|null=null;
  private running=false;
  private disposed=false;
  constructor(private render:(value:T)=>Promise<R>,private present:(result:R,value:T)=>void,private busy:(value:boolean)=>void,private error:(error:unknown)=>void){}
  request(value:T){if(this.disposed)return;this.latest={value};this.busy(true);if(!this.running)void this.drain();}
  private async drain(){
    this.running=true;
    while(this.latest&&!this.disposed){
      const {value}=this.latest;this.latest=null;
      try{const result=await this.render(value);if(!this.disposed)this.present(result,value);}catch(error){if(!this.disposed)this.error(error);}
    }
    this.running=false;if(!this.disposed)this.busy(false);
  }
  dispose(){this.disposed=true;this.latest=null;}
}
