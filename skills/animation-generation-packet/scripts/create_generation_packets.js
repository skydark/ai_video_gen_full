#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

function usage() {
  console.error('Usage: node create_generation_packets.js --shot-plan <shot_plan_dir> --assets <reference_assets_dir> --out <out_dir>');
  process.exit(2);
}
const args = process.argv.slice(2);
const opts = {};
for (let i = 0; i < args.length; i += 2) {
  if (!args[i] || !args[i].startsWith('--')) usage();
  opts[args[i].slice(2)] = args[i + 1];
}
opts['shot-plan'] = opts['shot-plan'] || opts.previs;
if (!opts['shot-plan'] || !opts.assets || !opts.out) usage();

const shotPlanDir = path.resolve(opts['shot-plan']);
const assets = path.resolve(opts.assets);
const out = path.resolve(opts.out);
const plan = JSON.parse(fs.readFileSync(path.join(shotPlanDir, 'shot_plan.json'), 'utf8'));
fs.mkdirSync(out, { recursive: true });

function safe(s) { const cleaned = String(s).replace(/[^a-zA-Z0-9_-]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 80); return cleaned || 'task'; }
function listFiles(dir) {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true }).filter(d => d.isFile()).map(d => path.join(dir, d.name));
}
const assetFiles = listFiles(assets);
const referenceMap = buildReferenceMap(plan, assetFiles);
const units = getTaskUnits(plan);

for (const unit of units) {
  const taskDir = path.join(out, `${unit.id}_${safe(unit.title)}`);
  const refsDir = path.join(taskDir, 'references');
  const imageDir = path.join(taskDir, 'imagegen');
  const videoDir = path.join(taskDir, 'seedance');
  fs.mkdirSync(refsDir, { recursive: true });
  fs.mkdirSync(imageDir, { recursive: true });
  fs.mkdirSync(videoDir, { recursive: true });
  const shots = plan.shots.filter(s => unit.shots.includes(s.id));
  const segments = plan.seedance_segments.filter(s => unit.segments.includes(s.id));
  const taskJson = { sequence_title: plan.sequence_title, task: unit, segments, characters: plan.characters, reference_map: referenceMap, dialogue_lines: plan.dialogue_lines || [], shots };
  fs.writeFileSync(path.join(taskDir, 'task.json'), JSON.stringify(taskJson, null, 2));
  fs.writeFileSync(path.join(taskDir, 'asset_manifest.md'), buildManifest(plan, unit, segments, shots, assetFiles, referenceMap));
  fs.writeFileSync(path.join(imageDir, 'gpt_image_brief.md'), buildImageBrief(plan, unit, segments, shots, referenceMap));
  fs.writeFileSync(path.join(imageDir, 'gpt_image_storyboard_grid_prompt.md'), buildStoryboardGridPrompt(plan, unit, segments, shots, referenceMap));
  fs.writeFileSync(path.join(videoDir, 'seedance_prompt.md'), buildSeedancePrompt(plan, unit, segments, shots, referenceMap));
  fs.writeFileSync(path.join(taskDir, 'checklist.md'), buildChecklist(unit));
}
console.log('Created generation packets: ' + out);

function getTaskUnits(plan) {
  if (Array.isArray(plan.video_tasks) && plan.video_tasks.length) {
    return plan.video_tasks.map(t => ({ ...t, title: t.title || t.reason || t.id }));
  }
  return (plan.seedance_segments || []).map(seg => ({
    id: seg.id,
    title: seg.title,
    max_duration: 15,
    segments: [seg.id],
    shots: seg.shots,
    estimated_duration: plan.shots.filter(s => seg.shots.includes(s.id)).reduce((a, s) => a + Number(s.duration || 0), 0),
    reason: 'fallback: no video_tasks in shot_plan'
  }));
}

function buildReferenceMap(plan, files) {
  const map = { scene: '@场景参考图' };
  const lowerFiles = files.map(f => ({ file: f, lower: path.basename(f).toLowerCase() }));
  for (const c of plan.characters || []) {
    const hit = lowerFiles.find(f => f.lower.includes(String(c.id).toLowerCase()) || f.lower.includes(String(c.name || '').toLowerCase()));
    map[c.id] = hit ? `@${path.basename(hit.file)}` : `@${c.name || c.id}设定图`;
  }
  const sceneHit = lowerFiles.find(f => /scene|background|environment|场景|背景|battlefield/.test(f.lower));
  if (sceneHit) map.scene = `@${path.basename(sceneHit.file)}`;
  return map;
}

function buildManifest(plan, unit, segments, shots, files, refs) {
  return `# 素材清单 - ${unit.id}\n\n## 任务信息\n\n- 预计时长：${unit.estimated_duration || 'unknown'} 秒\n- 包含片段：${unit.segments.join(', ')}\n- 任务理由：${unit.reason || ''}\n\n## 必需参考素材槽位\n\n- 本任务所有出场/说话角色的三视图或设定图。\n- 身份或情绪重要时，补充表情/姿态参考。\n- 场景/环境参考：战场、光线、天气、道具。\n- 已批准的 storyboard grid/关键帧，用于构图和 blocking。\n- 视频生成前由图像模型生成的关键帧。\n\n## 当前可用素材文件\n\n${files.length ? files.map(f => '- `' + path.relative(process.cwd(), f) + '`').join('\n') : '- 参考素材目录中没有找到文件。'}\n\n## 任务镜头\n\n${shots.map(s => `- ${s.id}: ${s.title} (${s.camera})`).join('\n')}\n`;
}
function buildImageBrief(plan, unit, segments, shots, refs) {
  const used = usedCharacters(plan, shots);
  return `# GPT-Image 关键帧 Brief - ${unit.id}\n\n使用授权角色/场景参考图，加上黑白或低饱和的线框分镜构图参考图，生成供视频使用的高保真关键帧。构图参考图只控制景别、画框、角色站位、前景/背景关系和运动方向，不控制最终画风。\n\n## 参考图锚点\n\n${formatReferenceAnchors(plan, refs, used)}\n\n## 任务范围\n\n${segments.map(s => `- ${s.title || s.id}: ${s.prompt_focus}`).join('\n')}\n\n## 需要生成的关键帧\n\n${shots.map(s => `- ${s.title} (${s.keyframe_policy || 'optional'}): ${s.camera}. ${s.video_prompt?.visual_action || concreteFallback(s)}`).join('\n')}\n\n## 一致性规则\n\n- 角色身份、服装、配色和场景整体样貌以参考图为准，不在正文扩写冲突细节。\n- 对话镜头保持 180 度轴线和 screen direction。\n- 保持 shot plan 中的主动方、视线方向和运动向量。\n- 构图参考图只作为布局/机位/走位参考。\n\n## 避免\n\n- 不要互换角色位置或颜色。\n- 不要让背景特效遮住主体动作。\n- 不要发明和 shot plan 矛盾的新服装、武器或机位。\n`;
}
function buildStoryboardGridPrompt(plan, unit, segments, shots, refs) {
  const used = usedCharacters(plan, shots);
  const panels = buildStoryboardPanels(shots).slice(0, 9);
  const panelCount = panels.length;
  return `# GPT-Image 多宫格分镜 Prompt - ${unit.id}

目标：生成一张 ${panelCount} 格黑白或低饱和的分镜草稿 contact sheet，用于在视频生成前检查角色左右关系、构图、镜头运动、动作起止和关键帧连续性。画面应像动画分镜/漫画草稿：清晰线稿、灰阶阴影、少量角色主色标识、分格明确，不追求精修插画质感。

## 使用参考图

${formatReferenceAnchors(plan, refs, used)}

## 总体要求

- 画幅：16:9 contact sheet，${panelCount} 个清晰分格，按时间从左到右、从上到下排列。
- 每格只保留很小的角标编号，不要把制作说明、文件名、代码词、参数名或长段文字画进画面。
- 使用角色参考图锁定身份、颜色、轮廓、服装/机甲和道具。
- 使用场景参考图锁定环境、光线、天气和空间结构。
- 使用构图参考图只锁定构图、机位、blocking、左右关系和运动方向，不作为画风参考。
- 画面风格为粗线条分镜草稿、灰阶/低饱和、清楚可读；不要生成精修海报、电影剧照或厚涂成片。
- 对话正反打必须保持同一 180 度轴线，不能交换角色左右位置。
- 每格重点清楚：主体、前景肩、背景方向、危险源、运动箭头或镜头运动感。

## 分格内容

${panels.map((panel, i) => `${i + 1}. ${panel}`).join('\n')}

## Avoid

- 不要交换角色身份、颜色或左右位置。
- 不要跳轴，不要反转视线方向。
- 不要让爆炸、烟尘、背景细节遮住主体。
- 不要加入额外角色、额外武器或与参考图矛盾的服装。
- 不要输出文字说明段落，只输出多宫格图像本身。
`;
}

function buildStoryboardPanels(shots) {
  const panels = [];
  for (const shot of shots) {
    panels.push(panelInstruction(shot, '首帧'));
    panels.push(panelInstruction(shot, '尾帧'));
  }
  return panels;
}

function panelInstruction(shot, phase) {
  const vp = shot.video_prompt || {};
  const action = vp.visual_action || concreteFallback(shot);
  const motion = vp.camera_motion || '镜头基本稳定';
  const phaseHint = phase === '首帧' ? '表现动作开始状态、角色初始位置和画框构图。' : '表现动作结束状态、视线/站位结果和下一镜衔接。';
  return `${shot.title}（${phase}）：${shot.camera}。${action} 镜头运动：${motion} ${phaseHint}`;
}
function buildSeedancePrompt(plan, unit, segments, shots, refs) {
  const used = usedCharacters(plan, shots);
  let cursor = 0;
  const timed = shots.map(s => {
    const start = cursor;
    cursor += Number(s.duration || 0);
    const fmt = v => String(Math.round(v)).padStart(2, '0');
    const dialogue = formatDialogue(s);
    const vp = s.video_prompt || {};
    return `[00:${fmt(start)}-00:${fmt(cursor)}] ${s.camera}\n画面与动作：${vp.visual_action || concreteFallback(s)}\n镜头运动：${vp.camera_motion || '镜头基本稳定'}\n对白/声音：${dialogue}\n避免：${vp.avoid || s.negative_from_risk || s.risk || '不要偏离参考图和已批准 storyboard/关键帧构图。'}`;
  }).join('\n\n');
  return `【风格】按项目统一动画/漫剧风格；保持参考图一致性。\n\n【时长】约 ${cursor.toFixed(1)} 秒。\n\n【参考图锚点】\n${formatReferenceAnchors(plan, refs, used)}\n\n【全局要求】\n- 参考图负责锁定角色身份、配色、轮廓、服装和场景整体样貌；正文不要重复大段外貌/场景描写。\n- 正文重点写参考图无法直接给定的信息：景别、运镜、动作、表情、视线、相对位置、前后景关系和声音方向。\n- 使用 approved storyboard/关键帧锁定构图、camera side、screen direction 和运动方向。\n- 对话镜头保持同一 180 度轴线，不交换左右关系。\n- 背景特效只做辅助运动，不遮挡主体。\n\n【时间码动作】\n${timed}\n\n【避免】\n- 不要身份漂移，不要改变角色配色、服装或轮廓。\n- 不要跳轴，不要互换左右位置，不要反转视线方向。\n- 不要把镜头编号、分镜编号或文字标签画进画面。\n- 避免 Seedance2 审核高风险词；必要时把“军人/军队/枪/爆炸/暗杀/血/政治人物”等弱化为中性视觉描述。\n`;
}
function formatDialogue(shot) {
  if (Array.isArray(shot.dialogue_timing) && shot.dialogue_timing.length) {
    return shot.dialogue_timing.map(d => {
      const text = String(d.text || '').trim();
      const speaker = d.speaker ? `${d.speaker}：` : '';
      const spoken = text ? `${speaker}"${text}"` : `${speaker}【缺少具体对白文本，补原文台词后再生成】`;
      return `${d.start}-${d.end}s ${spoken}${d.lip_sync ? '（画面内角色对口型）' : '（画外音/反应镜头）'}`;
    }).join(' / ');
  }
  const dialogue = String(shot.dialogue || '').trim();
  return dialogue ? dialogue.replace(/@?v\d{5,}/gi, '【删除语音编号，改写为具体对白文本】') : '无对白，按动作和环境声处理';
}
function formatReferenceAnchors(plan, refs, chars) {
  const lines = (chars || usedCharacters(plan, plan.shots || [])).filter(c => c.role !== 'threat').map(c => `- ${refs[c.id] || '@角色设定图'}：锁定 ${c.name || c.id} 的身份、服装、配色和轮廓；不要在正文重复外貌细节。`);
  lines.push(`- ${refs.scene || '@场景参考图'}：锁定场景整体样貌、光线、天气和空间结构；正文只补充镜头需要的局部关系。`);
  lines.push('- @构图参考图：黑白或低饱和线框分镜图，只作为构图、机位、blocking、运动方向参考，不作为画风参考。');
  return lines.join('\n');
}
function usedCharacters(plan, shots) {
  const ids = new Set();
  for (const s of shots || []) {
    if (s.speaker) ids.add(s.speaker);
    for (const d of s.dialogue_timing || []) if (d.speaker) ids.add(d.speaker);
    const r = s.render || {};
    for (const key of ['actor', 'target', 'subject', 'foreground_shoulder', 'speaker', 'listener']) if (r[key]) ids.add(r[key]);
    for (const id of r.visible_characters || []) ids.add(id);
    for (const id of r.moving_characters || []) ids.add(id);
    for (const id of r.actors || []) ids.add(id);
    for (const id of Object.keys(r.screen_positions || {})) ids.add(id);
  }
  return (plan.characters || []).filter(c => ids.has(c.id) && c.role !== 'threat');
}
function concreteFallback(shot) {
  return `${shot.camera || '既定机位'}，保持主体清楚可见，按照构图参考图的画框、站位和运动方向执行。`;
}
function buildChecklist(unit) {
  return `# Packet Checklist - ${unit.id}\n\n- [ ] 已包含授权角色参考。\n- [ ] 已包含授权场景参考。\n- [ ] 已准备批准的 storyboard grid/关键帧。\n- [ ] 已生成并 review 图像关键帧。\n- [ ] Seedance prompt 已对照 shot plan 检查。\n- [ ] 正文没有复制 asset YAML 的长篇外貌/场景 detail；参考图能说明的信息不再文字画蛇添足。\n- [ ] 正文重点写了景别、运镜、动作、表情、视线、相对空间位置、前后景和声音方向。\n- [ ] 已检查轴线/screen direction。\n- [ ] 已检查主动方和逃离/危险方向。\n- [ ] 已检查身份/颜色一致性。\n- [ ] 当前任务预计时长不超过 Seedance2 单次 15 秒上限。\n- [ ] 已检查并弱化 Seedance2 审核高风险词：军人、军队、士兵、武装、军事、枪、步枪、手枪、子弹、爆炸、炸弹、杀死、暗杀、血、尸体、政治人物、议员。\n`;
}



