const names=new Intl.Collator('zh-CN',{numeric:true,sensitivity:'base'});
export function compareStickers(a:{name:string;category:string[];id:string},b:{name:string;category:string[];id:string}){
  return names.compare(a.name,b.name)||names.compare(a.category.join('/'),b.category.join('/'))||a.id.localeCompare(b.id);
}
export function compareCategoryStickers(a:{name:string;category:string[];id:string},b:{name:string;category:string[];id:string},category:string[]){
  if(category.at(-1)==='新等级'){
    const rank=(name:string)=>/^p/i.test(name)?0:name.toLowerCase()==='crazy'?2:1;
    const priority=rank(a.name)-rank(b.name);if(priority)return priority;
  }
  return compareStickers(a,b);
}
