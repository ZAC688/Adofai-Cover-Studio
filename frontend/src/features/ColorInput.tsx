import {useEffect,useRef,useState} from 'react';
import {ColorBuffer} from '../services/colorBuffer';

/** The native palette updates immediately; expensive composition changes are
 * coalesced until a pause, acceptance, blur or another editor action. */
export function ColorInput({label,value,onChange,begin,end}:{label:string;value:string;onChange:(value:string)=>void;begin:()=>void;end:()=>void}){
  const [draft,setDraft]=useState(value),input=useRef<HTMLInputElement>(null),buffer=useRef<ColorBuffer|null>(null);
  if(!buffer.current)buffer.current=new ColorBuffer();
  const latest=useRef(onChange);latest.current=onChange;
  useEffect(()=>setDraft(value),[value]);
  useEffect(()=>{
    const field=input.current!,pending=buffer.current!,unregister=pending.register();
    const accept=()=>{const value=field.value;setDraft(value);pending.push(value,latest.current);pending.flush();};
    field.addEventListener('change',accept);
    return()=>{field.removeEventListener('change',accept);unregister();};
  },[]);
  return <input ref={input} aria-label={label} type="color" value={draft} onFocus={begin} onBlur={()=>{buffer.current!.flush();end();}} onChange={()=>{}}
    onInput={event=>{const value=event.currentTarget.value;setDraft(value);buffer.current!.push(value,onChange);}}/>;
}
