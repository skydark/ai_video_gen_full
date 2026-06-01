import { useEffect, useMemo, useState } from 'react';
import { call, clone, REF_USAGES } from './lib/api';
import type { Job, PreviewItem, Project } from './lib/types';
import { PreviewModal, YamlModal } from './components/Modals';
import { ReviewPage } from './pages/ReviewPage';
import { ExecutePage } from './pages/ExecutePage';
import { AssetsPage } from './pages/AssetsPage';
import { DeliverPage } from './pages/DeliverPage';

export function App() {
  const [root, setRoot] = useState(localStorage.getItem('genui.root') || 'E:/VideoProjects/BSDAnime/ai_video_gen_full/projects/bsd_1_7_5/task_project');
  const [recentProjects, setRecentProjects] = useState<Array<{ root: string; name: string }>>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [tab, setTab] = useState(localStorage.getItem('genui.tab') || 'review');
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedShotId, setSelectedShotId] = useState<string | null>(null);
  const [jobDraft, setJobDraft] = useState<Job | null>(null);
  const [jobDirty, setJobDirty] = useState(false);
  const [reviewDraft, setReviewDraft] = useState<any>(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<PreviewItem | null>(null);
  const [yamlEdit, setYamlEdit] = useState<any>(null);
  const [promote, setPromote] = useState<any>(null);
  const [folderPickerOpen, setFolderPickerOpen] = useState(false);
  const [folderPicker, setFolderPicker] = useState<any>(null);
  const selectedJob = useMemo(() => project?.jobs?.find(j => j.id === selectedJobId) || project?.jobs?.[0] || null, [project, selectedJobId]);

  useEffect(() => { localStorage.setItem('genui.tab', tab); }, [tab]);
  useEffect(() => { refreshProjects(); }, []);
  useEffect(() => {
    if (!selectedJob) return;
    if (!jobDirty || jobDraft?.id !== selectedJob.id) {
      setJobDraft(clone(selectedJob));
      setJobDirty(false);
      return;
    }
    setJobDraft({ ...clone(selectedJob), ...jobDraft, runs: selectedJob.runs, status: selectedJob.status, _dir: selectedJob._dir });
  }, [selectedJob?.id, project]);
  useEffect(() => { if (project?.review) setReviewDraft(clone(project.review)); }, [project?.review?._path, project?.review?.items?.length]);

  async function loadProject(nextRoot = root) {
    setBusy(true);
    try { const data = await call('/api/project/load', { root: nextRoot }); setProject(data); setSelectedJobId(data.jobs?.[0]?.id || null); setSelectedShotId(data.review?.items?.[0]?.id || null); localStorage.setItem('genui.root', nextRoot); setMessage(`Loaded ${data.jobs?.length || 0} jobs`); }
    catch (e: any) { setMessage(`Load failed: ${e.message}`); }
    finally { setBusy(false); }
  }
  async function refreshProjects() {
    try { const data = await call('/api/project/recent', {}); setRecentProjects(data.projects || []); }
    catch (e: any) { setMessage(`Project list failed: ${e.message}`); }
  }
  async function browseProject() {
    setFolderPickerOpen(true);
  }
  function openFolderPicker(onSelect: (path: string) => void, initial = root, mode: 'project' | 'folder' = 'folder') {
    setFolderPicker({ onSelect, initial, mode });
  }
  async function readYaml(absPath: string) { const data = await call('/api/asset/read-yaml', { path: absPath }); setYamlEdit(data); }
  async function saveYaml() { await call('/api/asset/save-yaml', yamlEdit); setYamlEdit(null); setMessage('YAML saved'); }
  async function promoteOutput(form: any) {
    const data = await call('/api/output/promote', { root: project?.root, ...form });
    setProject(data.project);
    setPromote(null);
    const bound = data.result?.bound_jobs || [];
    const approved = data.result?.approved ? 'approved, ' : '';
    setMessage(bound.length ? `Output ${approved}promoted and bound to ${bound.join(', ')}` : `Output ${approved}promoted; no matching bind target found`);
  }

  return <div className="appShell">
    <header className="topbar"><div className="brand">AI Video GenUI <span>tsx modular</span></div><select className="projectSelect" value={recentProjects.some(p => p.root === root) ? root : ''} onChange={e => { if (e.target.value) { setRoot(e.target.value); loadProject(e.target.value); } }}><option value="">Recent projects</option>{recentProjects.map(item => <option key={item.root} value={item.root}>{item.name}</option>)}</select><input className="rootInput" value={root} onChange={e => setRoot(e.target.value)} onKeyDown={e => e.key === 'Enter' && loadProject()} /><button onClick={() => loadProject()} disabled={busy}>Load</button><button onClick={refreshProjects} disabled={busy}>Refresh</button><button onClick={browseProject} disabled={busy}>Browse</button><button onClick={() => project && call('/api/open-dir', { path: project.root })} disabled={!project}>Open</button></header>
    {project && <ProjectSummary project={project} />}
    <nav className="tabs">{['review', 'execute', 'assets', 'deliver'].map(id => <button key={id} className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>{id}</button>)}<span className={message.includes('failed') ? 'message error' : 'message'}>{busy ? 'Working… ' : ''}{message}</span></nav>
    {!project ? <div className="empty"><h2>Load a task project</h2><p>Open a directory containing <code>task.yaml</code>.</p><button onClick={() => loadProject()}>Load Project</button></div> : <main className="workspace">
      {tab === 'review' && <ReviewPage project={project} reviewDraft={reviewDraft} setReviewDraft={setReviewDraft} selectedShotId={selectedShotId} setSelectedShotId={setSelectedShotId} setProject={setProject} setMessage={setMessage} setPreview={setPreview} busy={busy} setBusy={setBusy} />}
      {tab === 'execute' && <ExecutePage project={project} setProject={setProject} selectedJobId={selectedJobId} setSelectedJobId={setSelectedJobId} jobDraft={jobDraft} setJobDraft={setJobDraft} setJobDirty={setJobDirty} setMessage={setMessage} setBusy={setBusy} busy={busy} setPreview={setPreview} setPromote={setPromote} promoteOutput={promoteOutput} />}
      {tab === 'assets' && <AssetsPage project={project} setProject={setProject} setMessage={setMessage} setBusy={setBusy} setPreview={setPreview} readYaml={readYaml} />}
      {tab === 'deliver' && <DeliverPage project={project} setMessage={setMessage} setPreview={setPreview} openFolderPicker={openFolderPicker} />}
    </main>}
    {preview && <PreviewModal item={preview} root={project?.root} onSnapshot={(nextProject: Project) => { setProject(nextProject); setMessage('Snapshot saved to Assets'); }} onClose={() => setPreview(null)} />}
    {yamlEdit && <YamlModal value={yamlEdit} setValue={setYamlEdit} onSave={saveYaml} onClose={() => setYamlEdit(null)} />}
    {promote && <PromoteModal promote={promote} jobs={project?.jobs || []} onSubmit={promoteOutput} onClose={() => setPromote(null)} />}
    {folderPickerOpen && <FolderPickerModal mode="project" initial={root} onSelect={async (nextRoot: string) => { setFolderPickerOpen(false); setRoot(nextRoot); await loadProject(nextRoot); await refreshProjects(); }} onClose={() => setFolderPickerOpen(false)} />}
    {folderPicker && <FolderPickerModal mode={folderPicker.mode} initial={folderPicker.initial} onSelect={(path: string) => { folderPicker.onSelect(path); setFolderPicker(null); }} onClose={() => setFolderPicker(null)} />}
  </div>;
}

function FolderPickerModal({ initial, onSelect, onClose, mode = 'project' }: { initial: string; onSelect: (root: string) => void; onClose: () => void; mode?: 'project' | 'folder' }) {
  const [path, setPath] = useState(initial || '');
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');
  useEffect(() => { list(path); }, []);
  async function list(nextPath = path) {
    try { const next = await call('/api/fs/list-dirs', { path: nextPath }); setData(next); setPath(next.path); setError(''); }
    catch (e: any) { setError(e.message); }
  }
  function choose(dir: any) {
    if (mode === 'folder') list(dir.path);
    else if (dir.has_task_project) onSelect(`${dir.path}\\task_project`);
    else if (dir.has_task) onSelect(dir.path);
    else list(dir.path);
  }
  return <div className="modalBackdrop"><div className="yamlModal folderPicker"><div className="modalHead"><b>{mode === 'folder' ? 'Select Folder' : 'Select Project Folder'}</b><button onClick={onClose}>✕</button></div><div className="folderPath"><input value={path} onChange={e => setPath(e.target.value)} onKeyDown={e => e.key === 'Enter' && list()} /><button onClick={() => list()}>Go</button></div>{error && <p className="errorText pad">{error}</p>}<div className="folderList">{data?.parent && <button onClick={() => list(data.parent)}>..</button>}{(mode === 'folder' || data?.has_task) && <button className="primary" onClick={() => onSelect(data.path)}>Use this folder</button>}{(data?.dirs || []).map((dir: any) => <button key={dir.path} onClick={() => choose(dir)}><b>{dir.name}</b><span>{dir.has_task ? 'task.yaml' : dir.has_task_project ? 'task_project' : 'folder'}</span></button>)}</div><div className="modalFooter"><button onClick={onClose}>Close</button></div></div></div>;
}

function ProjectSummary({ project }: { project: Project }) {
  const stats = { shots: project.review?.items?.length || 0, jobs: project.jobs.length, runs: project.jobs.reduce((sum, job) => sum + (job.runs?.length || 0), 0), assets: project.assets.length, approved: project.approved.length };
  return <section className="summary"><div><b>{project.task?.project?.title || project.task?.project?.id || 'Untitled'}</b><span>{project.root}</span></div>{Object.entries(stats).map(([k, v]) => <div className="stat" key={k}><b>{v}</b><span>{k}</span></div>)}</section>;
}

function PromoteModal({ promote, jobs, onSubmit, onClose }: any) {
  const [form, setForm] = useState({ job_id: promote.job.id, run_id: promote.run.id, output_name: promote.output.name, asset_type: 'storyboard', usage: 'composition', label: promote.output.name, bind_mode: 'matching_video', target_job_ids: [] as string[], approve: false });
  const matching = findMatchingVideoJobs(jobs, promote.job);
  return <div className="modalBackdrop"><div className="yamlModal small"><div className="modalHead"><b>Use output as reference</b><button onClick={onClose}>✕</button></div><label>Label<input value={form.label} onChange={e => setForm({ ...form, label: e.target.value })} /></label><label>Asset type<select value={form.asset_type} onChange={e => setForm({ ...form, asset_type: e.target.value })}><option>storyboard</option><option>keyframe</option><option>scene</option><option>character</option><option>composition</option><option>misc</option></select></label><label>Usage<select value={form.usage} onChange={e => setForm({ ...form, usage: e.target.value })}>{REF_USAGES.map(item => <option key={item}>{item}</option>)}</select></label><label>Bind mode<select value={form.bind_mode} onChange={e => setForm({ ...form, bind_mode: e.target.value })}><option value="matching_video">Matching video job{matching.length ? ` (${matching.map((j: Job) => j.id).join(', ')})` : ''}</option><option value="next">Next job</option><option value="later_video">Later video jobs</option><option value="current">Current job</option><option value="selected">Selected jobs</option><option value="none">None</option></select></label>{form.bind_mode === 'selected' && <select multiple value={form.target_job_ids} onChange={e => setForm({ ...form, target_job_ids: [...e.target.selectedOptions].map(o => o.value) })}>{jobs.map((job: Job) => <option key={job.id} value={job.id}>{job.id}</option>)}</select>}<label className="check"><input type="checkbox" checked={form.approve} onChange={e => setForm({ ...form, approve: e.target.checked })} /> also approve</label><button className="primary" onClick={() => onSubmit(form)}>Promote</button></div></div>;
}

function findMatchingVideoJobs(jobs: Job[], source: Job) {
  const tokens = matchTokens(`${source.id} ${source.title || ''}`);
  return jobs.filter(job => job.kind === 'video' && job.id !== source.id && tokens.some(token => `${job.id} ${job.title || ''}`.toLowerCase().includes(token)));
}

function matchTokens(text: string) {
  const tokens = [...text.matchAll(/(?:task|seg)[-_ ]?\d+/gi)].map(match => match[0].toLowerCase().replace(/[_ ]/g, '-'));
  const id = text.split(' ')[0].toLowerCase();
  for (const suffix of ['_storyboard_grid', '-storyboard-grid', '_image_grid', '-image-grid', '_storyboard', '-storyboard', '_image', '-image']) {
    if (id.endsWith(suffix)) tokens.push(id.slice(0, -suffix.length).replace(/_/g, '-'));
  }
  return [...new Set(tokens)];
}

