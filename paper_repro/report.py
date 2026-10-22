from __future__ import annotations
import html
from pathlib import Path
from .common import read_json,write_json,now


def report(project):
    project=Path(project).resolve()
    manifest=read_json(project/'manifest.json')
    rows=[]
    db=project/'state.sqlite';runtime={}
    if db.exists():
        from .scheduler import Scheduler
        runtime={r['id']:r for r in Scheduler(project).rows()}
    for t in manifest['tasks']:
        # Scheduler COMPLETED means execution, never scientific verification.
        r=runtime.get(t['id']);grade='D';reason=t.get('reason','No verified execution')
        grade_file=project/'validation'/(t['id']+'.json')
        if grade_file.exists():
            from .validation import grade as regrade
            from .common import within
            spec=read_json(grade_file)
            if all(k in spec for k in ('model','data','metrics','thresholds')):
                kwargs={k:str(within(project,spec[k])) for k in ('convergence_path','physics_path','heldout_path') if spec.get(k)}
                verified=regrade(read_json(within(project,spec['model'])),within(project,spec['data']),spec['metrics'],spec['thresholds'],**kwargs)
                grade=verified['grade'];reason='; '.join(verified['reasons']) or 'All configured evidence gates passed'
        rows.append({'id':t['id'],'class':t['classification']['class'],'status':r['status'] if r else t['status'],
            'grade':grade,'reason':reason,'page':t['page'],'provisional':t['classification']['provisional']})
    summary={'generated_at':now(),'paper_sha256':manifest['paper_sha256'],'coverage_reviewed':manifest['coverage_reviewed'],
        'figure_count':manifest['figure_count'],'panel_count':manifest['panel_count'],'results':rows,
        'limitations':manifest.get('warnings',[])}
    write_json(project/'report.json',summary)
    lines=['# Paper reproduction report','',f"Figures: {summary['figure_count']}; panels: {summary['panel_count']}; visually audited coverage: {summary['coverage_reviewed']}.",'',
        'Execution completion and scientific verification are separate. D includes tasks not actually run.','',
        '| Panel | Page | Class | Provisional | Status | Grade | Evidence / blocker |',
        '|---|---:|---|---|---|---|---|']
    for r in rows:
        clean=lambda v:str(v).replace('|','\\|').replace('\n',' ')
        lines.append('| '+' | '.join(clean(r[k]) for k in ('id','page','class','provisional','status','grade','reason'))+' |')
    lines+=['','## Inventory warnings','']+[str(w) for w in summary['limitations']]
    (project/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return summary
