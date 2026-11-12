import type {Project,Title,TitleId,Ratio} from './project';
import type {FilterSpec} from './filters';
import {order,titleFor,titlePosition} from './objects';
import {replaceTargetFilters} from './filterPresets';

export type TextStyle=Omit<Title,'text'>;
export type TextPreset={style:TextStyle;fontSize:number;fontSizes:Partial<Record<Ratio,number>>;filters:FilterSpec[]};

export function captureTextStyle(project:Project,target:TitleId):TextPreset{
  if(!order(project).includes(target))throw new Error('当前标题已删除');
  const {text:content,...style}=structuredClone(titleFor(project,target));void content;
  return {style,fontSize:titlePosition(project.layouts[project.activeRatio]!,target).fontSize,
    fontSizes:Object.fromEntries(Object.entries(project.layouts).filter(([,places])=>!!places).map(([ratio,places])=>[ratio,titlePosition(places!,target).fontSize])),
    filters:structuredClone((project.filters||[]).filter(filter=>filter.targets.includes(target)))};
}

export function applyTextStyle(project:Project,target:TitleId,preset:TextPreset){
  if(!order(project).includes(target))throw new Error('应用目标已删除，请重新选择标题');
  const title=titleFor(project,target),content=title.text;
  Object.assign(title,structuredClone(preset.style),{text:content});
  for(const ratio of ['16:9','4:3'] as const){const places=project.layouts[ratio];if(places)titlePosition(places,target).fontSize=preset.fontSizes[ratio]??preset.fontSize;}
  replaceTargetFilters(project,target,preset.filters);
}
