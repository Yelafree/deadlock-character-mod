"""Read, verify and patch VPKs into a new unsigned self-contained v2 archive."""
import argparse,hashlib,json,struct,zlib
from pathlib import Path,PurePosixPath
import vpk_archive as vpk

def archive_file(path,index):
 stem=path.stem
 if stem.endswith('_dir'):stem=stem[:-4]
 return path.with_name(f'{stem}_{index:03d}.vpk')

def load(path):
 with path.open('rb') as f:
  h=vpk.read_header(f);entries=vpk.parse_tree(f.read(h.tree_size));payloads={}
  for e in entries:
   if e.path in payloads:raise ValueError(f'Duplicate entry: {e.path}')
   if not e.length:raw=b''
   elif e.embedded:
    if e.offset+e.length>h.file_data_size:raise ValueError(f'Invalid offset: {e.path}')
    f.seek(h.data_start+e.offset);raw=f.read(e.length)
   else:
    with archive_file(path,e.archive_index).open('rb') as part:part.seek(e.offset);raw=part.read(e.length)
   data=e.preload_data+raw
   if len(raw)!=e.length or zlib.crc32(data)&0xffffffff!=e.crc:raise ValueError(f'CRC/length mismatch: {e.path}')
   payloads[e.path]=data
 return h,entries,payloads

def verify(path):
 h,entries,payloads=load(path);errors=vpk.verify(path)
 if errors:raise ValueError(errors)
 if h.archive_md5_size:
  with path.open('rb') as f:
   f.seek(h.archive_md5_start);records=f.read(h.archive_md5_size)
   if len(records)%28:raise ValueError('Malformed archive MD5 section')
   for index,offset,length,expected in struct.iter_unpack('<III16s',records):
    archive=path if index==0x7fff else archive_file(path,index)
    with archive.open('rb') as part:
     part.seek((h.data_start if index==0x7fff else 0)+offset);chunk=part.read(length)
    if len(chunk)!=length or hashlib.md5(chunk).digest()!=expected:raise ValueError(f'Chunk MD5 mismatch: {index}/{offset}')
 return h,entries,payloads

def write_archive(output,entries,payloads):
 data=bytearray()
 for e in entries:
  payload=payloads[e.path];e.crc=zlib.crc32(payload)&0xffffffff;e.preload_bytes=0;e.preload_data=b'';e.archive_index=0x7fff;e.out_offset=len(data);e.offset=e.out_offset;e.length=len(payload);data.extend(payload)
 tree=vpk.build_tree(entries);chunks=bytearray()
 for offset in range(0,len(data),1<<20):
  chunk=data[offset:offset+(1<<20)];chunks.extend(struct.pack('<III16s',0x7fff,offset,len(chunk),hashlib.md5(chunk).digest()))
 header=struct.pack('<7I',0x55aa1234,2,len(tree),len(data),len(chunks),48,0)
 prefix=header+tree+data+chunks+hashlib.md5(tree).digest()+hashlib.md5(chunks).digest()
 with output.open('xb') as f:f.write(prefix);f.write(hashlib.md5(prefix).digest())

def unique_mapping(pairs):
 result={}
 for k,v in pairs:
  if k in result:raise ValueError(f'Duplicate replacement key: {k}')
  result[k]=v
 return result

def remove_entries(a,p):
 source=a.source.resolve()
 if not (a.match or a.ext or a.entry):p.error('Choose --ext, --match or --entry explicitly')
 with source.open('rb') as f:h=vpk.read_header(f);entries=vpk.parse_tree(f.read(h.tree_size))
 matches=lambda e:any(s.lower() in e.path.lower() for s in a.match) or e.ext.lower() in {s.lower().lstrip('.') for s in a.ext} or e.path.lower() in {s.lower() for s in a.entry}
 removed=[e.path for e in entries if matches(e)]
 if a.dry_run:
  print(json.dumps({'source':str(source),'would_remove':removed,'dry_run':True},indent=2));return
 if not a.out:p.error('Removal needs --out; use the batch helper for explicit in-place edits')
 if not removed:raise ValueError('Nothing matched; source untouched. Check the requested entry/pattern.')
 if len(removed)==len(entries):raise ValueError('Refusing to remove every entry; narrow the selector')
 if h.signature_size:raise ValueError('Signed input is read-only; never rewrite the base-game archive')
 output=a.out.resolve()
 if output==source or output.exists():p.error('Choose a new output; input/existing files will not be overwritten')
 before=hashlib.sha256(source.read_bytes()).hexdigest();_,entries,old=verify(source);kept=[e for e in entries if e.path not in removed];new={e.path:old[e.path] for e in kept}
 output.parent.mkdir(parents=True,exist_ok=True);write_archive(output,kept,new);_,_,decoded=verify(output)
 if decoded!=new or set(decoded)&set(removed):raise ValueError('Removal/payload comparison failed')
 if hashlib.sha256(source.read_bytes()).hexdigest()!=before:raise ValueError('Source changed during removal')
 report={'source':str(source),'output':str(output),'removed_entries':removed,'surviving_payloads_byte_identical':True,'source_sha256':before,'output_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'crc32_and_md5_verified':True,'installed':False}
 output.with_suffix('.verification.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report,indent=2))

def main():
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
 for name in ('list','verify'):
  command=sub.add_parser(name);command.add_argument('source',type=Path)
 command=sub.add_parser('patch');command.add_argument('source',type=Path);command.add_argument('--out',type=Path,required=True);command.add_argument('--replacements',type=Path,required=True);command.add_argument('--allow-add',action='store_true')
 command=sub.add_parser('remove');command.add_argument('source',type=Path);command.add_argument('--out',type=Path);command.add_argument('--match',action='append',default=[]);command.add_argument('--ext',action='append',default=[]);command.add_argument('--entry',action='append',default=[]);command.add_argument('--dry-run',action='store_true')
 a=p.parse_args();source=a.source.resolve()
 if a.command=='remove':remove_entries(a,p);return
 if a.command=='list':
  with source.open('rb') as f:h=vpk.read_header(f);entries=vpk.parse_tree(f.read(h.tree_size))
  print(json.dumps([{'path':e.path,'size':e.preload_bytes+e.length,'archive_index':e.archive_index,'crc32':f'{e.crc:08x}'} for e in entries],indent=2));return
 if a.command=='verify':
  _,entries,_=verify(source);print(json.dumps({'verified':str(source),'entries':len(entries),'crc32_and_md5':True}));return
 output=a.out.resolve()
 if output==source or output.exists():p.error('Choose a new output; input/existing files will not be overwritten')
 with source.open('rb') as f:h=vpk.read_header(f)
 if h.signature_size:p.error('Signed input is read-only; use an unsigned mod archive as the patch base')
 mapping=json.loads(a.replacements.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_mapping)
 if not isinstance(mapping,dict) or not mapping:p.error('Replacement JSON must be a nonempty object')
 before=hashlib.sha256(source.read_bytes()).hexdigest();_,entries,old=verify(source);new=dict(old)
 for key,filename in mapping.items():
  pure=PurePosixPath(key)
  if pure.is_absolute() or '..' in pure.parts or '\\' in key or ':' in key:raise ValueError(f'Unsafe/noncanonical entry path: {key}')
  file=Path(filename)
  if not file.is_absolute():file=a.replacements.resolve().parent/file
  if key not in old:
   if not a.allow_add:raise ValueError(f'Not in source; use --allow-add for intentional dependency: {key}')
   directory,_,leaf=key.rpartition('/');name,ext=leaf.rsplit('.',1);entries.append(vpk.Entry(ext,directory or ' ',name,0,0,0x7fff,0,0,b''))
  new[key]=file.read_bytes()
 output.parent.mkdir(parents=True,exist_ok=True);write_archive(output,entries,new);_,_,decoded=verify(output)
 if decoded!=new:raise ValueError('Output payload comparison failed')
 changed=[k for k in old if old[k]!=decoded[k]];added=[k for k in decoded if k not in old]
 if not set(changed+added)<=set(mapping):raise ValueError('Unexpected changed entry')
 if hashlib.sha256(source.read_bytes()).hexdigest()!=before:raise ValueError('Source changed during patch')
 report={'source':str(source),'output':str(output),'source_sha256':before,'output_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'changed_entries':changed,'added_entries':added,'crc32_and_md5_verified':True,'installed':False}
 output.with_suffix('.verification.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
