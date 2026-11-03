#!/usr/bin/env python3
"""Only retry proven pre-agent A failures. Original CSV, manifest checks and budget stay intact."""
import argparse,csv,fcntl,hashlib,importlib.util,json,os,subprocess,sys
from pathlib import Path
from datetime import datetime
HERE=Path(__file__).resolve().parent
ROOT=Path('/Users/haohao/Downloads/03work-fh')
ASSETS=HERE.parents[1]/'work/repair_a/assets'
ALLOWED=set('039 045 048 057 063 066 072 075 078 081 084 087 108 114'.split())
s=importlib.util.spec_from_file_location('old_entry',HERE.parent/'resume_A_after_039.py');old=importlib.util.module_from_spec(s);s.loader.exec_module(old);b=old.batch

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(path):
 with path.open() as h:return list(csv.DictReader(h))
def main():
 p=argparse.ArgumentParser();p.add_argument('--live',action='store_true');opt=p.parse_args()
 os.environ['DOCKER_DEFAULT_PLATFORM']='linux/amd64'
 sys.argv=[str(ROOT/'scripts/run_context_batch.py'),'--configuration','A','--suite','formal','--tua-root',str(ROOT/'vendor/TUA-Bench'),'--model','openrouter/minimax/minimax-m3.1-flash','--cost-limit','0.06','--uv','/Users/haohao/.local/bin/uv','--run-root',str(ROOT/'runs/context-formal'),'--record-root',str(ROOT/'results/context-formal'),'--progress-interval','30','--resume','--retry-infrastructure']+(['--live'] if opt.live else [])
 a=b.parse_args();record=a.record_root/'formal-A.csv';latest={x['task_id']:x for x in rows(record)};pending=[];protected=[]
 for task in a.tasks:
  x=latest.get(task)
  if not x:raise RuntimeError('Unexpected missing record: '+task)
  if x['status']=='completed' and x['cost_status']=='complete':
   try:action=b.prior_action(a,task,record)
   except RuntimeError as e:
    # Explicitly retain the already-paid 117 over-budget result, never rerun it.
    if task!='117-comma-text-to-table' or 'invalid or over-limit cost' not in str(e):raise
    metrics=b.trajectory_metrics(Path(x['trajectory_path']))
    if metrics.get('cost_status')!='complete' or abs(float(metrics['agent_usd'])-float(x['agent_usd']))>1e-9:raise RuntimeError('117 cost evidence mismatch')
   protected.append(task);continue
  if task[:3] not in ALLOWED or b.prior_action(a,task,record)!='retry' or not old.failed_before_agent(task,record):
   raise RuntimeError('Not a proven authorized pre-agent failure: '+task)
  pending.append(task)
 print('Protected completed tasks:',len(protected),'(117 over-budget record preserved)');print('Retry only:',', '.join(pending))
 if not opt.live:print('PLAN ONLY: no model call, container start or record mutation.');return 0
 if not pending:return 0
 if b.tua_commit(a.tua_root)!=b.EXPECTED_TUA_COMMIT or b.harbor_version()!='0.6.3':raise RuntimeError('Pinned runtime mismatch')
 if not any(k in os.environ for k in ['OPENROUTER_API_KEY','MSWEA_API_KEY']):raise RuntimeError('Run in original VS Code terminal; provider variable absent. Do not paste keys.')
 if not (ASSETS/'uv').is_file() or not (ASSETS/'uv-cache').is_dir():raise RuntimeError('Prepared uv/cache assets missing')
 with (a.run_root/'resume-A-after-039.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  ps=subprocess.run(['ps','-axo','pid,ppid,comm'],check=True,capture_output=True,text=True,timeout=10).stdout
  for line in ps.splitlines()[1:]:
   q=line.strip().split(None,2)
   if len(q)<3 or int(q[0]) in [os.getpid(),os.getppid()]:continue
   name=Path(q[2]).name.lower()
   if name in ['python','python3','harbor','uv'] or name.startswith('python3.'):raise RuntimeError('Another Python/Harbor/uv process exists; refusing overlap, PID '+q[0])
  active=subprocess.run(['docker','ps','--format','{{.Names}}'],check=True,capture_output=True,text=True,timeout=15).stdout
  if any('--context-' in line for line in active.splitlines()):raise RuntimeError('Active trial exists; no duplicate batch started')
  stamp=datetime.now().strftime('%Y%m%d-%H%M%S');logroot=a.record_root/('repair-A-'+stamp);logroot.mkdir()
  proxy='http://host.docker.internal:9674'
  env={k:proxy for k in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy']};env.update(NO_PROXY='localhost,127.0.0.1,::1',no_proxy='localhost,127.0.0.1,::1')
  overlay=logroot/'transport-overlay.json'
  overlay.write_text(json.dumps({'services':{'main':{'build':{'args':env},'environment':env,'volumes':[{'type':'bind','source':str(ASSETS/'uv'),'target':'/tmp/pe6203-uv-binary','read_only':True},{'type':'bind','source':str(ASSETS/'uv-cache'),'target':'/tmp/pe6203-uv-cache'}]}}},indent=2))
  provenance={'started_at':datetime.now().isoformat(),'authorized_tasks':pending,'protected_completed':protected,'model':a.model,'code_sha256':b.code_sha256(),'repair_shim_sha256':sha(HERE/'sitecustomize.py'),'uv_binary_sha256':sha(ASSETS/'uv'),'installed_reference_packages':json.loads((ASSETS/'installed-packages.json').read_text()),'environment_change':'cached original system build tools and HTTPS apt source transport in derived Dockerfile; setup contains no apt; existing proxy, pinned uv binary, shared public uv cache and mirror; task inputs/verifiers/A/step/time/cost settings preserved','comparison_limit':'Infrastructure preparation and dependency transport changed. Disclose for baseline reproducibility; new Python ABI wheels may be populated in shared cache.'}
  (logroot/'provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n')
  os.environ.update(PE6203_REPAIR_A='1',PE6203_REPAIR_OVERLAY=str(overlay),PYTHONPATH=str(HERE)+os.pathsep+os.environ.get('PYTHONPATH',''))
  original_command=b.command_for
  def command(args,task,run_id,trial_dir):
   cmd=original_command(args,task,run_id,trial_dir)
   (trial_dir/(run_id+'.repair.json')).write_text(json.dumps({'provenance':str(logroot/'provenance.json'),'shim_sha256':provenance['repair_shim_sha256'],'overlay':str(overlay),'original_code_sha256':b.code_sha256()},indent=2)+'\n')
   return cmd
  b.command_for=command
  print('Repair provenance:',logroot/'provenance.json',flush=True)
  outcomes=[]
  for task in pending:
   print('RETRY',task,flush=True)
   ok=b.run_task(a,task,record,allow_existing=True);x=old.last_row(task,record)
   outcomes.append({k:x.get(k) for k in ['task_id','status','reward','cost_status','agent_usd','trial_path']})
   (logroot/'outcomes.json').write_text(json.dumps(outcomes,indent=2)+'\n')
   if not ok:
    print('STOP: first retry failure or budget/record problem. Inspect this task before continuing; no automatic loop.',flush=True);return 1
  print('Authorized retry queue completed. Re-audit full 40-task CSV and the preserved 117 budget violation.',flush=True)
 return 0
if __name__=='__main__':raise SystemExit(main())
