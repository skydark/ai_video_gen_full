---
name: animation-generation-packet
description: 从已 review 通过的 shot_plan.json、storyboard grid/关键帧、参考素材目录和用户说明生成视频生成 packet。用于准备 GPT-image 关键帧 brief、Seedance/视频生成 prompt、资产清单、一致性 checklist 和按片段拆分的目录。
---

# 动画视频生成 Packet

在分镜 review 通过后，把 `shot_plan.json`、storyboard grid/关键帧、授权角色/场景素材和生成说明，整理成可执行的视频生成 packet。

这个 skill 不直接生成最终视频。它的职责是把材料整理清楚，降低后续用图像模型生成关键帧、再用 Seedance 等视频模型生成片段时的偏移。

## 输入

- 已批准的项目/分镜目录，里面需要有 `shot_plan.json`。
- 参考素材目录，放用户提供或授权使用的角色、道具、场景参考图。
- 可选：已生成并批准的 storyboard grid、首帧、尾帧或关键帧。
- 用户对哪些镜头已批准、哪些镜头要继续做关键帧的说明。

不要静默下载或复用受版权保护的角色图作为生产参考，除非用户提供或明确有权使用。对于游戏改编角色，优先让用户提供官方授权/自有参考图。网页搜索可以用于查经验、找灵感或找可合法使用素材，但不要擅自把受版权图片打包成图生图参考。

## 工作流

1. 读取已批准的 `shot_plan.json`。
2. 检查参考素材目录的文件名和结构。
3. 优先按 `video_tasks[]` 每个视频生成任务创建一个 packet；没有 `video_tasks` 时才退回 `seedance_segments[]`。
4. 调用脚本：

```bash
node <skill>/scripts/create_generation_packets.js --shot-plan <shot_plan_dir> --assets <reference_assets_dir> --out <packet_out_dir>
```

5. 如需在 RunningHub 上用 GPT-image 生成分镜参考图，先准备 dry-run 任务，检查 prompt 和参考图顺序：

```bash
python <skill>/scripts/runninghub_gpt_image.py prepare --packet <packet_out_dir> --out <rh_jobs_dir> --ref <role_id>=<character.jpg> --ref scene=<scene.jpg>
```

如果还没有场景参考图，可以先不传 `scene`，脚本会额外准备一个文生图背景任务；背景任务也默认只是 dry-run。

推荐两阶段执行：

```bash
# A. 先准备并提交背景参考图任务。
python <skill>/scripts/runninghub_gpt_image.py prepare --packet <packet_out_dir> --out <rh_jobs_dir> --task <task_id> --ref <role_id>=<character.jpg>
python <skill>/scripts/runninghub_gpt_image.py submit --job <rh_jobs_dir>/BG-001_battlefield_scene/job.json --live --confirm-cost --poll

# B. 背景图成功下载后，重新 prepare 同一目录。
# 脚本会自动把 <rh_jobs_dir>/BG-001_battlefield_scene/outputs/ 中的第一张图片作为 scene 参考加入多宫格任务。
python <skill>/scripts/runninghub_gpt_image.py prepare --packet <packet_out_dir> --out <rh_jobs_dir> --task <task_id> --ref <role_id>=<character.jpg>
python <skill>/scripts/runninghub_gpt_image.py submit --job <rh_jobs_dir>/<task_id>_storyboard_grid/job.json --live --confirm-cost --poll
```

如果用户已经提供场景图，直接传 `--ref scene=<scene.jpg>`，不用先生成背景图。检查 `*/prompt.txt`，确认“参考图顺序”里同时列出角色和场景。

6. 只有用户明确允许付费调用时，才提交 RunningHub 任务。必须使用 `--live --confirm-cost`：

```bash
python <skill>/scripts/runninghub_gpt_image.py submit --job <rh_jobs_dir>/<job_id>/job.json --live --confirm-cost --poll
```

不要在没有用户明确授权时运行 `submit --live`。RunningHub GPT-image 调用会扣费。

7. 如果用户指定了模型、尺寸、图数或 Seedance UI/API 限制，再 patch brief。
8. 在声称具体 API 参数正确前，刷新 OpenAI 和 Seedance/火山引擎当前官方文档；不要硬编码不确定参数。

## Packet 内容

每个片段目录包含：

- `task.json`：视频任务内镜头数据、参考图锚点和结构化字段。
- `asset_manifest.md`：需要的素材槽位和当前可用素材。
- `imagegen/gpt_image_brief.md`：用授权参考图 + 已批准 storyboard/关键帧生成高保真关键帧的 brief。
- `imagegen/gpt_image_storyboard_grid_prompt.md`：用 GPT-image 生成黑白/低饱和多宫格分镜草稿的 prompt，用于在视频生成前低成本检查构图、轴线、动作起止和参考图一致性。
- `seedance/seedance_prompt.md`：视频生成 prompt 包。
- `checklist.md`：一致性检查表。

可选 RunningHub 输出目录包含：

- `*/job.json`：可提交的 RunningHub 任务定义。
- `*/dry_run.json`：不会扣费的 payload 预览。
- `*/prompt.txt`：发给 GPT-image 的完整提示词。
- `*/outputs/`：付费提交并轮询成功后下载的结果图。

## 经验原则

- 把“身份参考”和“构图/关键帧参考”分开。
- storyboard grid 只控制构图、走位、镜头关系，不控制最终画风。
- 角色三视图/设定图用于锁定身份、颜色、轮廓。
- 场景图用于锁定光线、天气、建筑、空间密度。
- 身份、手部接触、正反打轴线、多角色 blocking 重要时，先做图像关键帧，再做视频。
- 在视频生成前，优先生成一张多宫格镜头引导图：对图像模型要写成“黑白或低饱和分镜草稿、清晰分格、线稿/灰阶、少量主色标识”，不要写“参考上面的预览”或“更接近真实参考图”这类依赖外部上下文的相对描述。
- 每个视频片段 prompt 要短、顺序清晰、连续性明确。
- 视频 prompt 正文只写模型能执行的可见内容：参考图锚点、主体、构图、动作、镜头运动、对白/声音、avoid。不要把 `intent`、`review`、镜头编号或内部字段名当作生成指令。
- prompt 必须自包含：对白写具体台词文本，声音写具体可理解内容；`voice_id`、`v10200075` 这类内部编号只能留在 metadata/配音记录，不能出现在图像或视频模型 prompt 正文。
- 角色必须用“视觉描述 + @参考图锚点”锁定；不要假设视频模型认识角色名字。
- negative/avoid 里写清身份漂移、跳轴、颜色互换、运动方向错误。
- RunningHub 脚本中的参考图顺序会写进 prompt；如果文件名无法自动表达角色身份，使用 `--ref 角色id=图片路径` 显式指定。
- 多宫格分镜图必须带场景参考：用户提供 `scene` 图时传 `--ref scene=...`；没有时先生成背景参考图，再重新 prepare 多宫格任务，让脚本自动带入已下载的背景图。
- 图像模型没有当前对话上下文，prompt 必须自包含；不要写“参考上面的预览”或“更真实”。

更多规则见 `references/packet_best_practices.md`。如果需要参考外部 prompt 经验，读取 `references/external_prompt_research.md`；只吸收 prompt 结构，不复制调用代码。

## 在 ai_video_gen_full 中使用

如果当前 workspace 根目录存在 `AGENTS.md` 且说明了 `ai_video_gen_full` 工作流，则把本 skill 的输出作为 WebUI Execute 阶段的输入：

- packet 默认输出到 `projects/<project_id>/generation_packet_v001/`，迭代版本使用 `generation_packet_v002/`、`generation_packet_v003/`。
- packet 完成后，用 `webui/scripts/import_generation_packet.py --packet <packet> --shot-plan <shot_plan_dir> --out <task_project>` 创建或更新 WebUI 任务项目。
- 如果用户已在 WebUI 中添加资产，迭代时尽量保留 `assets/` 和 `jobs/*/job.yaml` 中的用户编辑内容，只更新由分镜变化导致的 prompt、任务拆分和引用需求。
- 图像任务输出的多宫格分镜、首尾帧或关键帧，应能在 WebUI 中 `Use as Ref` 绑定给后续视频任务。
- 生成给图像/视频模型的 prompt 必须自包含，不引用“HTML 页面”“上面的预览”等外部上下文。
- packet 完成后运行自包含检查：`uv run --with pyyaml python skills/storyboard-to-project/scripts/check_self_contained_prompts.py <shot_plan_dir>/shot_plan.json <task_project_or_packet_dir>`；失败时先修 prompt，再进入 WebUI/提交 provider。


