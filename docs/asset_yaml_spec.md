# Asset 描述文件规范 v1.0

每个 assets 子目录下的参考图片应配有一个同名的 `.yaml` 描述文件。
AI Agent 在编写剧本/分镜/prompt 时应先读取相关 asset YAML，以保证角色和场景描述一致。

## 目录结构

```text
assets/
  chars/
    蕾_现代篇_制服_无外套.png
    蕾_现代篇_制服_无外套.yaml   # 同名描述文件
    甲_现代篇_制服_有外套.png
    甲_现代篇_制服_有外套.yaml
  scenes/
    现代篇_酒店房间_早晨.jpg
    现代篇_酒店房间_早晨.yaml
  props/
    # 道具类同理
```

## 字段说明

### 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 唯一标识符，用于 shot_plan 和 prompt 中引用，如 `rei`、`kou` |
| `name` | string | 显示名称（中文） |
| `type` | string | `character` / `scene` / `prop` |
| `brief` | string | 1-2句话简短描述，AI 快速识别用。写清最关键视觉特征 |
| `detail` | string | 完整视觉描述，类似生成 prompt。写清所有视觉细节，可直接用作 AI 图像/视频生成的 identity/scene prompt |
| `tags` | string[] | 关键词标签列表 |

### 可选字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `name_jp` | string | 日文名 |
| `source` | string | 来源作品 |
| `ref_images` | object[] | 关联的参考图列表，每个含 `path`（相对 assets 根目录）、`variant`（变体说明）、`pose`（姿态） |
| `personality` | string | 角色性格关键词（仅 character） |
| `generation_notes` | string | AI 生成时的额外注意事项/避免项 |

## 示例

### 角色 (character)

```yaml
id: rei
name: 桐岛蕾
name_jp: 桐島 レイン
type: character
source: Baldr Sky

brief: |
  金发长直发的年轻女性，蓝色瞳孔，灰色马甲+深蓝衬衫OL制服，
  黑色短裙与灰色过膝袜，气质干练冷艳。

detail: |
  一位身材高挑的年轻女性。金色长直发，刘海自然垂落，
  头顶两侧黑色角状发饰，脑后呆毛。蓝紫色眼睛，眼神锐利冷静。
  上身深蓝色长袖衬衫+深蓝领带，外搭浅灰色修身西装马甲。
  下身黑色紧身包臀短裙。灰色半透明过膝长筒丝袜，大腿处黑色袜圈。
  黑色尖头高跟鞋。肩膀有黑色皮质战术背带。站姿挺拔。

tags: [金色长发, 蓝色瞳孔, 灰色马甲, 深蓝衬衫, 黑色短裙, 过膝袜, OL制服]

ref_images:
  - path: 蕾_现代篇_制服_无外套.png
    variant: 制服无外套
    pose: 正面站立
```

### 场景 (scene)

```yaml
id: hotel_room_morning
name: 爱情旅馆房间（清晨）
type: scene
source: Baldr Sky

brief: |
  白天酒店标准间，阳光从右侧窗射入照亮床铺和地毯，
  包含睡眠区、休息区和玄关，安静略带复古感。

detail: |
  室内酒店客房。左侧入口区有深棕色木门、衣柜和挂衣架。
  中央双人床铺棕橙色格纹床罩，两侧床头柜和台灯。
  右侧靠窗紫色复古沙发和玻璃茶几，粉紫色窗帘。
  强烈自然光从窗外射入形成光束。前景木质地柜上老式CRT电视机。
  灰白墙壁，嵌入式筒灯。清晨柔和暖光氛围。

tags: [酒店房间, 室内, 清晨, 阳光光束, 双人床, 暖色调, 私密空间]

ref_images:
  - path: 现代篇_酒店房间_早晨.jpg
```

## 使用原则

1. **brief 用于 AI 快速上下文**：当 AI 需要了解"这是谁/哪"时先读 brief，节省 token
2. **detail 用于 prompt 生成**：当需要写图像/视频生成 prompt 时读取 detail，保证一致性
3. **tags 用于搜索和匹配**：WebUI 中可按标签筛选 asset
4. **WebUI 中创建的 asset 也应生成此 YAML**：用户在 WebUI 添加 asset 时自动生成模板，用户可后续编辑补充
5. **AI Agent 在写任何剧本/prompt 前必须先读相关 asset YAML**
