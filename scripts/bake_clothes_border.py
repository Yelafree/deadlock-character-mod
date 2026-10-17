"""Run inside Blender with -- separator; widths are in mesh local units."""
import bpy,numpy as np,collections,heapq,math,json,os
from pathlib import Path
import argparse,sys
p=argparse.ArgumentParser(description="Bake fixed garment-border opacity from actual mesh topology.")
p.add_argument('--object',required=True);p.add_argument('--material',required=True);p.add_argument('--out',type=Path,required=True)
p.add_argument('--size',type=int,default=2048);p.add_argument('--interior',type=float,default=.18);p.add_argument('--border',type=float,default=.60)
p.add_argument('--solid-width',type=float,default=.045);p.add_argument('--fade-width',type=float,default=.24);p.add_argument('--crease-angle',type=float,default=80.)
p.add_argument('--padding',type=int,default=8)
cfg=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
if not (0<=cfg.interior<=cfg.border<=1 and 0<=cfg.solid_width<cfg.fade_width and 0<cfg.crease_angle<=180 and cfg.size>0):p.error('Invalid opacity, size, angle or band widths')
if cfg.out.exists():p.error('Output already exists; choose a new file')
cfg.out=cfg.out.resolve();cfg.out.parent.mkdir(parents=True,exist_ok=True)
root=cfg.out.parent
o=bpy.data.objects[cfg.object];m=o.data;m.calc_loop_triangles();material_index=next(i for i,x in enumerate(m.materials) if x and x.name==cfg.material)
keys=[tuple(round(x,4) for x in v.co) for v in m.vertices]
ids={p:i for i,p in enumerate(dict.fromkeys(keys))};vid=[ids[p] for p in keys];points=np.array(list(ids),dtype=float)
edges=collections.defaultdict(list)
for f in m.polygons:
 for a,b in f.edge_keys:
  e=tuple(sorted((vid[a],vid[b])));edges[e].append(f.index)
graph=collections.defaultdict(dict);seeds=set();open_edges=0;sharp_edges=0
for (a,b),fs in edges.items():
 selected=[fi for fi in fs if m.polygons[fi].material_index==material_index]
 if not selected:continue
 length=float(np.linalg.norm(points[a]-points[b]));graph[a][b]=length;graph[b][a]=length
 boundary=len(fs)==1 or any(m.polygons[fi].material_index!=material_index for fi in fs)
 sharp=False
 if len(selected)==2:
  sharp=m.polygons[selected[0]].normal.dot(m.polygons[selected[1]].normal)<math.cos(math.radians(cfg.crease_angle))
 if boundary or sharp:seeds.update((a,b));open_edges+=int(boundary);sharp_edges+=int(sharp)
dist=np.full(len(ids),np.inf);queue=[]
for a in seeds:dist[a]=0.;heapq.heappush(queue,(0.,a))
while queue:
 d,a=heapq.heappop(queue)
 if d!=dist[a]:continue
 for b,length in graph[a].items():
  new=d+length
  if new<dist[b]:dist[b]=new;heapq.heappush(queue,(new,b))
size=cfg.size;opacity=np.full((size,size),cfg.interior,np.float32);coverage=np.zeros((size,size),bool)
uv=m.uv_layers.active.data
for t in m.loop_triangles:
 if t.material_index!=material_index:continue
 xy=np.array([uv[l].uv[:] for l in t.loops],dtype=float)*size-.5
 xmin=max(0,int(np.floor(xy[:,0].min())));xmax=min(size-1,int(np.ceil(xy[:,0].max())))
 ymin=max(0,int(np.floor(xy[:,1].min())));ymax=min(size-1,int(np.ceil(xy[:,1].max())))
 if xmin>xmax or ymin>ymax:continue
 x,y=np.meshgrid(np.arange(xmin,xmax+1),np.arange(ymin,ymax+1))
 (ax,ay),(bx,by),(cx,cy)=xy;den=(by-cy)*(ax-cx)+(cx-bx)*(ay-cy)
 if abs(den)<1e-9:continue
 wa=((by-cy)*(x-cx)+(cx-bx)*(y-cy))/den;wb=((cy-ay)*(x-cx)+(ax-cx)*(y-cy))/den;wc=1-wa-wb
 inside=(wa>=-1e-6)&(wb>=-1e-6)&(wc>=-1e-6)
 ds=np.minimum(np.array([dist[vid[v]] for v in t.vertices]),1e4)
 d=wa*ds[0]+wb*ds[1]+wc*ds[2]
 # 0.045 world-unit solid narrow hem plus a soft transition out to 0.24.
 blend=np.clip((cfg.fade_width-d)/(cfg.fade_width-cfg.solid_width),0,1);blend=blend*blend*(3-2*blend)
 value=cfg.interior+(cfg.border-cfg.interior)*blend
 region=opacity[ymin:ymax+1,xmin:xmax+1];region[inside]=value[inside]
 coverage[ymin:ymax+1,xmin:xmax+1]|=inside
# Padding extends each island's edge values only into unused texels, never into another island.
for iteration in range(cfg.padding):
 accum=np.zeros_like(opacity);counts=np.zeros_like(opacity)
 for axis in (0,1):
  for shift in (-1,1):
   c=np.roll(coverage,shift,axis);v=np.roll(opacity,shift,axis)
   if axis==0:c[0 if shift==1 else -1,:]=False
   else:c[:,0 if shift==1 else -1]=False
   accum+=v*c;counts+=c
 new=(~coverage)&(counts>0);opacity[new]=accum[new]/counts[new];coverage|=new
rgba=np.ones((size,size,4),np.float32);rgba[:,:,:3]=opacity[:,:,None]
im=bpy.data.images.new('Clothes physical border opacity',width=size,height=size,alpha=True);im.pixels.foreach_set(rgba.ravel());im.filepath_raw=str(cfg.out);im.file_format='PNG';im.save()
report={'resolution':size,'body_opacity':cfg.interior,'border_opacity':cfg.border,'solid_band_local_units':cfg.solid_width,'fade_extent_local_units':cfg.fade_width,'open_boundary_edges':open_edges,'sharp_hem_edges':sharp_edges,'angle_effect':False,'topological_welding_precision':.0001,'uv_seams_not_used_as_borders':True,'covered_pixels':int(coverage.sum()),'border_pixels':int((opacity>(cfg.interior+cfg.border)/2).sum())}
cfg.out.with_suffix('.report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
