import {useEffect,useRef,useState} from 'react';
import {appInfo,releaseNotes} from './appInfo';
import manual from '../../../docs/使用说明.md?raw';
const tabs={about:'关于',changes:'更新日志',manual:'使用说明'};
export function InfoDialog({close}:{close:()=>void}){
  const [tab,setTab]=useState<keyof typeof tabs>('about');
  const dialog=useRef<HTMLElement>(null),closeButton=useRef<HTMLButtonElement>(null),closeAction=useRef(close);closeAction.current=close;
  useEffect(()=>{
    const previous=document.activeElement;closeButton.current?.focus();
    const key=(event:KeyboardEvent)=>{
      // This read-only dialog owns editing shortcuts as well: browser-native undo
      // can otherwise undo the last textarea edit even while a button is focused.
      if(event.key==='Delete'||(event.ctrlKey||event.metaKey)&&['z','y'].includes(event.key.toLowerCase())){event.preventDefault();event.stopPropagation();}
      if(event.key==='Escape'){event.preventDefault();event.stopPropagation();closeAction.current();}
      if(event.key==='Tab'){
        const buttons=[...dialog.current!.querySelectorAll<HTMLElement>('button:not(:disabled),[tabindex="0"]')].filter(e=>e.getClientRects().length);
        const first=buttons[0],last=buttons.at(-1)!;
        if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
        else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
      }
    };
    document.addEventListener('keydown',key);return()=>{document.removeEventListener('keydown',key);if(previous instanceof HTMLElement&&previous.isConnected)previous.focus();};
  },[]);
  const plain=(line:string)=>line.replace(/`([^`]+)`/g,'$1').replace(/\[([^\]]+)\]\([^)]+\)/g,'$1');
  return <div className="modal-backdrop"><section ref={dialog} className="modal info-dialog" role="dialog" aria-modal="true" aria-label="关于封面制作器">
    <div className="modal-header"><h2>{appInfo.name}</h2><button ref={closeButton} aria-label="关闭信息" onClick={close}>×</button></div>
    <div className="info-tabs" role="tablist" aria-label="信息内容">{(Object.keys(tabs) as (keyof typeof tabs)[]).map(key=><button key={key} role="tab" aria-selected={tab===key} aria-controls="info-content" onClick={()=>setTab(key)}>{tabs[key]}</button>)}</div>
    <div id="info-content" className="info-body" role="tabpanel" aria-label={tabs[tab]} tabIndex={0} key={tab}>
      {tab==='about'&&<><div className="brand-mark">A</div><dl><dt>作者</dt><dd>{appInfo.author}</dd><dt>版本</dt><dd aria-label="应用版本">{appInfo.version}</dd><dt>运行方式</dt><dd>Windows · 独立桌面 · 完全离线</dd></dl><p>作品自动保存在当前电脑，可在下次打开时继续编辑。</p></>}
      {tab==='changes'&&releaseNotes.map(release=><section key={release.version}><h3>{release.version}</h3><ul>{release.items.map(item=><li key={item}>{item}</li>)}</ul></section>)}
      {tab==='manual'&&manual.split('\n').map((line,i)=>!line.trim()?null:/^#{1,3} /.test(line)?<h3 key={i}>{plain(line.replace(/^#+ /,''))}</h3>:<p key={i}>{plain(line)}</p>)}
    </div>
  </section></div>;
}
