# AI Video GenUI

本地单用户 AI 动画生成任务工作台。Review 核心是 `shot_plan + 多宫格分镜图`，Execute 负责图像/视频任务运行和输出批准。

## 启动

```powershell
cd E:\VideoProjects\BSDAnime\ai_video_gen_full\webui
uv sync
npm install
npm run build
uv run uvicorn app.main:app --host 127.0.0.1 --port 8787
```

访问：`http://127.0.0.1:8787`

开发模式可另开 Vite：

```powershell
npm run dev
```

## 页面

- `Review`：读取 `review/review.yaml` 和 `shot_plan.json`，逐 shot 记录反馈，导出 iteration brief。
- `Execute`：编辑 image/video jobs、prompt、params、refs，执行 dryrun/live provider，approve 或 promote 输出。
- `Assets`：管理项目资产、复制全局资产、编辑同名 YAML。

## 项目目录

```text
task_project/
  task.yaml
  jobs/<job_id>/job.yaml
  jobs/<job_id>/runs/<run_id>/
  assets/
  approved/images/
  approved/videos/
  review/review.yaml
  review/iteration_briefs/
```

目录即数据库。WebUI 不内置 AI 聊天；迭代通过 `Export Brief` 交给外部 AI Agent。
