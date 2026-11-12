import type {AlphaBounds} from './alphaGeometry';
export type Point={x:number;y:number};
export function center(bounds:AlphaBounds):Point{return {x:bounds.x+bounds.width/2,y:bounds.y+bounds.height/2};}
export function rotatePoint(point:Point,pivot:Point,degrees:number):Point{
  const angle=degrees*Math.PI/180,c=Math.cos(angle),s=Math.sin(angle),x=point.x-pivot.x,y=point.y-pivot.y;
  return {x:pivot.x+x*c-y*s,y:pivot.y+x*s+y*c};
}
export function normalizeDegrees(angle:number){return ((angle+180)%360+360)%360-180;}
export function boxContains(bounds:AlphaBounds,point:Point,degrees=0){
  const p=rotatePoint(point,center(bounds),-degrees);
  return p.x>=bounds.x&&p.y>=bounds.y&&p.x<=bounds.x+bounds.width&&p.y<=bounds.y+bounds.height;
}
