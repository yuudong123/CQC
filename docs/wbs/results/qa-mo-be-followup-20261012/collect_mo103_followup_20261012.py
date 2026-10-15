"""Read deployed provenance and preserved evidence; never change running services."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json
import re
import shutil
import subprocess
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path('C:/CQC')
KST = timezone(timedelta(hours=9))
OUT = ROOT/'outputs'/('qa-mo-be-followup-'+datetime.now(KST).strftime('%Y%m%d-%H%M%S'))
OUT.mkdir()

def save(name, value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def run(*args):
    return subprocess.check_output(args,timeout=35)

def text(*args):
    return run(*args).decode('utf-8',errors='replace').strip()

def docker(*args):
    return text('docker',*args)

def stamp(ms):
    return datetime.fromtimestamp(ms/1000,KST).isoformat()

base='/var/jenkins_home/jobs/CQC-CICD/builds'
numbers=sorted(int(x) for x in docker('exec','jenkins','ls','-1',base).splitlines() if x.isdigit())
builds=[]
for n in numbers[-12:]:
    x=ET.fromstring(docker('exec','jenkins','cat',f'{base}/{n}/build.xml'))
    started=int(x.findtext('startTime') or x.findtext('timestamp'))
    duration=int(x.findtext('duration') or 0)
    builds.append({'number':n,'result':x.findtext('result'),'started_kst':stamp(started),
                   'finished_kst':stamp(started+duration) if x.findtext('result') else None})
last_success=next(b for b in reversed(builds) if b['result']=='SUCCESS')
log=docker('exec','jenkins','cat',f"{base}/{last_success['number']}/log")
sha=re.findall(r'Checking out Revision ([0-9a-f]{40})',log)[-1]
node_digests=dict(re.findall(r'#(\d+) exporting manifest list (sha256:[0-9a-f]{64})',log))
service_digests={service:node_digests[node] for node,service in re.findall(r'#(\d+) naming to docker.io/library/cqc-cicd-([a-z-]+):latest',log) if node in node_digests}
selected=[re.sub(r'\x1b\[[0-9;]*m','',line) for line in log.splitlines() if any(v in line for v in ['Checking out Revision','exporting manifest list sha256:','naming to docker.io/library/cqc-cicd-','VERIFY SUCCESS','Finished:'])]
(OUT/'jenkins-selected-log.txt').write_text('\n'.join(selected)+'\n',encoding='utf-8')
containers=json.loads(docker('inspect',*[f'cqc-cicd-{s}-1' for s in ['backend','inference','simulator','logistics-web','mysql']]))
private={c['Name'].removeprefix('/cqc-cicd-').removesuffix('-1'):c for c in containers}
services=[]
for s,c in private.items():
    services.append({'service':s,'id':c['Id'],'image':c['Image'],'created':c['Created'],
        'started_at':c['State']['StartedAt'],'health':c['State'].get('Health',{}).get('Status'),
        'restart_count':c['RestartCount'],'build_digest':service_digests.get(s),
        'matches_build':c['Image']==service_digests.get(s) if s!='mysql' else None,
        'mounts':[{'type':m['Type'],'name':m.get('Name'),'source':m['Source'],'destination':m['Destination'],'rw':m['RW']} for m in c['Mounts']]})
daemon_limit=None
try:
    same_daemon=docker('info','--format','{{.ID}}')==docker('exec','jenkins','docker','info','--format','{{.ID}}')
except subprocess.TimeoutExpired:
    same_daemon=None
    daemon_limit='Jenkins internal docker info timed out after 35 seconds; daemon identity not independently reverified.'
fix=text('git','rev-parse','ee2987f^{commit}')
ancestor=subprocess.run(['git','merge-base','--is-ancestor',fix,sha],capture_output=True).returncode
file_path='src/api/services/quality_operations.py'
deployed=run('docker','exec','cqc-cicd-backend-1','cat','/app/'+file_path)
git_file=run('git','show',sha+':'+file_path)
(OUT/'deployed-quality-operations.py.txt').write_bytes(deployed)
provenance={'checked_kst':datetime.now(KST).isoformat(),'latest_build':builds[-1],'latest_success':last_success,
    'source_sha':sha,'ops13_fix_sha':fix,'fix_is_ancestor':ancestor==0,'ancestor_check_exit':ancestor,
    'same_docker_daemon':same_daemon,'daemon_check_limit':daemon_limit,'services':services,'four_app_images_match':all(s['matches_build'] for s in services if s['service']!='mysql'),
    'backend_file':{'path':file_path,'matches_checkout_bytes':deployed==git_file,
                    'deployed_sha256':hashlib.sha256(deployed).hexdigest(),'git_checkout_sha256':hashlib.sha256(git_file).hexdigest()},
    'scope':'latest SUCCESS selected; inspect source and image digest directly; no redeploy'}
save('deployment-provenance.json',provenance);save('jenkins-builds.json',builds)
queue_info={'api':None,'persisted_queue':None,'limits':'Persisted queue is not a live executor/queue assertion.'}
try:
    with urllib.request.urlopen('http://127.0.0.1:8080/queue/api/json',timeout=4) as r:q=json.load(r)
    queue_info['api']={'accessible':True,'count':len(q.get('items',[]))}
except Exception as exc:queue_info['api']={'accessible':False,'error':str(exc)}
qproc=subprocess.run(['docker','exec','jenkins','cat','/var/jenkins_home/queue.xml'],capture_output=True,timeout=8)
if qproc.returncode==0:
    q=ET.fromstring(qproc.stdout);queue_info['persisted_queue']={'root':q.tag,'item_count':len(q.findall('.//item')),'task_names':[v.text for v in q.findall('.//task') if v.text]}
save('jenkins-queue-check.json',queue_info)
save('resource-preflight.json',{'checked_kst':datetime.now(KST).isoformat(),
    'disk_bytes':{drive:{'total':shutil.disk_usage(drive).total,'free':shutil.disk_usage(drive).free} for drive in ['C:/','D:/']},
    'docker':json.loads(docker('info','--format','{"cpus":{{.NCPU}},"memory_bytes":{{.MemTotal}}}')),
    'container_stats':docker('stats','--no-stream','--format','{{json .}}').splitlines()})
paths=['src/simulator/config.py','src/simulator/main.py','src/simulator/schemas.py']
for f in paths:
    raw=run('docker','exec','cqc-cicd-simulator-1','cat','/app/'+f)
    (OUT/('deployed-'+Path(f).name+'.txt')).write_bytes(raw)
    save('simulator-source-'+Path(f).stem+'.json',{'source_path':f,'sha256':hashlib.sha256(raw).hexdigest(),
         'matches_checkout':raw==run('git','show',sha+':'+f),'auto_start_option_present':b'simulator_auto_start' in raw.lower()})
dataset_script="""import json,hashlib
from pathlib import Path
from src.simulator.dataset import SimulatorDataset
p=Path('/data/dataset');ds=SimulatorDataset(p,24*1024*1024,p/'demo-virtual-brix.csv')
print(json.dumps({'bundles':len(ds),'first_bundle':ds.bundle_id(0),'last_bundle':ds.bundle_id(len(ds)-1),'first_frames':len(ds.load(0).images),'last_frames':len(ds.load(len(ds)-1).images),'index_sha256':hashlib.sha256((p/'index.json').read_bytes()).hexdigest(),'brix_sha256':hashlib.sha256((p/'demo-virtual-brix.csv').read_bytes()).hexdigest(),'scope':'read existing index/CSV plus first and last bundle; not full 869-bundle runtime cycle'}))"""
dataset=json.loads(docker('exec','cqc-cicd-simulator-1','python','-c',dataset_script));save('dataset-check.json',dataset)
state_script="import json,urllib.request; print(json.dumps(json.load(urllib.request.urlopen('http://127.0.0.1:8002/state',timeout=5))))"
save('simulator-state.json',json.loads(docker('exec','cqc-cicd-simulator-1','python','-c',state_script)))
config={}
allowed={
 'backend':['INFERENCE_CLIENT_MODE','INFERENCE_URL','INFERENCE_CONNECT_TIMEOUT_MS','CULTIVAR_CONFIDENCE_THRESHOLD','QUALITY_CONFIDENCE_THRESHOLD','SIMULATOR_INTERNAL_URL','FAULT_IMAGE_STORAGE_ROOT'],
 'simulator':['SIMULATOR_DATASET_ROOT','SIMULATOR_BRIX_CSV_PATH','SIMULATOR_POSITION_PATH','SIMULATOR_BACKEND_URL','SIMULATOR_INTERVAL_MS'],
 'inference':['MODEL_DIR','MODEL_PATH','MODEL_CARD_PATH','INFERENCE_HOST','INFERENCE_PORT','LOG_DIR']}
for s,c in private.items():
    env=dict(v.split('=',1) for v in c['Config']['Env'])
    config[s]={'image':c['Image'],'entrypoint':c['Config'].get('Entrypoint'),'command':c['Config'].get('Cmd'),'working_dir':c['Config'].get('WorkingDir'),
               'safe_env':{k:env[k] for k in allowed.get(s,[]) if k in env},'healthcheck':c['Config'].get('Healthcheck'),
               'mounts':[m for m in services if m['service']==s][0]['mounts']}
save('environment-template-source.json',config)
for label,url in [('backend-health','http://127.0.0.1:8000/health'),('inference-health','http://127.0.0.1:8001/health')]:
    with urllib.request.urlopen(url,timeout=8) as r:save(label+'.json',json.load(r))
save('current-containers.json',docker('ps','-a','--format','{{.Names}}\t{{.Status}}').splitlines())
print(json.dumps({'output':str(OUT),'latest_build':provenance['latest_build'],'latest_success':last_success,
    'source_sha':sha,'fix_is_ancestor':ancestor==0,'four_images_match':provenance['four_app_images_match'],
    'backend_file_match':deployed==git_file,'dataset':dataset,'queue':queue_info},ensure_ascii=True))
