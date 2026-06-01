import { useRef, useState } from 'react';
import { captureVideoSnapshot, fileUrl } from '../lib/api';
import type { PreviewItem } from '../lib/types';

export function PreviewModal({ item, root, onSnapshot, onClose }: { item: PreviewItem; root?: string; onSnapshot?: (project: any) => void; onClose: () => void }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [captureStatus, setCaptureStatus] = useState('');
  async function capture() {
    const video = videoRef.current;
    if (!video || !root) { setCaptureStatus('Video/root not ready'); return; }
    try {
      setCaptureStatus('Capturing on backend…');
      const seconds = video.currentTime || 0;
      const data = await captureVideoSnapshot(root, item.path, seconds, `${item.name} @ ${seconds.toFixed(1)}s`);
      onSnapshot?.(data.project);
      setCaptureStatus('Saved to Assets');
    } catch (err: any) {
      setCaptureStatus(`Capture failed: ${err.message}`);
    }
  }
  return <div className="modalBackdrop" onClick={onClose}>
    <div className="previewModal" onClick={e => e.stopPropagation()}>
      <div className="modalHead"><b>{item.name}</b><div className="iconActions">{item.is_video && <button onClick={capture}>Capture to Assets</button>}<button onClick={onClose}>✕</button></div></div>
      {captureStatus && <div className="captureStatus">{captureStatus}</div>}
      {item.is_video ? <video ref={videoRef} src={fileUrl(item.path)} controls autoPlay /> : item.is_image ? <img src={fileUrl(item.path)} /> : <iframe src={fileUrl(item.path)} />}
    </div>
  </div>;
}

export function YamlModal({ value, setValue, onSave, onClose }: { value: any; setValue: (v: any) => void; onSave: () => void; onClose: () => void }) {
  const name = String(value.path || '').split(/[\\/]/).pop() || 'YAML';
  return <div className="modalBackdrop"><div className="yamlModal"><div className="modalHead"><div className="modalTitle"><b>{name}</b><small title={value.path}>{value.path}</small></div><button className="modalClose" onClick={onClose}>✕</button></div><textarea value={value.content || ''} onChange={e => setValue({ ...value, content: e.target.value })} /><div className="modalFooter"><button onClick={onClose}>Close</button><button className="primary" onClick={onSave}>Save YAML</button></div></div></div>;
}
