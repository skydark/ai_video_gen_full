import { useEffect, useState } from 'react';
import { FolderPlus, Upload } from 'lucide-react';
import { call, fileUrl, uploadAsset } from '../lib/api';
import type { Asset, Project } from '../lib/types';

export function AssetsPage({ project, setProject, setMessage, setBusy, setPreview, readYaml }: any) {
  const [publicAssets, setPublicAssets] = useState<Asset[]>([]);
  const [path, setPath] = useState('');
  const [type, setType] = useState('characters');
  const [filter, setFilter] = useState('');
  const [upload, setUpload] = useState<any>({ name: '', asset_type: 'character', brief: '', detail: '', tags: '', file: null });
  useEffect(() => { loadPublicAssets(); }, []);

  async function loadPublicAssets() {
    try { setPublicAssets(await call('/api/assets/public', {})); } catch (e: any) { setMessage(`Global asset scan failed: ${e.message}`); }
  }
  async function copyAsset(asset: Asset) {
    setBusy(true); try { const data = await call('/api/asset/copy-to-project', { root: project.root, path: asset.abs_path, type: asset.type, label: asset.label }); setProject(data.project); setMessage('Asset copied'); } catch (e: any) { setMessage(e.message); } finally { setBusy(false); }
  }
  async function addPath() {
    if (!path.trim()) return;
    setBusy(true); try { const data = await call('/api/asset/add', { root: project.root, path: path.trim(), type }); setProject(data.project); setPath(''); setMessage('Asset added'); } catch (e: any) { setMessage(e.message); } finally { setBusy(false); }
  }
  async function remove(asset: Asset) {
    if (!confirm(`Delete ${asset.label} from project?`)) return;
    const data = await call('/api/asset/delete', { root: project.root, path: asset.path }); setProject(data.project);
  }
  async function doUpload() {
    const form = new FormData();
    Object.entries({ root: project.root, ...upload }).forEach(([key, value]: any) => value !== null && form.append(key, value));
    setBusy(true); try { const data = await uploadAsset(form); setProject(data.project); setMessage('Uploaded'); } catch (e: any) { setMessage(e.message); } finally { setBusy(false); }
  }

  const assets = (project.assets || []).filter((asset: Asset) => `${asset.label} ${asset.type} ${asset.path}`.toLowerCase().includes(filter.toLowerCase()));
  return <div className="assetsLayout">
    <section className="panel"><div className="panelHead"><b>Project Assets</b><input placeholder="Filter" value={filter} onChange={e => setFilter(e.target.value)} /></div><div className="assetGrid">{assets.map((asset: Asset) => <AssetCard key={asset.path} asset={asset} setPreview={setPreview} readYaml={readYaml} remove={remove} />)}</div></section>
    <aside className="panel addAssetPanel"><div className="panelHead"><b>Add Asset</b></div><div className="pad"><h4>Copy local file into project</h4><label>Image path<input value={path} onChange={e => setPath(e.target.value)} placeholder="E:/.../asset.png" /></label><label>Destination type<select value={type} onChange={e => setType(e.target.value)}><option>characters</option><option>scenes</option><option>props</option><option>misc</option></select></label><button className="primary" onClick={addPath}><FolderPlus size={15}/> Copy to Project</button><hr/><h4>Upload new asset</h4><label>Name<input value={upload.name} onChange={e => setUpload({ ...upload, name: e.target.value })} /></label><label>Asset Type<select value={upload.asset_type} onChange={e => setUpload({ ...upload, asset_type: e.target.value })}><option>character</option><option>scene</option><option>prop</option><option>misc</option></select></label><label>Brief<textarea value={upload.brief} onChange={e => setUpload({ ...upload, brief: e.target.value })} /></label><label>Detail<textarea value={upload.detail} onChange={e => setUpload({ ...upload, detail: e.target.value })} /></label><label>Tags<input value={upload.tags} onChange={e => setUpload({ ...upload, tags: e.target.value })} /></label><input type="file" onChange={e => setUpload({ ...upload, file: e.target.files?.[0] })} /><button onClick={doUpload}><Upload size={15}/> Upload</button></div></aside>
    <aside className="panel"><div className="panelHead"><b>Global Assets</b><button onClick={loadPublicAssets}>Refresh</button></div><div className="assetGrid compact">{publicAssets.map(asset => <div className="assetCard" key={asset.abs_path}>{asset.is_image && <img src={fileUrl(asset.abs_path)} onClick={() => setPreview({ name: asset.label, path: asset.abs_path, is_image: true })} />}<b>{asset.label}</b><span>{asset.type}{asset.has_yaml ? ' · yaml' : ''}</span><button onClick={() => copyAsset(asset)}>Copy</button></div>)}</div></aside>
  </div>;
}

function AssetCard({ asset, setPreview, readYaml, remove }: any) {
  return <div className="assetCard">{asset.is_image ? <img src={fileUrl(asset.abs_path)} onClick={() => setPreview({ name: asset.label, path: asset.abs_path, is_image: true })} /> : <div className="filePreview">FILE</div>}<b>{asset.label}</b><span>{asset.type}</span><small>{asset.path}</small><div className="iconActions"><button onClick={() => readYaml(asset.abs_path)}>YAML</button><button onClick={() => remove(asset)}>Delete</button></div></div>;
}
