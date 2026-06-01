export type Ref = {
  asset_id?: string;
  source_path?: string;
  local_copy?: string;
  usage?: string;
  label?: string;
};

export type Output = {
  name: string;
  path: string;
  rel_path?: string;
  is_image?: boolean;
  is_video?: boolean;
  thumbnail?: string | null;
};

export type Run = {
  id: string;
  dir?: string;
  created_at?: string;
  provider?: string;
  status?: string;
  fail_reason?: string;
  credit_count?: number;
  cost?: Record<string, unknown>;
  request?: Record<string, unknown>;
  payload?: Record<string, unknown>;
  response?: Record<string, unknown>;
  outputs?: Output[];
};

export type Job = {
  id: string;
  kind: 'image' | 'video';
  title?: string;
  provider?: string;
  status?: string;
  prompt?: string;
  negative_prompt?: string;
  params?: Record<string, any>;
  refs?: Ref[];
  runs?: Run[];
  _dir?: string;
};

export type Asset = {
  id: string;
  label: string;
  type: string;
  path: string;
  abs_path: string;
  is_image?: boolean;
  brief?: string;
  has_yaml?: boolean;
};

export type ReviewItem = {
  id: string;
  title?: string;
  duration?: number;
  type?: string;
  camera?: string;
  dialogue?: string;
  intent?: string;
  review?: string;
  risk?: string;
  recommendation?: string;
  segment?: string;
  video_task?: string;
  prompt_preview?: string;
  status?: 'pending' | 'approved' | 'needs_change';
  feedback?: string;
  locked?: boolean;
};

export type Review = {
  _path?: string;
  global_feedback?: string;
  previs?: Record<string, any>;
  items?: ReviewItem[];
};

export type Project = {
  root: string;
  task: any;
  jobs: Job[];
  assets: Asset[];
  approved: Asset[];
  review: Review;
};

export type PreviewItem = { name: string; path: string; is_image?: boolean; is_video?: boolean };
