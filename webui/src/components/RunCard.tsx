import { Archive, Download, FolderOpen, Info, Link, Star, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { fileUrl } from '../lib/api';
import type { Job, Output, Run } from '../lib/types';

export function RunCard({ job, run, onPreview, onApprove, onPromote, onApproveBind, onPromoteAsset, onOpenDir, onDelete, onRetryDownload }: {
  job: Job; run: Run; onPreview: (item: any) => void; onApprove: (job: Job, run: Run, output: Output) => void; onPromote: (payload: any) => void; onApproveBind?: (payload: any) => void; onPromoteAsset?: (payload: any) => void; onOpenDir: (path?: string) => void; onDelete: (run: Run) => void; onRetryDownload?: (run: Run) => void;
}) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const outputs = run.outputs || [];
  const primary = outputs.find(o => o.is_video) || outputs.find(o => o.is_image) || outputs[0];
  const status = String(run.status || 'unknown').toLowerCase();
  const failed = ['failed', 'failure', 'error'].includes(status);
  const successWithoutOutput = !primary && ['success', 'succeeded'].includes(status);
  const approved = !!(primary as any)?.approved;
  const promotePayload = primary ? { job_id: job.id, run_id: run.id, output_name: primary.name, asset_type: job.kind === 'image' ? 'storyboard' : 'keyframe', usage: job.kind === 'image' ? 'composition' : 'keyframe', label: primary.name, target_job_ids: [] } : null;
  return <div className={`runCard compactRun ${status} ${approved ? 'approvedRun' : ''}`}>
    <div className="runHead compact"><div className="runTitle"><b title={run.id}>{run.id}</b><span className={`badge ${status}`}>{status}</span>{approved && <span className="badge approved">APPROVED</span>}</div><div className="iconActions"><button title="Run details" onClick={() => setDetailsOpen(true)}><Info size={15}/></button><button title="Open run directory" onClick={() => onOpenDir(run.dir)}><FolderOpen size={15}/></button><button title="Delete run record" onClick={() => onDelete(run)}><Trash2 size={15}/></button></div></div>
    {primary ? <button className="runHero" onClick={() => onPreview({ name: primary.name, path: primary.path, is_image: primary.is_image, is_video: primary.is_video })}>{primary.is_video ? <video src={fileUrl(primary.path)} muted preload="metadata" /> : primary.is_image ? <img src={fileUrl(primary.path)} /> : <span>FILE</span>}{primary.is_video && <em>▶</em>}</button> : successWithoutOutput ? <div className="missingOutput"><b>No downloaded output</b><span>Provider reported success, but no file exists locally.</span><button onClick={() => onRetryDownload?.(run)}><Download size={15}/> Retry download</button></div> : failed ? null : <div className="runHero emptyHero">Processing…</div>}
    {run.fail_reason && <p className="errorText compactText">{run.fail_reason}</p>}
    <div className="runStatusLine"><span>{run.provider || job.provider}</span><span>{run.created_at || '-'}</span><span>credits: {run.credit_count ?? (run.cost as any)?.actual ?? '-'}</span></div>
    {primary && <div className="iconActions runActions threeRunActions">
      <button title={approved ? 'Cancel approve / remove from approved outputs' : 'Approve / copy to approved outputs'} className={approved ? 'approvedBtn' : ''} onClick={() => onApprove(job, run, primary)}><Star size={15}/></button>
      <button title="Add to Project Assets only" onClick={() => promotePayload && (onPromoteAsset ? onPromoteAsset(promotePayload) : onPromote({ job, run, output: primary }))}><Archive size={15}/></button>
      <button title="Approve and bind to matching video job" className="primaryIcon" onClick={() => promotePayload && (onApproveBind ? onApproveBind(promotePayload) : onPromote({ job, run, output: primary }))}><Link size={15}/></button>
    </div>}
    {detailsOpen && <RunDetailsModal job={job} run={run} outputs={outputs} onClose={() => setDetailsOpen(false)} />}
  </div>;
}

function RunDetailsModal({ job, run, outputs, onClose }: { job: Job; run: Run; outputs: Output[]; onClose: () => void }) {
  const summary = { id: run.id, job_id: job.id, provider: run.provider || job.provider, status: run.status, created_at: run.created_at, dir: run.dir, cost: run.cost, credit_count: run.credit_count, fail_reason: run.fail_reason };
  return <div className="modalBackdrop"><div className="yamlModal runDetailsModal"><div className="modalHead"><b>Run Details · {run.id}</b><button onClick={onClose}>✕</button></div><div className="detailsGrid">
    <DetailsSection title="Summary" data={summary} />
    <DetailsSection title="Outputs" data={outputs.map(o => ({ name: o.name, rel_path: o.rel_path, path: o.path, approved: (o as any).approved, approved_path: (o as any).approved_path, is_image: o.is_image, is_video: o.is_video, thumbnail: o.thumbnail }))} />
    <DetailsSection title="Request" data={run.request || {}} />
    <DetailsSection title="Payload" data={run.payload || {}} />
    <DetailsSection title="Response" data={run.response || {}} />
  </div></div></div>;
}

function DetailsSection({ title, data }: { title: string; data: unknown }) {
  return <section className="detailsSection"><h3>{title}</h3><pre>{JSON.stringify(data, null, 2)}</pre></section>;
}
