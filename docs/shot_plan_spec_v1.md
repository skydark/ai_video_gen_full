# Shot Plan Schema v1.0（简化版，去掉 HTML render 依赖）

## 设计原则

- shot_plan 是纯粹的**分镜数据文件**，驱动后续 prompt 生成（多宫格/视频）
- 不包含任何 HTML canvas 渲染参数（mode、坐标、色块等）
- 所有面向 AI 生成模型的描述放在 `video_prompt` 中
- 所有面向人类 review 的信息放在 `intent`/`review`/`risk` 中

## 顶层结构

```json
{
  "schema_version": "shot-plan-1.0",
  "sequence_title": "BSD 1-7-5 清晨唤醒与新闻播报",
  "source_summary": "清城市清晨，蕾叫醒甲，晨间新闻播报米内议员暗杀事件后续。两人随后前往方舟虚拟都市。",
  "characters": [...],
  "assets_used": [...],
  "seedance_segments": [...],
  "video_tasks": [...],
  "shots": [...]
}
```

## characters

角色数组，引用 asset YAML：

```json
{
  "id": "rei",
  "asset_id": "rei",
  "name": "桐岛蕾",
  "role": "主角",
  "variant": "制服无外套"
}
```

## assets_used

本分镜用到的 asset 引用：

```json
{
  "asset_id": "hotel_room_morning",
  "type": "scene",
  "usage": "主场景"
}
```

## shots[]

每个镜头的核心字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | Y | 稳定编号，如 `S001` |
| `duration` | number | Y | 秒数 |
| `type` | string | Y | 语义类型：`dialogue_ots`/`dialogue_two`/`closeup`/`pov`/`establishing`/`action` |
| `title` | string | Y | 短标题 |
| `camera` | string | Y | 机位描述（人读），如"近景，甲正面偏右" |
| `subject` | string | N | 画面主体角色 id |
| `dialogue` | string | N | 纯文本对白（无时间轴时使用） |
| `dialogue_timing` | array | N | 对白时间轴，精确到秒 |
| `scene` | string | N | 场景 asset_id |
| `video_prompt` | object | Y | 给 AI 生成模型的执行描述 |
| `intent` | string | Y | 剧情目的（人读） |
| `review` | string | Y | review 检查要点（人读） |
| `risk` | string | Y | 生成风险（人读） |
| `recommendation` | string | Y | 建议：`可直接生成`/`先做多宫格`/`先做关键帧` |

### dialogue_timing

```json
{
  "speaker": "rei",
  "text": "おはようございます、甲さん",
  "voice_id": "v10100718",
  "start": 0.0,
  "end": 2.0,
  "lip_sync": true,
  "on_screen": true
}
```

### video_prompt

```json
{
  "visual_action": "过肩/近景，蕾在画面左侧作为前景肩部，甲作为主体在画面右侧，视线看向蕾。",
  "camera_motion": "镜头基本静止，仅保留轻微呼吸感",
  "lighting": "清晨暖光从右侧窗射入，柔和逆光",
  "avoid": "不要跳轴，不要交换角色左右位置。保持角色身份一致。"
}
```

### 镜头类型 (type) 枚举

- `establishing`：定场镜头，展示场景全貌
- `dialogue_two`：双人镜头，两人同框
- `dialogue_ots`：过肩对话镜头（需注明 subject 和 foreground_shoulder）
- `closeup`：近景/特写反应
- `pov`：主观视角
- `action`：动作/运动镜头
- `insert`：插入镜头（数据面板、手机屏幕等）
- `montage`：蒙太奇/叠画

## seedance_segments[]

叙事/分镜组织单位：

```json
{
  "id": "SEG-01",
  "title": "清晨唤醒",
  "shots": ["S001", "S002"],
  "generation_strategy": "先做多宫格确认构图再生成视频",
  "prompt_focus": "蕾叫醒甲的自然互动，保持清晨暖光氛围和角色一致性"
}
```

## video_tasks[]

视频生成任务（适配 Seedance 约15秒上限）：

```json
{
  "id": "TASK-01",
  "title": "清晨唤醒与新闻播报",
  "segments": ["SEG-01", "SEG-02"],
  "shots": ["S001", "S002", "S003", "S004", "S005"],
  "estimated_duration": 12.5,
  "reason": "同一场景、同一轴线，光线连续，合并生成保持一致性"
}
```

## 与旧版 (v0.4/v0.5) 的区别

移除的字段：
- `render` 整个对象（mode, screen_positions, cameraFrame, character positions, 等）
- `axis` 轴线坐标
- `characters[].color` / `characters[].accent`（改用 asset YAML）

新增字段：
- `assets_used`：显式声明用到的 asset
- `video_prompt.lighting`：光照描述
- `scene`：每个 shot 可指定场景
