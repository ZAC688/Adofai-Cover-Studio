import {alphaBounds} from '../domain/alphaGeometry';
const cache=new WeakMap<HTMLCanvasElement,ReturnType<typeof extract>>();
function extract(canvas:HTMLCanvasElement){
  const rgba=canvas.getContext('2d')!.getImageData(0,0,canvas.width,canvas.height).data;
  const alpha=new Uint8ClampedArray(canvas.width*canvas.height);for(let i=0;i<alpha.length;i++)alpha[i]=rgba[i*4+3];
  return {alpha,bounds:alphaBounds(alpha,canvas.width,canvas.height)};
}
/** Prepared source canvases are immutable; don't cache editable mask canvases here. */
export function canvasShape(canvas:HTMLCanvasElement){if(!cache.has(canvas))cache.set(canvas,extract(canvas));return cache.get(canvas)!;}
