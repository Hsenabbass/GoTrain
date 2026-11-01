"""Linux supervisor/service CPU fixtures; no real agent calls or GPU jobs."""
import copy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from gotrain.requests import RequestError, atomic_json, read_json
from gotrain.jobs import Jobs, JobController, StopRequested, alive, identity, supervise, revision
import test_admission as admission_fixture


class FakeRunner:
    """Explicit runner double: selection only, never model execution."""
    def __init__(self,lease): self.lease,self.best,self.runs=lease,None,[]
    def context(self): return {'goal':self.lease.owned()[1]['frozen']['summary']['goal'],'task':{'kind':'classification'}}
    def result(self,run):
        if run not in self.runs: raise ValueError('Unknown run')
        return {'run_id':run,'status':'completed'}
    def select(self,run): self.result(run); self.best=run; return run


@unittest.skipUnless(sys.platform=='linux' and Path('/home/sagemaker-user/GoTrain').is_dir(),'Supervisor checks run on SageMaker Linux')
class JobTests(unittest.TestCase):
    def setUp(self):
        self.fixture=admission_fixture.AdmissionTests(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.root,self.store,self.record,self.key=self.fixture.root,self.fixture.store,self.fixture.record,self.fixture.key
        (self.root/'configs').mkdir()
        for name in ('m3.json','service.json'): shutil.copyfile(ROOT/'configs'/name,self.root/'configs'/name)
        self.policy=copy.deepcopy(self.fixture.policy); self.policy['submission_deadline_local']='2099-11-01T15:00:00'
        atomic_json(self.root/'configs/m4.json',self.policy)
        self.launches=[]
        self.jobs=Jobs(self.root,self.store,lambda folder,launch:self.launches.append(launch))

    def start(self): return self.jobs.start(self.record['id'],self.key)
    def folder(self): return self.jobs.folder(self.record['id'])
    def claim(self,process=None): atomic_json(self.folder()/'claim.json',{'process':process or identity(os.getpid())})

    def test_duplicate_and_service_restart_never_relaunch(self):
        self.start(); self.start()
        Jobs(self.root,self.store,lambda *_:self.fail('Reconnect launched work')).start(self.record['id'],self.key)
        self.assertEqual(len(self.launches),1)
        with self.assertRaises(RequestError): self.jobs.start(self.record['id'],'request_'+'d'*32)

    def test_uncertain_spawn_is_not_retried(self):
        def failed(*_): self.launches.append('attempted'); raise OSError('explicit fixture spawn failure')
        self.jobs.launcher=failed
        with self.assertRaises(OSError): self.start()
        self.start(); self.assertEqual(len(self.launches),1)
        launch=read_json(self.folder()/'launch.json')
        launch['created_utc']=(datetime.now(timezone.utc)-timedelta(seconds=31)).isoformat()
        atomic_json(self.folder()/'launch.json',launch)
        self.assertTrue(self.jobs.get(self.record['id'])['audit_required'])

    def test_dead_or_reused_owner_requires_audit(self):
        self.start(); owner=identity(os.getpid()); owner['start_ticks']='wrong'
        self.claim(owner)
        atomic_json(self.folder()/'state.json',{'status':'running','job_id':'fixture','model_requests':7})
        view=self.jobs.get(self.record['id'])
        self.assertEqual(view['status'],'interrupted'); self.assertEqual(view['model_requests'],7)
        self.assertEqual(self.start()['status'],'interrupted'); self.assertEqual(len(self.launches),1)

    def test_stop_is_persisted_and_reconnect_keeps_it(self):
        self.start(); self.claim()
        atomic_json(self.folder()/'state.json',{'status':'running','stage':'Comparing','model_requests':4})
        self.assertEqual(self.jobs.stop(self.record['id'])['status'],'stopping')
        self.assertEqual(Jobs(self.root,self.store).get(self.record['id'])['status'],'stopping')
        self.assertEqual(read_json(self.folder()/'state.json')['model_requests'],4)
        atomic_json(self.folder()/'state.json',{'status':'stopped','best':'prior'})
        self.assertEqual(self.jobs.stop(self.record['id'])['best'],'prior')

    def test_controller_charges_before_calls_and_stop_spends_no_new_call(self):
        from gotrain.admission import Admission
        self.start()
        with Admission(self.root,self.policy) as lease:
            lease.admit(self.store,self.record['id'],self.key)
            controller=JobController(lease,self.folder(),FakeRunner)
            controller.bound('model_requests')
            self.assertEqual(read_json(lease.path)['jobs'][lease.job_id]['model_requests'],3)
            self.jobs.stop(self.record['id'])
            with self.assertRaises(StopRequested): controller.bound('model_requests')
            self.assertEqual(read_json(lease.path)['jobs'][lease.job_id]['model_requests'],3)
            lease.finish('stopped')

    def test_real_agent_tool_schemas_construct_without_a_model_call(self):
        from gotrain.admission import Admission
        from gotrain.agent import create_agent
        self.start()
        with Admission(self.root,self.policy) as lease:
            lease.admit(self.store,self.record['id'],self.key)
            controller=JobController(lease,self.folder(),FakeRunner)
            self.assertIsNotNone(create_agent(controller))
            self.assertEqual(lease.owned()[1]['model_requests'],2)
            lease.finish('stopped')

    def test_stop_drains_current_model_stream_before_propagating(self):
        import asyncio
        from unittest.mock import patch
        from strands.models import BedrockModel
        from gotrain.admission import Admission
        from gotrain.agent import create_agent
        self.start()
        drained=[]
        async def current_response(_model,*args,**kwargs):
            yield {'messageStart': {'role':'assistant'}}
            self.jobs.stop(self.record['id'])
            yield {'messageStop': {'stopReason':'end_turn'}}
            drained.append(True)
        with Admission(self.root,self.policy) as lease:
            lease.admit(self.store,self.record['id'],self.key)
            controller=JobController(lease,self.folder(),FakeRunner)
            agent=create_agent(controller)
            async def consume():
                async for _event in agent.model.stream(messages=[]): pass
            with patch.object(BedrockModel,'stream',current_response):
                with self.assertRaises(StopRequested): asyncio.run(consume())
            self.assertEqual(drained,[True])
            self.assertEqual(lease.owned()[1]['model_requests'],3)
            lease.finish('stopped')

    def test_supervisor_persists_selection_and_settles_once(self):
        self.start()
        def factory(controller):
            def run(_message):
                controller.bound('model_requests')
                controller.runner.runs.append('fixture_final')
                controller.invoke('select_candidate',run_id='fixture_final',reason='Explicit CPU fixture final')
                controller.invoke('finish_search',reason='Selection fixture finished')
            return run
        supervise(self.root,self.store,self.record['id'],self.launches[0]['nonce'],agent_factory=factory,runner_factory=FakeRunner,verify_source=False)
        state=self.jobs.get(self.record['id'])
        self.assertEqual((state['status'],state['best'],state['model_requests']),('selected','fixture_final',3))
        self.assertIsNone(read_json(self.root/'artifacts/m4-budget.json')['active'])
        with self.assertRaises(FileExistsError):
            supervise(self.root,self.store,self.record['id'],self.launches[0]['nonce'],agent_factory=factory,runner_factory=FakeRunner,verify_source=False)

    def test_stop_after_current_retains_eligible_final_without_more_calls(self):
        self.start()
        def factory(controller):
            def run(_message):
                controller.bound('model_requests')
                controller.runner.runs.append('finished_current_fixture')
                self.jobs.stop(self.record['id'])
                controller.bound('model_requests')
                self.fail('Stop did not interrupt the next call')
            return run
        supervise(self.root,self.store,self.record['id'],self.launches[0]['nonce'],agent_factory=factory,runner_factory=FakeRunner,verify_source=False)
        view=self.jobs.get(self.record['id'])
        self.assertEqual((view['status'],view['best'],view['model_requests']),('stopped','finished_current_fixture',3))

    def test_package_failure_never_reports_ready_or_loses_best(self):
        self.start()
        def factory(controller):
            def run(_message):
                controller.runner.runs.append('fixture_final')
                controller.invoke('select_candidate',run_id='fixture_final',reason='CPU fixture')
                controller.invoke('finish_search',reason='CPU fixture complete')
            return run
        def failed(*_): raise ValueError('Explicit package verification failure')
        supervise(self.root,self.store,self.record['id'],self.launches[0]['nonce'],agent_factory=factory,runner_factory=FakeRunner,verify_source=False,finalizer=failed)
        result=self.jobs.get(self.record['id'])
        self.assertEqual((result['status'],result['best']),('failed','fixture_final'))
        self.assertNotIn('package',result)

    def test_unfinished_agent_is_failed_and_never_ready(self):
        self.start()
        supervise(self.root,self.store,self.record['id'],self.launches[0]['nonce'],agent_factory=lambda _:lambda _message:None,runner_factory=FakeRunner,verify_source=False)
        self.assertEqual(self.jobs.get(self.record['id'])['status'],'failed')

    def test_rejected_optional_budget_does_not_prevent_a_final_attempt(self):
        from unittest.mock import patch
        from gotrain.admission import Admission
        self.start()
        with Admission(self.root,self.policy) as lease:
            lease.admit(self.store,self.record['id'],self.key)
            controller=JobController(lease,self.folder(),FakeRunner)
            controller.runner.recipe=lambda *_: {}
            def rejected(*_): raise RequestError('Finalization reserve prevents optional tuning',409)
            controller.runner.run_trial=rejected
            with patch('gotrain.jobs.revision',return_value='explicit_CPU_fixture'):
                result=controller.invoke('run_trial',candidate='resnet18',phase='tune',settings={},hypothesis='CPU budget fixture')
            self.assertIn('reserve',result['error'])
            self.assertFalse(controller.state.get('fatal',False))
            controller.bound('model_requests')
            self.assertEqual(lease.owned()[1]['model_requests'],3)
            lease.finish('stopped')

    def test_terminal_display_cannot_hide_unsettled_reservation(self):
        from gotrain.admission import Admission
        self.start(); self.claim()
        with Admission(self.root,self.policy) as lease:
            lease.admit(self.store,self.record['id'],self.key)
            atomic_json(self.folder()/'state.json',{'status':'selected','job_id':lease.job_id})
            self.assertEqual(self.jobs.get(self.record['id'])['status'],'finishing')
            bad=identity(os.getpid()); bad['start_ticks']='wrong'; self.claim(bad)
            self.assertTrue(self.jobs.get(self.record['id'])['audit_required'])
            lease.finish('failed')

    def test_api_start_read_stop_and_origin_protection(self):
        from fastapi.testclient import TestClient
        from gotrain.service import create_app
        with TestClient(create_app(self.store,jobs=self.jobs)) as client:
            route='/api/conversations/'+self.record['id']
            headers={'X-GoTrain-Request':'1'}
            self.assertEqual(client.post(route+'/start',json={'request_id':self.key}).status_code,403)
            self.assertEqual(client.post(route+'/start',headers=headers,json={'request_id':self.key}).status_code,200)
            self.assertEqual(client.get(route+'/job').json()['status'],'starting')
            self.assertEqual(client.post(route+'/stop',headers=headers).json()['status'],'stopping')
        self.assertEqual(len(self.launches),1)

    def test_uncommitted_source_rejected_before_launch(self):
        subprocess.run(['git','init','-q',str(self.root)],check=True,capture_output=True)
        (self.root/'source.py').write_text('print(1)')
        subprocess.run(['git','add','source.py'],cwd=self.root,check=True,capture_output=True)
        with self.assertRaisesRegex(RequestError,'Commit reviewed'): revision(self.root)

    def test_real_parent_death_kills_only_the_cpu_fixture_child(self):
        # Exercise the actual Linux safeguard in isolated processes, never in this
        # test runner or a real job. Both fixtures also have ten-second lifetimes.
        child="import os,time; from gotrain.m4 import protect_parent; protect_parent(os.getppid()); print(os.getpid(),flush=True); time.sleep(10)"
        parent="import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c',sys.argv[1]],stdout=subprocess.PIPE,text=True); print(p.stdout.readline().strip(),flush=True); time.sleep(10)"
        process=subprocess.Popen([sys.executable,'-c',parent,child],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env={**os.environ,'PYTHONPATH':str(ROOT/'src')})
        self.addCleanup(lambda:process.kill() if process.poll() is None else None)
        self.addCleanup(process.stdout.close)
        self.addCleanup(process.stderr.close)
        pid=int(process.stdout.readline().strip()); saved=identity(pid)
        process.kill(); process.wait(timeout=2)
        for _ in range(40):
            if not alive(saved): break
            time.sleep(.05)
        if alive(saved): os.kill(pid,9)
        self.assertFalse(alive(saved))

    def test_detached_supervisor_survives_parent_exit_and_fresh_client_stops_it(self):
        atomic_json(self.root/'fixture-caps.json',self.store.caps)
        atomic_json(self.root/'fixture-benchmarks.json',self.store.benchmarks)
        child="""import sys,time
from pathlib import Path
from gotrain.requests import Requests,read_json
from gotrain.jobs import supervise
from test_jobs import FakeRunner
root=Path(sys.argv[1])
store=Requests(root/'artifacts/service',read_json(root/'fixture-caps.json'),read_json(root/'fixture-benchmarks.json'))
def factory(controller):
 def run(_message):
  controller.bound('model_requests')
  controller.runner.runs.append('completed_cpu_fixture')
  controller.save()
  while True:
   controller.check_event()
   time.sleep(.02)
 return run
supervise(root,store,sys.argv[2],sys.argv[3],agent_factory=factory,runner_factory=FakeRunner,verify_source=False)
"""
        processes=[]
        def launch(folder,intent):
            parent_code="import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c',*sys.argv[1:]],start_new_session=True); print(p.pid,flush=True); time.sleep(10)"
            parent=subprocess.Popen([sys.executable,'-c',parent_code,child,str(self.root),self.record['id'],intent['nonce']],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env={**os.environ,'PYTHONPATH':str(ROOT/'src')+os.pathsep+str(ROOT/'tests')})
            self.addCleanup(parent.stdout.close)
            self.addCleanup(parent.stderr.close)
            processes.extend([parent,int(parent.stdout.readline().strip())])
        self.jobs.launcher=launch
        self.start()
        parent,pid=processes
        self.addCleanup(lambda:parent.kill() if parent.poll() is None else None)
        saved=identity(pid)
        self.addCleanup(lambda:os.kill(pid,9) if alive(saved) else None)
        for _ in range(100):
            view=self.jobs.get(self.record['id'])
            if view['status']=='running' and view.get('model_requests')==3: break
            time.sleep(.03)
        self.assertEqual(self.jobs.get(self.record['id'])['status'],'running')
        parent.kill(); parent.wait(timeout=2)
        fresh=Jobs(self.root,self.store)
        self.assertTrue(alive(saved))
        self.assertEqual(fresh.get(self.record['id'])['model_requests'],3)
        fresh.stop(self.record['id'])
        for _ in range(100):
            if fresh.get(self.record['id'])['status']=='stopped': break
            time.sleep(.03)
        self.assertEqual(fresh.get(self.record['id'])['status'],'stopped')
        self.assertIsNone(read_json(self.root/'artifacts/m4-budget.json')['active'])


if __name__=='__main__': unittest.main()
