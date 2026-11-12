import {dimensions,type Project,type TitleId} from './project';
import {addObject,order,isTitle,titleFor,titlePosition} from './objects';

export type ChartInfo={id:string;name:string;tileCount:number;song:string;artist:string};
export const titleCapacity=(project:Project)=>5-order(project).filter(isTitle).length;

export function addChartTitles(project:Project,texts:string[]):TitleId[]{
  if(texts.length>titleCapacity(project))throw new Error('标题名额不足，请先删除不需要的标题，现有内容已保留');
  return texts.map((text,index)=>{
    const id=addObject(project,'title') as TitleId;
    titleFor(project,id).text=text;
    const units=Array.from(text).reduce((n,char)=>n+(char.charCodeAt(0)>255?1:.6),0);
    for(const ratio of ['16:9','4:3'] as const){
      const places=project.layouts[ratio];if(!places)continue;const size=dimensions(ratio);
      Object.assign(titlePosition(places,id),{x:120,y:size.height-230+index*100,fontSize:Math.max(1,Math.min(64,(size.width-240)/Math.max(1,units))),rotation:0});
    }
    return id;
  });
}
