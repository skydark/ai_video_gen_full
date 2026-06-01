export const API = 'http://127.0.0.1:8787';

export const PROVIDERS: Record<string, string[]> = {
  image: ['dryrun', 'runninghub_gpt_image', 'dreamina_image'],
  video: ['dryrun', 'runninghub_seedance', 'dreamina_video'],
};

export const MODELS: Record<string, string[]> = {
  dryrun: ['default'],
  runninghub_gpt_image: ['gpt-image-2'],
  runninghub_seedance: ['seedance2.0fast_vip', 'seedance2.0_vip', 'seedance2.0fast', 'seedance2.0'],
  dreamina_image: ['5.0', '4.6', '4.5', '4.1', '4.0'],
  dreamina_video: ['seedance2.0fast_vip', 'seedance2.0_vip', 'seedance2.0fast', 'seedance2.0'],
};

export const REF_USAGES = ['identity', 'scene', 'style', 'composition', 'keyframe', 'misc'];

export function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value ?? null));
}

export function fileUrl(path?: string) {
  return `${API}/api/file?path=${encodeURIComponent(path || '')}`;
}

export async function call(path: string, body?: unknown): Promise<any> {
  const res = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
  const text = await res.text();
  let data: any = {};
  try { data = text ? JSON.parse(text) : {}; } catch { data = { detail: text }; }
  if (!res.ok) throw new Error(data?.detail || data?.error || res.statusText);
  return data;
}

export async function uploadAsset(form: FormData): Promise<any> {
  const res = await fetch(`${API}/api/asset/upload-form`, { method: 'POST', body: form });
  const data = await res.json();
  if (!res.ok || data.error) throw new Error(data.detail || data.error || 'Upload failed');
  return data;
}

export function isLiveProvider(provider?: string) {
  return provider && provider !== 'dryrun';
}

export async function uploadSnapshot(form: FormData): Promise<any> {
  const res = await fetch(`${API}/api/asset/upload-snapshot`, { method: 'POST', body: form });
  const data = await res.json();
  if (!res.ok || data.error) throw new Error(data.detail || data.error || 'Snapshot upload failed');
  return data;
}

export async function captureVideoSnapshot(root: string, path: string, seconds: number, label?: string): Promise<any> {
  return call('/api/video/capture-snapshot', { root, path, seconds, label });
}
