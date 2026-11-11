"""Read-only qualification predicates; no status rewriting or SDK control."""
from datetime import datetime
import math
import re

CAPABILITY='saved-em-qualification-v1'
OPERATION='qualify_saved_em'
EXPLORATORY_CAPABILITY='exploratory-saved-em-v1'
EXPLORATORY_OPERATION='qualify_exploratory_em'


def validate_exploratory(p):
    expected={'project_id','em_job_id','expected_digest','run_id','port_ids','fmin_hz','fmax_hz',
              'required_frequencies_hz','frequency_atol_hz','max_residual','acknowledged_warnings'}
    if not isinstance(p,dict) or set(p)!=expected: raise ValueError('Exact exploratory qualification fields required')
    warnings=p['acknowledged_warnings']
    if (not isinstance(warnings,list) or not warnings or len(warnings)>1000
            or any(not isinstance(w,str) or not w.strip() or len(w)>10000 for w in warnings)
            or len(set(warnings))!=len(warnings)):
        raise ValueError('Explicit unique warning texts required')
    validate(dict({k:v for k,v in p.items() if k!='acknowledged_warnings'}, delta_s_limit=.01, consecutive_passes=1))


def exploratory_log_proof(text, job, p):
    """Identify one finished broadband run without making a mesh-convergence claim."""
    starts=list(re.finditer(r'^([0-9-]{10} [0-9:]{8})\s+Solver started at: ([0-9-]{10} [0-9:]{8} [+-][0-9]{4})\s*$',text,re.M))
    if len(starts)!=1: raise ValueError('Exactly one timestamped native solve required')
    start=datetime.strptime(starts[0].group(2),'%Y-%m-%d %H:%M:%S %z')
    if not job['started_at']-1<=start.timestamp()<=job['finished_at']: raise ValueError('Native start outside source job window')
    blocks=[]
    for line in text[starts[0].start():].splitlines():
        match=re.match(r'^([0-9-]{10} [0-9:]{8})\s+(.*)$',line)
        if match:
            stamp=datetime.strptime(match.group(1),'%Y-%m-%d %H:%M:%S').replace(tzinfo=start.tzinfo).timestamp()
            if not start.timestamp()<=stamp<=job['finished_at'] or (blocks and stamp<blocks[-1][0]): raise ValueError('Native log outside job window or unordered')
            blocks.append((stamp,match.group(2)))
        elif blocks: blocks[-1]=(blocks[-1][0],blocks[-1][1]+' '+line.strip())
    joined='\n'.join(v for _,v in blocks)
    if re.search(r'\b(?:aborted|abort|cancelled|canceled|fatal|failed)\b|^Error\s*:',joined,re.I|re.M): raise ValueError('Conflicting native failure')
    patterns=[r'Finished the general purpose interpolative broadband frequency sweep:.*All broadband sweep convergence criteria have been satisfied after.*calculating (\d+) frequency samples:',
              r'Post-processing finished\.',rf'Creating parametric 1D results for Run ID {p["run_id"]}\b']
    hits=[]
    for pattern in patterns:
        found=[(i,re.search(pattern,v)) for i,(_,v) in enumerate(blocks) if re.search(pattern,v)]
        if len(found)!=1: raise ValueError('Missing or ambiguous terminal marker')
        hits.append(found[0])
    indices=[i for i,_ in hits]
    if indices!=sorted(set(indices)) or re.findall(r'Creating parametric 1D results for Run ID (\d+)',joined)!=[str(p['run_id'])]: raise ValueError('Wrong terminal order or multiple runs')
    expected_count=int(hits[0][1].group(1)); samples=[]; current=None
    for _,body in blocks[:indices[0]]:
        match=re.search(r'Calculation \d+(?: of \d+)? \(Frequency: ([0-9.eE+-]+) (Hz|kHz|MHz|GHz)\)',body)
        if match:
            current={'frequency':float(match.group(1))*{'Hz':1,'kHz':1e3,'MHz':1e6,'GHz':1e9}[match.group(2)],'ports':{}}
            if not math.isfinite(current['frequency']) or current['frequency']<0: raise ValueError('Invalid native frequency')
            samples.append(current)
        for match in re.finditer(r'Stimulation port\s*:\s*(\d+)\s+Accuracy\s*:\s*([0-9.eE+-]+)\s+Iterations\s*:',body):
            port=int(match.group(1)); value=float(match.group(2))
            if current is None or port not in p['port_ids'] or port in current['ports'] or not math.isfinite(value) or not 0<=value<=p['max_residual']:
                raise ValueError('Invalid per-excitation residual')
            current['ports'][port]=value
    if len(samples)!=expected_count or any(set(s['ports'])!=set(p['port_ids']) for s in samples): raise ValueError('Incomplete direct sample/port coverage')
    frequencies=[s['frequency'] for s in samples]
    if not frequencies or min(frequencies)>p['fmin_hz']+p['frequency_atol_hz'] or max(frequencies)<p['fmax_hz']-p['frequency_atol_hz']:
        raise ValueError('Direct sample band coverage missing')
    if any(not any(abs(f-v)<=p['frequency_atol_hz'] for f in frequencies) for v in p['required_frequencies_hz']): raise ValueError('Required direct sample missing')
    return {'native_start':start.isoformat(),'direct_samples':len(samples),
            'max_residual':max(v for sample in samples for v in sample['ports'].values()),
            'mesh_convergence':'unknown','terminal_times':[blocks[i][0] for i in indices]}


def validate(p):
    required={'project_id','em_job_id','expected_digest','run_id','port_ids','fmin_hz','fmax_hz',
        'required_frequencies_hz','frequency_atol_hz','delta_s_limit','consecutive_passes',
        'max_residual'}
    if not isinstance(p,dict) or set(p)!=required: raise ValueError('Exact qualification fields required')
    from cst_automation.em_network import sha,finite
    sha(p['expected_digest'])
    if type(p['run_id']) is not int or p['run_id']<=0: raise ValueError('Positive saved Run ID required')
    ports=p['port_ids']
    if not isinstance(ports,list) or not 1<=len(ports)<=128 or any(type(v) is not int or v<=0 for v in ports) or len(set(ports))!=len(ports):
        raise ValueError('Explicit unique positive native port IDs required')
    for key in ('fmin_hz','fmax_hz','frequency_atol_hz','delta_s_limit','max_residual'):finite(p[key])
    if not (0<=p['fmin_hz']<p['fmax_hz'] and 0<=p['frequency_atol_hz']<p['fmax_hz'] and 0<p['delta_s_limit']<1 and 0<p['max_residual']<1):
        raise ValueError('Invalid qualification numerical limits')
    if type(p['consecutive_passes']) is not int or not 1<=p['consecutive_passes']<=100:raise ValueError('Bounded mesh pass count required')
    frequencies=p['required_frequencies_hz']
    if not isinstance(frequencies,list) or not 1<=len(frequencies)<=10000:raise ValueError('Explicit required samples required')
    for f in frequencies:
        if not p['fmin_hz']<=finite(f)<=p['fmax_hz']:raise ValueError('Required sample outside band')


def log_proof(text,job,p):
    starts=list(re.finditer(r'^([0-9-]{10} [0-9:]{8})\s+Solver started at: ([0-9-]{10} [0-9:]{8} [+-][0-9]{4})\s*$',text,re.M))
    if len(starts)!=1:raise ValueError('Exactly one timestamped native solve required')
    start=datetime.strptime(starts[0].group(2),'%Y-%m-%d %H:%M:%S %z')
    if not job['started_at']-1<=start.timestamp()<=job['finished_at']:raise ValueError('Native start outside source job window')
    lines=text[starts[0].start():].splitlines();blocks=[];time=None
    for line in lines:
        m=re.match(r'^([0-9-]{10} [0-9:]{8})\s+(.*)$',line)
        if m:
            time=datetime.strptime(m.group(1),'%Y-%m-%d %H:%M:%S').replace(tzinfo=start.tzinfo).timestamp()
            if not start.timestamp()<=time<=job['finished_at']:raise ValueError('Native log extends outside execution window')
            if blocks and time<blocks[-1][0]:raise ValueError('Native timestamps are not chronological')
            blocks.append((time,m.group(2)))
        elif blocks:blocks[-1]=(blocks[-1][0],blocks[-1][1]+' '+line.strip())
    joined='\n'.join(v for _,v in blocks)
    if re.search(r'\b(?:aborted|abort|cancelled|canceled|fatal|failed)\b|^Error\s*:',joined,re.I|re.M):raise ValueError('Conflicting native failure in source run')
    patterns=[r'Mesh adaptation terminated because the desired accuracy limit is reached\.',
        r'Finished the general purpose interpolative broadband frequency sweep:.*All broadband sweep convergence criteria have been satisfied after.*calculating \d+ frequency samples:',
        r'Post-processing finished\.',rf'Creating parametric 1D results for Run ID {p["run_id"]}\b']
    indices=[]
    for pattern in patterns:
        hits=[i for i,(_,v) in enumerate(blocks) if re.search(pattern,v)]
        if len(hits)!=1:raise ValueError('Missing or ambiguous native terminal marker')
        indices.append(hits[0])
    if indices!=sorted(set(indices)):raise ValueError('Native terminal events out of order')
    deltas=[float(m.group(1)) for _,v in blocks[:indices[0]+1] for m in re.finditer(r'All S-Parameters\s*[:=]\s*([0-9.eE+-]+)',v)]
    count=p['consecutive_passes'];last=deltas[-count:]
    if len(last)!=count or any(not math.isfinite(v) or not 0<=v<=p['delta_s_limit'] for v in last):raise ValueError('Mesh delta requirement not met')
    run_ids=re.findall(r'Creating parametric 1D results for Run ID (\d+)',joined)
    if run_ids!=[str(p['run_id'])]:raise ValueError('Multiple saved runs in native log')
    frequency=None;residuals={port:[] for port in p['port_ids']}
    for _,body in blocks:
        f=re.search(r'Calculation \d+(?: of \d+)? \(Frequency: ([0-9.eE+-]+) (Hz|kHz|MHz|GHz)\)',body)
        if f:
            frequency=float(f.group(1))*{'Hz':1,'kHz':1e3,'MHz':1e6,'GHz':1e9}[f.group(2)]
            if not math.isfinite(frequency) or frequency<0:raise ValueError('Invalid native calculation frequency')
        for match in re.finditer(r'Stimulation port\s*:\s*(\d+)\s+Accuracy\s*:\s*([0-9.eE+-]+)\s+Iterations\s*:',body):
            port=int(match.group(1));value=float(match.group(2))
            if port not in residuals or frequency is None or not math.isfinite(value) or not 0<=value<=p['max_residual']:
                raise ValueError('Invalid or excessive native per-excitation residual')
            residuals[port].append((frequency,value))
    for rows in residuals.values():
        if not rows or min(f for f,_ in rows)>p['fmin_hz']+p['frequency_atol_hz'] or max(f for f,_ in rows)<p['fmax_hz']-p['frequency_atol_hz']:
            raise ValueError('Native residual coverage missing for an excitation port')
        if any(not any(abs(f-required)<=p['frequency_atol_hz'] for f,_ in rows) for required in p['required_frequencies_hz']):
            raise ValueError('Native residual missing at required frequency')
    return {'native_start':start.isoformat(),'terminal_times':[blocks[i][0] for i in indices],'mesh_deltas':last,
            'max_residual':max(v for rows in residuals.values() for _,v in rows),
            'residual_samples_by_port':{str(k):len(v) for k,v in residuals.items()}}
