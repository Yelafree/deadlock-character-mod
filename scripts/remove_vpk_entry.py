"""Batch removal compatibility helper: default vnmskel_c; new outputs unless --in-place is explicit."""
import argparse,json,os,re,subprocess,sys,uuid,shutil
from pathlib import Path
import vpk_patch as core

def inputs(paths,recursive):
 found=[]
 for raw in paths:
  path=Path(raw).resolve()
  if path.is_dir():found.extend(sorted(path.rglob('*.vpk') if recursive else path.glob('*.vpk')))
  elif path.is_file():found.append(path)
  else:raise ValueError(f'Input not found: {path}')
 # Numbered data shards have no VPK directory header; ignore them during folder expansion.
 result=[]
 for path in dict.fromkeys(found):
  try:
   with path.open('rb') as f:core.vpk.read_header(f)
  except core.vpk.VpkError:
   if re.search(r'_\d{3}\.vpk$',path.name,re.IGNORECASE):continue
   raise
  result.append(path)
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('paths',nargs='+');p.add_argument('--recursive','-r',action='store_true');p.add_argument('--match','-m',action='append',default=[]);p.add_argument('--ext','-e',action='append',default=[]);p.add_argument('--entry',action='append',default=[]);p.add_argument('--dry-run','-n',action='store_true');p.add_argument('--out','-o',type=Path);p.add_argument('--in-place',action='store_true');p.add_argument('--report',type=Path);a=p.parse_args()
 if a.out and a.in_place:p.error('--out and --in-place are mutually exclusive')
 if a.report and a.report.exists():p.error('Report already exists')
 sources=inputs(a.paths,a.recursive)
 if not sources:p.error('No VPK directory archives found')
 if a.out and len(sources)!=1:p.error('--out requires exactly one input archive')
 if not (a.match or a.ext or a.entry):a.ext=['vnmskel_c']
 results=[];failures=0;matched=False
 for source in sources:
  selectors=[]
  for option,values in [('--match',a.match),('--ext',a.ext),('--entry',a.entry)]:
   for value in values:selectors.extend([option,value])
  helper=Path(__file__).with_name('vpk_patch.py')
  plan=subprocess.run([sys.executable,str(helper),'remove',str(source),*selectors,'--dry-run'],capture_output=True,text=True,encoding='utf8')
  try:
   if plan.returncode:raise ValueError(plan.stderr)
   details=json.loads(plan.stdout);removed=details['would_remove'];matched|=bool(removed)
   if a.dry_run or not removed:
    results.append(details);continue
   if a.in_place:
    # Verify a complete new container before creating a backup and atomically switching files.
    output=source.with_name(source.name+f'.{uuid.uuid4().hex}.pending.vpk')
   else:
    output=a.out.resolve() if a.out else source.with_name(source.stem+'_clean.vpk')
   run=subprocess.run([sys.executable,str(helper),'remove',str(source),*selectors,'--out',str(output)],capture_output=True,text=True,encoding='utf8')
   if run.returncode:raise ValueError(run.stderr)
   result=json.loads(run.stdout)
   if a.in_place:
    if core.hashlib.sha256(source.read_bytes()).hexdigest()!=result['source_sha256']:raise ValueError('Source changed before atomic replacement')
    backup=source.with_name(source.name+'.bak');number=2
    while backup.exists():backup=source.with_name(source.name+f'.bak{number}');number+=1
    try:os.link(source,backup)
    except OSError:shutil.copy2(source,backup)
    os.replace(output,source)
    try:core.verify(source)
    except Exception:
     shutil.copy2(backup,source);raise
    temporary_report=output.with_suffix('.verification.json')
    if temporary_report.exists():temporary_report.unlink()
    result.update(output=str(source),backup=str(backup),in_place=True)
   results.append(result)
  except Exception as exc:
   failures+=1;results.append({'source':str(source),'error':str(exc)})
 report={'archives':results,'failures':failures,'dry_run':a.dry_run}
 if a.report:
  if a.report.exists():p.error('Report already exists')
  a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2),encoding='utf8')
 print(json.dumps(report,indent=2));return 1 if failures else 0 if matched else 3
if __name__=='__main__':sys.exit(main())
