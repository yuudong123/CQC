"""Locate preserved evidence; no HTTP/SQL probes, tests, builds, or service changes."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json
import subprocess
import zipfile

ROOT = Path('C:/CQC')
OUT = ROOT / 'outputs/qa-mo-sim06-sim09-inventory-20261014'
OUT.mkdir(exist_ok=True)
KST = timezone(timedelta(hours=9))

def cmd(args, timeout=40):
    return subprocess.check_output(args, timeout=timeout)

def save(name, obj):
    (OUT / name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def public_state():
    names=['mysql','inference','backend','simulator','logistics-api','logistics-web','logistics-mongodb']
    data=json.loads(cmd(['docker','inspect',*['cqc-cicd-'+n+'-1' for n in names]]))
    return [{'name':c['Name'],'id':c['Id'],'image':c['Image'],'started_at':c['State']['StartedAt'],'status':c['State']['Status'],'health':c['State'].get('Health',{}).get('Status')} for c in data]

before=public_state()
save('e1-before.json',before)
ids=set()
runs=[]
for f in (ROOT / 'outputs').glob('*e2*20261006/fault-evidence.json'):
    rows=json.loads(f.read_text(encoding='utf-8'))
    runs.append({'path':f.relative_to(ROOT).as_posix(),'rows':len(rows),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
    for row in rows:
        if row.get('fault_row'): ids.add(row['fault_row']['id'])
        if row.get('next_normal_id'): ids.add(row['next_normal_id'])
ids.update(['qa-mo09-mysql-down-e87f0b64e1624fbc','qa-mo09-mysql-recovered-d6ecd322e9494b34'])
args=['rg','-l','-F','--hidden','--no-ignore','-g','!outputs/cqc-portfolio/**','-g','!outputs/qa-mo-sim06-sim09-inventory-20261014/**','-g','!outputs/inventory_sim0609_20261014.py','-g','!**/node_modules/**','-g','!**/.git/**']
for item in sorted(ids): args+=['-e',item]
args+=['docs','outputs']
result=subprocess.run(args,cwd=ROOT,capture_output=True,timeout=40)
assert result.returncode in [0,1]
save('text-search.json',{'at_kst':datetime.now(KST).isoformat(),'patterns':sorted(ids),'source_runs':runs,'roots':['docs','outputs'],'includes_ignored_files':True,'matched_paths':result.stdout.decode('utf-8','replace').splitlines(),'excludes':['outputs/cqc-portfolio','new inventory output','this collector','node_modules','.git'],'limits':'Other machines and arbitrary user folders not searched'})
archives=[]
for f in (ROOT / 'outputs').rglob('*.zip'):
    if 'cqc-portfolio' in f.parts:continue
    matches=[]
    with zipfile.ZipFile(f) as z:
        for n in z.namelist():
            if Path(n).suffix.lower() not in ['.json','.jsonl','.md','.txt','.log','.sql','.csv']:continue
            data=z.read(n)
            found=[i for i in ids if i.encode() in data]
            if found:matches.append({'member':n,'matching_ids':found})
        archives.append({'path':f.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'members':len(z.namelist()),'matches':matches})
save('archive-search.json',archives)

log_code='''from pathlib import Path
import json,sys,re,hashlib
patterns=json.loads(sys.argv[1]);rows=[]
for f in Path('/var/log/cqc').rglob('*'):
 if not f.is_file():continue
 data=f.read_bytes();txt=data.decode('utf-8','replace');lines=txt.splitlines()
 ts=re.findall(r'20\\d\\d-\\d\\d-\\d\\d[ T]\\d\\d:\\d\\d:\\d\\d',txt)
 rows.append({'path':str(f),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'first_timestamp':ts[0] if ts else None,'last_timestamp':ts[-1] if ts else None,'matching_id_counts':{p:txt.count(p) for p in patterns if p in txt},'oct06_line_count':sum('2026-10-06' in s for s in lines)})
print(json.dumps(rows))
'''
logs=[]
for service in ['backend','simulator']:
    name='cqc-cicd-'+service+'-1'
    logs.append({'container':name,'volume':'cqc-cicd_'+service+'_logs','files':json.loads(cmd(['docker','exec',name,'python','-c',log_code,json.dumps(sorted(ids))]))})
save('persistent-log-search.json',logs)

volume_names=cmd(['docker','volume','ls','-q']).decode().splitlines()
volumes=json.loads(cmd(['docker','volume','inspect',*volume_names]))
save('docker-volume-inventory.json',[{'name':v['Name'],'created_at':v.get('CreatedAt'),'labels':v.get('Labels')} for v in volumes])
containers=json.loads(cmd(['docker','inspect',*cmd(['docker','ps','-aq']).decode().splitlines()]))
save('docker-container-inventory.json',[{'name':c['Name'],'status':c['State']['Status'],'project':c['Config'].get('Labels',{}).get('com.docker.compose.project'),'volumes':[m.get('Name') for m in c['Mounts'] if m['Type']=='volume']} for c in containers])
cold=[v['Name'] for v in volumes if (v.get('Labels') or {}).get('com.docker.volume.anonymous')=='' and str(v.get('CreatedAt','')).startswith('2026-10-06')]
cold+=['cqc_mysql_data']
active={m.get('Name') for c in containers if c['State']['Status']=='running' for m in c['Mounts']}
assert not (set(cold)&active), 'Do not examine active database volumes'
image=next(c['Image'] for c in containers if c['Name']=='/cqc-cicd-backend-1')
helper_name='cqc-mo103-inventory-ro-20261014'
assert not any(c['Name']=='/'+helper_name for c in containers)
mysql_uid=cmd(['docker','exec','cqc-cicd-mysql-1','id','-u','mysql']).decode().strip()
mysql_gid=cmd(['docker','exec','cqc-cicd-mysql-1','id','-g','mysql']).decode().strip()
assert mysql_uid.isdigit() and mysql_gid.isdigit()
args=['docker','run','--name',helper_name,'--rm','--pull','never','--read-only','--network','none','--user',mysql_uid+':'+mysql_gid,'--cap-drop','ALL','--security-opt','no-new-privileges']
for i,n in enumerate(cold):args+=['--mount',f'type=volume,src={n},dst=/evidence/v{i},readonly']
volume_code='''from pathlib import Path
import sys,json,hashlib
names=json.loads(sys.argv[1]);patterns=json.loads(sys.argv[2]);rows=[]
for i,name in enumerate(names):
 root=Path('/evidence/v'+str(i));files=[];tables=[]
 for f in root.iterdir():
  if f.is_symlink():files.append({'path':f.name,'kind':'symlink'});continue
  if f.is_dir():files.append({'path':f.name+'/','children':[c.name for c in f.iterdir()][:40]})
  else:files.append({'path':f.name,'bytes':f.lstat().st_size})
 for f in root.glob('*/*.ibd'):
  if not any(s in f.stem.lower() for s in ['inspection','control_attempt','error_log']):continue
  size=f.stat().st_size
  entry={'path':str(f.relative_to(root)),'bytes':size}
  if size<=128*1024*1024:
   data=f.read_bytes();entry['sha256']=hashlib.sha256(data).hexdigest();entry['literal_id_matches']=[p for p in patterns if p.encode() in data]
  else:entry['skipped']='over 128MiB cap'
  tables.append(entry)
 rows.append({'volume':name,'top_level':files,'literal_binary_scan':tables})
print(json.dumps(rows))
'''
result=subprocess.run(args+['--entrypoint','python',image,'-c',volume_code,json.dumps(cold),json.dumps(sorted(ids))],capture_output=True,timeout=90)
if result.returncode: raise RuntimeError(result.stderr.decode('utf-8','replace')[:1000])
save('cold-volume-search.json',{'helper_name':helper_name,'existing_image':image,'read_only_root_and_mounts':True,'network':'none','rows':json.loads(result.stdout),'limit':'Literal ID byte search in selected .ibd files only; no MySQL startup, logical row recovery, or proof that compressed/deleted pages contain no data'})

wsl=subprocess.run(['wsl','-d','Ubuntu','--','sh','-lc','find /home /root /tmp -maxdepth 3 -type d -iname "*cqc*" 2>/dev/null'],capture_output=True,timeout=30)
save('wsl-location-search.json',{'distro':'Ubuntu','scope':'Directory names only under /home /root /tmp, maxdepth 3','exit_code':wsl.returncode,'matched_directories':wsl.stdout.decode('utf-8','replace').splitlines(),'limit':'Not a full WSL filesystem content search; excludes /mnt and other computers'})
after=public_state()
save('e1-after.json',after)
assert before==after and all(c['health']=='healthy' for c in after)
save('summary.json',{'completed_kst':datetime.now(KST).isoformat(),'inspection_ids_searched':len(ids),'archives_checked':len(archives),'cold_volumes_checked':len(cold),'new_tests':False,'http_or_sql_probe':False,'e1_unchanged_and_healthy':True,'note':'Negative findings apply only to the recorded search scope; no claim that original data were deleted'})
print(json.dumps({'output':str(OUT),'ids':len(ids),'archives':len(archives),'cold_volumes':len(cold),'cold_binary_matches':sum(len(t.get('literal_id_matches',[])) for r in json.loads(result.stdout) for t in r['literal_binary_scan']),'e1_unchanged':True}))
