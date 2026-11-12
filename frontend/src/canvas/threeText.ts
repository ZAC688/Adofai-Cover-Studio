import {WebGLRenderer,Scene,OrthographicCamera,PerspectiveCamera,Mesh,MeshStandardMaterial,DirectionalLight,AmbientLight,ExtrudeGeometry,SRGBColorSpace,MathUtils} from 'three';
import {SVGLoader} from 'three/addons/loaders/SVGLoader.js';
import type {Title,TextPlacement} from '../domain/project';
import {defaultText3D} from '../domain/text3d';
import {api,jsonRequest} from '../services/api';
import {canvasShape} from './alpha';

type Outline={paths:string[];width:number;height:number;fallbackCharacters:string[];missingCharacters:string[]};
type Body={canvas:HTMLCanvasElement;x:number;y:number};
const outlines=new Map<string,Promise<Outline>>(),geometries=new Map<string,ExtrudeGeometry>(),bodies=new Map<string,Promise<Body|null>>();
let renderer:WebGLRenderer|null=null,queue:Promise<unknown>=Promise.resolve();
async function outline(title:Title){
  const key=JSON.stringify([title.fontId,title.text]);
  if(!outlines.has(key)){
    if(outlines.size>=32)outlines.delete(outlines.keys().next().value!);
    outlines.set(key,api<Outline>('/text-outline',jsonRequest(title,'POST')).catch(error=>{outlines.delete(key);throw error;}));
  }
  return outlines.get(key)!;
}
function geometry(title:Title,data:Outline){
  const config=title.text3d||defaultText3D(),key=JSON.stringify([title.fontId,title.text,config.depth,config.bevel]);
  if(!geometries.has(key)){
    const loader=new SVGLoader(),shapes=data.paths.flatMap(path=>{
      const svg=loader.parse(`<svg xmlns="http://www.w3.org/2000/svg"><path fill-rule="evenodd" d="${path}"/></svg>`);
      return svg.paths.flatMap(path=>SVGLoader.createShapes(path));
    });
    const depth=config.depth*10,bevel=config.bevel*10;
    const result=new ExtrudeGeometry(shapes,{depth,steps:1,curveSegments:10,bevelEnabled:bevel>0,bevelThickness:bevel,bevelSize:bevel,bevelSegments:3});
    // Rotate rather than reflect, retaining outward-facing normals and glyph holes.
    result.rotateX(Math.PI);result.scale(.001,.001,.001);result.translate(-data.width/2000,data.height/2000,depth/2000);
    if(geometries.size>=8){const oldest=geometries.keys().next().value!;geometries.get(oldest)!.dispose();geometries.delete(oldest);}
    geometries.set(key,result);
  }
  return geometries.get(key)!;
}
async function draw(title:Title,p:TextPlacement,width:number,height:number):Promise<Body|null>{
  const data=await outline(title);if(!data.paths.length)return null;
  const config=title.text3d||defaultText3D();
  renderer??=new WebGLRenderer({alpha:true,antialias:true,preserveDrawingBuffer:true});
  renderer.setPixelRatio(1);renderer.setSize(width,height,false);renderer.setClearColor(0,0);renderer.outputColorSpace=SRGBColorSpace;
  const scene=new Scene(),front=new MeshStandardMaterial({color:title.color,roughness:.35,metalness:.05}),side=new MeshStandardMaterial({color:config.sideColor,roughness:.45,metalness:.05});
  const mesh=new Mesh(geometry(title,data),[front,side]);mesh.scale.setScalar(p.fontSize);
  mesh.position.set(p.x+data.width/2000*p.fontSize-width/2,height/2-p.y-data.height/2000*p.fontSize,0);
  mesh.rotation.set(MathUtils.degToRad(config.rotationX),MathUtils.degToRad(config.rotationY),-MathUtils.degToRad(config.rotationZ));scene.add(mesh);
  const orthographic=new OrthographicCamera(-width/2,width/2,height/2,-height/2,.1,100000),fov=Math.max(1,config.perspective*.75),distance=height/(2*Math.tan(MathUtils.degToRad(fov/2)));
  const camera=config.perspective===0?orthographic:new PerspectiveCamera(fov,width/height,.1,100000);
  camera.position.z=config.perspective===0?10000:distance;camera.lookAt(0,0,0);camera.updateProjectionMatrix();
  const light=new DirectionalLight('#ffffff',config.lightIntensity),azimuth=MathUtils.degToRad(config.lightDirection),elevation=MathUtils.degToRad(config.lightElevation);
  light.position.set(Math.sin(azimuth)*Math.cos(elevation),Math.sin(elevation),Math.cos(azimuth)*Math.cos(elevation));
  scene.add(light,new AmbientLight('#ffffff',config.ambientIntensity));
  try{
    renderer.render(scene,camera);
    const full=document.createElement('canvas');full.width=width;full.height=height;full.getContext('2d',{willReadFrequently:true})!.drawImage(renderer.domElement,0,0);
    const box=canvasShape(full).bounds;if(!box)return null;
    const x=Math.max(0,box.x-2),y=Math.max(0,box.y-2),right=Math.min(width,box.x+box.width+2),bottom=Math.min(height,box.y+box.height+2);
    const canvas=document.createElement('canvas');canvas.width=right-x;canvas.height=bottom-y;
    canvas.getContext('2d',{willReadFrequently:true})!.drawImage(full,x,y,canvas.width,canvas.height,0,0,canvas.width,canvas.height);
    return {canvas,x,y};
  }finally{front.dispose();side.dispose();scene.clear();}
}
export function renderThreeText(title:Title,p:TextPlacement,width:number,height:number):Promise<Body|null>{
  const key=JSON.stringify([title.text,title.fontId,title.color,title.text3d,p,width,height]);
  if(!bodies.has(key)){
    if(bodies.size>=12)bodies.delete(bodies.keys().next().value!);
    const pending=queue.then(()=>draw(title,p,width,height));queue=pending.catch(()=>{});
    bodies.set(key,pending.catch(error=>{bodies.delete(key);throw error;}));
  }
  return bodies.get(key)!;
}
