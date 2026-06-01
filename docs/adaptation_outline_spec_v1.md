# Adaptation Outline Schema v1.0

`adaptation_outline.yaml` 是从原始剧情到分镜脚本之间的中间层。它用于长片段改编讨论：先确定保留哪些剧情点、场景和原作语音，再进入 `bsd_*.md` 脚本初稿与 `shot_plan.json`。

## 目标

- 面向 5-7 分钟级别长片段，避免直接跳到镜头级分镜。
- 只做剧情裁剪、场景组织、台词候选和制作风险判断。
- 支持多轮讨论：每版都可复制、回退、继续细化。

## 顶层结构

```yaml
schema_version: adaptation-outline-1.0
project_id: bsd_1_7_6
source:
  raw_script: bsd_anime_script/raw/01：レイン編07.txt
  previous_context: bsd_anime_script/bsd_1_7_5.md
target:
  final_duration_minutes: 5-7
  scene_count: 3-8
  voice_policy: use_original_lines_only
summary: |
  一句话说明本段改编目标。
beats:
  - id: B01
    title: 场景/剧情 beat 标题
    source_range: 原始剧情的大致位置或标记
    purpose: 这个 beat 在改编中的作用
    keep: 必须保留的信息与情绪
    cut_or_compress: 可删减或压缩的内容
    location: 场景名称
    characters: [kou, rei]
    estimated_duration: 45
    voice_candidates:
      - speaker: rei
        voice_id: v10100000
        text: 原作台词
        priority: must_keep
    visual_strategy: 多宫格/关键帧/可直接生成的建议
    risks: 制作风险与需要用户确认的问题
open_questions:
  - 需要用户决定的问题
next_outputs:
  - bsd_anime_script/bsd_1_7_6.md
```

## 使用原则

- 不重写原作台词；只摘录候选语音句。
- 每个 beat 应能映射到后续 1-3 个 `video_tasks`。
- 对话密集段优先压缩成少量正反打或双人镜头。
- 难懂的空间/动作关系标记为“先做多宫格”。
- 用户确认大纲后，再生成 `bsd_*.md` 脚本初稿。
