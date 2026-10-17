"""Strict text KV3 subset and opt-in legacy encoder for attachment repair; not a general Source 2 serializer."""
from pathlib import Path
import re,json,struct,uuid,copy,hashlib
ROOT=Path(__file__).resolve().parent
class Flagged(str):
 def __new__(cls,value,flag):
  result=str.__new__(cls,value);result.flag=flag;return result
 def __reduce__(self):return (Flagged,(str(self),self.flag))
def parse(text):
 tokens=re.findall(r'"""[\s\S]*?"""|"(?:\\.|[^"\\])*"|(?:resource_name|resource|soundevent|subclass|panorama):|[{}\[\]=,]|[^\s{}\[\]=,"]+',text);i=0
 def value():
  nonlocal i
  tok=tokens[i];i+=1
  if tok=='{':
   result={}
   while tokens[i]!='}':
    key=tokens[i];i+=1
    if key==',':continue
    if key.startswith('"'):key=json.loads(key)
    assert tokens[i]=='=',(key,tokens[i]);i+=1;result[key]=value()
   i+=1;return result
  if tok=='[':
   result=[]
   while tokens[i]!=']':
    if tokens[i]==',':i+=1;continue
    result.append(value())
   i+=1;return result
  if tok.endswith(':'):
   flags={'resource:':1,'resource_name:':2,'panorama:':8,'soundevent:':16,'subclass:':32};return Flagged(value(),flags[tok])
  if tok.startswith('"""'):return tok[3:-3]
  if tok.startswith('"'):return json.loads(tok)
  if tok in ('true','false'):return tok=='true'
  if tok=='null':return None
  try:return float(tok) if '.' in tok or 'e' in tok.lower() else int(tok,0) if tok.startswith('0x') else int(tok)
  except ValueError:raise ValueError(('unknown token',tok,i))
 result=value();assert i==len(tokens),(i,len(tokens),tokens[i:i+10]);return result
def blocks_from_dump(filename,block):
 text=(ROOT/filename).read_text(encoding='utf-8-sig');parts=text.split(f'--- Data for block "{block}" ---')[1:]
 return [parse(p[p.index('-->')+3:].strip()) for p in parts]
def binary_kv3(value):
 # Legacy uncompressed KV3 is supported by Source 2 and lets every edited value be independently decoded.
 strings=[];ids={}
 def sid(s):
  if s not in ids:ids[s]=len(strings);strings.append(s)
  return ids[s]
 def encode(v):
  if isinstance(v,dict):return b'\x09'+struct.pack('<i',len(v))+b''.join(struct.pack('<i',sid(k))+encode(x) for k,x in v.items())
  if isinstance(v,list):return b'\x08'+struct.pack('<i',len(v))+b''.join(encode(x) for x in v)
  if v is None:return b'\x01'
  if isinstance(v,bool):return b'\x02'+bytes([v])
  if isinstance(v,int):return (b'\x03'+struct.pack('<q',v)) if v<2**63 else b'\x04'+struct.pack('<Q',v)
  if isinstance(v,float):return b'\x05'+struct.pack('<d',v)
  if isinstance(v,Flagged):return bytes([6|128,v.flag])+struct.pack('<i',sid(str(v)))
  if isinstance(v,str):return b'\x06'+struct.pack('<i',sid(v))
  raise TypeError(v)
 payload=encode(value)
 return struct.pack('<I',0x03564b56)+uuid.UUID('1b860500-f7d8-40c1-ad82-75a48267e714').bytes_le+uuid.UUID('7412167c-06e9-4698-aff2-e63eb59037e7').bytes_le+struct.pack('<I',len(strings))+b''.join(s.encode()+b'\0' for s in strings)+payload+b'\xff'*4
def read_resource(path):
 blob=path.read_bytes();offset,count=struct.unpack_from('<II',blob,8);table=8+offset;result=[]
 for i in range(count):
  pos=table+12*i;kind=blob[pos:pos+4];off,size=struct.unpack_from('<II',blob,pos+4);start=pos+4+off;result.append((kind,blob[start:start+size]))
 return blob,result
