import { dimensions, layout, type Assets, type ObjectId, type Project,type TrackId } from '../domain/project';
import {resolveEffects,type Effects} from '../domain/effects';
import {renderEffects} from './effectsClient';
import {RasterCache} from '../services/rasterCache';
import {ensureFont,fontCSS} from '../services/fonts';
import {canvasShape} from './alpha';
import {drawShadow} from './shadow';
import {order,isTitle,isTrack,isSticker,isGraphic,titleFor,trackFor,titlePosition,imagePosition,graphicView,graphicAsset} from '../domain/objects';
import {blendOperation} from '../domain/fusion';
import {gradientMask} from './gradientMask';
import {threeBounds,rememberThreeBounds} from './threeBounds';

const images = new Map<string, Promise<HTMLImageElement>>();
const lightPixels=new RasterCache<Awaited<ReturnType<typeof renderEffects>>>(96*1024*1024,result=>result.canvas.width*result.canvas.height*4);
const sourceIds=new WeakMap<HTMLCanvasElement,number>();let sourceSequence=0;
function sourceId(canvas:HTMLCanvasElement){if(!sourceIds.has(canvas))sourceIds.set(canvas,++sourceSequence);return sourceIds.get(canvas)!;}
function lightLayer(identity:unknown,settings:Effects,prepare:()=>HTMLCanvasElement,cache=true){
  const create=()=>renderEffects(prepare(),settings);
  return cache?lightPixels.get(JSON.stringify([identity,settings]),create):create();
}
export function assetImage(id: string): Promise<HTMLImageElement> {
  if (!images.has(id)) {
    const promise = new Promise<HTMLImageElement>((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => { images.delete(id); reject(new Error('图片加载失败，请重试')); };
      image.src = '/api/assets/' + id;
    });
    images.set(id, promise);
  }
  return images.get(id)!;
}

export function alphaMask(mask: HTMLImageElement) {
  const canvas = document.createElement('canvas'); canvas.width = mask.naturalWidth; canvas.height = mask.naturalHeight;
  const ctx = canvas.getContext('2d',{willReadFrequently:true})!;
  ctx.drawImage(mask, 0, 0);
  const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height);
  for (let i = 0; i < pixels.data.length; i += 4) {
    const value = pixels.data[i]; pixels.data[i] = pixels.data[i+1] = pixels.data[i+2] = 255; pixels.data[i+3] = value;
  }
  ctx.putImageData(pixels, 0, 0); return canvas;
}

const prepared = new Map<string, Promise<HTMLCanvasElement>>();
export async function trackLayer(project: Project,overrideMask?:HTMLCanvasElement) {
  const fusion=project.fusion?.enabled&&!project.removeBackground?project.fusion:null;
  const key = [project.trackAsset, project.removeBackground ? project.maskAsset : '', project.trackColor,JSON.stringify(fusion)].join(':');
  const prepare=async()=>{
      const source = await assetImage(project.trackAsset!);
      const canvas = document.createElement('canvas'); canvas.width = source.naturalWidth; canvas.height = source.naturalHeight;
      const ctx = canvas.getContext('2d',{willReadFrequently:true})!; ctx.drawImage(source, 0, 0);
      if (project.removeBackground && project.maskAsset) {
        ctx.globalCompositeOperation = 'destination-in';
        ctx.drawImage(alphaMask(await assetImage(project.maskAsset)), 0, 0);
      }
      if(fusion&&(overrideMask||fusion.maskAsset||fusion.kind==='gradient')){
        const mask=overrideMask||(fusion.kind==='gradient'?gradientMask(canvas.width,canvas.height,fusion):alphaMask(await assetImage(fusion.maskAsset!)));
        ctx.globalCompositeOperation='destination-in';ctx.drawImage(mask,0,0);
      }
      if (project.trackColor) { ctx.globalCompositeOperation = 'source-in'; ctx.fillStyle = project.trackColor; ctx.fillRect(0, 0, canvas.width, canvas.height); }
      ctx.globalCompositeOperation = 'source-over'; return canvas;
  };
  if(overrideMask)return prepare();
  if (!prepared.has(key)) {
    const pending = prepare().catch(error => {prepared.delete(key); throw error;});
    // Only cache recent layers; project history stores file IDs, not raster copies.
    if (prepared.size > 12) prepared.delete(prepared.keys().next().value!);
    prepared.set(key, pending);
  }
  return prepared.get(key)!;
}

function glow(ctx: CanvasRenderingContext2D, color: string, strength: number, draw: () => void) {
  ctx.save();
  if (strength > 0) { ctx.shadowColor = color; ctx.shadowBlur = strength * .55; draw(); ctx.shadowBlur = strength * .18; }
  draw(); ctx.restore();
}

type CompositionOverrides={fusionMasks?:Partial<Record<TrackId,HTMLCanvasElement>>;filterMasks?:Record<string,HTMLCanvasElement>};
export async function compose(project: Project,overrides:CompositionOverrides={}) {
  const {width, height} = dimensions(project.activeRatio);
  await document.fonts.ready;
  const ids=order(project);
  await Promise.all(ids.filter(isTitle).map(id=>ensureFont(titleFor(project,id).fontId)));
  const background=project.bgAsset?await assetImage(project.bgAsset):null;
  const tracks=new Map(await Promise.all(ids.filter(isGraphic).map(async id=>[id,graphicAsset(project,id)?await trackLayer(graphicView(project,id),isTrack(id)?overrides.fusionMasks?.[id]:undefined):null] as const)));
  const staging = document.createElement('canvas'); staging.width = width; staging.height = height;
  const ctx = staging.getContext('2d',{willReadFrequently:true})!, positions = layout(project);
  const destination=ctx;
  const hasFilters=(id:ObjectId|'canvas')=>(project.filters||[]).some(filter=>filter.enabled&&filter.targets.includes(id));
  const filtered=async(layer:HTMLCanvasElement,id:ObjectId|'canvas')=>hasFilters(id)?(await import('./filters')).filterLayer(layer,id==='canvas'?undefined:staging,project,id,overrides.filterMasks):layer;
  ctx.fillStyle = '#080d16'; ctx.fillRect(0, 0, width, height);
  if (background) {
    const layer=hasFilters('bg')?document.createElement('canvas'):null;if(layer){layer.width=width;layer.height=height;}
    const ctx=layer?layer.getContext('2d',{willReadFrequently:true})!:destination;
    const p = positions.bg;
    ctx.drawImage(background, p.x-background.naturalWidth*p.scale/2, p.y-background.naturalHeight*p.scale/2,
      background.naturalWidth*p.scale, background.naturalHeight*p.scale);
    if(layer)destination.drawImage(await filtered(layer,'bg'),0,0);
  }
  for(const id of [...ids].reverse()){
  if(isGraphic(id)){
    const track=tracks.get(id);if(!track)continue;
    const p = imagePosition(positions,id);
    const fusion=isTrack(id)&&!trackFor(project,id).removeBackground&&trackFor(project,id).fusion?.enabled?trackFor(project,id).fusion:null;
    const layer=fusion||hasFilters(id)?document.createElement('canvas'):null;if(layer){layer.width=width;layer.height=height;}
    const ctx=layer?layer.getContext('2d',{willReadFrequently:true})!:destination;
    ctx.save();
    if(p.rotation){
      const pivotSource=fusion?await trackLayer({...graphicView(project,id),fusion:null}):track;
      const body=canvasShape(pivotSource).bounds;
      const cx=p.x+(body?body.x+body.width/2-track.width/2:0)*p.scale,cy=p.y+(body?body.y+body.height/2-track.height/2:0)*p.scale;
      ctx.translate(cx,cy);ctx.rotate(p.rotation*Math.PI/180);ctx.translate(-cx,-cy);
    }
    if(isSticker(id)){
      const base=document.createElement('canvas');base.width=Math.max(1,Math.ceil(track.width*p.scale));base.height=Math.max(1,Math.ceil(track.height*p.scale));base.getContext('2d',{willReadFrequently:true})!.drawImage(track,0,0,base.width,base.height);
      drawShadow(ctx,base,p.x-base.width/2,p.y-base.height/2,project.stickers![id].shadow);
      ctx.drawImage(base,p.x-base.width/2,p.y-base.height/2);ctx.restore();if(layer)destination.drawImage(await filtered(layer,id),0,0);continue;
    }
    const item=trackFor(project,id),settings=resolveEffects(item.trackEffects,item.trackGlow,item.trackColor||'#ffffff');
    if(item.trackShadow?.enabled){
      const base=document.createElement('canvas');base.width=Math.max(1,Math.ceil(track.width*p.scale));base.height=Math.max(1,Math.ceil(track.height*p.scale));base.getContext('2d',{willReadFrequently:true})!.drawImage(track,0,0,base.width,base.height);
      drawShadow(ctx,base,p.x-base.width/2,p.y-base.height/2,item.trackShadow);
    }
    if(item.trackEffects&&Object.values(settings).some(effect=>effect.enabled)){
      const w=Math.max(1,Math.ceil(track.width*p.scale)),h=Math.max(1,Math.ceil(track.height*p.scale));
      const effect=await lightLayer(['graphic',sourceId(track),w,h],settings,()=>{
        const base=document.createElement('canvas');base.width=w;base.height=h;
        base.getContext('2d',{willReadFrequently:true})!.drawImage(track,0,0,w,h);return base;
      },!isTrack(id)||!overrides.fusionMasks?.[id]);
      ctx.drawImage(effect.canvas,p.x-w/2-effect.padding,p.y-h/2-effect.padding);
    }else glow(ctx,item.trackColor||'#ffffff',item.trackEffects?0:item.trackGlow,()=>ctx.drawImage(track,
      p.x-track.width*p.scale/2,p.y-track.height*p.scale/2,track.width*p.scale,track.height*p.scale));
    ctx.restore();
    if(layer){destination.save();if(fusion&&fusion.kind!=='gradient'){destination.globalAlpha=fusion.opacity/100;destination.globalCompositeOperation=blendOperation(fusion.mode);}destination.drawImage(await filtered(layer,id),0,0);destination.restore();}
  }else if(isTitle(id)){
    const title=titleFor(project,id);if(!title.text)continue;
    const p = titlePosition(positions,id);
    const layer=hasFilters(id)?document.createElement('canvas'):null;if(layer){layer.width=width;layer.height=height;}
    const ctx=layer?layer.getContext('2d',{willReadFrequently:true})!:destination;
    if(title.text3d?.enabled){
      const body=await (await import('./threeText')).renderThreeText(title,p,width,height);
      if(body){
        rememberThreeBounds(title,p,project.activeRatio,{x:body.x,y:body.y,width:body.canvas.width,height:body.canvas.height});
        ctx.save();
        if(p.rotation){const cx=body.x+body.canvas.width/2,cy=body.y+body.canvas.height/2;ctx.translate(cx,cy);ctx.rotate(p.rotation*Math.PI/180);ctx.translate(-cx,-cy);}
        drawShadow(ctx,body.canvas,body.x,body.y,title.shadow);
        const settings=resolveEffects(title.effects,title.glow,title.color);
        if(title.effects&&Object.values(settings).some(effect=>effect.enabled)){
          const effect=await lightLayer(['3d',sourceId(body.canvas)],settings,()=>body.canvas);ctx.drawImage(effect.canvas,body.x-effect.padding,body.y-effect.padding);
        }else glow(ctx,title.color,title.effects?0:title.glow,()=>ctx.drawImage(body.canvas,body.x,body.y));
        ctx.restore();
      }
      if(layer)destination.drawImage(await filtered(layer,id),0,0);
      continue;
    }
    ctx.font = fontCSS(title.fontId,p.fontSize);
    ctx.textBaseline = 'top'; ctx.fillStyle = title.color;
    ctx.save();
    if(p.rotation){const cx=p.x+Math.max(20,ctx.measureText(title.text).width)/2,cy=p.y+p.fontSize*.6;ctx.translate(cx,cy);ctx.rotate(p.rotation*Math.PI/180);ctx.translate(-cx,-cy);}
    const settings=resolveEffects(title.effects,title.glow,title.color);
    if(title.shadow?.enabled){
      const base=document.createElement('canvas');base.width=Math.ceil(ctx.measureText(title.text).width)+4;base.height=Math.ceil(p.fontSize*1.5)+4;
      const body=base.getContext('2d',{willReadFrequently:true})!;body.font=ctx.font;body.textBaseline='top';body.fillStyle=title.color;body.fillText(title.text,2,2);
      drawShadow(ctx,base,p.x-2,p.y-2,title.shadow);
    }
    if(title.effects&&Object.values(settings).some(effect=>effect.enabled)){
      const effect=await lightLayer(['text',title.fontId,title.text,title.color,ctx.font,p.fontSize],settings,()=>{
        const base=document.createElement('canvas');base.width=Math.ceil(ctx.measureText(title.text).width)+4;base.height=Math.ceil(p.fontSize*1.5)+4;
        const body=base.getContext('2d',{willReadFrequently:true})!;body.font=ctx.font;body.textBaseline='top';body.fillStyle=title.color;body.fillText(title.text,2,2);return base;
      });ctx.drawImage(effect.canvas,p.x-2-effect.padding,p.y-2-effect.padding);
    }else glow(ctx,title.color,title.effects?0:title.glow,()=>ctx.fillText(title.text,p.x,p.y));
    ctx.restore();
    if(layer)destination.drawImage(await filtered(layer,id),0,0);
  }
  }
  return await filtered(staging,'canvas');
}

/** Keep the display surface stable; resizing it for every edit reallocates it. */
export function presentComposition(canvas:HTMLCanvasElement,frame:HTMLCanvasElement){
  if(canvas.width!==frame.width)canvas.width=frame.width;
  if(canvas.height!==frame.height)canvas.height=frame.height;
  const ctx=canvas.getContext('2d',{willReadFrequently:true})!;
  ctx.clearRect(0,0,canvas.width,canvas.height);ctx.drawImage(frame,0,0);
}

export async function drawComposition(canvas:HTMLCanvasElement,project:Project,overrides:CompositionOverrides={}){
  presentComposition(canvas,await compose(project,overrides));
}

export type Bounds = {x: number; y: number; width: number; height: number};
export function objectBounds(project: Project, assets: Assets, id: ObjectId): Bounds | null {
  const positions=layout(project);
  if (id === 'bg' || isGraphic(id)) {
    const p=imagePosition(positions,id);
    const asset = assets[(id === 'bg' ? project.bgAsset : graphicAsset(project,id)) || ''];
    if (!asset) return null;
    const scale = p.scale;
    return {x: p.x - asset.width*scale/2, y: p.y-asset.height*scale/2, width: asset.width*scale, height: asset.height*scale};
  }
  const title = titleFor(project,id),p=titlePosition(positions,id);
  if (!title.text) return null;
  if(title.text3d?.enabled){const bounds=threeBounds(title,p,project.activeRatio);if(bounds)return bounds;}
  const fontSize = p.fontSize;
  const ctx = document.createElement('canvas').getContext('2d',{willReadFrequently:true})!;
  ctx.font = fontCSS(title.fontId,fontSize);
  return {x: p.x, y: p.y, width: Math.max(20, ctx.measureText(title.text).width), height: fontSize*1.2};
}
