export type UploadedFont={id:string;label:string;extension:string};
type BuiltinFont={id:string;label:string;weight?:number;style?:'normal'|'italic'};
export const builtinFonts:BuiltinFont[]=[{id:'system',label:'系统黑体 · 原有字体'},{id:'noto-sans-sc',label:'Noto Sans SC · 中文黑体'},
  {id:'noto-serif-sc',label:'Noto Serif SC · 中文宋体'},{id:'inter',label:'Inter · 英文无衬线'},{id:'noto-serif',label:'Noto Serif · 英文衬线'},
  {id:'bebas-neue',label:'Bebas Neue · 常规',weight:400},{id:'russo-one',label:'Russo One · 常规',weight:400},
  {id:'space-mono',label:'Space Mono · 常规',weight:400},{id:'space-mono-italic',label:'Space Mono · 斜体',weight:400,style:'italic'},
  {id:'space-mono-bold',label:'Space Mono · 粗体',weight:700},{id:'space-mono-bold-italic',label:'Space Mono · 粗斜体',weight:700,style:'italic'}];
const uploaded=new Map<string,UploadedFont>();
const loaded=new Map<string,Promise<void>>();
export function registerFonts(fonts:UploadedFont[]){for(const font of fonts)uploaded.set(font.id,font);}
function renderedFont(id:string){return id==='system'&&typeof window!=='undefined'&&window.AndroidDevice?'noto-sans-sc':id;}
function family(id:string){return 'CoverFont_'+id.replace(/-/g,'_');}
export async function ensureFont(id='system'){
  id=renderedFont(id);
  if(id==='system')return;
  if(!loaded.has(id)){
    const local=builtinFonts.find(font=>font.id===id),info=uploaded.get(id);
    if(!local&&!info)throw new Error('字体尚未载入，请重新读取作品');
    const url=local?`/fonts/${id}.ttf`:`/api/fonts/${id}`;
    const font=new FontFace(family(id),`url("${url}")`,{weight:local?.weight?String(local.weight):'100 900',style:local?.style||'normal'});
    loaded.set(id,font.load().then(face=>{document.fonts.add(face);}).catch(error=>{loaded.delete(id);throw error;}));
  }
  await loaded.get(id);
}
export function fontCSS(id='system',size:number){
  id=renderedFont(id);
  const face=builtinFonts.find(font=>font.id===id);
  return `${face?.style==='italic'?'italic ':''}${face?.weight||900} ${size}px ${id==='system'?'':`"${family(id)}", `}"Microsoft YaHei", "Segoe UI", sans-serif`;
}
