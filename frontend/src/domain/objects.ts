import {dimensions,layout,type ObjectId,type TitleId,type TrackId,type Project,type Track,type Layout,type Placement,type TextPlacement,type StickerId,type GraphicId,type Sticker,type Asset} from './project';

export const titleIds:TitleId[]=['title1','title2','title3','title4','title5'];
export const trackIds:TrackId[]=['track','track2','track3','track4','track5'];
export const isTitle=(id:ObjectId):id is TitleId=>id.startsWith('title');
export const isTrack=(id:ObjectId):id is TrackId=>id.startsWith('track');
export const isSticker=(id:ObjectId):id is StickerId=>id.startsWith('sticker_');
export const isGraphic=(id:ObjectId):id is GraphicId=>isTrack(id)||isSticker(id);
export const order=(project:Project):ObjectId[]=>project.layerOrder||['title2','title1','track','bg'];
export const titleFor=(project:Project,id:TitleId)=>project.titles[titleIds.indexOf(id)];
export function trackFor(project:Project,id:TrackId):Track{return id==='track'?project:project.extraTracks![id]!;}
export function titlePosition(positions:Layout,id:TitleId):TextPlacement{return id==='title1'||id==='title2'?positions[id]:positions.extraTitles![id]!;}
export function imagePosition(positions:Layout,id:GraphicId|'bg'):Placement{return isSticker(id)?positions.stickers![id]:id==='bg'||id==='track'?positions[id]:positions.extraTracks![id]!;}
export function position(positions:Layout,id:ObjectId){return isTitle(id)?titlePosition(positions,id):imagePosition(positions,id);}
export const objectNames:Record<Exclude<ObjectId,StickerId>,string>={bg:'底图',track:'轨道图形',track2:'轨道图形 2',track3:'轨道图形 3',track4:'轨道图形 4',track5:'轨道图形 5',title1:'第一行标题',title2:'第二行标题',title3:'第三行标题',title4:'第四行标题',title5:'第五行标题'};
export const objectName=(project:Project,id:ObjectId)=>isSticker(id)?'贴纸 · '+project.stickers![id].name:objectNames[id];
export const graphicAsset=(project:Project,id:GraphicId)=>isSticker(id)?project.stickers![id].asset:trackFor(project,id).trackAsset;

// Compatibility slots retain the first two titles and first track from v1.
// Presence and stacking are determined only by layerOrder; hidden slots make
// deletion and undo lossless without deleting any original files.
export function addObject(project:Project,kind:'title'|'track'):ObjectId|null{
  const ids=kind==='title'?titleIds:trackIds;
  const id=ids.find(value=>!order(project).includes(value));if(!id)return null;
  project.layerOrder=[id,...order(project)];
  if(isTitle(id)){
    project.titles[titleIds.indexOf(id)]={text:'',color:'#ffffff',glow:0,effects:null,fontId:'system'};
  }else{
    const value:Track={trackAsset:null,maskAsset:null,baseMaskAsset:null,removeBackground:false,trackColor:null,trackGlow:0,trackEffects:null,trackShadow:null,fusion:null,generatedTrack:null};
    if(id==='track')Object.assign(project,value);else(project.extraTracks??={})[id]=value;
  }
  for(const ratio of ['16:9','4:3'] as const){
    const places=project.layouts[ratio];if(!places)continue;const size=dimensions(ratio);
    if(isTitle(id)){
      const p={x:160,y:200+titleIds.indexOf(id)*120,fontSize:72,rotation:0};
      if(id==='title1'||id==='title2')places[id]=p;else(places.extraTitles??={})[id]=p;
    }else{
      const p={x:size.width/2,y:size.height/2,scale:1,rotation:0};
      if(id==='track')places.track=p;else(places.extraTracks??={})[id]=p;
    }
  }
  return id;
}
export function removeObject(project:Project,id:ObjectId){
  if(id==='bg')return;project.layerOrder=order(project).filter(value=>value!==id);
  project.filters=(project.filters||[]).flatMap(filter=>{const targets=filter.targets.filter(target=>target!==id);return targets.length?[{...filter,targets}]:[];});
  if(isSticker(id)){delete project.stickers![id];for(const places of Object.values(project.layouts))if(places)delete places.stickers?.[id];}
}
export function addSticker(project:Project,item:Sticker,asset:Asset):StickerId{
  const id:StickerId=`sticker_${globalThis.crypto.randomUUID().replaceAll('-','')}`;
  (project.stickers??={})[id]=item;project.layerOrder=[id,...order(project)];
  for(const ratio of ['16:9','4:3'] as const){const places=project.layouts[ratio];if(!places)continue;const size=dimensions(ratio);(places.stickers??={})[id]={x:size.width/2,y:size.height/2,scale:Math.min(1,320/Math.max(asset.width,asset.height)),rotation:0};}
  return id;
}
export function reorderObject(project:Project,source:ObjectId,target:ObjectId){
  if(source==='bg'||source===target||!order(project).includes(source)||!order(project).includes(target))return;
  const values=order(project).filter(value=>value!==source);values.splice(values.indexOf(target),0,source);project.layerOrder=values;
}
export function selectedTrackView(project:Project,id:TrackId):Project{
  return {...project,...trackFor(project,id),generatedTrack:trackFor(project,id).generatedTrack??null,layouts:{...project.layouts,[project.activeRatio]:{...layout(project),track:imagePosition(layout(project),id)}}};
}
export function graphicView(project:Project,id:GraphicId):Project{
  return isTrack(id)?selectedTrackView(project,id):{...project,trackAsset:project.stickers![id].asset,maskAsset:null,baseMaskAsset:null,removeBackground:false,trackColor:null,fusion:null};
}
export function changeTrack(project:Project,id:TrackId,mutate:(view:Project)=>void){
  if(!order(project).includes(id))return;
  const view=selectedTrackView(project,id);mutate(view);const target=trackFor(project,id);
  for(const key of ['trackAsset','maskAsset','baseMaskAsset','removeBackground','trackColor','trackGlow','trackEffects','trackShadow','fusion','generatedTrack'] as const)Object.assign(target,{[key]:view[key]});
}
