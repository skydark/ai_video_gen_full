# 外部 Prompt 经验摘要

资料来源：

- ZeroLu/awesome-seedance `README-zh.md`：https://raw.githubusercontent.com/ZeroLu/awesome-seedance/refs/heads/main/README-zh.md
- YouMind-OpenLab/awesome-gpt-image-2：https://github.com/YouMind-OpenLab/awesome-gpt-image-2
- wuyoscar/GPT-Image2-Skill：https://github.com/wuyoscar/GPT-Image2-Skill

只参考 prompt 设计和制作流程，不参考 API 调用代码。

## Seedance 2.0 经验观察

从 `awesome-seedance` 的电影、动漫、短剧、AI 漫剧案例中抽象出的可复用模式：

- 高质量视频 prompt 通常是“风格 + 时长 + 分时间段镜头脚本”，而不是一段泛描述。
- 时间码常用 `[00-05s]`、`[05-10s]`、`[10-15s]`，每段写清景别、人物、动作、情绪和镜头运动。
- 电影类 prompt 会明确摄影风格、画幅感、色调、颗粒、运动模糊、镜头晃动、慢动作、切黑等。
- 短剧类 prompt 会明确竖屏/横屏、快切节奏、台词/字幕逐字一致、表情爆发、反转点和观众反应。
- 动漫/战斗类 prompt 会把动作拆为“静止与爆发、属性/形态转换、碰撞交互、结果/转场”。
- AI 漫剧案例强调：用参考视频/图片锁定画风和动作表现；打斗要明确招式、受力、后退、碎片、碰撞结果。
- 多图参考和 image-to-video 案例说明：短 prompt 也能驱动过渡，但生产项目仍应把主体、方向、风格、目标写清。

## GPT-Image 2 经验观察

从 `awesome-gpt-image-2` 和 `GPT-Image2-Skill` 的 prompt 集合中抽象出的可复用模式：

- 先结构后目标：按 `背景/场景 -> 主体 -> 关键细节 -> 约束 -> 用途` 写，比散文稳定。
- 任意格式都可行，但生产中推荐稳定模板；JSON 风格、分栏、panel 描述都适合复杂画面。
- 需要图中文字时，把必须出现的文字放进引号，并明确布局位置。
- 先确定比例：1:1、3:4、4:3、9:16、16:9 等，不要最后才补。
- 复杂画面最好只有一个 hero subject，其他都是 supporting detail。
- 多 panel / storyboard / 角色设定表适合用明确网格：例如 3x2 storyboard、三视图、表情格、信息条。
- 角色参考表 prompt 通常包括：正面、侧面、背面、表情变化、服装/装备拆解、色板、世界观说明、干净排版。
- 动作插画 prompt 常明确前景角色、背景对手、姿态、能量/碎片/尘土、透视角度和光线。

## 对本工作流的落地改造

- GPT-image 阶段：把每个关键帧 brief 写成结构化模板，而不是自然段。
- Seedance 阶段：把每个片段 prompt 写成时间码镜头脚本，继承 `shot_plan.json` 的时长、镜头顺序和风险约束。
- 漫剧对话段：使用短剧 prompt 的“口型/字幕/情绪/反应”结构，但用 storyboard grid/关键帧保证轴线和镜头关系。
- 漫剧动作段：使用动漫 prompt 的“准备、爆发、碰撞、结果”结构，但不要把太多动作塞入一个片段。
- 角色一致性：先用 GPT-image 生成/整理角色设定表和关键帧，再喂给视频生成。

