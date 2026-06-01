# AI Video Gen Full 工作流

本目录是一个可复制的本地 AI 动画生成工作包。目标是让用户用自然语言提出分镜改编需求，AI Agent 读取 asset YAML 和剧本，设计 shot_plan，生成多宫格分镜图用于视觉校验，最终生成视频。

## 目录职责

```text
ai_video_gen_full/
  AGENTS.md                 # 给 AI Agent 的主工作流入口
  README.md                 # 给用户的启动说明
  assets/                   # 全局参考素材（角色/场景图片 + 同名 YAML 描述）
    chars/                  # 角色参考图 + .yaml
    scenes/                 # 场景参考图 + .yaml
  docs/                     # 规范文档
    asset_yaml_spec.md      # Asset YAML 格式规范
    shot_plan_spec_v1.md    # Shot Plan 简化 schema（v1.0，无 HTML 依赖）
  skills/
    storyboard-to-project/  # 剧本 → shot_plan + 多宫格 prompt + 项目目录
    animation-generation-packet/  # shot_plan → generation packet（执行准备）
  webui/                    # FastAPI + React 本地工具
  projects/                 # 新任务输出目录，按项目/版本创建
```

## 用户触发方式

当用户提出以下任一需求时，按本工作流执行：

- "帮我把这段剧情改编为动画分镜"
- "设计这个片段的 shot_plan"
- "生成多宫格分镜图"
- "根据我的反馈迭代分镜"
- "分镜通过后生成图像/视频任务"
- "在 WebUI 中执行生成任务"

## 阶段 0：准备（首次使用时）

1. 确保 asset 参考图已放入 `assets/chars/` 和 `assets/scenes/`
2. 确保每个 asset 有同名 YAML 描述文件（遵循 `docs/asset_yaml_spec.md`）
3. 如果缺失，用视觉模型分析图片生成 YAML（参考 `scripts/analyze_assets.py`）

## 阶段 1：剧本改编与分镜设计

1. 读取用户剧本（如 `bsd_anime_script/bsd_1_7_5.md`），提取对白、场景、角色、语音 ID。
2. 读取相关 asset YAML（`assets/chars/*.yaml`、`assets/scenes/*.yaml`），锁定角色外观和场景特征。
3. 与用户讨论改编方向：保留/删减的剧情点、场景数、目标动画时长。
4. 使用 `skills/storyboard-to-project` 设计 `shot_plan.json`（遵循 `docs/shot_plan_spec_v1.md`）。

**shot_plan 设计要点：**
- 每个镜头写清 `video_prompt`（面向生成模型的具体画面描述）和 `intent`/`review`/`risk`（面向人类）
- 角色视觉描述从 asset YAML 的 `detail` 字段引用，不自编
- `recommendation` 诚实评估：简单镜头"可直接生成"，OTS/POV/手部接触等"先做多宫格"
- `video_tasks` 合并不超过 15 秒
- 分镜必须引导观众视线：先交代角色位置/反应，再用视线、声音方向、镜头移动或道具特写解释为什么切到下一画面
- 超过 6-8 秒的静止镜头通常需要拆分、加入反应/插入镜头或明确镜头运动

## 阶段 2：多宫格分镜图（可选，推荐）

对不确定构图的 video_task 生成多宫格分镜 prompt：
- 黑白/低饱和线稿风格，6-9 格
- 引用角色和场景参考图
- 遵循 `skills/animation-generation-packet/references/packet_best_practices.md` 中的多宫格模板

**多宫格分镜图是主要的视觉校验手段**。
成本约 ¥1-2/次，远低于视频生成，适合反复迭代。

## 阶段 3：创建 WebUI 项目

1. 在 `projects/<project_id>/` 创建项目目录，含 `task.yaml` + `jobs/`。
2. 使用 `skills/animation-generation-packet` 生成 generation packet。
3. 将 asset 引用写入 `task.yaml` 和 `jobs/*/job.yaml`。

## 阶段 4：WebUI Review

1. 启动 WebUI：
   ```bash
   cd webui
   uv run uvicorn app.main:app --host 127.0.0.1 --port 8787
   ```
   前端已构建到 `dist/`，直接访问 `http://127.0.0.1:8787`。

2. 用户在 WebUI 中加载 `projects/<project_id>/`。
3. 在 `Execute` 页查看/编辑 job prompt 和参数。
4. 在 `Review` 页加载多宫格分镜图，逐镜头 review。
5. 用户写入反馈，点击 `Export Brief`。

## 阶段 5：Iterate

当用户要求"根据反馈继续改"时：

1. 读取最新 `review/iteration_briefs/iteration_*/brief.md` 和 `review/review.yaml`。
2. 保持 `approved` 或 `locked` 的镜头不变。
3. 只修改 `needs_change` 或有 feedback 的镜头。
4. 输出新版本目录，不覆盖旧版。
5. 告诉用户刷新 WebUI 继续审核。

## 阶段 6：Execute

当 review 通过后，用户在 WebUI 的 `Execute` 页执行：

1. 先跑 `dryrun` 确认任务正常。
2. 付费 provider 必须由用户显式点击并确认。
3. 图像任务生成多宫格分镜、首尾帧或关键帧。
4. 图像输出 `Use as Ref` 绑定给后续视频任务。
5. 视频任务使用 Seedance/Dreamina provider，单任务不超过 15 秒。
6. 用户满意后点击 `Approve`。

## 设计原则

- **多宫格分镜图优先**：AI 图像模型输出的多宫格更能暴露身份漂移、构图问题
- **asset YAML 锁定角色/场景**：所有 prompt 引用 asset YAML 的 `detail`，不自己编造
- **从便宜到贵**：文本迭代(免费) → 多宫格图(¥2) → 视频(¥10+)，每步可回退
- 目录就是数据库，优先 YAML/JSON
- 每个版本、每个 run 都可追溯、可复制
- WebUI 不内置 AI 聊天，只导出结构化 brief
- Prompt 面向生成模型时必须具体描述可见画面，不写抽象意图或外部上下文
