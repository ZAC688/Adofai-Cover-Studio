export type AlphaBounds={x:number;y:number;width:number;height:number};
export function alphaBounds(alpha:Uint8ClampedArray,width:number,height:number):AlphaBounds|null{
  let left=width,top=height,right=-1,bottom=-1;
  for(let y=0;y<height;y++)for(let x=0;x<width;x++)if(alpha[y*width+x]>=16){left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);}
  return right<left?null:{x:left,y:top,width:right-left+1,height:bottom-top+1};
}

/** Directed pixel-cell boundaries retain concavities, islands and transparent holes. */
export function alphaContour(alpha:Uint8ClampedArray,width:number,height:number):string{
  const stride=width+1,edges=new Map<number,number[]>();
  function add(from:number,to:number){const next=edges.get(from)||[];next.push(to);edges.set(from,next);}
  const solid=(x:number,y:number)=>x>=0&&y>=0&&x<width&&y<height&&alpha[y*width+x]>=16;
  for(let y=0;y<height;y++)for(let x=0;x<width;x++)if(solid(x,y)){
    const a=y*stride+x,b=a+1,c=b+stride,d=a+stride;
    if(!solid(x,y-1))add(a,b);if(!solid(x+1,y))add(b,c);if(!solid(x,y+1))add(c,d);if(!solid(x-1,y))add(d,a);
  }
  const paths:string[]=[];
  while(edges.size){
    const start=edges.keys().next().value!;const points:number[]=[];let at=start;
    do{
      points.push(at);const next=edges.get(at);if(!next?.length)break;
      const destination=next.pop()!;if(!next.length)edges.delete(at);at=destination;
    }while(at!==start);
    const corners=points.filter((point,index)=>{
      const prev=points[(index+points.length-1)%points.length],next=points[(index+1)%points.length];
      return (point%stride-prev%stride)!==(next%stride-point%stride)||Math.floor(point/stride)-Math.floor(prev/stride)!==Math.floor(next/stride)-Math.floor(point/stride);
    });
    if(corners.length>2)paths.push(corners.map((point,index)=>(index?'L':'M')+(point%stride)+','+Math.floor(point/stride)).join(' ')+'Z');
  }
  return paths.join(' ');
}
