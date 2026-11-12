import {gradientAlpha,type GradientFusion} from '../domain/fusion';
export function gradientMask(width:number,height:number,settings:GradientFusion){
  const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;
  const ctx=canvas.getContext('2d')!,pixels=ctx.createImageData(width,height);
  for(let y=0;y<height;y++)for(let x=0;x<width;x++){
    const i=(y*width+x)*4;pixels.data[i]=pixels.data[i+1]=pixels.data[i+2]=255;
    pixels.data[i+3]=gradientAlpha(x+.5,y+.5,width,height,settings);
  }
  ctx.putImageData(pixels,0,0);return canvas;
}
