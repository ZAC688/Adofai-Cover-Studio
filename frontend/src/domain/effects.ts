export const effectNames = {
  outerGlow:'外发光', innerGlow:'内发光', bloom:'多尺度 Bloom', stroke:'发光描边',
  gradient:'渐变填充', bevel:'斜面高光', horizontalBlur:'水平模糊',
} as const;
export type EffectKind=keyof typeof effectNames;
export type Effect={enabled:boolean;color:string;color2:string;intensity:number;radius:number;width:number;direction:number;blend:'screen'|'add';followGradient?:boolean};
export type Effects=Record<EffectKind,Effect>;
export function resolveEffects(value:Partial<Effects>|null|undefined,glow:number,color:string):Effects{
  const result={} as Effects;
  for(const kind of Object.keys(effectNames) as EffectKind[]){
    result[kind]={enabled:kind==='outerGlow'&&glow>0,color,color2:'#62bfff',intensity:kind==='gradient'?100:kind==='outerGlow'&&glow>0?glow:55,
      radius:kind==='outerGlow'?Math.max(1,glow*.55):kind==='bloom'?40:18,width:4,direction:90,blend:'screen',followGradient:false,...value?.[kind]};
  }
  return result;
}

/** The same body-relative ramp is used by the fill and every following light. */
export function gradientFraction(x:number,y:number,width:number,height:number,direction:number){
  const angle=direction*Math.PI/180,dx=Math.cos(angle),dy=Math.sin(angle);
  const extent=Math.max(.0001,Math.abs(width*dx/2)+Math.abs(height*dy/2));
  return Math.max(0,Math.min(1,.5+(x*dx+y*dy)/(extent*2)));
}

/** Two-pass octile distance field, with no DOM dependency. */
export function distances(alpha:Uint8ClampedArray,width:number,height:number,toInside:boolean):Float32Array{
  const result=new Float32Array(width*height),diagonal=Math.SQRT2;
  for(let i=0;i<result.length;i++)result[i]=((alpha[i]>12)===toInside)?0:1e6;
  for(let y=0;y<height;y++)for(let x=0;x<width;x++){
    const i=y*width+x;let v=result[i];
    if(x)v=Math.min(v,result[i-1]+1);
    if(y){v=Math.min(v,result[i-width]+1);if(x)v=Math.min(v,result[i-width-1]+diagonal);if(x+1<width)v=Math.min(v,result[i-width+1]+diagonal);}
    result[i]=v;
  }
  for(let y=height-1;y>=0;y--)for(let x=width-1;x>=0;x--){
    const i=y*width+x;let v=result[i];
    if(x+1<width)v=Math.min(v,result[i+1]+1);
    if(y+1<height){v=Math.min(v,result[i+width]+1);if(x)v=Math.min(v,result[i+width-1]+diagonal);if(x+1<width)v=Math.min(v,result[i+width+1]+diagonal);}
    result[i]=v;
  }
  return result;
}

/** X-only box blur; repeating it approximates an anisotropic Gaussian. */
export function horizontalPass(input:Float32Array,width:number,height:number,radius:number):Float32Array{
  radius=Math.max(0,Math.round(radius));if(!radius)return input.slice();
  const output=new Float32Array(input.length),divisor=radius*2+1;
  for(let y=0;y<height;y++){
    let sum=0;const row=y*width;
    for(let x=0;x<=Math.min(radius,width-1);x++)sum+=input[row+x];
    for(let x=0;x<width;x++){
      output[row+x]=sum/divisor;
      if(x-radius>=0)sum-=input[row+x-radius];
      if(x+radius+1<width)sum+=input[row+x+radius+1];
    }
  }
  return output;
}
