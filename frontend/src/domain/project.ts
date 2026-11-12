export type Ratio = '16:9' | '4:3';
export type TitleId='title1'|'title2'|'title3'|'title4'|'title5';
export type TrackId='track'|'track2'|'track3'|'track4'|'track5';
export type StickerId=`sticker_${string}`;
export type GraphicId=TrackId|StickerId;
export type ObjectId = 'bg' | GraphicId | TitleId;
export type Placement = { x: number; y: number; scale: number;rotation?:number };
export type TextPlacement = { x: number; y: number; fontSize: number;rotation?:number };
export type Layout = { bg: Placement; track: Placement; title1: TextPlacement; title2: TextPlacement;
  extraTitles?:Partial<Record<TitleId,TextPlacement>>;extraTracks?:Partial<Record<TrackId,Placement>>;stickers?:Record<StickerId,Placement> };
export type Title = { text: string; color: string; glow: number; effects?:import('./effects').Effects|null;fontId?:string;shadow?:import('./shadow').Shadow|null;text3d?:import('./text3d').Text3D|null };
export type Asset = { id: string; width: number; height: number; kind: string };
export type Assets = Record<string, Asset>;
export type ChartRecipe={sourceId:string;start:number;end:number;style:'gold'|'chart';aspect:'16:9'|'4:3'|'tight';resolution:1920|2560|3840|4096;margin:number;icons:boolean;rotate:boolean;labels:boolean;crop:[number,number,number,number]|null};
export type Track = {trackAsset:string|null;maskAsset:string|null;baseMaskAsset:string|null;removeBackground:boolean;trackColor:string|null;trackGlow:number;trackEffects?:import('./effects').Effects|null;trackShadow?:import('./shadow').Shadow|null;fusion?:import('./fusion').Fusion|null;generatedTrack?:ChartRecipe|null};
export type Sticker={asset:string;name:string;presetId:string;frame:number;shadow?:import('./shadow').Shadow|null};
export type Project = {
  schemaVersion: 1; name: string; activeRatio: Ratio;
  bgAsset: string | null; trackAsset: string | null;
  maskAsset: string | null; baseMaskAsset: string | null; removeBackground: boolean;
  trackColor: string | null; trackGlow: number; titles: Title[];
  trackEffects?:import('./effects').Effects|null;
  trackShadow?:import('./shadow').Shadow|null;
  fusion?:import('./fusion').Fusion|null;
  generatedTrack?:ChartRecipe|null;
  layouts: Record<Ratio, Layout | null>;
  extraTracks?:Partial<Record<TrackId,Track>>;
  layerOrder?:ObjectId[];
  stickers?:Record<StickerId,Sticker>;
  filters?:import('./filters').FilterSpec[];
};
export type Loaded = { revision: number; project: Project; assets: Assets };
export const dimensions = (ratio: Ratio) => ({ width: ratio === '16:9' ? 1920 : 1440, height: 1080 });
export function layout(project: Project) { return project.layouts[project.activeRatio]!; }
export function fitScale(image: {width: number; height: number}, canvas: {width: number; height: number}, cover = true) {
  return (cover ? Math.max : Math.min)(canvas.width / image.width, canvas.height / image.height);
}
export function screenPoint(client: {x: number; y: number}, rect: {left: number; top: number; width: number; height: number}, canvas: {width: number; height: number}) {
  return {x: (client.x - rect.left) * canvas.width / rect.width, y: (client.y - rect.top) * canvas.height / rect.height};
}
export function changeRatio(project: Project, ratio: Ratio, assets: Assets): Project {
  if (ratio === project.activeRatio) return project;
  const next = structuredClone(project);
  if (!next.layouts[ratio]) {
    const oldSize = dimensions(project.activeRatio), size = dimensions(ratio);
    const scale = Math.min(size.width / oldSize.width, size.height / oldSize.height);
    const copy = structuredClone(layout(project));
    for (const key of ['bg', 'track', 'title1', 'title2'] as const) {
      copy[key].x *= size.width / oldSize.width;
      copy[key].y *= size.height / oldSize.height;
    }
    copy.track.scale *= scale;
    copy.title1.fontSize *= scale; copy.title2.fontSize *= scale;
    for(const placement of Object.values(copy.extraTitles||{})){placement.x*=size.width/oldSize.width;placement.y*=size.height/oldSize.height;placement.fontSize*=scale;}
    for(const placement of Object.values(copy.extraTracks||{})){placement.x*=size.width/oldSize.width;placement.y*=size.height/oldSize.height;placement.scale*=scale;}
    for(const placement of Object.values(copy.stickers||{})){placement.x*=size.width/oldSize.width;placement.y*=size.height/oldSize.height;placement.scale*=scale;}
    if (next.bgAsset && assets[next.bgAsset]) {
      copy.bg = {x: size.width / 2, y: size.height / 2, scale: fitScale(assets[next.bgAsset], size)};
    }
    next.layouts[ratio] = copy;
  }
  next.activeRatio = ratio;
  return next;
}

export class History<T> {
  private past: T[] = [];
  private future: T[] = [];
  remember(before: T) { this.past.push(structuredClone(before)); if (this.past.length > 60) this.past.shift(); this.future = []; }
  undo(current: T): T | null { const previous = this.past.pop(); if (!previous) return null; this.future.push(structuredClone(current)); return previous; }
  redo(current: T): T | null { const next = this.future.pop(); if (!next) return null; this.past.push(structuredClone(current)); return next; }
  canUndo() { return this.past.length > 0; }
  canRedo() { return this.future.length > 0; }
}
