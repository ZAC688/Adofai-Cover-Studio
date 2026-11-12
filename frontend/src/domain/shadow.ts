export type Shadow={enabled:boolean;color:string;opacity:number;blur:number;distance:number;direction:number};
export function resolveShadow(value?:Shadow|null):Shadow{return {enabled:false,color:'#000000',opacity:55,blur:18,distance:20,direction:135,...value};}
export function shadowOffset(shadow:Shadow){const angle=shadow.direction*Math.PI/180;return {x:Math.cos(angle)*shadow.distance,y:Math.sin(angle)*shadow.distance};}
