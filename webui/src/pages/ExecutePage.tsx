import { Plus, Save, Trash2, Play, ArrowUp, ArrowDown, RefreshCw, FolderOpen } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { call, isLiveProvider } from '../lib/api';
import type { Job, Output, Run } from '../lib/types';
import { RunCard } from '../components/RunCard';
import { JobEditorCore } from '../components/JobEditorCore';

export function ExecutePage({ project, setProject, selectedJobId, setSelectedJobId, jobDraft, setJobDraft, setJobDirty, setMessage, setBusy, busy, setPreview, setPromote, promoteOutput }: any) {
  const [query, setQuery] = useState('');
  const jobs = (project.jobs || []).filter((job: Job) => `${job.id} ${job.title} ${job.status} ${job.provider}`.toLowerCase().includes(query.toLowerCase()));
  const selected = jobDraft as Job | null;
  const hasActiveRuns = useMemo(() => (project.jobs || []).some((job: Job) => isActiveStatus(job.status) || (job.runs || []).some(run => isActiveStatus(run.status))), [project.jobs]);
  const approvedJobIds = useMemo(() => new Set((project.approved || []).map((item: any) => String(item.name || item.path || '').match(/^(.*?)_(?:image|video)_take_/)?.[1]).filter(Boolean)), [project.approved]);

  useEffect(() => {
    if (!hasActiveRuns || !project?.root) return;
    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        const data = await call('/api/project/load', { root: project.root });
        if (!cancelled) setProject(data);
      } catch (err: any) {
        if (!cancelled) setMessage(`Auto refresh failed: ${err.message}`);
      }
    }, 5000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [hasActiveRuns, project?.root, setProject, setMessage]);

  async function saveJob(next = selected) {
    if (!next) return;
    const data = await call('/api/job/save', { root: project.root, job: next });
    setProject(data.project); setJobDraft(data.job); setJobDirty?.(false); setMessage('Job saved');
  }
  async function createJob(kind: 'image' | 'video') {
    setBusy(true); try { const data = await call('/api/job/create', { root: project.root, kind }); setProject(data.project); setSelectedJobId(data.job.id); setMessage(`Created ${data.job.id}`); } catch (e: any) { setMessage(e.message); } finally { setBusy(false); }
  }
  async function deleteJob() {
    if (!selected || !confirm(`Delete ${selected.id}?`)) return;
    setBusy(true); try { const data = await call('/api/job/delete', { root: project.root, job_id: selected.id }); setProject(data.project); setSelectedJobId(data.project.jobs?.[0]?.id); } catch (e: any) { setMessage(e.message); } finally { setBusy(false); }
  }
  async function moveJob(direction: 'up' | 'down') {
    if (!selected) return;
    const data = await call('/api/job/move', { root: project.root, job_id: selected.id, direction });
    setProject(data.project); setSelectedJobId(selected.id);
  }
  async function moveJobByDrag(fromId: string, toId: string) {
    if (!fromId || !toId || fromId === toId) return;
    const current = project.jobs.findIndex((job: Job) => job.id === fromId);
    const target = project.jobs.findIndex((job: Job) => job.id === toId);
    if (current < 0 || target < 0) return;
    let data: any = { project };
    let movingIndex = current;
    while (movingIndex > target) { data = await call('/api/job/move', { root: project.root, job_id: fromId, direction: 'up' }); movingIndex--; }
    while (movingIndex < target) { data = await call('/api/job/move', { root: project.root, job_id: fromId, direction: 'down' }); movingIndex++; }
    setProject(data.project); setSelectedJobId(fromId);
  }
  async function runJob() {
    if (!selected) return;
    if (isLiveProvider(selected.provider) && !isProviderConfirmed(selected.provider) && !confirm(`Run ${selected.provider}? This may cost credits. You will not be asked again for this provider in this browser session.`)) return;
    if (isLiveProvider(selected.provider)) rememberProviderConfirmed(selected.provider);
    setBusy(true);
    try { await saveJob(selected); const data = await call('/api/job/run', { root: project.root, job_id: selected.id, confirm_live: isLiveProvider(selected.provider), timeout: 420, interval: 8 }); setProject(data.project); setJobDirty?.(false); setMessage(isLiveProvider(selected.provider) ? 'Live run submitted' : 'Dryrun completed'); }
    catch (e: any) { setMessage(`Run failed: ${e.message}`); }
    finally { setBusy(false); }
  }
  async function approveOutput(job: Job, run: Run, output: Output) {
    const data = await call('/api/output/approve', { root: project.root, job_id: job.id, run_id: run.id, output_name: output.name });
    setProject(data.project); setMessage('Approved');
  }
  async function deleteRun(run: Run) {
    if (!selected || !confirm(`Delete run record ${run.id}? Files are kept.`)) return;
    const data = await call('/api/run/delete', { root: project.root, job_id: selected.id, run_id: run.id });
    setProject(data.project); setMessage('Run record deleted');
  }
  async function retryDownload(run: Run) {
    if (!selected) return;
    setBusy(true);
    try {
      const data = await call('/api/run/retry-download', { root: project.root, job_id: selected.id, run_id: run.id });
      setProject(data.project); setMessage(`Downloaded ${data.result?.downloaded?.length || 0} output file(s)`);
    } catch (e: any) {
      setMessage(`Retry download failed: ${e.message}`);
    } finally {
      setBusy(false);
    }
  }
  async function openDir(path?: string) { if (path) await call('/api/open-dir', { path }); }
  async function openCurrentJobApproved() {
    if (!selected || !project?.root) return;
    await call('/api/open-dir', { path: `${project.root}\\jobs\\${selected.id}\\runs` });
  }

  function patch(patchValue: Partial<Job>) { setJobDraft({ ...selected, ...patchValue }); setJobDirty?.(true); }
  return <div className="executeLayout v2">
    <aside className="panel jobList"><div className="panelHead"><b>Jobs</b><input placeholder="Search" value={query} onChange={e => setQuery(e.target.value)} /></div><div className="buttonRow pad"><button onClick={() => createJob('image')}><Plus size={14} /> Image</button><button onClick={() => createJob('video')}><Plus size={14} /> Video</button></div><div className="listScroll">{jobs.map((job: Job) => <button key={job.id} className={`jobItem ${selectedJobId === job.id ? 'active' : ''} ${job.status} ${approvedJobIds.has(job.id) ? 'hasApproved' : ''}`} draggable onDragStart={e => e.dataTransfer.setData('text/plain', job.id)} onDragOver={e => e.preventDefault()} onDrop={e => moveJobByDrag(e.dataTransfer.getData('text/plain'), job.id)} onClick={() => setSelectedJobId(job.id)}><b>{job.title || job.id}</b><span>{job.id}{approvedJobIds.has(job.id) && <em>APPROVED</em>}</span><small>{job.kind} · {job.provider} · {job.status}</small></button>)}</div></aside>
    <section className="panel editorPanel">{selected ? <><div className="panelHead"><b>Edit Job</b><div className="iconActions"><button title="Move up" onClick={() => moveJob('up')}><ArrowUp size={15}/></button><button title="Move down" onClick={() => moveJob('down')}><ArrowDown size={15}/></button><button title="Save" onClick={() => saveJob()}><Save size={15}/></button><button title="Run selected provider" className="primary" onClick={runJob} disabled={busy}><Play size={15}/>{selected.provider === 'dryrun' ? 'Dryrun' : 'Run'}</button><button title="Delete job" onClick={deleteJob}><Trash2 size={15}/></button></div></div>
      <JobEditorCore job={selected} assets={project.assets || []} patch={patch} onPreview={setPreview} />
    </> : <p className="muted pad">No job selected.</p>}</section>
    <aside className="panel runsPanel"><div className="panelHead"><b>Runs</b><div className="iconActions"><button title="Open current job runs/approved folders" onClick={openCurrentJobApproved}><FolderOpen size={15}/></button><button title="Refresh project" onClick={() => call('/api/project/load', { root: project.root }).then((d: any) => setProject(d))}><RefreshCw size={15}/></button></div></div><div className="runList">{selected?.runs?.length ? [...selected.runs].reverse().map(run => <RunCard key={run.id} job={selected} run={run} onPreview={setPreview} onApprove={approveOutput} onPromote={setPromote} onApproveBind={(payload: any) => promoteOutput?.({ ...payload, bind_mode: 'matching_video', approve: true })} onPromoteAsset={(payload: any) => promoteOutput?.({ ...payload, bind_mode: 'none', approve: false })} onOpenDir={openDir} onDelete={deleteRun} onRetryDownload={retryDownload} />) : <p className="muted pad">No runs.</p>}</div></aside>
  </div>;
}

function isActiveStatus(status?: string) {
  return ['submitted', 'running', 'processing', 'queued', 'pending', 'created'].includes(String(status || '').toLowerCase());
}

function isProviderConfirmed(provider?: string) {
  return sessionStorage.getItem(`confirmedLiveProvider:${provider || ''}`) === 'true';
}

function rememberProviderConfirmed(provider?: string) {
  if (provider) sessionStorage.setItem(`confirmedLiveProvider:${provider}`, 'true');
}






