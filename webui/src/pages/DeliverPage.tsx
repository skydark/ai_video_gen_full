import { Copy, FolderOpen, RefreshCw } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { call, fileUrl } from '../lib/api';

type DeliverItem = {
  id: string;
  job_id: string;
  job_title?: string;
  job_kind?: string;
  run_id: string;
  name: string;
  path: string;
  is_image?: boolean;
  is_video?: boolean;
};

export function DeliverPage({ project, setMessage, setPreview, openFolderPicker }: any) {
  const [items, setItems] = useState<DeliverItem[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [targetDir, setTargetDir] = useState(localStorage.getItem('genui.deliverTarget') || '');
  const [busy, setBusy] = useState(false);
  const grouped = useMemo(() => groupByJob(items), [items]);

  useEffect(() => { load(); }, [project?.root]);

  async function load() {
    if (!project?.root) return;
    const data = await call('/api/deliver/list', { root: project.root });
    const nextItems = data.items || [];
    setItems(nextItems);
    setSelected(new Set(nextItems.map((item: DeliverItem) => item.path)));
  }
  function toggle(path: string) {
    const next = new Set(selected);
    next.has(path) ? next.delete(path) : next.add(path);
    setSelected(next);
  }
  function setJob(jobId: string, checked: boolean) {
    const next = new Set(selected);
    items.filter(item => item.job_id === jobId).forEach(item => checked ? next.add(item.path) : next.delete(item.path));
    setSelected(next);
  }
  function setAll(checked: boolean) {
    setSelected(new Set(checked ? items.map(item => item.path) : []));
  }
  function selectKind(kind: 'image' | 'video') {
    setSelected(new Set(items.filter(item => kind === 'image' ? item.is_image : item.is_video).map(item => item.path)));
  }
  function jobSelectedCount(jobId: string) {
    return items.filter(item => item.job_id === jobId && selected.has(item.path)).length;
  }
  async function exportSelected() {
    if (!targetDir) { setMessage('Choose deliver target directory first'); return; }
    setBusy(true);
    try {
      localStorage.setItem('genui.deliverTarget', targetDir);
      const data = await call('/api/deliver/export', { root: project.root, files: [...selected], target_dir: targetDir });
      setMessage(`Delivered ${data.result?.copied?.length || 0} file(s)`);
    } catch (e: any) { setMessage(`Deliver failed: ${e.message}`); }
    finally { setBusy(false); }
  }

  return <div className="deliverLayout panel">
    <div className="panelHead"><b>Deliver Approved Outputs</b><div className="iconActions"><button onClick={load}><RefreshCw size={15}/> Refresh</button><button onClick={() => setAll(true)}>Select All</button><button onClick={() => selectKind('image')}>Images</button><button onClick={() => selectKind('video')}>Videos</button><button onClick={() => setAll(false)}>Clear</button></div></div>
    <div className="deliverToolbar"><input placeholder="Target directory" value={targetDir} onChange={e => setTargetDir(e.target.value)} /><button onClick={() => openFolderPicker((path: string) => setTargetDir(path))}><FolderOpen size={15}/> Choose</button><button className="primary" onClick={exportSelected} disabled={busy || selected.size === 0}><Copy size={15}/> Copy Selected ({selected.size})</button></div>
    <div className="deliverJobChips">{grouped.map(group => <div className="deliverJobChip" key={group.job_id}><button className={jobSelectedCount(group.job_id) ? 'selected' : ''} title={group.job_title} onClick={() => setJob(group.job_id, jobSelectedCount(group.job_id) !== group.items.length)}><b>{group.job_id}</b><span>{jobSelectedCount(group.job_id)}/{group.items.length}</span></button></div>)}</div>
    <div className="deliverGrid flat">{items.map(item => <article className={`deliverCard ${selected.has(item.path) ? 'selected' : ''}`} key={item.path}><div className="deliverMeta"><label><input type="checkbox" checked={selected.has(item.path)} onChange={() => toggle(item.path)} /> {item.name}</label><span>{item.job_id}</span></div><button className="deliverPreview" onClick={() => setPreview({ name: item.name, path: item.path, is_image: item.is_image, is_video: item.is_video })}>{item.is_image ? <img src={fileUrl(item.path)} /> : item.is_video ? <video src={fileUrl(item.path)} muted preload="metadata" /> : <span>FILE</span>}</button><small>{item.run_id}</small></article>)}</div>
    {items.length === 0 && <p className="muted pad">No approved outputs yet.</p>}
  </div>;
}

function groupByJob(items: DeliverItem[]) {
  const map = new Map<string, { job_id: string; job_title?: string; items: DeliverItem[] }>();
  for (const item of items) {
    if (!map.has(item.job_id)) map.set(item.job_id, { job_id: item.job_id, job_title: item.job_title, items: [] });
    map.get(item.job_id)!.items.push(item);
  }
  return [...map.values()];
}
