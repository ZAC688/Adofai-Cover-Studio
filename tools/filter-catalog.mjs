import * as upstream from '../frontend/node_modules/pixi-filters/lib/index.mjs';
import {Texture} from '../frontend/node_modules/pixi.js/lib/index.mjs';
import {writeFileSync} from 'node:fs';

const labels={Adjustment:'颜色调整',AdvancedBloom:'高级泛光',Ascii:'字符画',BackdropBlur:'背景模糊',Bevel:'斜面',Bloom:'泛光',BulgePinch:'膨胀收缩',CRT:'CRT 显示器',ColorGradient:'颜色渐变',ColorMap:'色彩查找表',ColorOverlay:'颜色覆盖',ColorReplace:'颜色替换',Convolution:'卷积',CrossHatch:'交叉排线',Dot:'网点',DropShadow:'投影',Emboss:'浮雕',Glitch:'故障',Glow:'辉光',Godray:'光束',Grayscale:'灰度',HslAdjustment:'色相饱和度',KawaseBlur:'Kawase 模糊',MotionBlur:'运动模糊',MultiColorReplace:'多色替换',OldFilm:'旧胶片',Outline:'描边',Pixelate:'像素化',RGBSplit:'RGB 分离',RadialBlur:'径向模糊',Reflection:'倒影',Shockwave:'冲击波',SimpleLightmap:'光照贴图',SimplexNoise:'单纯形噪声',TiltShiftAxis:'单轴移轴',TiltShift:'移轴',Twist:'扭曲',ZoomBlur:'缩放模糊'};
const extras={BackdropBlurFilter:{strength:8,quality:4,kernelSize:5,frontAlpha:.15},EmbossFilter:{strength:5},PixelateFilter:{size:{x:10,y:10}},MotionBlurFilter:{velocity:{x:12,y:0}},ConvolutionFilter:{matrix:[0,-1,0,-1,5,-1,0,-1,0]},ShockwaveFilter:{time:.7},RadialBlurFilter:{angle:15},TiltShiftAxisFilter:{axis:'horizontal'},DropShadowFilter:{kernels:[]},MultiColorReplaceFilter:{maxColors:1}};
const clean=value=>value instanceof Texture?null:ArrayBuffer.isView(value)?Array.from(value):Array.isArray(value)?value.map(clean):value&&typeof value==='object'?Object.fromEntries(Object.entries(value).map(([k,v])=>[k,clean(v)])):value;
function fields(defaults){return Object.entries(defaults).map(([key,value])=>{
  let type=typeof value==='boolean'?'boolean':typeof value==='number'?'number':typeof value==='string'?'select':Array.isArray(value)?'array':value&&'x'in value?'point':'texture';
  if(key==='color'||key.endsWith('Color')){type='color';value='#'+Number(value).toString(16).padStart(6,'0');}
  let min=-10000,max=10000,step=.01;
  if(/^(alpha|.*Alpha|threshold|tolerance|boundary|mix|seed)$/.test(key)){min=0;max=1;}
  if(key==='quality'){min=.01;max=20;}
  if(/^(size|width|height|distance|thickness|blur|strength|gradientBlur|noiseSize|scratchWidth|lineWidth|noiseScale|gain|lacunarity|gamma|wavelength)$/.test(key)){min=.01;max=key==='width'||key==='height'?10000:1000;}
  if(key==='radius'){min=-1;max=4000;}
  if(/^(kernelSize|maxKernelSize|slices|sampleSize|maxColors|type|fillMode)$/.test(key)){min=['maxColors','type','fillMode'].includes(key)?0:1;max=key==='type'?2:key==='fillMode'?4:key==='kernelSize'?25:key==='maxKernelSize'?64:512;step=1;}
  return {key,type,value,min,max,step,...(type==='select'?{options:key==='axis'?['horizontal','vertical']:[value]}:{})};
});}
const filters=Object.entries(upstream).filter(([name,value])=>name.endsWith('Filter')&&typeof value==='function').map(([name,Ctor])=>{
  const defaults=clean({...Ctor.DEFAULT_OPTIONS,...Ctor.defaults,...extras[name]});
  if('center'in defaults)defaults.center={x:.5,y:.5};
  if(name==='TwistFilter')defaults.offset={x:.5,y:.5};
  if(name.startsWith('TiltShift')){defaults.start={x:0,y:.5};defaults.end={x:1,y:.5};}
  const params=fields(defaults);
  for(const field of params){
    if(field.key==='quality'){field.min=name==='GlowFilter'||name==='OutlineFilter'?.01:1;field.max=name==='GlowFilter'||name==='OutlineFilter'?1:10;field.step=field.min===1?1:.01;}
    if(name==='BulgePinchFilter'&&field.key==='strength'){field.min=-1;field.max=1;}
    if(['center','start','end'].includes(field.key)||name==='TwistFilter'&&field.key==='offset'){field.min=0;field.max=1;}
    if(field.key==='pixelSize'){field.min=.1;field.max=10;}
    if(['blur','strength'].includes(field.key)&&/Blur|Bloom/.test(name))field.max=120;
    if(field.key==='distance'||field.key==='padding')field.max=180;
    if(field.key==='kernelSize'){field.min=5;field.max=name==='BloomFilter'||name==='BackdropBlurFilter'?15:25;field.step=2;}
    if(field.key==='type'||field.key==='fillMode'){field.type='enum';field.options=Array.from({length:field.max+1},(_,i)=>i);}
  }
  return {type:name,label:labels[name.replace(/Filter$/,'')]||name,fields:params};
});
writeFileSync(new URL('../frontend/public/filter-catalog.json',import.meta.url),JSON.stringify({upstream:'pixijs/filters',version:'6.1.5',pixiVersion:'8.22.0',filters},null,2)+'\n');
console.log(`Catalogued ${filters.length} exported filters`);
