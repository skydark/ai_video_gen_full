# 分镜迭代 Brief

## 给 AI Agent 的任务
你是这个项目中的 AI 动画分镜 Agent。请读取本 brief、review.yaml、shot_plan 和当前 task.yaml，根据用户反馈迭代 shot_plan、多宫格 storyboard prompt 和生成任务。保持 approved 或 locked 镜头不变；只修改 needs_change、有 feedback，或全局反馈明确涉及的镜头。输出新版本目录，不覆盖旧版本。

## 项目信息
- 项目目录：`E:\VideoProjects\BSDAnime\ai_video_gen_full\projects\bsd_1_7_6_v001\task_project`
- 项目标题：BSD 1-7-6 蕾的料理惨剧与婚姻观
- Shot plan：`E:\VideoProjects\BSDAnime\ai_video_gen_full\projects\bsd_1_7_6_v001\shot_plan.json`
- Review YAML：`E:\VideoProjects\BSDAnime\ai_video_gen_full\projects\bsd_1_7_6_v001\task_project\review\review.yaml`

## 全局反馈
无

## 需要修改的镜头
- `S005` 料理无能对话（轴线建立）
  - 状态：pending
  - 标签：无
  - 反馈：刀只是在上一个镜头有用，到了这个镜头就让蕾收起刀，不要让观众再注意。
- `S006` 甲一怔（听者反应）
  - 状态：pending
  - 标签：无
  - 反馈：“背景为虚化花园绿植和午后光斑。”背景就是宿舍后院，由参考图指导，不要添加错误的描述。
- `S012` 饭香唤回+淡出
  - 状态：pending
  - 标签：无
  - 反馈：两人应该向宿舍建筑(厨房)方向转头，而不是“右侧”，除非之前要求建筑必须在画面右侧。

## 已批准 / 锁定镜头
无

## 输出要求
- 在新的独立目录中输出新版本，不覆盖旧版。
- 更新 shot_plan 中的镜头、时长、dialogue_timing、camera_motion、video_tasks。
- 重新生成 storyboard grid prompt 和 WebUI task 项目。
- 保留用户已添加的资产引用；复制参考图时同时复制同名 YAML。
- 若反馈涉及跳轴、角色左右、运动方向、镜头移动，应优先通过多宫格 storyboard 检查。
