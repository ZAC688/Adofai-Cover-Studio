import {resolveShadow,shadowOffset,type Shadow} from '../domain/shadow';

/** Draw only the tinted alpha silhouette; the original body is drawn once later. */
export function drawShadow(ctx:CanvasRenderingContext2D,base:HTMLCanvasElement,x:number,y:number,value?:Shadow|null){
  const settings=resolveShadow(value);if(!settings.enabled||settings.opacity<=0)return;
  const tint=document.createElement('canvas');tint.width=base.width;tint.height=base.height;
  const body=tint.getContext('2d')!;body.drawImage(base,0,0);body.globalCompositeOperation='source-in';body.fillStyle=settings.color;body.fillRect(0,0,tint.width,tint.height);
  const offset=shadowOffset(settings);
  ctx.save();ctx.globalAlpha=settings.opacity/100;ctx.filter=settings.blur>0?`blur(${settings.blur}px)`:'none';ctx.drawImage(tint,x+offset.x,y+offset.y);ctx.restore();
}
