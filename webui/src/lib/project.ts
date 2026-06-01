import type { Job, Project, ReviewItem } from './types';

export function segmentKey(item: ReviewItem) {
  return item.video_task || item.segment || 'Unassigned';
}

export function groupShotsBySegment(items: ReviewItem[] = []) {
  const groups: { key: string; items: ReviewItem[]; duration: number; status: string }[] = [];
  const byKey = new Map<string, ReviewItem[]>();
  for (const item of items) {
    const key = segmentKey(item);
    byKey.set(key, [...(byKey.get(key) || []), item]);
  }
  for (const [key, groupItems] of byKey) {
    const duration = groupItems.reduce((sum, item) => sum + Number(item.duration || 0), 0);
    const status = groupItems.some(i => i.status === 'needs_change') ? 'needs_change' : groupItems.every(i => i.status === 'approved') ? 'approved' : 'pending';
    groups.push({ key, items: groupItems, duration, status });
  }
  return groups;
}

export function findStoryboardJob(project: Project, segmentKeyValue: string): Job | undefined {
  const tokens = matchTokens(segmentKeyValue);
  return project.jobs.find(job => {
    const haystack = `${job.id} ${job.title || ''}`.toLowerCase().replace(/_/g, '-');
    return job.kind === 'image' && (haystack.includes('storyboard') || haystack.includes('image-grid')) && tokens.some(token => haystack.includes(token));
  });
}

export function collectSegmentImages(project: Project, segmentKeyValue: string) {
  const job = findStoryboardJob(project, segmentKeyValue);
  const tokens = matchTokens(segmentKeyValue);
  const images = [] as { name: string; path: string }[];
  if (job) {
    for (const run of job.runs || []) {
      for (const output of run.outputs || []) {
        if (output.is_image) images.push({ name: `${job.id}/${output.name}`, path: output.path });
      }
    }
  }
  for (const asset of project.assets || []) {
    const haystack = `${asset.id} ${asset.label} ${asset.path}`.toLowerCase().replace(/_/g, '-');
    if ((asset.type === 'storyboard' || asset.type === 'composition') && asset.is_image && tokens.some(token => haystack.includes(token))) images.push({ name: asset.label, path: asset.abs_path });
  }
  return images.slice(-6).reverse();
}

function matchTokens(value: string) {
  const text = String(value || '').toLowerCase().replace(/_/g, '-');
  const tokens = [...text.matchAll(/(?:task|seg)[- ]?\d+/g)].map(match => match[0].replace(/ /g, '-'));
  const first = text.split(/\s+/)[0];
  if (first) tokens.push(first);
  return [...new Set(tokens.filter(Boolean))];
}

export function defaultParams(kind: string, provider: string) {
  if (kind === 'video') return { duration_limit: 10, aspect_ratio: '16:9', model_version: provider.includes('seedance') ? 'seedance2.0fast_vip' : 'default', generate_audio: false, real_person_mode: false, seed: -1 };
  return { aspect_ratio: '16:9', resolution: '2k', model_version: provider === 'dreamina_image' ? '5.0' : 'gpt-image-2', seed: '' };
}
