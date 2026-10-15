import os,json,time,threading,pathlib,runpy,sys
sys.path.insert(0,'/opt/cqc-sim-qa/source')
from datetime import datetime,timezone
import httpx
from src.simulator.dataset import SimulatorDataset
O=pathlib.Path(os.environ["CQC_TIMING_EVIDENCE"])
lock=threading.Lock()
def event(value):
 with lock:
  with (O/"events.jsonl").open("a") as f:f.write(json.dumps(value,ensure_ascii=False)+"\n")
def now():return datetime.now(timezone.utc).isoformat()
original_post=httpx.AsyncClient.post
async def traced_post(self,url,*args,**kwargs):
 if str(url)!="http://127.0.0.1:28000/v1/inspections":return await original_post(self,url,*args,**kwargs)
 start=time.monotonic();at=now();r=None;error=None
 try:
  r=await original_post(self,url,*args,**kwargs);return r
 except BaseException as e:error=type(e).__name__;raise
 finally:
  event(dict(kind="inspection_http",inspection_id=kwargs.get("data",{}).get("inspection_id"),source_reference=kwargs.get("headers",{}).get("X-CQC-Simulator-Bundle-ID"),started_utc=at,completed_utc=now(),start_monotonic=start,end_monotonic=time.monotonic(),round_trip_seconds=time.monotonic()-start,http_status=r.status_code if r is not None else None,error_type=error))
httpx.AsyncClient.post=traced_post
original_load=SimulatorDataset.load
def traced_load(self,position):
 begin=time.monotonic();at=now();bundle=None
 try:bundle=original_load(self,position);return bundle
 finally:event(dict(kind="dataset_load",position=position,source_reference=bundle.bundle_id if bundle else None,started_utc=at,completed_utc=now(),start_monotonic=begin,end_monotonic=time.monotonic(),load_seconds=time.monotonic()-begin))
SimulatorDataset.load=traced_load
runpy.run_module("src.simulator.main",run_name="__main__")
