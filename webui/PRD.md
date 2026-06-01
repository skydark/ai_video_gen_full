# AI Video GenUI PRD（当前版）

> 本文档描述当前 `shot_plan + storyboard grid` 流程。若需要历史设计，请查看 git 历史。

## 背景

WebUI 是本地 AI 动画生成任务工作台，服务当前流程：

```text
粗脚本/改编大纲 -> shot_plan.json -> storyboard grid/关键帧 -> WebUI Review/Execute -> approved outputs
```

WebUI 不内置 AI 聊天。AI Agent 负责读取剧本、资产 YAML 和 review brief，生成或迭代项目文件；WebUI 负责审阅、编辑、运行、记录和批准输出。

## 目标

- 加载 `task_project/` 目录。
- 在 Review 页按 `shot_plan.json` 检查 shot、segment 和 storyboard grid。
- 在 Execute 页编辑 image/video jobs、refs、provider/model/params，并执行 dryrun/live provider。
- 管理项目资产和全局资产，项目使用的资产复制到当前项目目录。
- 记录每次 run 的 request、payload、response、outputs、cost 和 status。
- 成功输出可在 Runs 中 approve/unapprove；approved 状态直接在 run 卡片上显示。
- 视频 run 支持缩略图、播放、按时间截帧到 assets。

## 非目标

- 不做多用户、远程部署或数据库。
- 不承担最终剪辑 timeline。
- 不自动优化 prompt。
- 不主动付费提交 provider；live provider 必须由用户明确确认。
- 不支持旧式网页预览作为 review 主路径。

## 项目目录

```text
task_project/
  task.yaml
  task.initial.yaml
  assets/
  jobs/<job_id>/
    job.yaml
    refs/
    runs/<run_id>/
      request.yaml
      payload.json
      response.json
      outputs/
      cost.yaml
  approved/images/
  approved/videos/
  review/review.yaml
  review/iteration_briefs/
```

目录就是数据库。`review.yaml` 中如仍出现 `previs` 字段，只是旧 WebUI 兼容字段名，用来保存 `shot_plan` 路径。

## 页面

- `Review`：读取 `review/review.yaml` 和 `shot_plan.json`，按 segment/shot 记录反馈，可触发 storyboard grid 图像任务。
- `Execute`：管理 Jobs、Project Assets、References、Runs；支持 job/references 排序、执行、approve、截帧。
- `Assets`：扫描/导入全局资产，复制图片和同名 YAML 到项目资产区。
