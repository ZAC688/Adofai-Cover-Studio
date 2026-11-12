export type FusionMode='normal'|'multiply'|'screen'|'overlay'|'soft-light'|'add';
export type LegacyFusion={kind?:undefined;enabled:boolean;maskAsset:string|null;mode:FusionMode;opacity:number};
export type GradientFusion={kind:'gradient';enabled:boolean;maskAsset:string|null;position:number;width:number;angle:number;reverse:boolean};
export type Fusion=LegacyFusion|GradientFusion;
export const fusionModes:Record<FusionMode,string>={normal:'正常',multiply:'正片叠底',screen:'滤色',overlay:'叠加','soft-light':'柔光',add:'线性减淡（Add）'};
export const resolveFusion=(value?:LegacyFusion|null):LegacyFusion=>({enabled:true,maskAsset:null,mode:'normal',opacity:100,...value});
export const newGradientFusion=():GradientFusion=>({kind:'gradient',enabled:true,maskAsset:null,position:50,width:50,angle:0,reverse:false});
export function gradientAlpha(x:number,y:number,width:number,height:number,settings:GradientFusion){
  const radians=settings.angle*Math.PI/180,c=Math.cos(radians),s=Math.sin(radians);
  const span=Math.abs(c)*width+Math.abs(s)*height;
  const at=.5+((x-width/2)*c+(y-height/2)*s)/span;
  const t=Math.max(0,Math.min(1,(at-settings.position/100)/(settings.width/100)+.5));
  const smooth=t*t*(3-2*t);return Math.round(255*(settings.reverse?1-smooth:smooth));
}
export function blendOperation(mode:FusionMode):GlobalCompositeOperation{return mode==='normal'?'source-over':mode==='add'?'lighter':mode;}
