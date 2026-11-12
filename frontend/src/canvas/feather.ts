export type Brush={size:number;softness:number;strength:number;tool:'erase'|'restore'};
export function brushStroke(mask:HTMLCanvasElement,from:{x:number;y:number},to:{x:number;y:number},brush:Brush){
  const ctx=mask.getContext('2d')!,radius=brush.size/2;
  const steps=Math.ceil(Math.hypot(to.x-from.x,to.y-from.y)/Math.max(1,radius*.2));
  ctx.save();ctx.globalCompositeOperation=brush.tool==='erase'?'destination-out':'source-over';
  for(let step=steps?1:0;step<=steps;step++){
    const t=steps?step/steps:1,x=from.x+(to.x-from.x)*t,y=from.y+(to.y-from.y)*t;
    const inner=Math.min(radius-.001,radius*(1-brush.softness/100));
    const gradient=ctx.createRadialGradient(x,y,Math.max(0,inner),x,y,radius);
    gradient.addColorStop(0,`rgba(255,255,255,${brush.strength/100})`);gradient.addColorStop(1,'rgba(255,255,255,0)');
    ctx.fillStyle=gradient;ctx.fillRect(x-radius,y-radius,brush.size,brush.size);
  }
  ctx.restore();
}
export async function maskBlob(mask:HTMLCanvasElement){
  const canvas=document.createElement('canvas');canvas.width=mask.width;canvas.height=mask.height;const ctx=canvas.getContext('2d')!,data=mask.getContext('2d')!.getImageData(0,0,mask.width,mask.height);
  for(let i=0;i<data.data.length;i+=4){data.data[i]=data.data[i+1]=data.data[i+2]=data.data[i+3];data.data[i+3]=255;}
  ctx.putImageData(data,0,0);return new Promise<Blob>((resolve,reject)=>canvas.toBlob(value=>value?resolve(value):reject(new Error('融合蒙版生成失败')),'image/png'));
}
