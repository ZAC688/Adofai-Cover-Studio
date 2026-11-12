import raw from '../../public/filter-catalog.json';
import type {ObjectId,Ratio} from './project';
export type Value=null|boolean|number|string|Value[]|{[key:string]:Value};
export type Parameter={key:string;type:string;value:Value;min:number;max:number;step:number;options?:(string|number)[]};
export const filterCatalog=raw.filters as {type:string;label:string;fields:Parameter[]}[];
export type FilterRegion={mode:'all'|'rect'|'paint';x:number;y:number;width:number;height:number;feather:number;maskAsset:string|null};
export type FilterSpec={id:string;type:string;enabled:boolean;targets:(ObjectId|'canvas')[];params:Record<string,Value>;regions:Partial<Record<Ratio,FilterRegion>>};
export const defaultRegion=():FilterRegion=>({mode:'all',x:.25,y:.25,width:.5,height:.5,feather:0,maskAsset:null});
export function defaultParameters(type:string):Record<string,Value>{
  const entry=filterCatalog.find(entry=>entry.type===type);if(!entry)throw new Error('滤镜不存在');
  return Object.fromEntries(entry.fields.map(field=>[field.key,structuredClone(field.value)]));
}
export function newFilter(type:string,target:ObjectId|'canvas'):FilterSpec{
  return {id:globalThis.crypto.randomUUID().replaceAll('-',''),type,enabled:true,targets:[target],params:defaultParameters(type),regions:{}};
}
export const parameterLabels:Record<string,string>={gamma:'伽马',contrast:'对比度',saturation:'饱和度',brightness:'亮度',red:'红通道',green:'绿通道',blue:'蓝通道',alpha:'不透明度',threshold:'阈值',bloomScale:'泛光强度',blur:'模糊',quality:'质量',pixelSize:'像素大小',size:'尺寸',color:'颜色',replaceColor:'替换颜色',rotation:'方向',thickness:'厚度',lightColor:'亮部颜色',lightAlpha:'亮部浓度',shadowColor:'阴影颜色',shadowAlpha:'阴影浓度',strength:'强度',center:'中心（比例）',radius:'半径',time:'静态时间',seed:'随机种子',matrix:'卷积矩阵',width:'宽度',height:'高度',originalColor:'原颜色',targetColor:'目标颜色',tolerance:'容差',scale:'比例',angle:'角度',offset:'偏移',offsetX:'水平偏移',offsetY:'垂直偏移',offsetZ:'深度偏移',colorMap:'色彩查找表',lightMap:'光照贴图',nearest:'临近采样',mix:'混合强度',stops:'渐变色标',replacements:'替换色组',type:'渐变类型',replace:'替换主体颜色',maxColors:'最大颜色数',velocity:'速度',kernelSize:'采样数量',maxKernelSize:'最大采样数量',knockout:'隐藏主体',start:'起点（比例）',end:'终点（比例）',axis:'方向',gradientBlur:'过渡范围',boundary:'倒影分界',amplitude:'振幅',waveLength:'波长范围',wavelength:'波长',mirror:'镜像',parallel:'平行光束',noiseScale:'噪声比例',step:'阈值步进',slices:'切片数量',sampleSize:'切片分辨率',fillMode:'边缘填充',average:'均匀切片',minSize:'最小切片',hue:'色相',lightness:'明度',colorize:'着色',padding:'边缘留白',distance:'范围',outerStrength:'外辉光',innerStrength:'内辉光',resolution:'分辨率',clamp:'限制边缘',sepia:'棕褐色',noise:'噪点',noiseSize:'噪点大小',scratch:'划痕',scratchDensity:'划痕密度',scratchWidth:'划痕宽度',vignetting:'暗角',vignettingAlpha:'暗角浓度',vignettingBlur:'暗角过渡',curvature:'曲率',lineWidth:'扫描线宽',lineContrast:'扫描线对比',verticalLine:'竖向扫描线',speed:'传播速度',gain:'增益',lacunarity:'光束密度'};
