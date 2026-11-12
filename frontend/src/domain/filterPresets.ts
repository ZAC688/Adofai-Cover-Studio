import type {FilterSpec} from './filters';
import type {ObjectId,Project} from './project';
import {order} from './objects';
export function replaceTargetFilters(project:Project,target:ObjectId|'canvas',preset:FilterSpec[]){
  if(target!=='canvas'&&!order(project).includes(target))throw new Error('应用目标已删除，请重新选择对象');
  const list=project.filters||[],first=list.findIndex(f=>f.targets.includes(target));
  const result:FilterSpec[]=[];
  const clones=preset.map(filter=>({...structuredClone(filter),id:crypto.randomUUID().replaceAll('-',''),targets:[target]}));
  for(let i=0;i<list.length;i++){
    if(i===first)result.push(...clones);
    const filter=list[i];if(!filter.targets.includes(target)){result.push(filter);continue;}
    const targets=filter.targets.filter(id=>id!==target);
    if(targets.length)result.push({...filter,targets});
  }
  if(first<0)result.push(...clones);
  project.filters=result;
}
