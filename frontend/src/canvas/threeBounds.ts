import type {Title,TextPlacement,Ratio} from '../domain/project';
type Bounds={x:number;y:number;width:number;height:number};
const bounds=new Map<string,Bounds>();
const key=(title:Title,p:TextPlacement,ratio:Ratio)=>JSON.stringify([title.text,title.fontId,title.text3d,p,ratio]);
export function rememberThreeBounds(title:Title,p:TextPlacement,ratio:Ratio,value:Bounds){
  if(bounds.size>60)bounds.delete(bounds.keys().next().value!);bounds.set(key(title,p,ratio),value);
}
export const threeBounds=(title:Title,p:TextPlacement,ratio:Ratio)=>bounds.get(key(title,p,ratio));
