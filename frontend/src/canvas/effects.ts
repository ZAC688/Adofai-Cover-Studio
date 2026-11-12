import {distances,horizontalPass,gradientFraction,type Effects,type Effect} from '../domain/effects';

function surface(width:number,height:number){
  if(typeof document==='undefined')return new OffscreenCanvas(width,height);
  const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;return canvas;
}
function tint(alpha:ArrayLike<number>,width:number,height:number,color:string,gradient?:{effect:Effect;baseWidth:number;baseHeight:number}){
  const canvas=surface(width,height),ctx=canvas.getContext('2d',{willReadFrequently:true})!,pixels=ctx.createImageData(width,height);
  const r=parseInt(color.slice(1,3),16),g=parseInt(color.slice(3,5),16),b=parseInt(color.slice(5,7),16);
  const start=gradient?[1,3,5].map(at=>parseInt(gradient.effect.color.slice(at,at+2),16)):[r,g,b];
  const finish=gradient?[1,3,5].map(at=>parseInt(gradient.effect.color2.slice(at,at+2),16)):start;
  for(let i=0;i<alpha.length;i++){
    const at=i*4,t=gradient?gradientFraction(i%width+.5-width/2,Math.floor(i/width)+.5-height/2,gradient.baseWidth,gradient.baseHeight,gradient.effect.direction):0;
    for(let channel=0;channel<3;channel++)pixels.data[at+channel]=start[channel]+(finish[channel]-start[channel])*t;
    pixels.data[at+3]=Math.min(255,Math.max(0,alpha[i]));
  }
  ctx.putImageData(pixels,0,0);return canvas;
}
export function effectsMargin(effects:Effects){
  return Math.ceil(Math.max(4,...Object.values(effects).filter(e=>e.enabled).map(e=>e.radius*3+e.width)));
}
export function applyEffects(base:HTMLCanvasElement|OffscreenCanvas,effects:Effects){
  const padding=effectsMargin(effects),width=base.width+padding*2,height=base.height+padding*2;
  const shape=surface(width,height),shapeCtx=shape.getContext('2d',{willReadFrequently:true})!;shapeCtx.drawImage(base,padding,padding);
  const data=shapeCtx.getImageData(0,0,width,height),alpha=new Uint8ClampedArray(width*height);
  for(let i=0;i<alpha.length;i++)alpha[i]=data.data[i*4+3];
  const output=surface(width,height),ctx=output.getContext('2d',{willReadFrequently:true})!;
  const colorMask=(effect:Effect,values:ArrayLike<number>=alpha)=>tint(values,width,height,effect.color,effect.followGradient?{effect:effects.gradient,baseWidth:base.width,baseHeight:base.height}:undefined);
  const paint=(canvas:CanvasImageSource,effect:Effect,opacity=1,blur=0)=>{
    ctx.save();ctx.globalCompositeOperation=effect.blend==='add'?'lighter':'screen';
    ctx.globalAlpha=Math.min(1,effect.intensity/100*opacity);ctx.filter=blur>0?`blur(${blur}px)`:'none';ctx.drawImage(canvas,0,0);ctx.restore();
  };
  // Far-to-near light order. The clear body is drawn after all external light.
  const bloom=effects.bloom;
  if(bloom.enabled){const mask=colorMask(bloom);for(const [scale,opacity] of [[2.2,.30],[1,.36],[.4,.24]])paint(mask,bloom,opacity,bloom.radius*scale);}
  const outer=effects.outerGlow;
  if(outer.enabled){const mask=colorMask(outer);paint(mask,outer,.75,outer.radius);paint(mask,outer,.45,outer.radius*.32);}
  const horizontal=effects.horizontalBlur;
  if(horizontal.enabled){let blurred:Float32Array=Float32Array.from(alpha);for(let i=0;i<3;i++)blurred=horizontalPass(blurred,width,height,horizontal.radius/2);paint(colorMask(horizontal,blurred),horizontal,.8);}
  const inside=(effects.innerGlow.enabled||effects.bevel.enabled)?distances(alpha,width,height,false):null;
  if(effects.stroke.enabled){
    const stroke=effects.stroke,outside=distances(alpha,width,height,true),ring=new Float32Array(alpha.length);
    for(let i=0;i<ring.length;i++)ring[i]=Math.max(0,Math.min(1,stroke.width+.5-outside[i]))*(1-alpha[i]/255)*255;
    const colored=colorMask(stroke,ring);paint(colored,stroke,.7,stroke.radius*.3);paint(colored,stroke);
  }
  ctx.drawImage(shape,0,0);
  if(effects.gradient.enabled){
    const effect=effects.gradient,fill=surface(width,height),fillCtx=fill.getContext('2d',{willReadFrequently:true})!;
    const angle=effect.direction*Math.PI/180,dx=Math.cos(angle),dy=Math.sin(angle);
    const extent=Math.abs(base.width*dx/2)+Math.abs(base.height*dy/2),cx=width/2,cy=height/2;
    const gradient=fillCtx.createLinearGradient(cx-dx*extent,cy-dy*extent,cx+dx*extent,cy+dy*extent);
    gradient.addColorStop(0,effect.color);gradient.addColorStop(1,effect.color2);fillCtx.fillStyle=gradient;fillCtx.fillRect(0,0,width,height);
    fillCtx.globalCompositeOperation='destination-in';fillCtx.drawImage(shape,0,0);
    ctx.save();ctx.globalAlpha=effect.intensity/100;ctx.drawImage(fill,0,0);ctx.restore();
  }
  if(effects.innerGlow.enabled&&inside){
    const effect=effects.innerGlow,edge=new Float32Array(alpha.length);
    for(let i=0;i<edge.length;i++)edge[i]=alpha[i]*Math.max(0,1-inside[i]/Math.max(1,effect.radius));
    paint(colorMask(effect,edge),effect,.65);
  }
  if(effects.bevel.enabled&&inside){
    const effect=effects.bevel,edge=new Float32Array(alpha.length),angle=effect.direction*Math.PI/180;
    for(let y=1;y<height-1;y++)for(let x=1;x<width-1;x++){
      const i=y*width+x;if(!alpha[i])continue;
      const gx=(inside[i+1]-inside[i-1])*.5,gy=(inside[i+width]-inside[i-width])*.5;
      const facing=Math.max(0,-gx*Math.cos(angle)-gy*Math.sin(angle));
      edge[i]=alpha[i]*Math.min(1,facing)*Math.max(0,1-inside[i]/Math.max(1,effect.radius));
    }
    paint(colorMask(effect,edge),effect,.8);
  }
  return {canvas:output,padding};
}
