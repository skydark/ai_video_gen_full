---
name: storyboard-to-project
description: 将已确认的动画粗脚本或剧情片段转成 WebUI 可审阅/执行的项目。用于从 bsd_anime_script/bsd_*.md、改编大纲或用户指定片段生成 shot_plan.json、按 segment/video_task 组织的多宫格分镜图 job、视频 job、review.yaml、task.yaml 和项目 assets。
---

# Storyboard to Project

把用户已经确认方向的粗脚本，整理成可在本仓库 WebUI 中审阅和执行的任务项目。

典型用户只需要说：

```text
从 bsd_anime_script/bsd_1_7_6.md 开始，帮我做一轮可在 WebUI 审阅的动画分镜项目。
```

Agent 应自动读取本 skill、根目录 `AGENTS.md`、`docs/shot_plan_spec_v1.md` 和相关 asset YAML，完成必要的分析、讨论、建档和项目创建。

## 输出目标

优先生成一个版本化项目目录，例如：

```text
projects/bsd_1_7_6_v001/
  shot_plan.json
  task_project/
    task.yaml
    task.initial.yaml
    assets/
    jobs/
      <segment_or_task>_storyboard_grid/job.yaml
      <segment_or_task>_video/job.yaml
    review/review.yaml
```

其中：

- `shot_plan.json` 遵循 `docs/shot_plan_spec_v1.md`。
- `task_project/` 可直接由 WebUI 加载。
- `assets/` 复制本项目会用到的参考图及同名 YAML，不只复制图片。
- storyboard grid 是图像生成任务，用于低成本检查构图、轴线、动作和角色一致性。
- video job 是后续视频生成任务，默认先保持 draft/dryrun，不主动付费提交。

## 禁止项

- 不生成、维护或要求用户查看旧式网页预览。
- 不把网页预览、canvas 坐标、色块角色、`render` 字段作为分镜依据。
- 不在未获用户明确授权时运行付费 provider。
- 不编造原作语音 ID；没有 voice id 的新台词只能作为无语音字幕/动作说明，并需明确标注。
- 不覆盖已有版本目录；默认创建 `_v001`、`_v002` 等新目录。

## 输入处理

1. 读取用户指定的 `bsd_anime_script/bsd_*.md` 或改编大纲。
2. 如果文本编码显示异常，先尝试以常见日文/中文编码读取；需要落盘时，另存 UTF-8 辅助副本，不覆盖原文件。
3. 提取：片段 ID、衔接点、场景、角色、剧情 beat、对白、voice id、用户指定的目标时长/场景数。
4. 读取相关 asset YAML：
   - 角色：`assets/chars/*.yaml`
   - 场景：`assets/scenes/*.yaml`
   - 道具或其他：按 `assets/**/<name>.yaml` 搜索
5. 若资产缺失，继续设计但在输出中列出 `asset_gaps`，并在 job refs 中标为待补。

## 与用户讨论

在写完整 `shot_plan.json` 前，先给用户一个短的方向确认，除非用户明确要求直接生成：

- 用 5-8 条短 bullet 说明保留的剧情 beat、删减信息、预计 video_task、风险镜头和资产缺口。
- 不写长篇解释；用户没时间读论文式分析。
- 如果用户指出镜头思路错误，先用 3-5 条短 bullet 复盘并给修正方案，不要辩解。

问题要少而关键；不要让用户学习内部命令或目录结构。

## 分镜设计流程（必须按顺序）

不要一上来直接排 shot。必须先完成“动机层 → 关键分镜 → 支撑镜头 → 输出数据”：

### 1. 动机层：先说明这段到底要讲什么

用短表格或 5-8 条 bullet 写清：

- **故事功能**：这段在整章里推进什么信息或人物关系。
- **情感曲线**：观众应从什么情绪走到什么情绪，例如轻松日常 → 荒唐笑点 → 关系试探 → 温柔收束。
- **观众注意点**：每个 beat 中观众必须注意什么信息、道具、表情或声音来源。
- **视线引导策略**：用谁的视线、反应、动作、声音方向或构图线索带观众看下一处。
- **空间/轴线策略**：角色位置、左右关系、镜头运动方向如何保持连续。

如果这一层说不清，不要继续写 shot_plan。

### 2. 关键分镜：先设计必须成立的镜头

先列出 3-6 个关键镜头/转场，不要铺满所有细节：

- 信息必须被看见的镜头：例如声音来源、战斗刀、关键表情。
- 情感转折镜头：例如甲一怔、蕾低落、蕾闹别扭。
- 空间转接镜头：例如从甲的位置顺视线移动到厨房方向。
- 关系镜头：例如双人站位、距离变化、谁主动靠近/回避。

每个关键镜头必须写：`目的 → 观众看哪里 → 如何引导 → 为什么这样切/动`。

### 3. 支撑镜头：反推前后镜头

围绕关键镜头补支撑镜头：

- 关键道具特写前，先让观众知道角色在哪、为什么会注意到它。
- 新角色出场前，先用主角视线/声音/动作建立出场方向。
- 情感特写前，先铺垫上一句对白或反应；特写后要给对方反应或关系结果。
- 长对话拆成“说话者表情 → 听者反应 → 双人关系”循环，不要单镜头硬撑。

### 4. 技术检查：再确定 shot 和 video_task

最后才按生成限制落到具体 shot：

- 单个 video_task 通常不超过 15 秒。
- 超过 6-8 秒的 shot 必须有清晰内部变化：镜头运动、动作阶段、表情变化或视线转移。
- 每个 `video_prompt.visual_action` 必须能对应动机层的“观众注意点”。
- 每个 `intent` 必须解释该镜头为什么存在，不允许只写“展示某人说话”。
- 每个 `review` 必须让用户能检查：信息是否被看见、情绪是否成立、视线/空间是否连贯。

## 自包含 Prompt 检查（强制）

生成模型只能看到 prompt 和参考图，不能理解内部符号。所有 image/video job prompt 必须自包含：

- 对白必须写具体台词文本，可附说话人和情绪；不能只写 `v10200075`、`voice_id`、“这句台词”。
- 动作必须写可见动作；不能只写“表现关系变化”“按剧本推进”“同上”。
- 声音必须写可理解内容；例如“厨房方向传来菜ノ叶的画外音：『……』”，不能只写“播放语音 vxxxx”。
- 参考图可用 `@角色参考图`、`@场景参考图` 这类锚点，但 prompt 本身仍要写清角色、场景、动作、对白。
- `voice_id` 只能保留在 `dialogue_timing[].voice_id`、metadata 或后期配音记录中，不得出现在发给图像/视频模型的 prompt 正文。

写完 `shot_plan.json` 和 `task_project/jobs/*/job.yaml` 后，必须运行：

```bash
uv run --with pyyaml python skills/storyboard-to-project/scripts/check_self_contained_prompts.py <project_dir>/shot_plan.json <project_dir>/task_project/jobs
```

如果检查失败，先修 prompt，再让用户 review。

## 分镜思维规则

设计镜头时先问“观众怎么知道该看哪里、为什么切到这里”：

- **交代因果**：画外声、骚动、视线变化必须有来源或方向。先让观众看到角色反应，再用镜头移动/切换揭示声音来源。
- **视线引导**：角色看向哪里，镜头就可以顺着视线摇移、推移或切到下一主体；不要无提示地硬切到新角色。
- **关系表达**：镜头要表达角色关系、距离和情绪变化，不只是把对白排成正反打。
- **重点特写**：如果某个道具/动作是剧情重点，必须给清晰特写或插入镜头；不要指望观众在复杂画面里自动注意到它。
- **避免死镜头**：超过 6-8 秒的静止对话或静止环境镜头通常不合格；需要表演层次、镜头运动、反应切换或插入镜头。
- **空间连续**：跨空间动作要先建立角色位置、方向和目标，再移动/切换到目标空间。
- **每镜有功能**：每个 shot 的 `intent` 必须说明它在引导视线、交代信息、推进关系或制造情绪中的功能。

## shot_plan 设计规则

按 `docs/shot_plan_spec_v1.md` 写 `shot_plan.json`：

- `characters[]` 只引用 asset 中的角色身份和 variant。
- `assets_used[]` 列出本项目实际会用到的角色、场景、道具。
- `shots[]` 写清 `duration`、`type`、`title`、`camera`、`scene`、`video_prompt`、`intent`、`review`、`risk`、`recommendation`。
- `dialogue_timing[]` 保留原文台词和 voice id；时间可按句长估算，后续允许 WebUI/人工调整。
- `video_prompt.visual_action` 必须是可见画面，不写抽象意图。
- `video_prompt` 中引用对白时写具体文本，不写 voice id；voice id 只放在 `dialogue_timing[].voice_id`。
- `video_prompt.avoid` 写身份漂移、跳轴、左右互换、手部错误、文字入画等风险。
- `seedance_segments[]` 按剧情 beat/空间关系组织。
- `video_tasks[]` 面向实际视频生成，单 task 建议不超过 15 秒；同场景同轴线优先合并。

## storyboard grid job

对每个重要 `video_task` 或风险较高的 `segment` 创建一个图像 job：

- 标题使用 `TASK-xx / SEG-xx 多宫格分镜`。
- prompt 写成自足的图像生成说明：黑白或低饱和线稿/灰阶、清晰分格、从左到右按时间推进。
- 每格描述景别、主体、动作起止、视线方向、左右关系和场景光线。
- 引用角色/场景参考图；不要写“参考上面的预览”“更真实”这类依赖外部上下文的词。
- 默认 provider 可为 `dryrun` 或项目默认图像 provider；不自动 live submit。

## video job

为每个 `video_task` 创建视频 job：

- prompt 从 `shots[].video_prompt` 和对白时间轴合成，按时间顺序描述。
- refs 包含角色、场景、已生成/已批准的 storyboard grid 或关键帧占位。
- 默认 duration 取 `video_task.estimated_duration`。
- `video job.params.duration_limit` 必须来自 `video_task.estimated_duration` 的四舍五入/模型支持值。Seedance2 单次硬上限是 15 秒，所以 15 秒是合法值；但不能把它当默认值无脑写入所有任务，必须能解释为该 task 的实际预计时长或上限截断。
- provider/model/params 使用项目默认值；未知时保守使用 `dryrun`。
- 不写 negative prompt，除非目标 provider 明确支持且用户要求。

## Seedance Prompt 校对（强制）

写完每个视频 job prompt 后，必须逐项校对并修正：

1. **参考图优先**：角色外貌、服装、配色、场景整体样貌如果已由 refs/asset YAML/批准 storyboard 锁定，就不要在 prompt 正文反复长篇描写。正文只保留必要锚点，例如“甲在左、蕾在右”。
2. **文字只写参考图无法表达的信息**：重点写景别、运镜、角色动作、表情变化、视线方向、相对空间位置、前后景关系、节奏、画内/画外对白和声音方向。
3. **删除画蛇添足描述**：删掉与参考图重复或可能冲突的外貌细节、服装细节、泛泛场景形容、抽象情绪口号。
4. **自包含但不过载**：prompt 要让视频模型不看工程上下文也能执行，但不要把 asset YAML 的 `detail` 整段复制进视频 prompt。
5. **Seedance2 审核词检查**：提交前搜索并替换可能触发审核的敏感词或直白暴力/军事/政治/血腥词。常见风险词包括：`军人`、`军队`、`士兵`、`武装`、`军事`、`枪`、`步枪`、`手枪`、`子弹`、`爆炸`、`炸弹`、`杀死`、`暗杀`、`血`、`尸体`、`政治人物`、`议员`。能弱化就改为更中性的可视描述，例如“制服人员/警备人员/远处冲突声/强光冲击/事件新闻”。
6. **必要保留例外**：如果原作台词必须保留敏感词，放在对白 metadata 或用户确认后的台词区，避免在画面动作描述中重复扩写。

校对失败时，不要让用户先 review；先改 job prompt 和相关 `shot_plan.video_prompt`。

## task_project 结构

创建 WebUI 项目时：

1. 写 `task.yaml`：项目元数据、source script、`source.shot_plan_dir`、assets、jobs 列表、默认 provider 设置。
2. 写 `task.initial.yaml`：初始备份。
3. 写 `review/review.yaml`：必须包含 WebUI 可直接显示的 `items[]`；不要只写 shot id/title/duration。
4. 为每个 job 写 `jobs/<job_id>/job.yaml`。
5. 复制本项目用到的 asset 文件和同名 YAML 到 `task_project/assets/`，保持来源可追溯。

### WebUI review 数据契约

WebUI 的 Review 页按 `review.items[]` 渲染，并用 `video_task || segment` 分组。skill 必须直接写当前格式，不要求 WebUI 兼容旧格式。

`task.yaml` 的 source 必须写目录路径：

```yaml
project:
  source:
    script: bsd_anime_script/bsd_1_7_6.md
    shot_plan_dir: ..
```

`review/review.yaml` 的 `previs.shot_plan` 必须是 WebUI 后端可直接读取的路径。对于推荐目录结构 `projects/<id>/task_project/review/review.yaml`，写绝对路径最稳妥：

```yaml
previs:
  shot_plan: E:\VideoProjects\BSDAnime\ai_video_gen_full\projects\<id>\shot_plan.json
```

每个 item 至少要包含：

```yaml
schema_version: 1
status: in_review
previs:
  shot_plan: ../shot_plan.json
  sequence_title: 项目标题
global_feedback: ''
items:
  - id: S001
    title: 短标题
    duration: 3.5
    type: establishing
    camera: 远景，先交代甲在花园的位置
    dialogue: ''
    intent: 建立甲的位置，并为后续厨房方向的声音做空间铺垫
    review: 检查观众是否能理解甲在哪里、声音来自哪个方向
    risk: 空间方向不清，镜头移动过慢
    recommendation: 先做多宫格
    segment: SEG-01 花园定场+厨房骚动
    video_task: TASK-01 花园定场+厨房骚动
    prompt_preview: 甲听到厨房方向骚动，镜头顺着他的视线向厨房窗外移动
    status: pending
    feedback: ''
    tags: []
    locked: false
```

不要输出只有 `id/title/duration/status` 的 review item；那会导致 Review 页缺少 camera、intent、review focus、risk、segment/video_task 和 prompt preview。

## 迭代规则

当用户基于 WebUI brief 要求修改：

1. 读取 `task_project/review/iteration_briefs/iteration_*/brief.md` 和 `review/review.yaml`。
2. 保持 approved/locked 的 shots、jobs 和 refs 不变。
3. 只修改 needs_change 或有明确反馈的部分。
4. 输出新版本目录，不覆盖旧目录。
5. 告诉用户在 WebUI 加载新 `task_project/` 继续 review。

## 完成标准

一次 storyboard-to-project 任务完成时，应能回答：

- 新项目目录在哪里。
- `shot_plan.json` 是否通过 JSON 解析。
- 自包含 prompt 检查是否通过。
- WebUI 应加载哪个 `task_project/`。
- 哪些 storyboard grid job 建议先跑。
- 哪些资产缺失或需要用户确认。
