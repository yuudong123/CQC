"""Render a standalone project configuration without creating containers or volumes."""
from pathlib import Path
import json,os,socket,subprocess

OUT=Path('C:/CQC/outputs/qa-mo-be-followup-20261012-162118')
source=json.loads((OUT/'environment-template-source.json').read_text(encoding='utf-8'))
project='cqc-mo103-e2-20261012'
services={}
for name in ['mysql','inference','backend','simulator']:
    c=source[name]
    service={'image':c['image'],'pull_policy':'never','restart':'no','networks':['qa'],
             'working_dir':c['working_dir'],'command':c['command']}
    if c['entrypoint'] is not None:service['entrypoint']=c['entrypoint']
    h=c['healthcheck']
    service['healthcheck']={'test':h['Test'],'interval':str(h['Interval']//1000000000)+'s',
         'timeout':str(h['Timeout']//1000000000)+'s','start_period':str(h.get('StartPeriod',0)//1000000000)+'s','retries':h['Retries']}
    services[name]=service
services['mysql'].update({'environment':{'MYSQL_DATABASE':'cqc_mo103_qa','MYSQL_USER':'cqc_mo103_qa',
    'MYSQL_PASSWORD':'${CQC_QA_MYSQL_PASSWORD:?Set a dedicated QA password}',
    'MYSQL_ROOT_PASSWORD':'${CQC_QA_MYSQL_ROOT_PASSWORD:?Set a dedicated QA root password}'},
    'volumes':['qa_mysql:/var/lib/mysql']})
services['mysql']['healthcheck'].update({'test':['CMD-SHELL','MYSQL_PWD="$$MYSQL_ROOT_PASSWORD" mysql --protocol=TCP -h127.0.0.1 -uroot -Nse "SELECT 1" >/dev/null 2>&1'],'start_period':'300s'})
services['inference'].update({'environment':source['inference']['safe_env'],'volumes':['qa_inference_logs:/var/log/cqc'],
    'ports':['127.0.0.1:28001:8001']})
services['backend'].update({'environment':{**source['backend']['safe_env'],
    'DATABASE_URL':'mysql+pymysql://cqc_mo103_qa:${CQC_QA_MYSQL_PASSWORD:?Set a dedicated QA password}@mysql:3306/cqc_mo103_qa',
    'SIMULATOR_FAULT_TOKEN':'${CQC_QA_FAULT_TOKEN:?Set a dedicated QA token}','LOG_DIR':'/var/log/cqc'},
    'depends_on':{'mysql':{'condition':'service_healthy'},'inference':{'condition':'service_healthy'}},
    'ports':['127.0.0.1:28000:8000'],'volumes':['qa_fault_images:/data/fault-images','qa_backend_logs:/var/log/cqc']})
services['simulator'].update({'environment':{**source['simulator']['safe_env'],
    'SIMULATOR_FAULT_TOKEN':'${CQC_QA_FAULT_TOKEN:?Set a dedicated QA token}','LOG_DIR':'/var/log/cqc'},
    'depends_on':{'backend':{'condition':'service_healthy'}},'ports':['127.0.0.1:28002:8002'],
    'volumes':[{'type':'volume','source':'dataset','target':'/data/dataset','read_only':True},
               'qa_position:/data/state','qa_simulator_logs:/var/log/cqc']})
config={'services':services,'networks':{'qa':{'internal':True}},
    'volumes':{k:{} for k in ['qa_mysql','qa_fault_images','qa_position','qa_backend_logs','qa_inference_logs','qa_simulator_logs']}}
config['volumes']['dataset']={'external':True,'name':'cqc_simulator_dataset'}
file=OUT/'isolated-compose.json';file.write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
(OUT/'empty.env').write_bytes(b'')
env=os.environ.copy()
for key in ['COMPOSE_FILE','COMPOSE_PROJECT_NAME','DATABASE_URL','SIMULATOR_FAULT_TOKEN','INFERENCE_URL']:
    env.pop(key,None)
env.update({'CQC_QA_MYSQL_PASSWORD':'render-only-qa-password','CQC_QA_MYSQL_ROOT_PASSWORD':'render-only-root-password','CQC_QA_FAULT_TOKEN':'render-only-qa-token'})
proc=subprocess.run(['docker','compose','--env-file',str(OUT/'empty.env'),'-p',project,'-f',str(file),
                     'config','--format','json'],env=env,capture_output=True,text=True,encoding='utf-8',timeout=25)
if proc.returncode:raise RuntimeError(proc.stderr)
rendered=json.loads(proc.stdout)
checks={'four_services_only':set(rendered['services'])=={'mysql','inference','backend','simulator'},
 'pinned_deployed_images':all(rendered['services'][n]['image']==source[n]['image'] for n in services),
 'no_build':all('build' not in s for s in rendered['services'].values()),
 'no_pulls':all(s.get('pull_policy')=='never' for s in rendered['services'].values()),
 'no_e1_db_url':rendered['services']['backend']['environment']['DATABASE_URL'].endswith('@mysql:3306/cqc_mo103_qa'),
 'no_e1_rw_volumes':all(v.get('source','').startswith('qa_') or v.get('source')=='dataset' for s in rendered['services'].values() for v in s.get('volumes',[])),
 'dataset_read_only':any(v.get('source')=='dataset' and v.get('read_only') is True for v in rendered['services']['simulator']['volumes']),
 'independent_position':'qa_position' in rendered['volumes'] and rendered['volumes']['qa_position']['name']==project+'_qa_position',
 'internal_network':all(n.get('internal') is True for n in rendered['networks'].values()),
 'loopback_ports':all(v.get('host_ip')=='127.0.0.1' for s in rendered['services'].values() for v in s.get('ports',[])),
 'no_auto_start_false_assumption':'SIMULATOR_AUTO_START' not in rendered['services']['simulator']['environment'],
}
port_status={}
for port in [28000,28001,28002]:
    s=socket.socket();s.settimeout(0.5)
    port_status[str(port)]={'listening':s.connect_ex(('127.0.0.1',port))==0};s.close()
checks['ports_unused']=not any(v['listening'] for v in port_status.values())
assert all(checks.values()),checks
for s in rendered['services'].values():
    for k in list(s.get('environment',{})):
        if any(x in k for x in ['PASSWORD','TOKEN']) or k=='DATABASE_URL':s['environment'][k]='[REDACTED RENDER-ONLY VALUE]'
    s.pop('labels',None)
(OUT/'isolated-compose-rendered-redacted.json').write_text(json.dumps(rendered,indent=2)+'\n',encoding='utf-8')
result={'project':project,'render_exit_code':proc.returncode,'checks':checks,'ports':port_status,'executed':'docker compose config only',
    'containers_created':False,'volumes_created':False,'runtime_health_verified':False,
    'startup_behavior':'Current image automatically starts valid dataset playback; only separate QA DB would receive it. Stopped boot requires a separately agreed product option; SIM-04/05 may instead stop an approved isolated running instance first.',
    'shared_host_limit':'Network and volumes are independent, but CPU/RAM/disk are shared with E1. Schedule runtime outside E1 acceptance measurement.'}
(OUT/'isolated-preflight.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
