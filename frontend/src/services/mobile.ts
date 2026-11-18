import {useEffect,useState} from 'react';

declare global {
  interface Window {
    adofaiBackRequest?:()=>Promise<boolean>;
    AndroidDevice?: {
      version:()=>string;closeResult:(saved:boolean)=>void;
      beginDownload:(name:string,mime:string,size:number)=>string;
      appendDownload:(id:string,offset:number,encoded:string)=>string;
      finishDownload:(id:string)=>string;cancelDownload:(id:string)=>void;
    };
  }
}

export type MobilePanel='objects'|'properties'|'effects'|'filters';

export function useCompactLayout(){
  const [compact,setCompact]=useState(()=>!!window.AndroidDevice||window.matchMedia('(max-width:1049px)').matches);
  useEffect(()=>{
    const query=window.matchMedia('(max-width:1049px)');
    const update=()=>setCompact(!!window.AndroidDevice||query.matches);
    query.addEventListener('change',update);update();
    return()=>query.removeEventListener('change',update);
  },[]);
  return compact;
}

/** Some mobile engines suppress the click immediately following a drag. Use the
 * completed touch for buttons, suppress its later duplicate, and leave scrolling,
 * drag handles, mouse and keyboard activation to their normal input paths. */
export function useMobileButtons(enabled:boolean){
  useEffect(()=>{
    if(!enabled)return;
    let pending:{button:HTMLButtonElement;id:number;x:number;y:number;moved:boolean}|null=null;
    const accepted=new WeakMap<HTMLButtonElement,number>();
    const down=(event:PointerEvent)=>{
      if(event.pointerType!=='touch')return;
      const button=event.target instanceof Element?event.target.closest('button'):null;
      pending=button&&!button.disabled&&!button.classList.contains('touch-reorder')?
        {button,id:event.pointerId,x:event.clientX,y:event.clientY,moved:false}:null;
    };
    const move=(event:PointerEvent)=>{if(pending?.id===event.pointerId&&Math.hypot(event.clientX-pending.x,event.clientY-pending.y)>10)pending.moved=true;};
    const cancel=()=>{pending=null;};
    const up=(event:PointerEvent)=>{
      const touch=pending;if(!touch||touch.id!==event.pointerId)return;pending=null;
      if(touch.moved||!touch.button.isConnected||touch.button.disabled||!(event.target instanceof Node)||!touch.button.contains(event.target))return;
      event.preventDefault();accepted.set(touch.button,performance.now());touch.button.click();
    };
    const click=(event:MouseEvent)=>{
      if(!event.isTrusted||!event.detail||event instanceof PointerEvent&&event.pointerType!=='touch')return;
      const button=event.target instanceof Element?event.target.closest('button'):null;
      if(button&&performance.now()-(accepted.get(button)??-Infinity)<500){event.preventDefault();event.stopImmediatePropagation();}
    };
    window.addEventListener('pointerdown',down,true);window.addEventListener('pointermove',move,true);
    window.addEventListener('pointerup',up,{capture:true,passive:false});window.addEventListener('pointercancel',cancel,true);
    window.addEventListener('click',click,true);
    return()=>{
      window.removeEventListener('pointerdown',down,true);window.removeEventListener('pointermove',move,true);
      window.removeEventListener('pointerup',up,true);window.removeEventListener('pointercancel',cancel,true);
      window.removeEventListener('click',click,true);
    };
  },[enabled]);
}
