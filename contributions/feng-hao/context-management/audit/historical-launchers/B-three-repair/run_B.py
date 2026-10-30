#!/usr/bin/env python3
"""Formal B, one sequential trial per task, with no infrastructure retries."""
import signal
import argparse,csv,fcntl,hashlib,importlib.util,json,math,os,subprocess,sys,time,traceback
from pathlib import Path
from datetime import datetime

HERE=Path(__file__).resolve().parent
ROOT=Path('/Users/haohao/Downloads/03work-fh')
STOP=ROOT/'results/context-formal/B-stop-requested'
ASSETS=HERE.parents[1]/'work/repair_a/assets'
spec=importlib.util.spec_from_file_location('existing_batch',ROOT/'scripts/run_context_batch.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

def now():return datetime.now().astimezone().isoformat()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def records(p):
    if not p.exists():return []
    with p.open() as f:raw=list(csv.DictReader(f))
    return list({x['task_id']:x for x in raw}.values())
def snapshot(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)

def main():
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--live',action='store_true');opt=cli.parse_args()
    os.environ['DOCKER_DEFAULT_PLATFORM']='linux/amd64'
    sys.argv=[str(ROOT/'scripts/run_context_batch.py'),'--configuration','B','--suite','formal','--tua-root',str(ROOT/'vendor/TUA-Bench'),'--model','openrouter/minimax/minimax-m3.1-flash','--cost-limit','0.06','--uv','/Users/haohao/.local/bin/uv','--run-root',str(ROOT/'runs/context-formal'),'--record-root',str(ROOT/'results/context-formal'),'--progress-interval','30','--resume']+(['--live'] if opt.live else [])
    a=b.parse_args();record=a.record_root/'formal-B.csv';old=records(record)
    if len({x['task_id'] for x in old})!=len(old):raise RuntimeError('Existing B CSV has repeated tasks; inspect before starting')
    fingerprints={'model':a.model,'code_sha256':b.code_sha256(),'base_config_sha256':sha(b.BASE_CONFIG),'variant_config_sha256':sha(b.CONFIGS['B'])}
    for x in old:
        if x['config_id']!='B' or x['suite']!='formal' or x['task_id'] not in a.tasks:raise RuntimeError('Unexpected data in B CSV')
        if any(x.get(k)!=v for k,v in fingerprints.items()):raise RuntimeError('B fingerprint changed; refuse mixing results')
    authorized=set(json.loads((HERE/'retry-authorization.json').read_text())['tasks'])
    consumed_path=ROOT/'results/context-formal/B-three-repair-consumed.json'
    consumed=set(json.loads(consumed_path.read_text())) if consumed_path.exists() else set()
    prior={x['task_id']:x for x in old};pending=[];retries=set()
    for task in a.tasks:
        taskdir=a.run_root/'formal/B'/task
        if task in prior and prior[task]['status']=='infrastructure_failure' and task in authorized and task not in consumed:
            pending.append(task);retries.add(task)
        elif task in prior:
            print('SKIP recorded B task (including reward 0 or infrastructure failure):',task,flush=True)
        elif taskdir.exists() and any(taskdir.iterdir()):
            raise RuntimeError('Unrecorded B trial files exist; refuse duplicate trial: '+task)
        else:pending.append(task)
    print('B queue:',len(pending),'authorized repair tasks; one attempt each; cost parameter $0.06.',flush=True)
    print('CSV:',record,flush=True)
    if not opt.live:
        print('PLAN ONLY: no containers/model calls/result writes.');return 0
    if not pending:return 0
    if not set(pending).issubset(authorized):raise RuntimeError('Repair batch must contain only three authorized tasks')
    evidence=json.loads((HERE/'preflight-results.json').read_text())
    if {x['task'] for x in evidence if x['status']=='passed'}!=authorized:raise RuntimeError('Three environment preflights must pass before paid run')
    if STOP.exists():raise RuntimeError('Stop marker present; remove only when a new start is authorized')
    if not any(k in os.environ for k in ('OPENROUTER_API_KEY','MSWEA_API_KEY')):
        raise RuntimeError('No provider variable in this process. Launch screen once from your original configured terminal; never paste keys into chat.')
    if b.tua_commit(a.tua_root)!=b.EXPECTED_TUA_COMMIT or b.harbor_version()!='0.6.3':raise RuntimeError('Pinned TUA/Harbor mismatch')
    if not (ASSETS/'uv').is_file() or not (ASSETS/'uv-cache').is_dir():raise RuntimeError('Prepared infrastructure assets missing')
    a.run_root.mkdir(parents=True,exist_ok=True)
    with (a.run_root/'resume-A-after-039.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        active=subprocess.run(['docker','ps','--format','{{.Names}}'],check=True,capture_output=True,text=True,timeout=15).stdout
        if any('--context-' in x for x in active.splitlines()):raise RuntimeError('Another context trial is running; refusing overlap')
        a.record_root.mkdir(parents=True,exist_ok=True);stamp=datetime.now().strftime('%Y%m%d-%H%M%S');logroot=a.record_root/('B-launch-'+stamp);logroot.mkdir()
        proxy='http://host.docker.internal:9674';env={k:proxy for k in ('http_proxy','https_proxy','HTTP_PROXY','HTTPS_PROXY')};env.update(NO_PROXY='localhost,127.0.0.1,::1',no_proxy='localhost,127.0.0.1,::1')
        overlay=logroot/'transport-overlay.json'
        snapshot(overlay,{'services':{'main':{'build':{'args':env},'environment':env,'volumes':[{'type':'bind','source':str(ASSETS/'uv'),'target':'/tmp/pe6203-uv-binary','read_only':True},{'type':'bind','source':str(ASSETS/'uv-cache'),'target':'/tmp/pe6203-uv-cache'}]}}})
        snapshot(logroot/'provenance.json',{'started_at':now(),'configuration':'B',**fingerprints,'task_list_sha256':sha(b.CANONICAL_TASKS),'cost_parameter_usd':0.06,'repair_shim_sha256':sha(HERE/'sitecustomize.py'),'uv_binary_sha256':sha(ASSETS/'uv'),'policy':'one authorized repair attempt for six preserved pre-model infrastructure failures; completed including zero skipped; new failures retained without further retries','infrastructure':'v2 early CA+HTTPS bootstrap and cached tool/mirror/proxy preparation; original tasks/verifiers and model/decoding/step/time settings preserved','cost_limit_note':'Existing harness passes 0.06; internal accounting may not enforce a hard stop. Actual response costs are audited after each task; over-budget result is retained and flagged, then queue continues. This is a post-trial audit, not a hard in-call cutoff.'})
        os.environ.update(PE6203_REPAIR_A='1',PE6203_REPAIR_OVERLAY=str(overlay),PYTHONPATH=str(HERE)+os.pathsep+os.environ.get('PYTHONPATH',''))
        statepath=a.record_root/'B-progress.json';state={'configuration':'B','status':'running','started_at':now(),'pid':os.getpid(),'screen_session':'pe6203-B','total':40,'current_task':None,'current_trial':None,'record_path':str(record),'provenance':str(logroot/'provenance.json'),'infrastructure_exceptions':[]}
        launch={}
        def update(**values):
            state.update(values);rr=records(record);state.update(updated_at=now(),recorded_tasks=len(rr),completed_tasks=sum(x.get('status')=='completed' and x.get('cost_status')=='complete' for x in rr),infrastructure_failures=sum(x.get('status')=='infrastructure_failure' for x in rr));snapshot(statepath,state)
        original=b.command_for
        def command(args,task,run_id,trialdir):
            trialdir.mkdir(parents=True,exist_ok=True);launch.update(task=task,run_id=run_id,trial=trialdir/run_id)
            snapshot(trialdir/(run_id+'.infrastructure.json'),{'provenance':str(logroot/'provenance.json'),'shim_sha256':sha(HERE/'sitecustomize.py')})
            update(current_trial=str(trialdir/run_id));return original(args,task,run_id,trialdir)
        b.command_for=command
        def heartbeat(command,cwd,log_path,interval,task):
            start=time.monotonic()
            with log_path.open('w') as log:
                process=subprocess.Popen(command,cwd=cwd,stdout=log,stderr=subprocess.STDOUT,text=True,start_new_session=True)
                while True:
                    if STOP.exists():
                        os.killpg(process.pid,signal.SIGTERM)
                        try:process.wait(timeout=15)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid,signal.SIGKILL);process.wait()
                        return -15
                    try:return process.wait(timeout=interval)
                    except subprocess.TimeoutExpired:
                        update(elapsed_current_s=round(time.monotonic()-start,1));print(task,'running;',round(time.monotonic()-start),'seconds',flush=True)
        b.run_with_heartbeat=heartbeat;update()
        try:
            for task in pending:
                if STOP.exists():
                    update(status='stopped',stop_reason='stop_marker');return 1
                if b.code_sha256()!=fingerprints['code_sha256'] or sha(b.CONFIGS['B'])!=fingerprints['variant_config_sha256'] or sha(b.BASE_CONFIG)!=fingerprints['base_config_sha256']:
                    raise RuntimeError('Code/config changed during B run; stopped before next trial')
                update(current_task=task,current_trial=None,elapsed_current_s=0);print('START B',task,flush=True)
                if task in retries:
                    consumed.add(task);snapshot(consumed_path,sorted(consumed))
                try:b.run_task(a,task,record,allow_existing=task in retries)
                except Exception as e:
                    if not any(x['task_id']==task for x in records(record)):
                        b.append_csv(record,{'suite':'formal','config_id':'B','task_id':task,'run_id':launch.get('run_id',''),'status':'infrastructure_failure','cost_status':'unknown','exception':'runner_exception:'+type(e).__name__,'trial_path':str(launch.get('trial','')),**fingerprints})
                    (logroot/(task+'-runner-stack.txt')).write_text(''.join(traceback.format_tb(e.__traceback__)))
                rr=[x for x in records(record) if x['task_id']==task]
                if len(rr)!=1:raise RuntimeError('Expected exactly one CSV row for '+task)
                x=rr[0]
                if x['status']=='infrastructure_failure':
                    state['infrastructure_exceptions'].append({'task':task,'exception':x.get('exception'),'cost_status':x.get('cost_status'),'time':now()});print('INFRASTRUCTURE FAILURE retained; advancing without retry:',task,x.get('exception'),flush=True)
                else:print('RESULT',task,'reward='+x.get('reward',''),'cost_status='+x.get('cost_status',''),flush=True)
                update()
                if STOP.exists():
                    update(status='stopped',stop_reason='stop_marker');return 1
                if x.get('agent_usd') and math.isfinite(float(x['agent_usd'])) and float(x['agent_usd'])>a.cost_limit:
                    snapshot(logroot/(task+'-over-budget.json'),{'task':task,'run_id':x['run_id'],'actual_agent_usd':x['agent_usd'],'parameter_limit_usd':a.cost_limit,'action':'retained_without_retry_continue_next','hard_cutoff':False})
                    print('OVER BUDGET: actual cost exceeded 0.06; retained without retry; continuing next task.',flush=True)
            update(status='queue_finished',current_task=None,current_trial=None,finished_at=now());print('B QUEUE FINISHED:',state['completed_tasks'],'completed,',state['infrastructure_failures'],'infrastructure failures; no retries.',flush=True)
            return 0
        except BaseException as e:
            update(status='stopped',stop_reason=type(e).__name__);raise

if __name__=='__main__':raise SystemExit(main())
