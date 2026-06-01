import { X } from 'lucide-react';
import { fileUrl } from '../lib/api';
import type { Asset, Ref } from '../lib/types';

export function RefCards({ refs, assets, setRefs, onPreview }: { refs: Ref[]; assets: Asset[]; setRefs: (refs: Ref[]) => void; onPreview: (item: any) => void }) {
  const move = (from: number, to: number) => {
    if (to < 0 || to >= refs.length || from === to) return;
    const next = [...refs];
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    setRefs(next);
  };
  const remove = (index: number) => setRefs(refs.filter((_, i) => i !== index));
  return <div className="refsBlock"><div className="panelSubhead">References</div><div className="refCards simple">{refs.map((ref, index) => {
    const asset = assets.find(a => a.path === ref.source_path || a.id === ref.asset_id);
    const imagePath = asset?.abs_path;
    return <div className="refCardSimple" key={`${ref.asset_id}-${ref.source_path}-${index}`} draggable onDragStart={e => e.dataTransfer.setData('text/plain', String(index))} onDragOver={e => e.preventDefault()} onDrop={e => move(Number(e.dataTransfer.getData('text/plain')), index)} title="Drag to reorder">
      <div className="refTitle"><b>{ref.label || asset?.label || ref.asset_id || 'Reference'}</b><button onClick={() => remove(index)}><X size={14}/></button></div>
      <button className="refImage" onClick={() => imagePath && onPreview({ name: ref.label || asset?.label || 'Reference', path: imagePath, is_image: true })}>{imagePath ? <img src={fileUrl(imagePath)} /> : <span>No image</span>}</button>
    </div>;
  })}</div>{refs.length === 0 && <p className="muted">No references. Add from Project Assets.</p>}</div>;
}

export function ProjectAssetPicker({ assets, onAdd, onPreview }: { assets: Asset[]; onAdd: (asset: Asset) => void; onPreview: (item: any) => void }) {
  const imageAssets = assets.filter(a => a.is_image);
  return <aside className="panel projectAssetsPanel"><div className="panelHead"><b>Project Assets</b><span>{imageAssets.length}</span></div><div className="assetMiniGrid big">{imageAssets.map(asset => <div key={asset.path} className="assetMiniCard"><button onClick={() => onPreview({ name: asset.label, path: asset.abs_path, is_image: true })}><img src={fileUrl(asset.abs_path)} /></button><b>{asset.label}</b><small>{asset.type}</small><button onClick={() => onAdd(asset)}>Add Ref</button></div>)}</div></aside>;
}
