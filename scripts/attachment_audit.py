"""Audit current-game vs custom-model attachments; optional compatibility patch with strict round-trip checks."""
import argparse,copy,hashlib,json,re,struct,subprocess
from pathlib import Path
import kv3_resource as kv

def dumps(cli,model,label,work):
 result={}
 for block in ('DATA','MDAT'):
  run=subprocess.run([str(cli),'-i',str(model),'-b',block],capture_output=True,text=True,encoding='utf-8',errors='strict')
  path=work/f'{label}_{block}.txt';path.write_text(run.stdout,encoding='utf8')
  if run.returncode or 'Exception:' in run.stderr or f'--- Data for block "{block}" ---' not in run.stdout:raise ValueError(f'Failed to decode {model}/{block}: {run.stderr[:2000]}')
  result[block]=kv.blocks_from_dump(path.resolve(),block)
 if len(result['DATA'])!=1 or not result['MDAT']:raise ValueError('Unsupported model block layout')
 return result

def close(a,b,tol=1e-3):
 if isinstance(a,(int,float)) and isinstance(b,(int,float)):return abs(a-b)<=tol
 if isinstance(a,list) and isinstance(b,list):return len(a)==len(b) and all(close(x,y,tol) for x,y in zip(a,b))
 if isinstance(a,dict) and isinstance(b,dict):return a.keys()==b.keys() and all(close(a[k],b[k],tol) for k in a)
 return a==b

def bindings_compatible(original,mod,attachments):
 a=original['m_modelSkeleton'];b=mod['m_modelSkeleton'];ai={n:i for i,n in enumerate(a['m_boneName'])};bi={n:i for i,n in enumerate(b['m_boneName'])};seen=set();issues=[]
 def visit(name):
  if name in seen:return
  seen.add(name)
  if name not in ai or name not in bi:issues.append(f'Missing attachment parent bone: {name}');return
  i,j=ai[name],bi[name];ap=a['m_nParent'][i];bp=b['m_nParent'][j];an=a['m_boneName'][ap] if ap>=0 else None;bn=b['m_boneName'][bp] if bp>=0 else None
  if an!=bn:issues.append(f'Parent hierarchy differs: {name}')
  if not close(a['m_bonePosParent'][i],b['m_bonePosParent'][j]):issues.append(f'Bind position differs: {name}')
  aq=a['m_boneRotParent'][i];bq=b['m_boneRotParent'][j]
  if not (close(aq,bq) or close(aq,[-x for x in bq])):issues.append(f'Bind rotation differs: {name}')
  if 'm_boneScaleParent' in a and 'm_boneScaleParent' in b and not close(a['m_boneScaleParent'][i],b['m_boneScaleParent'][j]):issues.append(f'Bind scale differs: {name}')
  if an:visit(an)
 for item in attachments:
  for name in item['value']['m_influenceNames']:
   if name:visit(name)
 return sorted(set(issues))

def property_text(text,key):
 match=re.search(r'(?m)^\s*'+re.escape(key)+r'\s*=\s*',text)
 if not match:return None
 start=match.end();opening=text[start];closing={'[':']','{':'}'}[opening];level=0;quoted=False;escaped=False
 for i in range(start,len(text)):
  c=text[i]
  if escaped:escaped=False
  elif quoted and c=='\\':escaped=True
  elif c=='"':quoted=not quoted
  elif not quoted:
   if c==opening:level+=1
   elif c==closing:
    level-=1
    if level==0:return match.start(),i+1,text[match.start():i+1]
 raise ValueError(f'Unbalanced camera property {key}')

def patch_keys(old,current):
 result=old
 for key in ('CitadelCameraSettings_t','AttachmentCameraData'):
  source=property_text(current,key)
  if not source:continue
  target=property_text(result,key)
  if target:result=result[:target[0]]+source[2]+result[target[1]:]
  else:
   end=result.rfind('}');result=result[:end]+source[2]+'\n'+result[end:]
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cli',required=True,type=Path);p.add_argument('--original',required=True,type=Path);p.add_argument('--mod',required=True,type=Path);p.add_argument('--out-dir',required=True,type=Path);p.add_argument('--patch-model',type=Path);p.add_argument('--allow-legacy-kv3',action='store_true');a=p.parse_args()
 if a.patch_model and not a.allow_legacy_kv3:p.error('Patch requires explicit --allow-legacy-kv3; see references/attachments.md')
 if a.patch_model and (a.patch_model.exists() or a.patch_model.resolve() in (a.original.resolve(),a.mod.resolve())):p.error('Choose a new model output')
 a.out_dir.mkdir(parents=True,exist_ok=True);original=dumps(a.cli,a.original,'original',a.out_dir);mod=dumps(a.cli,a.mod,'mod',a.out_dir)
 canonical=original['MDAT'][0]['m_attachments'];v={x['key']:x['value'] for x in canonical}
 if not all(mesh.get('m_attachments')==canonical for mesh in original['MDAT']):raise ValueError('Original model has different attachment tables per mesh; inspect manually')
 if not all('m_attachments' in mesh for mesh in mod['MDAT']):raise ValueError('Custom mesh missing attachment table; inspect manually')
 issues=bindings_compatible(original['DATA'][0],mod['DATA'][0],canonical)
 diffs=[]
 for i,mesh in enumerate(mod['MDAT']):
  m={x['key']:x['value'] for x in mesh['m_attachments']};diffs.append({'mesh_index':i,'exact_differences':[k for k in sorted(v.keys()|m.keys()) if v.get(k)!=m.get(k)],'material_differences_tolerance_1e3':{k:{'original':v.get(k),'mod':m.get(k)} for k in sorted(v.keys()|m.keys()) if not close(v.get(k),m.get(k))}})
 report={'original':str(a.original.resolve()),'mod':str(a.mod.resolve()),'original_sha256':hashlib.sha256(a.original.read_bytes()).hexdigest(),'mod_sha256':hashlib.sha256(a.mod.read_bytes()).hexdigest(),'attachment_count':len(v),'mesh_differences':diffs,'binding_issues':issues,'in_game_visual_test':False}
 report_path=a.out_dir/'audit.json';report_path.write_text(json.dumps(report,indent=2),encoding='utf8')
 if not a.patch_model:print(json.dumps({'report':str(report_path),'binding_issues':issues,'meshes':len(diffs)},indent=2));return
 if issues:raise ValueError(f'Patch stopped; coordinate conversion required: {issues}')
 fixed=copy.deepcopy(mod);data=fixed['DATA'][0];info=data['m_modelInfo'];info['m_keyValueText']=patch_keys(info['m_keyValueText'],original['DATA'][0]['m_modelInfo']['m_keyValueText'])
 for mesh in fixed['MDAT']:
  extras=[x for x in mesh['m_attachments'] if x['key'] not in v];mesh['m_attachments']=copy.deepcopy(canonical)+extras
 before,blocks=kv.read_resource(a.mod)
 if struct.unpack_from('<I',before,0)[0]!=len(before):raise ValueError('Streamed/trailing model data: use native serializer')
 count=len(blocks);out=bytearray(before[:16]+bytes(12*count));struct.pack_into('<II',out,8,8,count);index=0
 for i,(kind,payload) in enumerate(blocks):
  if kind==b'MDAT':payload=kv.binary_kv3(fixed['MDAT'][index]);index+=1
  elif kind==b'DATA':payload=kv.binary_kv3(data)
  while len(out)%16:out.append(0)
  start=len(out);out.extend(payload);pos=16+12*i;out[pos:pos+4]=kind;struct.pack_into('<II',out,pos+4,start-pos-4,len(payload))
 struct.pack_into('<I',out,0,len(out));a.patch_model.parent.mkdir(parents=True,exist_ok=True)
 with a.patch_model.open('xb') as f:f.write(out)
 decoded=dumps(a.cli,a.patch_model,'fixed',a.out_dir)
 # CLI formatting can add a leading newline to embedded multiline strings. Compare the nested
 # game-data KV3 semantically, while all remaining decoded fields must match exactly.
 decoded_keys=decoded['DATA'][0]['m_modelInfo'].pop('m_keyValueText')
 expected_keys=fixed['DATA'][0]['m_modelInfo'].pop('m_keyValueText')
 game=lambda t:kv.parse(t[t.index('-->')+3:].strip())
 if decoded!=fixed or game(decoded_keys)!=game(expected_keys):raise ValueError('Round-trip semantic verification failed; do not package this model')
 _,after=kv.read_resource(a.patch_model)
 for (kind,x),(kind2,y) in zip(blocks,after):
  if kind!=kind2 or (kind not in (b'MDAT',b'DATA') and x!=y):raise ValueError('Unexpected resource block change')
 report.update(patched_model=str(a.patch_model.resolve()),patched_sha256=hashlib.sha256(out).hexdigest(),legacy_binary_kv3=True,non_target_resource_blocks_byte_identical=True,roundtrip_semantic_verification=True)
 report_path.write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps({'report':str(report_path),'patched_model':str(a.patch_model),'in_game_visual_test':False},indent=2))
if __name__=='__main__':main()
