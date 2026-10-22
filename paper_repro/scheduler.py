"""SQLite DAG/checkpoints with atomic claims, cache invalidation and bounded execution."""
from __future__ import annotations
import concurrent.futures
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from .common import Blocked,digest,read_json,write_json,sha256,within
from .data import load_data
from .compare import compare_curves
from .engine import run_worker

STATES={'PENDING','RUNNING','COMPLETED','VERIFIED','FAILED','BLOCKED'}


def check_plan(plan):
    ids=[t['id'] for t in plan['tasks']]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate task id')
    graph={t['id']:t.get('dependencies',[]) for t in plan['tasks']}
    seen,active=set(),set()
    def visit(k):
        if k not in graph:raise ValueError('Unknown dependency: '+k)
        if k in active:raise ValueError('Cyclic dependency')
        if k in seen:return
        active.add(k)
        for d in graph[k]:visit(d)
        active.remove(k);seen.add(k)
    for k in graph:visit(k)


class Scheduler:
    def __init__(self,root):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.db=self.root/'state.sqlite';self.owner=uuid.uuid4().hex
        with self.connect() as c:
            c.execute('CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, config TEXT, fingerprint TEXT, status TEXT, attempts INTEGER DEFAULT 0, owner TEXT, lease REAL, error TEXT, artifacts TEXT DEFAULT "{}")')
            c.execute('CREATE TABLE IF NOT EXISTS events(at REAL, task TEXT, old TEXT, new TEXT, detail TEXT)')
    def connect(self):
        c=sqlite3.connect(self.db,timeout=30);c.row_factory=sqlite3.Row
        c.execute('PRAGMA journal_mode=WAL');return c
    def sync(self,plan):
        check_plan(plan)
        # Include dependencies and all input bytes; changes invalidate their descendants.
        tasks={t['id']:t for t in plan['tasks']};fingerprints={}
        def fp(k):
            if k in fingerprints:return fingerprints[k]
            t=tasks[k];inputs={}
            for key in ('model','reference','simulation','config','script','contract'):
                if key in t:
                    path=within(self.root,t[key])
                    producers=[other for other in tasks.values() if other.get('output')==t[key]]
                    if producers:
                        if any(other['id'] not in t.get('dependencies',[]) for other in producers):raise ValueError('Generated inputs require their producer as a direct dependency')
                        inputs[key]='DEPENDENCY_OUTPUT'
                    else:inputs[key]=sha256(path) if path.is_file() else 'MISSING'
            fingerprints[k]=digest({'task':t,'inputs':inputs,'deps':[fp(d) for d in t.get('dependencies',[])]})
            return fingerprints[k]
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            existing={r['id']:r for r in c.execute('SELECT * FROM tasks')}
            invalidated=set()
            for id,t in tasks.items():
                f=fp(id);old=existing.get(id)
                if old and old['status']=='RUNNING':
                    if old['fingerprint']!=f:raise RuntimeError('Cannot change a running task')
                    continue
                cached=old and old['fingerprint']==f
                if cached and old['status'] in {'COMPLETED','VERIFIED'}:
                    for rel,expected in json.loads(old['artifacts']).items():
                        p=within(self.root,rel)
                        if not p.is_file() or sha256(p)!=expected:cached=False;break
                if not cached:
                    invalidated.add(id)
                    if old and old['status'] in {'COMPLETED','VERIFIED'}:
                        archive=self.root/'.history'/digest(id)/old['fingerprint']
                        for rel in json.loads(old['artifacts']):
                            source=within(self.root,rel)
                            if source.is_file():
                                dest=archive/rel;dest.parent.mkdir(parents=True,exist_ok=True)
                                __import__('shutil').copyfile(source,dest)
                    c.execute('INSERT OR REPLACE INTO tasks(id,config,fingerprint,status,attempts,artifacts) VALUES(?,?,?,?,0,?)',
                        (id,json.dumps(t),f,'PENDING','{}'))
            # A failed artifact hash invalidates all consumers even if task definitions are unchanged.
            growing=True
            while growing:
                growing=False
                for id,t in tasks.items():
                    if id not in invalidated and any(d in invalidated for d in t.get('dependencies',[])):
                        row=c.execute('SELECT status FROM tasks WHERE id=?',(id,)).fetchone()
                        if row['status']=='RUNNING':raise RuntimeError('Cannot invalidate an active dependent task')
                        c.execute('UPDATE tasks SET status="PENDING",attempts=0,artifacts="{}" WHERE id=?',(id,))
                        invalidated.add(id);growing=True
            for stale in set(existing)-set(tasks):
                if existing[stale]['status']=='RUNNING':raise RuntimeError('Cannot remove a running task')
                c.execute('DELETE FROM tasks WHERE id=?',(stale,))
    def recover(self,force=False):
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            for row in c.execute('SELECT * FROM tasks WHERE status="RUNNING"').fetchall():
                if force or (row['lease'] or 0)<time.time():
                    c.execute('UPDATE tasks SET status="PENDING",owner=NULL,lease=NULL,error=? WHERE id=?',('Interrupted execution recovered',row['id']))
                    c.execute('INSERT INTO events VALUES(?,?,?,?,?)',(time.time(),row['id'],'RUNNING','PENDING','expired lease'))
    def rows(self):
        with self.connect() as c:return [dict(r) for r in c.execute('SELECT * FROM tasks ORDER BY id')]
    def _claim(self,lease_seconds=90):
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            rows={r['id']:r for r in c.execute('SELECT * FROM tasks')}
            choices=[]
            for r in rows.values():
                if r['status']!='PENDING':continue
                t=json.loads(r['config']);deps=[rows[d]['status'] for d in t.get('dependencies',[])]
                if any(s in {'FAILED','BLOCKED'} for s in deps):
                    c.execute('UPDATE tasks SET status="BLOCKED",error=? WHERE id=?',('Dependency failed/blocked',r['id']));continue
                if all(s in {'COMPLETED','VERIFIED'} for s in deps):choices.append((t.get('priority',0),r))
            if not choices:return None
            row=max(choices,key=lambda v:v[0])[1]
            c.execute('UPDATE tasks SET status="RUNNING",attempts=attempts+1,owner=?,lease=? WHERE id=?',
                (self.owner,time.time()+lease_seconds,row['id']))
            c.execute('INSERT INTO events VALUES(?,?,?,?,?)',(time.time(),row['id'],row['status'],'RUNNING','claimed'))
            return json.loads(row['config'])
    def _finish(self,task,status,error='',artifacts=None):
        hashes={str(Path(p).resolve().relative_to(self.root)):sha256(p) for p in artifacts or []}
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            r=c.execute('SELECT * FROM tasks WHERE id=?',(task['id'],)).fetchone()
            if r['owner']!=self.owner:raise RuntimeError('Lease ownership lost')
            if status=='FAILED' and r['attempts']<task.get('max_attempts',1):status='PENDING'
            c.execute('UPDATE tasks SET status=?,error=?,owner=NULL,lease=NULL,artifacts=? WHERE id=?',
                (status,error,json.dumps(hashes),task['id']))
            c.execute('INSERT INTO events VALUES(?,?,?,?,?)',(time.time(),task['id'],'RUNNING',status,error))
    def _execute(self,t,remaining):
        output=within(self.root,t['output']);timeout=min(t.get('timeout',600),remaining)
        if timeout<=0:raise Blocked('Budget exhausted')
        if t['kind']=='simulate':
            model=within(self.root,t['model'])
            run_worker(model,output,t.get('backend','lumerical'),timeout,t.get('method','Radau'))
            # Freeze exact model bytes next to each run for convergence/family checks.
            write_json(output.with_suffix('.model.json'),read_json(model))
            return [output,output.with_suffix('.provenance.json'),output.with_suffix('.model.json')]
        if t['kind']=='script':
            from .product import run_product_worker
            run_product_worker(within(self.root,t['script']),within(self.root,t['contract']),output,t.get('product','FDTD'),timeout)
            return [output,output.with_suffix('.provenance.json')]
        if t['kind']=='compare':
            from .compare import compare_files
            value=compare_files(within(self.root,t['reference']),within(self.root,t['simulation']),t['column'],t.get('ref_x','x'),t.get('ref_y','y'),t.get('uncertainty_y',0))
            write_json(output,value);return [output]
        if t['kind']=='plot':
            from .plotting import plot_matlab
            cfg=read_json(within(self.root,t['config']))
            for fig in cfg['figures']:fig['data']=str(within(self.root,fig['data']))
            cfg['output_dir']=str(within(self.root,cfg['output_dir']))
            receipt=plot_matlab(cfg,output,timeout)
            return [output,output.with_suffix('.plot-receipt.json')]+[Path(a['file']) for a in receipt['outputs']]
        raise ValueError('Unknown task kind: '+t['kind'])
    def run(self,budget_seconds=600,workers=1):
        if budget_seconds<=0 or not 1<=workers<=16:raise ValueError('Invalid budget/worker count')
        self.recover();deadline=time.monotonic()+budget_seconds;active={}
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            try:
                while active or time.monotonic()<deadline:
                    while len(active)<workers and time.monotonic()<deadline:
                        t=self._claim()
                        if t is None:break
                        active[pool.submit(self._execute,t,deadline-time.monotonic())]=t
                    if not active:break
                    done,_=concurrent.futures.wait(active,timeout=1,return_when=concurrent.futures.FIRST_COMPLETED)
                    with self.connect() as c:
                        c.execute('UPDATE tasks SET lease=? WHERE status="RUNNING" AND owner=?',(time.time()+90,self.owner))
                    for future in done:
                        t=active.pop(future)
                        try:self._finish(t,'COMPLETED',artifacts=future.result())
                        except Blocked as e:self._finish(t,'BLOCKED',str(e))
                        except Exception as e:self._finish(t,'FAILED',f'{type(e).__name__}: {e}')
            except KeyboardInterrupt:
                # Workers are bounded by per-task timeout; leave recoverable leases.
                for f in active:f.cancel()
                raise
        return self.rows()
