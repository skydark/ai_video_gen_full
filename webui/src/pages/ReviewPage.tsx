import { ImagePlus, Play, Save, Send } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { call, fileUrl } from '../lib/api';
import { collectSegmentImages, defaultParams, findStoryboardJob, groupShotsBySegment } from '../lib/project';
import type { Job, Project, Review, ReviewItem } from '../lib/types';
import { JobEditorCore } from '../components/JobEditorCore';

export function ReviewPage({ project, reviewDraft, setReviewDraft, selectedShotId, setSelectedShotId, setProject, setMessage, setPreview, busy, setBusy }: any) {
  const [selectedSegment, setSelectedSegment] = useState('');
  const [storyboard, setStoryboard] = useState<any>(null);
  const items = reviewDraft?.items || [];
  const groups = useMemo(() => groupShotsBySegment(items), [items]);
  const activeGroup = groups.find(g => g.key === selectedSegment) || groups[0];
  const selected = items.find((item: ReviewItem) => item.id === selectedShotId) || activeGroup?.items?.[0];
  const images = activeGroup ? collectSegmentImages(project, activeGroup.key) : [];
  const storyboardJob = activeGroup ? findStoryboardJob(project, activeGroup.key) : undefined;
  const storyboardActive = !!storyboardJob && (isActiveStatus(storyboardJob.status) || (storyboardJob.runs || []).some((run: any) => isActiveStatus(run.status)));

  useEffect(() => {
    if (!storyboardActive || !project?.root) return;
    const timer = window.setInterval(async () => {
      try {
        const data = await call('/api/project/load', { root: project.root });
        setProject(data);
      } catch (err: any) {
        setMessage(`Storyboard refresh failed: ${err.message}`);
      }
    }, 5000);
    return () => window.clearInterval(timer);
  }, [storyboardActive, project?.root, setProject, setMessage]);

  function patchReview(patch: Partial<Review>) { setReviewDraft({ ...reviewDraft, ...patch }); }
  function patchShot(id: string, patch: Partial<ReviewItem>) { setReviewDraft({ ...reviewDraft, items: items.map((item: ReviewItem) => item.id === id ? { ...item, ...patch } : item) }); }

  async function saveReview() {
    setBusy(true);
    try {
      const data = await call('/api/review/save', { root: project.root, review: reviewDraft });
      setProject(data.project); setReviewDraft(data.review); setMessage('Review saved');
    } catch (err: any) { setMessage(`Review save failed: ${err.message}`); }
    finally { setBusy(false); }
  }
  async function exportBrief() {
    setBusy(true);
    try {
      await call('/api/review/save', { root: project.root, review: reviewDraft });
      const data = await call('/api/review/export-brief', { root: project.root });
      setProject(data.project); setMessage(`Brief exported: ${data.result.path}`);
    } catch (err: any) { setMessage(`Export failed: ${err.message}`); }
    finally { setBusy(false); }
  }

  return <div className="reviewLayout segmentReview">
    <aside className="panel segmentList">
      <div className="panelHead"><b>Segments</b><span>{groups.length}</span></div>
      <textarea className="globalFeedback" placeholder="Global feedback" value={reviewDraft?.global_feedback || ''} onChange={e => patchReview({ global_feedback: e.target.value })} />
      <div className="listScroll">{groups.map(group => <button key={group.key} className={`segmentItem ${group.status} ${activeGroup?.key === group.key ? 'active' : ''}`} onClick={() => { setSelectedSegment(group.key); setSelectedShotId(group.items[0]?.id); }}>
        <b>{group.key}</b><span>{group.items.length} shots · {group.duration.toFixed(1)}s</span><small>{group.status}</small>
      </button>)}</div>
      <div className="stackActions"><button onClick={saveReview} disabled={busy}><Save size={15} /> Save</button><button className="primary" onClick={exportBrief} disabled={busy}><Send size={15} /> Export Brief</button></div>
    </aside>

    <section className="panel detailPanel">
      <div className="panelHead"><b>{activeGroup?.key || 'No segment'}</b><div className="iconActions"><span className={`badge ${storyboardJob?.status || 'pending'}`}>{storyboardJob ? storyboardJob.status : 'no storyboard'}</span><button onClick={() => setStoryboard({ group: activeGroup, job: storyboardJob })} disabled={!activeGroup}><ImagePlus size={15} /> {storyboardJob ? 'Storyboard Job' : 'Generate Storyboard'}</button></div></div>
      <div className="segmentOverview">
        {(activeGroup?.items || []).map((item: ReviewItem) => <button key={item.id} className={`shotPill ${item.status || 'pending'} ${selected?.id === item.id ? 'active' : ''}`} onClick={() => setSelectedShotId(item.id)}>{item.id}<span>{item.duration}s</span></button>)}
      </div>
      {images.length > 0 ? <div className="storyboardFocus"><button className="storyboardMain" onClick={() => setPreview({ name: images[0].name, path: images[0].path, is_image: true })}><img src={fileUrl(images[0].path)} /></button>{images.length > 1 && <div className="storyboardStrip">{images.slice(1).map(image => <button key={image.path} onClick={() => setPreview({ name: image.name, path: image.path, is_image: true })}><img src={fileUrl(image.path)} /><span>{image.name}</span></button>)}</div>}</div> : <p className="muted pad">No storyboard image yet.</p>}
      <div className="segmentContextBottom"><div className="panelSubhead">Segment Prompt Context</div>{(activeGroup?.items || []).map((item: ReviewItem) => <div className="textBlock" key={item.id}><b>{item.id} {item.title}</b><p>{item.prompt_preview || item.intent}</p></div>)}</div>
    </section>

    <aside className="panel segmentNotes"><div className="panelHead"><b>Task Design</b></div>{selected ? <ShotDetail item={selected} patch={patchShot} compact /> : <p className="muted pad">No shot selected.</p>}</aside>
    {storyboard && <StoryboardModal project={project} group={storyboard.group} existingJob={storyboard.job} setPreview={setPreview} onClose={() => setStoryboard(null)} onDone={(data: any, msg = 'Storyboard updated') => { setProject(data.project); setMessage(msg); }} />}
  </div>;
}

function isActiveStatus(status?: string) {
  return ['submitted', 'running', 'processing', 'queued', 'pending', 'created'].includes(String(status || '').toLowerCase());
}

function ShotDetail({ item, patch, compact = false }: { item: ReviewItem; patch: (id: string, patch: Partial<ReviewItem>) => void; compact?: boolean }) {
  return <div className={`shotDetail ${compact ? 'compactShotDetail' : ''}`}>
    <div className="statusRow">{['pending', 'approved', 'needs_change'].map(status => <button key={status} className={item.status === status ? 'active' : ''} onClick={() => patch(item.id, { status: status as any })}>{status}</button>)}<label><input type="checkbox" checked={!!item.locked} onChange={e => patch(item.id, { locked: e.target.checked })} /> locked</label></div>
    <div className="infoGrid"><b>Type</b><span>{item.type}</span><b>Camera</b><span>{item.camera}</span><b>Dialogue</b><span>{item.dialogue}</span><b>Recommendation</b><span>{item.recommendation}</span><b>Risk</b><span>{item.risk}</span></div>
    <div className="textBlock"><b>Intent</b><p>{item.intent}</p></div>
    <div className="textBlock"><b>Review Focus</b><p>{item.review}</p></div>
    <div className="textBlock"><b>Prompt Preview</b><p>{item.prompt_preview}</p></div>
    <label className="fieldLabel">Shot Feedback</label><textarea className="feedbackBox" value={item.feedback || ''} onChange={e => patch(item.id, { feedback: e.target.value })} />
  </div>;
}

function StoryboardModal({ project, group, existingJob, setPreview, onClose, onDone }: any) {
  const prompt = `Goal: Generate a ${Math.min(9, Math.max(4, group.items.length))}-panel grayscale storyboard contact sheet for this video segment. Keep panel order left-to-right, top-to-bottom.\n\nSegment: ${group.key}\n\n${group.items.map((item: ReviewItem) => `${item.id}: ${item.title}. ${item.camera}. ${item.prompt_preview || item.intent}`).join('\n')}\n\nAvoid: captions, subtitles, swapped character positions, inconsistent camera side.`;
  const [job, setJob] = useState<Job>(existingJob || { id: '', kind: 'image', title: `${group.key} - storyboard grid`, provider: 'runninghub_gpt_image', status: 'ready', prompt, params: { ...defaultParams('image', 'runninghub_gpt_image'), model_version: 'gpt-image-2' }, refs: project.assets.filter((a: any) => a.is_image).slice(0, 6).map((a: any) => ({ asset_id: a.id, source_path: a.path, usage: a.type === 'scene' ? 'scene' : 'identity', label: a.label })) });
  const [submitting, setSubmitting] = useState(false);
  const patch = (value: Partial<Job>) => setJob({ ...job, ...value });
  async function save() {
    const base = existingJob ? { job } : await call('/api/job/create', { root: project.root, kind: 'image', title: job.title });
    const saved = await call('/api/job/save', { root: project.root, job: { ...base.job, ...job, id: base.job.id || job.id } });
    onDone(saved, 'Storyboard job saved');
    return saved.job;
  }
  async function run() {
    setSubmitting(true);
    try {
      const savedJob = await save();
      const data = await call('/api/job/run', { root: project.root, job_id: savedJob.id, confirm_live: true, timeout: 420, interval: 8 });
      onDone(data, 'Storyboard run submitted; refreshing in Review');
      onClose();
    } catch (err: any) {
      onDone({ project }, `Storyboard run failed: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  }
  return <div className="modalBackdrop"><div className="yamlModal storyboardJobModal"><div className="modalHead"><b>Storyboard Image Job</b><button onClick={onClose} disabled={submitting}>✕</button></div>{submitting && <div className="captureStatus">Submitting storyboard run…</div>}<JobEditorCore job={job} assets={project.assets || []} patch={patch} onPreview={setPreview} allowKindChange={false} compact /><div className="modalFooter"><button onClick={save} disabled={submitting}>Save Job</button><button className="primary" onClick={run} disabled={submitting}><Play size={15}/> {submitting ? 'Submitting…' : 'Run'}</button><button onClick={onClose} disabled={submitting}>Close</button></div></div></div>;
}
