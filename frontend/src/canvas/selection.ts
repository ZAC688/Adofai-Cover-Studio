import {alphaBounds,alphaContour,type AlphaBounds} from '../domain/alphaGeometry';
import type {Placement,Project} from '../domain/project';
import {trackLayer} from './render';
import {canvasShape} from './alpha';
import {rotatePoint,type Point} from '../domain/rotation';

export type TrackGeometry={width:number;height:number;outlineWidth:number;outlineHeight:number;alpha:Uint8ClampedArray;path:string;bounds:AlphaBounds|null;pivot:Point};
const cache=new Map<string,Promise<TrackGeometry>>();
export function getTrackGeometry(project:Project):Promise<TrackGeometry>{
  const fusion=project.fusion?.enabled&&!project.removeBackground;
  const key=[project.trackAsset,project.removeBackground?project.maskAsset:'',fusion?JSON.stringify(project.fusion):''].join(':');
  if(!cache.has(key)){
    const pending=(async()=>{
      const body=await trackLayer(project),width=body.width,height=body.height,alpha=canvasShape(body).alpha;
      const original=fusion?await trackLayer({...project,fusion:null}):body,pivotBounds=canvasShape(original).bounds;
      const pivot={x:pivotBounds?pivotBounds.x+pivotBounds.width/2:width/2,y:pivotBounds?pivotBounds.y+pivotBounds.height/2:height/2};
      const ratio=Math.min(1,512/Math.max(width,height));
      const reduced=document.createElement('canvas');reduced.width=Math.max(1,Math.round(width*ratio));reduced.height=Math.max(1,Math.round(height*ratio));
      reduced.getContext('2d')!.drawImage(body,0,0,reduced.width,reduced.height);
      return {width,height,alpha,pivot,bounds:alphaBounds(alpha,width,height),path:alphaContour(canvasShape(reduced).alpha,reduced.width,reduced.height),outlineWidth:reduced.width,outlineHeight:reduced.height};
    })().catch(error=>{cache.delete(key);throw error;});
    if(cache.size>8)cache.delete(cache.keys().next().value!);cache.set(key,pending);
  }
  return cache.get(key)!;
}
export function trackPivot(geometry:TrackGeometry,placement:Placement):Point{return {x:placement.x+(geometry.pivot.x-geometry.width/2)*placement.scale,y:placement.y+(geometry.pivot.y-geometry.height/2)*placement.scale};}
export function trackBounds(geometry:TrackGeometry,placement:Placement):AlphaBounds|null{
  const b=geometry.bounds;if(!b)return null;
  return {x:placement.x+(b.x-geometry.width/2)*placement.scale,y:placement.y+(b.y-geometry.height/2)*placement.scale,width:b.width*placement.scale,height:b.height*placement.scale};
}
export function trackContains(geometry:TrackGeometry,placement:Placement,point:{x:number;y:number}){
  const box=trackBounds(geometry,placement);if(!box)return false;
  const unrotated=rotatePoint(point,trackPivot(geometry,placement),-(placement.rotation||0));
  const x=Math.floor((unrotated.x-placement.x)/placement.scale+geometry.width/2),y=Math.floor((unrotated.y-placement.y)/placement.scale+geometry.height/2);
  return x>=0&&y>=0&&x<geometry.width&&y<geometry.height&&geometry.alpha[y*geometry.width+x]>=16;
}
