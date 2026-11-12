import {autoDetectRenderer,Container,Sprite,Texture,CanvasSource,Rectangle,type Renderer,type Filter} from 'pixi.js';
import * as community from 'pixi-filters';
import {filterCatalog,defaultRegion,type FilterSpec,type Value} from '../domain/filters';
import type {Project,ObjectId} from '../domain/project';
import {assetImage,alphaMask} from './render';

let gpu:Promise<Renderer>|null=null;
let pending:Promise<unknown>=Promise.resolve();
function canvas(width:number,height:number){const result=document.createElement('canvas');result.width=width;result.height=height;return result;}
function texture(source:HTMLCanvasElement|HTMLImageElement){
  if(source instanceof HTMLImageElement){const copy=canvas(source.naturalWidth,source.naturalHeight);copy.getContext('2d')!.drawImage(source,0,0);source=copy;}
  return new Texture({source:new CanvasSource({resource:source,resolution:1})});
}
function defaultMap(lut:boolean){
  const output=canvas(lut?256:256,lut?16:256),ctx=output.getContext('2d')!;
  if(lut){const pixels=ctx.createImageData(256,16);for(let y=0;y<16;y++)for(let x=0;x<256;x++){const at=(y*256+x)*4;pixels.data[at]=Math.min(255,(x%16)*17+25);pixels.data[at+1]=y*15;pixels.data[at+2]=Math.floor(x/16)*13;pixels.data[at+3]=255;}ctx.putImageData(pixels,0,0);}
  else{const gradient=ctx.createRadialGradient(128,128,0,128,128,180);gradient.addColorStop(0,'#fff4bc');gradient.addColorStop(1,'#304570');ctx.fillStyle=gradient;ctx.fillRect(0,0,256,256);}
  return output;
}
const maps=new Map<boolean,HTMLCanvasElement>();
function deterministic<T>(seed:number,build:()=>T){
  let state=(Math.round(seed*1e6)||17)>>>0;const previous=Math.random;
  Math.random=()=>{state=(Math.imul(1664525,state)+1013904223)>>>0;return state/4294967296;};
  try{return build();}finally{Math.random=previous;}
}
async function create(spec:FilterSpec,width:number,height:number){
  const params=structuredClone(spec.params) as Record<string,Value|Texture>,textures:Texture[]=[];
  for(const field of filterCatalog.find(entry=>entry.type===spec.type)!.fields){
    if(field.type==='texture'){
      const id=params[field.key];let source:HTMLImageElement|HTMLCanvasElement;
      if(typeof id==='string'){source=await assetImage(id);if(field.key==='colorMap'&&source.naturalWidth!==source.naturalHeight**2)throw new Error('色彩查找表尺寸应为 N² × N，例如 256 × 16');}
      else{const lut=field.key==='colorMap';if(!maps.has(lut))maps.set(lut,defaultMap(lut));source=maps.get(lut)!;}
      const map=texture(source);textures.push(map);params[field.key]=map;
    }
  }
  const pointKeys=spec.type==='BulgePinchFilter'?[]:spec.type==='TwistFilter'?['offset']:spec.type.startsWith('TiltShift')?['start','end']:['center'];
  for(const key of pointKeys){const point=params[key] as {x:number;y:number}|undefined;if(point)params[key]={x:point.x*width,y:point.y*height};}
  const Ctor=(community as unknown as Record<string,new(options?:unknown)=>Filter>)[spec.type];
  if(Array.isArray(params.kernels)&&!params.kernels.length)delete params.kernels;
  if(spec.type==='MultiColorReplaceFilter')params.maxColors=Math.max(Number(params.maxColors||1),(params.replacements as Value[]).length);
  let filter:Filter;
  if(spec.type==='PixelateFilter')filter=new Ctor(params.size);
  else if(spec.type==='EmbossFilter')filter=new Ctor(params.strength);
  else filter=deterministic(Number(params.seed??0),()=>new Ctor(params));
  if(spec.type==='ShockwaveFilter')(filter as Filter&{time:number}).time=Number(params.time??.7);
  if(spec.type.startsWith('TiltShift'))(filter as Filter&{updateDelta:()=>void}).updateDelta();
  return {filter,textures};
}
async function native(input:HTMLCanvasElement,backdrop:HTMLCanvasElement|undefined,spec:FilterSpec){
  if(!gpu)gpu=autoDetectRenderer({width:input.width,height:input.height,preference:'webgl',backgroundAlpha:0,antialias:false,resolution:1,preserveDrawingBuffer:true}).catch(error=>{gpu=null;throw error;});
  const renderer=await gpu;renderer.resize(input.width,input.height);
  const stage=new Container(),inputTexture=texture(input),front=new Sprite(inputTexture),owned:Texture[]=[inputTexture];
  const {filter,textures}=await create(spec,input.width,input.height);owned.push(...textures);
  const backgroundBlur=spec.type==='BackdropBlurFilter';
  try{
    if(backgroundBlur){const backTexture=texture(backdrop||input);owned.push(backTexture);stage.addChild(new Sprite(backTexture));front.alpha=Number(spec.params.frontAlpha??.15);}
    front.filterArea=new Rectangle(0,0,input.width,input.height);front.filters=[filter];stage.addChild(front);
    renderer.render({container:stage,clear:true});
    const output=canvas(input.width,input.height),ctx=output.getContext('2d')!;ctx.drawImage(renderer.canvas as HTMLCanvasElement,0,0);
    if(backgroundBlur){ctx.globalCompositeOperation='destination-in';ctx.drawImage(input,0,0);}
    return output;
  }finally{stage.destroy({children:true});filter.destroy();for(const item of owned)item.destroy(true);}
}
export async function regionMask(spec:FilterSpec,project:Project,width:number,height:number,override?:HTMLCanvasElement){
  const region=spec.regions[project.activeRatio]||defaultRegion();if(region.mode==='all')return null;
  const mask=canvas(width,height),ctx=mask.getContext('2d')!;
  if(region.mode==='paint'){if(override)ctx.drawImage(override,0,0,width,height);else if(region.maskAsset)ctx.drawImage(alphaMask(await assetImage(region.maskAsset)),0,0,width,height);}
  else{ctx.fillStyle='#fff';ctx.filter=region.feather?`blur(${region.feather}px)`:'none';ctx.fillRect(region.x*width,region.y*height,region.width*width,region.height*height);}
  return mask;
}
export async function filterLayer(input:HTMLCanvasElement,backdrop:HTMLCanvasElement|undefined,project:Project,target:ObjectId|'canvas',masks?:Record<string,HTMLCanvasElement>){
  const list=(project.filters||[]).filter(filter=>filter.enabled&&filter.targets.includes(target));if(!list.length)return input;
  const run=async()=>{
    let result=input;
    for(const spec of list){
      const filtered=await native(result,backdrop,spec),mask=await regionMask(spec,project,input.width,input.height,masks?.[spec.id]);
      if(!mask){result=filtered;continue;}
      const output=canvas(input.width,input.height),ctx=output.getContext('2d')!,part=canvas(input.width,input.height),partCtx=part.getContext('2d')!;
      ctx.drawImage(result,0,0);ctx.globalCompositeOperation='destination-out';ctx.drawImage(mask,0,0);
      partCtx.drawImage(filtered,0,0);partCtx.globalCompositeOperation='destination-in';partCtx.drawImage(mask,0,0);
      ctx.globalCompositeOperation='lighter';ctx.drawImage(part,0,0);result=output;
    }
    return result;
  };
  const result=pending.then(run,run);pending=result.catch(()=>{});return result;
}
