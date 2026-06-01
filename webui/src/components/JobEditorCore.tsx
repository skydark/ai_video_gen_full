import { MODELS, PROVIDERS } from '../lib/api';
import { defaultParams } from '../lib/project';
import type { Asset, Job, Ref } from '../lib/types';
import { ProjectAssetPicker, RefCards } from './Refs';

export function JobEditorCore({ job, assets, patch, onPreview, allowKindChange = true, compact = false }: {
  job: Job;
  assets: Asset[];
  patch: (patch: Partial<Job>) => void;
  onPreview: (item: any) => void;
  allowKindChange?: boolean;
  compact?: boolean;
}) {
  const setRefs = (refs: Ref[]) => patch({ refs });
  const addAssetRef = (asset: Asset) => setRefs([...(job.refs || []), { asset_id: asset.id, source_path: asset.path, usage: asset.type === 'scene' ? 'scene' : asset.type === 'storyboard' ? 'composition' : 'identity', label: asset.label }]);
  const changeProvider = (provider: string) => patch({ provider, params: { ...defaultParams(job.kind || 'image', provider), ...(job.params || {}), model_version: MODELS[provider]?.[0] } });
  const changeKind = (kind: 'image' | 'video') => patch({ kind, provider: 'dryrun', params: defaultParams(kind, 'dryrun') });
  const provider = job.provider || 'dryrun';
  const modelValue = job.params?.model_version || MODELS[provider]?.[0] || 'default';

  return <div className={`jobEditorCore ${compact ? 'compact' : ''}`}>
    <div className="formGrid"><label>Title<input value={job.title || ''} onChange={e => patch({ title: e.target.value })} /></label>{allowKindChange && <label>Kind<select value={job.kind} onChange={e => changeKind(e.target.value as any)}><option>image</option><option>video</option></select></label>}<label>Provider<select value={provider} onChange={e => changeProvider(e.target.value)}>{(PROVIDERS[job.kind] || PROVIDERS.image).map(item => <option key={item}>{item}</option>)}</select></label><label>Model<select value={modelValue} onChange={e => patch({ params: { ...(job.params || {}), model_version: e.target.value } })}>{(MODELS[provider] || ['default']).map(item => <option key={item}>{item}</option>)}</select></label></div>
    <ParamsEditor job={job} patch={patch} />
    <label className="fieldLabel">Prompt</label><textarea className="promptBox" value={job.prompt || ''} onChange={e => patch({ prompt: e.target.value })} />
    <RefCards refs={job.refs || []} assets={assets || []} setRefs={setRefs} onPreview={onPreview} />
    <div className="executeBottomPanels"><ProjectAssetPicker assets={assets || []} onAdd={addAssetRef} onPreview={onPreview} /></div>
  </div>;
}

function ParamsEditor({ job, patch }: { job: Job; patch: (patch: Partial<Job>) => void }) {
  const params = job.params || {};
  const setParam = (key: string, value: any) => patch({ params: { ...params, [key]: value } });
  if (job.kind === 'video') return <div className="formGrid"><label>Aspect<select value={params.aspect_ratio || '16:9'} onChange={e => setParam('aspect_ratio', e.target.value)}><option>16:9</option><option>9:16</option><option>1:1</option></select></label><label>Duration<input type="number" min="4" max="15" value={params.duration_limit || 10} onChange={e => setParam('duration_limit', Number(e.target.value))} /></label><label>Audio<select value={String(params.generate_audio ?? false)} onChange={e => setParam('generate_audio', e.target.value === 'true')}><option value="false">false</option><option value="true">true</option></select></label><label>Seed<input value={params.seed ?? -1} onChange={e => setParam('seed', e.target.value)} /></label></div>;
  return <div className="formGrid"><label>Aspect<select value={params.aspect_ratio || '16:9'} onChange={e => setParam('aspect_ratio', e.target.value)}><option>16:9</option><option>9:16</option><option>1:1</option><option>4:3</option><option>3:4</option></select></label><label>Resolution<select value={params.resolution || '2k'} onChange={e => setParam('resolution', e.target.value)}><option>1k</option><option>2k</option><option>4k</option></select></label><label>Seed<input value={params.seed || ''} onChange={e => setParam('seed', e.target.value)} /></label></div>;
}

