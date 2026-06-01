from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from PIL import Image, ImageDraw, ImageFont


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".gif", ".txt"}
PROVIDERS_BY_KIND = {
    "image": {"dryrun", "runninghub_gpt_image", "dreamina_image"},
    "video": {"dryrun", "runninghub_seedance", "dreamina_video"},
}


def now_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_project(root: Path) -> dict[str, Any]:
    root = root.resolve()
    task = read_yaml(root / "task.yaml")
    jobs_by_id = {}
    for job_dir in sorted((root / "jobs").glob("*")) if (root / "jobs").exists() else []:
        if not job_dir.is_dir():
            continue
        job_path = job_dir / "job.yaml"
        if not job_path.exists():
            continue
        job = read_yaml(job_path)
        job["_dir"] = str(job_dir)
        job["runs"] = list_runs(job_dir)
        jobs_by_id[job.get("id") or job_dir.name] = job
    jobs = []
    for item in task.get("jobs", []) or []:
        job_id = item.get("id")
        if job_id in jobs_by_id:
            jobs.append(jobs_by_id.pop(job_id))
    jobs.extend(jobs_by_id[job_id] for job_id in sorted(jobs_by_id))
    assets = scan_assets(root)
    approved = scan_approved(root)
    review = load_review(root)
    return {"root": str(root), "task": task, "jobs": jobs, "assets": assets, "approved": approved, "review": review}


def load_review(root: Path) -> dict[str, Any]:
    review_path = root / "review" / "review.yaml"
    if review_path.exists():
        review = read_yaml(review_path)
    else:
        review = create_initial_review(root)
        write_yaml(review_path, review)
    repaired = repair_review_previs(root, review)
    if repaired != review:
        review = repaired
        write_yaml(review_path, review)
    review.setdefault("_path", str(review_path.resolve()))
    return review


def repair_review_previs(root: Path, review: dict[str, Any]) -> dict[str, Any]:
    review = dict(review or {})
    task = read_yaml(root / "task.yaml")
    previs = dict(review.get("previs") or {})
    shot_plan_path = Path(str(previs.get("shot_plan") or "")) if previs.get("shot_plan") else None
    has_shot_plan = bool(shot_plan_path and shot_plan_path.exists())
    if not has_shot_plan:
        inferred = infer_shot_plan_dir(root, task)
        if inferred:
            shot_plan = inferred / "shot_plan.json"
            previs.update({
                "dir": str(inferred),
                "shot_plan": str(shot_plan) if shot_plan.exists() else "",
            })
            shot_plan_path = shot_plan if shot_plan.exists() else None
    if shot_plan_path and shot_plan_path.exists():
        try:
            shot_plan = json.loads(shot_plan_path.read_text(encoding="utf-8"))
            previs.setdefault("sequence_title", shot_plan.get("sequence_title") or task.get("project", {}).get("title", ""))
            review["items"] = merge_review_items(review.get("items", []) or [], shot_plan)
        except json.JSONDecodeError:
            pass
    if not previs.get("sequence_title"):
        previs["sequence_title"] = task.get("project", {}).get("title", "")
    review["previs"] = previs
    review.setdefault("schema_version", 1)
    review.setdefault("status", "in_review")
    review.setdefault("global_feedback", "")
    review.setdefault("items", [])
    return review


def infer_shot_plan_dir(root: Path, task: dict[str, Any]) -> Path | None:
    source = task.get("project", {}).get("source", {}) or {}
    explicit = resolve_source_path(root, source.get("shot_plan_dir")) or resolve_source_path(root, source.get("previs_dir"))
    if explicit and (explicit / "shot_plan.json").exists():
        return explicit
    generation_packet = resolve_source_path(root, source.get("generation_packet_dir"))
    candidates: list[Path] = []
    if generation_packet and generation_packet.name.startswith("generation_packet"):
        suffix = generation_packet.name.removeprefix("generation_packet")
        candidates.append(generation_packet.parent / f"storyboard{suffix}")
        candidates.append(generation_packet.parent / f"shot_plan{suffix}")
        candidates.append(generation_packet.parent / f"previs{suffix}")
    candidates.extend(root.parent.glob("storyboard*"))
    candidates.extend(root.parent.glob("shot_plan*"))
    candidates.extend(root.parent.glob("previs*"))
    valid = [p.resolve() for p in candidates if p.is_dir() and (p / "shot_plan.json").exists()]
    if not valid:
        return None
    return sorted(set(valid), key=lambda p: p.stat().st_mtime, reverse=True)[0]

def review_items_from_shot_plan(shot_plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [review_item_from_shot(shot, shot_plan) for shot in shot_plan.get("shots", []) or []]


def merge_review_items(existing: list[dict[str, Any]], shot_plan: dict[str, Any]) -> list[dict[str, Any]]:
    by_id = {item.get("id"): item for item in existing if item.get("id")}
    merged = []
    for shot in shot_plan.get("shots", []) or []:
        base = review_item_from_shot(shot, shot_plan)
        old = by_id.get(base.get("id"), {})
        for key in ["status", "feedback", "tags", "locked"]:
            if key in old:
                base[key] = old[key]
        merged.append(base)
    return merged


def review_item_from_shot(shot: dict[str, Any], shot_plan: dict[str, Any]) -> dict[str, Any]:
    shot_id = shot.get("id")
    segment = next((seg for seg in shot_plan.get("seedance_segments", []) or [] if shot_id in (seg.get("shots") or [])), {})
    task = next((task for task in shot_plan.get("video_tasks", []) or [] if shot_id in (task.get("shots") or [])), {})
    video_prompt = shot.get("video_prompt") or {}
    dialogue = " / ".join([d.get("text", "") for d in shot.get("dialogue_timing", []) or [] if d.get("text")]) or shot.get("dialogue", "")
    return {
        "id": shot_id,
        "title": shot.get("title", ""),
        "duration": shot.get("duration"),
        "type": shot.get("type", ""),
        "camera": shot.get("camera", ""),
        "dialogue": dialogue,
        "intent": shot.get("intent", ""),
        "review": shot.get("review", ""),
        "risk": shot.get("risk", ""),
        "recommendation": shot.get("recommendation", ""),
        "segment": f"{segment.get('id', '')} {segment.get('title', '')}".strip(),
        "video_task": f"{task.get('id', '')} {task.get('title', '')}".strip(),
        "prompt_preview": " / ".join([str(video_prompt.get("visual_action", "")), str(video_prompt.get("camera_motion", ""))]).strip(" /"),
        "status": "pending",
        "feedback": "",
        "tags": [],
        "locked": False,
    }


def save_review(root: Path, review: dict[str, Any]) -> dict[str, Any]:
    review = dict(review or {})
    review.pop("_path", None)
    review.setdefault("schema_version", 1)
    review["updated_at"] = now_iso()
    write_yaml(root / "review" / "review.yaml", review)
    return load_review(root)


def create_initial_review(root: Path) -> dict[str, Any]:
    task = read_yaml(root / "task.yaml")
    shot_plan_dir = infer_shot_plan_dir(root, task)
    shot_plan_path = shot_plan_dir / "shot_plan.json" if shot_plan_dir else None
    shots = []
    shot_plan = {}
    if shot_plan_path and shot_plan_path.exists():
        try:
            shot_plan = json.loads(shot_plan_path.read_text(encoding="utf-8"))
            shots = review_items_from_shot_plan(shot_plan)
        except json.JSONDecodeError:
            shots = []
    return {
        "schema_version": 1,
        "status": "in_review",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "previs": {
            "dir": str(shot_plan_dir) if shot_plan_dir else "",
            "shot_plan": str(shot_plan_path) if shot_plan_path and shot_plan_path.exists() else "",
            "sequence_title": shot_plan.get("sequence_title") or task.get("project", {}).get("title", ""),
        },
        "global_feedback": "",
        "items": shots,
    }


def resolve_source_path(root: Path, value: object) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = (root / path).resolve()
    return path


def export_iteration_brief(root: Path) -> dict[str, Any]:
    review = load_review(root)
    task = read_yaml(root / "task.yaml")
    brief_dir = unique_path(root / "review" / "iteration_briefs" / f"iteration_{now_id()}")
    brief_dir.mkdir(parents=True, exist_ok=True)
    brief_path = brief_dir / "brief.md"
    lines = build_iteration_brief(root, task, review)
    brief_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_yaml(brief_dir / "review_snapshot.yaml", review)
    return {"brief_path": str(brief_path.resolve()), "brief_dir": str(brief_dir.resolve()), "content": brief_path.read_text(encoding="utf-8")}


def build_iteration_brief(root: Path, task: dict[str, Any], review: dict[str, Any]) -> list[str]:
    project = task.get("project", {}) or {}
    previs = review.get("previs", {}) or {}
    items = review.get("items", []) or []
    needs_change = [item for item in items if item.get("status") == "needs_change" or item.get("feedback")]
    approved = [item for item in items if item.get("status") == "approved" or item.get("locked")]
    prompt = (
        "你是这个项目中的 AI 动画分镜 Agent。请读取本 brief、review.yaml、shot_plan 和当前 task.yaml，"
        "根据用户反馈迭代 shot_plan、多宫格 storyboard prompt 和生成任务。保持 approved 或 locked 镜头不变；"
        "只修改 needs_change、有 feedback，或全局反馈明确涉及的镜头。输出新版本目录，不覆盖旧版本。"
    )
    lines = [
        "# 分镜迭代 Brief",
        "",
        "## 给 AI Agent 的任务",
        prompt,
        "",
        "## 项目信息",
        f"- 项目目录：`{root}`",
        f"- 项目标题：{project.get('title', root.name)}",
        f"- Shot plan：`{previs.get('shot_plan', '')}`",
        f"- Review YAML：`{root / 'review' / 'review.yaml'}`",
        "",
        "## 全局反馈",
        review.get("global_feedback") or "无",
        "",
        "## 需要修改的镜头",
    ]
    if needs_change:
        for item in needs_change:
            lines.extend([
                f"- `{item.get('id')}` {item.get('title', '')}",
                f"  - 状态：{item.get('status', 'pending')}",
                f"  - 标签：{', '.join(item.get('tags', []) or []) or '无'}",
                f"  - 反馈：{item.get('feedback') or '无'}",
            ])
    else:
        lines.append("无逐镜头反馈，只按全局反馈判断。")
    lines.extend(["", "## 已批准 / 锁定镜头"])
    if approved:
        for item in approved:
            lines.append(f"- `{item.get('id')}` {item.get('title', '')}")
    else:
        lines.append("无")
    lines.extend([
        "",
        "## 输出要求",
        "- 在新的独立目录中输出新版本，不覆盖旧版。",
        "- 更新 shot_plan 中的镜头、时长、dialogue_timing、camera_motion、video_tasks。",
        "- 重新生成 storyboard grid prompt 和 WebUI task 项目。",
        "- 保留用户已添加的资产引用；复制参考图时同时复制同名 YAML。",
        "- 若反馈涉及跳轴、角色左右、运动方向、镜头移动，应优先通过多宫格 storyboard 检查。",
    ])
    return lines

def scan_assets(root: Path) -> list[dict[str, Any]]:
    assets = read_yaml(root / "task.yaml").get("assets", [])
    by_path = {}
    for asset in assets:
        for f in asset.get("files", []) or []:
            p = (root / f.get("path", "")).resolve()
            by_path[str(p)] = asset
    results = []
    assets_dir = root / "assets"
    if assets_dir.exists():
        for path in sorted(p for p in assets_dir.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS | VIDEO_EXTS):
            rel = path.relative_to(root).as_posix()
            asset = by_path.get(str(path.resolve()), {})
            results.append({
                "id": asset.get("id") or rel.replace("/", "_"),
                "label": asset.get("label") or path.stem,
                "type": asset.get("type") or path.parent.name,
                "path": rel,
                "abs_path": str(path.resolve()),
                "is_image": path.suffix.lower() in IMAGE_EXTS,
            })
    return results


def scan_approved(root: Path) -> list[dict[str, Any]]:
    out = []
    approved = root / "approved"
    if approved.exists():
        for path in sorted(p for p in approved.rglob("*") if p.is_file()):
            out.append({"path": path.relative_to(root).as_posix(), "abs_path": str(path.resolve()), "name": path.name})
    return out


def scan_deliverables(root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for job in list_jobs(root):
        job_id = job.get("id")
        if not job_id:
            continue
        job_dir = root / "jobs" / str(job_id)
        for marker in sorted(job_dir.glob("runs/*/approved/*.yaml")):
            approval = read_yaml(marker)
            approved_path = Path(str(approval.get("approved_path", "")))
            if not approved_path.exists() or not approved_path.is_file():
                continue
            run_id = marker.parents[1].name
            suffix = approved_path.suffix.lower()
            items.append({
                "id": f"{job_id}/{run_id}/{approved_path.name}",
                "job_id": job_id,
                "job_title": job.get("title", job_id),
                "job_kind": job.get("kind", ""),
                "run_id": run_id,
                "name": approved_path.name,
                "path": str(approved_path.resolve()),
                "rel_path": approved_path.relative_to(root).as_posix() if root in approved_path.resolve().parents else str(approved_path),
                "is_image": suffix in IMAGE_EXTS,
                "is_video": suffix in VIDEO_EXTS and suffix not in IMAGE_EXTS,
                "approved_at": approval.get("approved_at"),
            })
    return items


def export_deliverables(root: Path, file_paths: list[str], target_dir: Path) -> dict[str, Any]:
    target_dir.mkdir(parents=True, exist_ok=True)
    allowed = {item["path"]: item for item in scan_deliverables(root)}
    copied = []
    for raw in file_paths:
        item = allowed.get(str(Path(raw).resolve()))
        if not item:
            continue
        dest = unique_path(target_dir / Path(item["path"]).name)
        shutil.copy2(item["path"], dest)
        copied.append({"source": item["path"], "dest": str(dest.resolve()), "job_id": item["job_id"]})
    return {"target_dir": str(target_dir.resolve()), "copied": copied}


def list_runs(job_dir: Path) -> list[dict[str, Any]]:
    runs_dir = job_dir / "runs"
    runs = []
    if not runs_dir.exists():
        return runs
    recorded = set(read_yaml(job_dir / "job.yaml").get("runs", []) or [])
    for run_dir in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
        if recorded and run_dir.name not in recorded:
            continue
        request = read_yaml(run_dir / "request.yaml")
        response = {}
        resp_path = run_dir / "response.json"
        if resp_path.exists():
            try:
                response = json.loads(resp_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        payload = {}
        payload_path = run_dir / "payload.json"
        if payload_path.exists():
            try:
                payload = json.loads(payload_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        cost = read_yaml(run_dir / "cost.yaml")
        outputs = []
        out_dir = run_dir / "outputs"
        if out_dir.exists():
            for out in sorted(p for p in out_dir.iterdir() if p.is_file()):
                if out.name.endswith(".thumb.png"):
                    continue
                thumb = None
                if out.suffix.lower() in VIDEO_EXTS and out.suffix.lower() not in IMAGE_EXTS:
                    candidate = out.with_suffix(".thumb.png")
                    thumb = str(candidate.resolve()) if candidate.exists() else generate_video_thumbnail(job_dir.parent.parent, job_dir.name, run_dir.name, out.name)
                outputs.append({
                    "name": out.name,
                    "path": str(out.resolve()),
                    "rel_path": out.relative_to(job_dir.parent.parent).as_posix(),
                    "is_image": out.suffix.lower() in IMAGE_EXTS,
                    "is_video": out.suffix.lower() in VIDEO_EXTS and out.suffix.lower() not in IMAGE_EXTS,
                    "thumbnail": thumb,
                    "approved": bool(read_approval(job_dir.parent.parent, job_dir.name, run_dir.name, out.name)),
                    "approved_path": read_approval(job_dir.parent.parent, job_dir.name, run_dir.name, out.name).get("approved_path"),
                })
        runs.append({
            "id": run_dir.name,
            "dir": str(run_dir.resolve()),
            "created_at": request.get("created_at"),
            "provider": request.get("provider"),
            "status": response.get("status") or request.get("status", "unknown"),
            "fail_reason": response.get("fail_reason"),
            "credit_count": response.get("credit_count"),
            "cost": cost,
            "request": request,
            "payload": payload,
            "response": response,
            "outputs": outputs,
        })
    return runs


def save_job(root: Path, job_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    job_dir = root / "jobs" / job_id
    job_path = job_dir / "job.yaml"
    job = read_yaml(job_path)
    for key in ["title", "kind", "provider", "status", "prompt", "negative_prompt", "params", "refs"]:
        if key in patch:
            job[key] = patch[key]
    kind = job.get("kind", "image")
    if job.get("provider") not in PROVIDERS_BY_KIND.get(kind, {"dryrun"}):
        job["provider"] = "dryrun"
    job["updated_at"] = now_iso()
    write_yaml(job_path, job)
    return job


def create_job(root: Path, kind: str, title: str | None = None) -> dict[str, Any]:
    base = "video" if kind == "video" else "image"
    jobs_dir = root / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    index = 1
    while True:
        job_id = f"{base}_{index:03d}"
        job_dir = jobs_dir / job_id
        if not job_dir.exists():
            break
        index += 1
    (job_dir / "refs").mkdir(parents=True, exist_ok=True)
    (job_dir / "runs").mkdir(parents=True, exist_ok=True)
    job = {
        "schema_version": 1,
        "id": job_id,
        "kind": base,
        "title": title or ("新视频任务" if base == "video" else "新图像任务"),
        "provider": "dryrun",
        "status": "draft",
        "version": 1,
        "refs": [],
        "prompt": "",
        "params": {"aspect_ratio": "16:9", **({"duration_limit": 15} if base == "video" else {"resolution": "2k"})},
        "runs": [],
        "created_at": now_iso(),
    }
    write_yaml(job_dir / "job.yaml", job)
    task = read_yaml(root / "task.yaml")
    task.setdefault("jobs", []).append({"id": job_id, "kind": base, "title": job["title"], "provider": "dryrun", "status": "draft"})
    write_yaml(root / "task.yaml", task)
    return job


def move_job_in_task(root: Path, job_id: str, direction: str) -> None:
    task = read_yaml(root / "task.yaml")
    jobs = task.get("jobs", [])
    ids = [j.get("id") for j in jobs]
    try:
        idx = ids.index(job_id)
    except ValueError:
        return
    new_idx = idx - 1 if direction == "up" else idx + 1
    if new_idx < 0 or new_idx >= len(jobs):
        return
    jobs[idx], jobs[new_idx] = jobs[new_idx], jobs[idx]
    task["jobs"] = jobs
    write_yaml(root / "task.yaml", task)


def delete_job(root: Path, job_id: str) -> None:
    job_dir = root / "jobs" / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)
    task = read_yaml(root / "task.yaml")
    task["jobs"] = [j for j in task.get("jobs", []) if j.get("id") != job_id]
    write_yaml(root / "task.yaml", task)


def add_asset(root: Path, src: Path, asset_type: str, label: str | None = None) -> dict[str, Any]:
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(src)
    asset_type = asset_type if asset_type in {"characters", "scenes", "props", "misc"} else "misc"
    dest_dir = root / "assets" / asset_type
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = unique_path(dest_dir / src.name)
    shutil.copy2(src, dest)
    # Also copy YAML if exists
    yaml_src = src.with_suffix(".yaml")
    if yaml_src.exists():
        yaml_dest = dest.with_suffix(".yaml")
        shutil.copy2(yaml_src, yaml_dest)
    asset_id = f"asset_{safe_id(dest.stem)}"
    asset = {
        "id": asset_id,
        "type": asset_type[:-1] if asset_type.endswith("s") else asset_type,
        "label": label or dest.stem,
        "files": [{"path": dest.relative_to(root).as_posix(), "role": "reference"}],
    }
    task = read_yaml(root / "task.yaml")
    task.setdefault("assets", []).append(asset)
    write_yaml(root / "task.yaml", task)
    return asset


def delete_asset(root: Path, asset_path: str) -> None:
    target = (root / asset_path).resolve()
    root_resolved = root.resolve()
    if root_resolved not in target.parents or target == root_resolved:
        raise ValueError("asset path must stay inside project root")
    if target.exists() and target.is_file():
        target.unlink()
    task = read_yaml(root / "task.yaml")
    kept = []
    for asset in task.get("assets", []):
        files = asset.get("files", []) or []
        if any(f.get("path") == asset_path for f in files):
            continue
        kept.append(asset)
    task["assets"] = kept
    write_yaml(root / "task.yaml", task)


def open_directory(path: Path) -> None:
    target = path if path.is_dir() else path.parent
    if os.name == "nt":
        os.startfile(str(target))  # type: ignore[attr-defined]
    else:
        raise RuntimeError("open_directory is currently implemented for Windows only")


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    index = 2
    while True:
        candidate = path.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def safe_id(value: object) -> str:
    text = str(value or "item")
    return "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in text).strip("_") or "item"


def create_dryrun(root: Path, job_id: str) -> dict[str, Any]:
    job_dir = root / "jobs" / job_id
    job_path = job_dir / "job.yaml"
    job = read_yaml(job_path)
    run_id = f"run_{now_id()}"
    run_dir = job_dir / "runs" / run_id
    out_dir = run_dir / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    request_data = build_request(root, job)
    request_data.update({"run_id": run_id, "created_at": now_iso(), "status": "succeeded"})
    payload = {"provider": "dryrun", "job_id": job_id, "kind": job.get("kind"), "prompt": job.get("prompt", ""), "params": job.get("params", {}), "refs": request_data.get("refs", [])}
    response = {"status": "SUCCESS", "provider": "dryrun", "message": "Dummy output generated locally."}

    if job.get("kind") == "video":
        output = out_dir / f"{job_id}_{run_id}_dummy_video.gif"
        draw_dummy_gif(output, job, run_id)
    else:
        output = out_dir / f"{job_id}_{run_id}_dummy.png"
        draw_dummy_image(output, job, run_id, label="DUMMY IMAGE")

    write_yaml(run_dir / "request.yaml", request_data)
    write_json(run_dir / "payload.json", payload)
    write_json(run_dir / "response.json", response)
    write_yaml(run_dir / "cost.yaml", {"currency": "CNY", "estimated": 0, "actual": 0, "provider_unit": "dryrun", "notes": "dryrun is zero cost"})
    (run_dir / "run.log").write_text(f"{now_iso()} dryrun completed\n", encoding="utf-8")

    job["status"] = "succeeded"
    job.setdefault("runs", []).append(run_id)
    job["latest_run"] = run_id
    job["updated_at"] = now_iso()
    write_yaml(job_path, job)
    return {"job": job, "run": list_runs(job_dir)[-1]}


def build_request(root: Path, job: dict[str, Any]) -> dict[str, Any]:
    refs = []
    for ref in job.get("refs", []) or []:
        source = ref.get("source_path") or ref.get("local_copy") or ref.get("path") or ""
        path = (root / source).resolve() if source else None
        item = dict(ref)
        if path and path.exists():
            item["sha256"] = file_sha256(path)
            item["abs_path"] = str(path)
        refs.append(item)
    params = dict(job.get("params", {}) or {})
    estimated = (job.get("source") or {}).get("estimated_duration")
    if job.get("kind") == "video" and estimated and params.get("duration_limit") == 15:
        params["duration_limit"] = max(1, min(15, round(float(estimated))))
    return {
        "schema_version": 1,
        "job_id": job.get("id"),
        "kind": job.get("kind"),
        "provider": job.get("provider", "dryrun"),
        "prompt": job.get("prompt", ""),
        "negative_prompt": job.get("negative_prompt", ""),
        "params": params,
        "refs": refs,
    }


def draw_dummy_image(path: Path, job: dict[str, Any], run_id: str, label: str) -> None:
    width, height = 1280, 720
    img = Image.new("RGB", (width, height), "#d8dedb")
    draw = ImageDraw.Draw(img)
    font_big, font, font_small = load_fonts()
    draw.rectangle((0, 0, width, 90), fill="#263238")
    draw.text((32, 24), label, fill="#ffffff", font=font_big)
    draw.text((32, 130), f"Job: {job.get('id')} / {job.get('title', '')}", fill="#1d2b2a", font=font)
    draw.text((32, 170), f"Run: {run_id}  Provider: {job.get('provider', 'dryrun')}  Kind: {job.get('kind')}", fill="#1d2b2a", font=font)
    draw.text((32, 220), "Prompt summary:", fill="#2d4b4a", font=font)
    prompt = (job.get("prompt") or "").replace("\n", " ")[:360]
    for i, line in enumerate(wrap_text(prompt, 86)[:6]):
        draw.text((32, 260 + i * 30), line, fill="#263238", font=font_small)
    refs = job.get("refs", []) or []
    draw.text((32, 490), f"References: {len(refs)}", fill="#2d4b4a", font=font)
    for i, ref in enumerate(refs[:5]):
        draw.text((52, 530 + i * 28), f"- {ref.get('asset_id') or ref.get('source_path') or ref.get('local_copy')} ({ref.get('usage', 'ref')})", fill="#263238", font=font_small)
    draw.rectangle((930, 140, 1190, 400), outline="#607d8b", width=4)
    draw.line((930, 400, 1190, 140), fill="#607d8b", width=3)
    draw.text((956, 420), "output placeholder", fill="#455a64", font=font_small)
    img.save(path)


def load_fonts() -> tuple[ImageFont.ImageFont, ImageFont.ImageFont, ImageFont.ImageFont]:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                return (
                    ImageFont.truetype(str(candidate), 44),
                    ImageFont.truetype(str(candidate), 24),
                    ImageFont.truetype(str(candidate), 18),
                )
            except OSError:
                continue
    fallback = ImageFont.load_default()
    return fallback, fallback, fallback


def draw_dummy_gif(path: Path, job: dict[str, Any], run_id: str) -> None:
    frames = []
    for i in range(8):
        frame_path = path.with_suffix(f".frame{i}.png")
        draw_dummy_image(frame_path, job, run_id, label=f"DUMMY VIDEO FRAME {i + 1}")
        frame = Image.open(frame_path).convert("P")
        frames.append(frame)
        frame_path.unlink(missing_ok=True)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=260, loop=0)


def wrap_text(text: str, limit: int) -> list[str]:
    lines = []
    while text:
        lines.append(text[:limit])
        text = text[limit:]
    return lines or [""]


def approval_marker_path(root: Path, job_id: str, run_id: str, output_name: str) -> Path:
    return root / "jobs" / job_id / "runs" / run_id / "approved" / f"{safe_id(output_name)}.yaml"


def read_approval(root: Path, job_id: str, run_id: str, output_name: str) -> dict[str, Any]:
    return read_yaml(approval_marker_path(root, job_id, run_id, output_name))

def approve_output(root: Path, job_id: str, run_id: str, output_name: str) -> dict[str, Any]:
    job_dir = root / "jobs" / job_id
    src = job_dir / "runs" / run_id / "outputs" / output_name
    if not src.exists():
        raise FileNotFoundError(src)
    marker = approval_marker_path(root, job_id, run_id, output_name)
    existing = read_yaml(marker)
    if existing:
        approved_path = Path(str(existing.get("approved_path", "")))
        if approved_path.exists() and approved_path.is_file():
            approved_path.unlink()
        marker.unlink(missing_ok=True)
        return {"approved": False, "removed_path": str(approved_path) if approved_path else ""}

    kind = read_yaml(job_dir / "job.yaml").get("kind", "image")
    dest_dir = root / "approved" / ("videos" if kind == "video" else "images")
    dest_dir.mkdir(parents=True, exist_ok=True)
    existing_files = sorted(dest_dir.glob(f"{job_id}_{kind}_take_*{src.suffix}"))
    take = len(existing_files) + 1
    dest = dest_dir / f"{job_id}_{kind}_take_{take:03d}{src.suffix}"
    shutil.copy2(src, dest)
    approval = {"approved": True, "approved_path": str(dest.resolve()), "relative_path": dest.relative_to(root).as_posix(), "approved_at": now_iso()}
    write_yaml(marker, approval)
    return approval


def ensure_output_approved(root: Path, job_id: str, run_id: str, output_name: str) -> dict[str, Any]:
    existing = read_approval(root, job_id, run_id, output_name)
    approved_path = Path(str(existing.get("approved_path", ""))) if existing else None
    if existing and approved_path and approved_path.exists() and approved_path.is_file():
        return existing

    job_dir = root / "jobs" / job_id
    src = job_dir / "runs" / run_id / "outputs" / output_name
    if not src.exists():
        raise FileNotFoundError(src)

    kind = read_yaml(job_dir / "job.yaml").get("kind", "image")
    dest_dir = root / "approved" / ("videos" if kind == "video" else "images")
    dest_dir.mkdir(parents=True, exist_ok=True)
    existing_files = sorted(dest_dir.glob(f"{job_id}_{kind}_take_*{src.suffix}"))
    take = len(existing_files) + 1
    dest = dest_dir / f"{job_id}_{kind}_take_{take:03d}{src.suffix}"
    shutil.copy2(src, dest)
    approval = {"approved": True, "approved_path": str(dest.resolve()), "relative_path": dest.relative_to(root).as_posix(), "approved_at": now_iso()}
    write_yaml(approval_marker_path(root, job_id, run_id, output_name), approval)
    return approval

def promote_output_to_asset(
    root: Path,
    source_job_id: str,
    run_id: str,
    output_name: str,
    asset_type: str,
    usage: str,
    label: str,
    bind_mode: str,
    target_job_ids: list[str] | None = None,
    approve: bool = False,
) -> dict[str, Any]:
    source_job_dir = root / "jobs" / source_job_id
    src = source_job_dir / "runs" / run_id / "outputs" / output_name
    if not src.exists():
        raise FileNotFoundError(src)

    normalized_type = normalize_asset_type(asset_type)
    dest_dir = root / "assets" / "generated" / normalized_type
    dest_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"{safe_id(source_job_id)}_{safe_id(run_id)}_{safe_id(label or src.stem)}{src.suffix}"
    dest = unique_path(dest_dir / base_name)
    shutil.copy2(src, dest)

    rel = dest.relative_to(root).as_posix()
    asset_id = f"asset_{safe_id(normalized_type)}_{safe_id(source_job_id)}_{safe_id(run_id)}_{safe_id(output_name)}"
    asset = {
        "id": asset_id,
        "type": normalized_type,
        "label": label or src.stem,
        "files": [{"path": rel, "role": "reference"}],
        "provenance": {
            "source_job_id": source_job_id,
            "source_run_id": run_id,
            "source_output": output_name,
            "promoted_at": now_iso(),
        },
    }
    write_generated_asset_yaml(root, dest, asset, source_job_id, run_id, output_name)

    task = read_yaml(root / "task.yaml")
    task.setdefault("assets", []).append(asset)
    write_yaml(root / "task.yaml", task)

    target_ids = resolve_bind_targets(root, source_job_id, bind_mode, target_job_ids or [])
    ref = {"asset_id": asset_id, "source_path": rel, "usage": usage, "label": asset["label"]}
    for job_id in target_ids:
        add_ref_to_job(root, job_id, ref)

    approved = None
    if approve:
        approved = ensure_output_approved(root, source_job_id, run_id, output_name)

    return {"asset": asset, "bound_jobs": target_ids, "approved": approved}


def normalize_asset_type(asset_type: str) -> str:
    value = safe_id(asset_type or "generated")
    allowed = {"storyboard", "keyframe", "scene", "character", "style", "composition", "misc", "generated"}
    return value if value in allowed else "generated"


def write_generated_asset_yaml(root: Path, dest: Path, asset: dict[str, Any], source_job_id: str, run_id: str, output_name: str) -> None:
    source_job = read_yaml(root / "jobs" / source_job_id / "job.yaml")
    yaml_path = dest.with_suffix(".yaml")
    data = {
        "id": asset.get("id"),
        "name": asset.get("label") or dest.stem,
        "type": asset.get("type") or "generated",
        "brief": f"Generated {asset.get('type', 'asset')} from {source_job_id}/{run_id}.",
        "detail": "Generated project asset. Use provenance and source prompt to understand intended composition/reference role.",
        "tags": [asset.get("type") or "generated", "generated", "webui"],
        "ref_images": [{"path": dest.name, "role": "reference"}],
        "provenance": {
            "source_job_id": source_job_id,
            "source_run_id": run_id,
            "source_output": output_name,
            "source_job_title": source_job.get("title", ""),
            "source_prompt": source_job.get("prompt", ""),
            "promoted_at": now_iso(),
        },
    }
    write_yaml(yaml_path, data)


def resolve_bind_targets(root: Path, source_job_id: str, bind_mode: str, target_job_ids: list[str]) -> list[str]:
    jobs = list_jobs(root)
    ids = [j.get("id") for j in jobs]
    if bind_mode == "selected":
        return [j for j in target_job_ids if j in ids and j != source_job_id]
    if bind_mode == "current":
        return [source_job_id]
    if bind_mode == "matching_video":
        matched = matching_video_job_ids(jobs, source_job_id)
        if matched:
            return matched
        try:
            source_index = ids.index(source_job_id)
        except ValueError:
            source_index = -1
        return [j.get("id") for j in jobs[source_index + 1:] if j.get("kind") == "video"][:1] if source_index >= 0 else []
    try:
        source_index = ids.index(source_job_id)
    except ValueError:
        source_index = -1
    if bind_mode == "next":
        return [ids[source_index + 1]] if 0 <= source_index < len(ids) - 1 else []
    if bind_mode == "later_video":
        return [j.get("id") for j in jobs[source_index + 1:] if j.get("kind") == "video"] if source_index >= 0 else []
    return []


def matching_video_job_ids(jobs: list[dict[str, Any]], source_job_id: str) -> list[str]:
    source = next((job for job in jobs if job.get("id") == source_job_id), {})
    tokens = job_match_tokens(source_job_id, source.get("title", ""))
    numbers = job_match_numbers(source_job_id, source.get("title", ""), source.get("prompt", ""))
    matches = []
    for job in jobs:
        job_id = str(job.get("id") or "")
        if job_id == source_job_id or job.get("kind") != "video":
            continue
        haystack = f"{job_id} {job.get('title', '')}".lower()
        job_numbers = job_match_numbers(job_id, job.get("title", ""), job.get("prompt", ""))
        if any(token and token in haystack for token in tokens) or bool(numbers & job_numbers):
            matches.append(job_id)
    return matches[:1]


def job_match_tokens(job_id: str, title: str) -> list[str]:
    text = f"{job_id} {title}"
    tokens = []
    for pattern in [r"task[-_ ]?\d+", r"seg[-_ ]?\d+"]:
        tokens.extend(match.group(0).lower().replace("_", "-").replace(" ", "-") for match in re.finditer(pattern, text, re.IGNORECASE))
    cleaned = safe_id(job_id).lower()
    for suffix in ["_storyboard_grid", "-storyboard-grid", "_image_grid", "-image-grid", "_storyboard", "-storyboard", "_image", "-image"]:
        if cleaned.endswith(suffix):
            tokens.append(cleaned[: -len(suffix)].replace("_", "-"))
    return list(dict.fromkeys(tokens))


def job_match_numbers(*parts: object) -> set[str]:
    text = " ".join(str(part or "") for part in parts)
    values = set()
    for match in re.finditer(r"(?:task|seg)[-_ ]?(\d+)", text, re.IGNORECASE):
        raw = match.group(1)
        values.add(raw.lstrip("0") or "0")
    return values


def list_jobs(root: Path) -> list[dict[str, Any]]:
    jobs = []
    jobs_dir = root / "jobs"
    if not jobs_dir.exists():
        return jobs
    for job_dir in sorted(p for p in jobs_dir.iterdir() if p.is_dir()):
        job_path = job_dir / "job.yaml"
        if job_path.exists():
            jobs.append(read_yaml(job_path))
    return jobs


def add_ref_to_job(root: Path, job_id: str, ref: dict[str, Any]) -> None:
    job_path = root / "jobs" / job_id / "job.yaml"
    job = read_yaml(job_path)
    refs = job.setdefault("refs", [])
    if any(r.get("asset_id") == ref.get("asset_id") or r.get("source_path") == ref.get("source_path") for r in refs):
        return
    refs.append(dict(ref))
    job["updated_at"] = now_iso()
    write_yaml(job_path, job)


def create_project(parent_path: Path, name: str, title: str | None = None) -> dict[str, Any]:
    root = (parent_path / name).resolve()
    root.mkdir(parents=True, exist_ok=True)
    (root / "assets" / "characters").mkdir(parents=True, exist_ok=True)
    (root / "assets" / "scenes").mkdir(parents=True, exist_ok=True)
    (root / "assets" / "props").mkdir(parents=True, exist_ok=True)
    (root / "assets" / "misc").mkdir(parents=True, exist_ok=True)
    (root / "jobs").mkdir(exist_ok=True)
    (root / "approved" / "images").mkdir(parents=True, exist_ok=True)
    (root / "approved" / "videos").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(exist_ok=True)
    (root / "review").mkdir(exist_ok=True)

    project_title = title or name
    task = {
        "schema_version": 1,
        "project": {
            "id": name,
            "title": project_title,
            "created_at": now_iso(),
            "source": {},
        },
        "settings": {
            "default_provider": "dryrun",
            "live_requires_confirm": True,
            "max_concurrent_jobs": 1,
            "approved_naming": "{job_id}_{kind}_take_{take:03d}{ext}",
        },
        "assets": [],
        "jobs": [],
    }
    write_yaml(root / "task.yaml", task)
    write_yaml(root / "task.initial.yaml", task)
    return {"root": str(root), "task": task}


def read_asset_yaml(asset_path: Path) -> str:
    yaml_path = asset_path.with_suffix(".yaml")
    if yaml_path.exists():
        return yaml_path.read_text(encoding="utf-8")
    return ""


def save_asset_yaml(asset_path: Path, content: str) -> None:
    yaml_path = asset_path.with_suffix(".yaml")
    yaml_path.write_text(content, encoding="utf-8")


def delete_run_record(root: Path, job_id: str, run_id: str) -> None:
    """Remove run_id from job.yaml runs list without deleting files."""
    job_path = root / "jobs" / job_id / "job.yaml"
    job = read_yaml(job_path)
    runs = job.get("runs", [])
    job["runs"] = [r for r in runs if r != run_id]
    if job.get("latest_run") == run_id:
        job["latest_run"] = job["runs"][-1] if job["runs"] else None
    job["updated_at"] = now_iso()
    write_yaml(job_path, job)


def generate_video_thumbnail(root: Path, job_id: str, run_id: str, output_name: str) -> str | None:
    """Generate a PNG thumbnail from a video output using Pillow/PIL."""
    import struct
    output_path = root / "jobs" / job_id / "runs" / run_id / "outputs" / output_name
    if not output_path.exists():
        return None
    thumb_path = output_path.with_suffix(".thumb.png")
    if thumb_path.exists():
        return str(thumb_path.resolve())

    suffix = output_path.suffix.lower()
    if suffix == ".gif":
        from PIL import Image
        img = Image.open(output_path)
        img.seek(0)
        img.save(thumb_path, "PNG")
        return str(thumb_path.resolve())
    elif suffix in (".mp4", ".mov", ".webm"):
        return None

    return None


def capture_video_snapshot(root: Path, video_path: Path, seconds: float, label: str | None = None) -> dict[str, Any]:
    import subprocess
    from shutil import which
    root = root.resolve()
    video_path = video_path.resolve()
    if root not in video_path.parents:
        raise ValueError("video path must stay inside project root")
    if not video_path.exists() or not video_path.is_file():
        raise FileNotFoundError(video_path)
    ffmpeg = which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for backend video snapshot capture")
    dest_dir = root / "assets" / "generated" / "keyframe"
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_label = safe_id(label or f"{video_path.stem}_{int(seconds)}s")
    dest = unique_path(dest_dir / f"{safe_label}.png")
    cmd = [ffmpeg, "-y", "-ss", str(max(0, seconds)), "-i", str(video_path), "-frames:v", "1", "-update", "1", str(dest)]
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=60)
    if proc.returncode != 0 or not dest.exists():
        raise RuntimeError(proc.stderr[-1000:] or "ffmpeg snapshot failed")
    yaml_path = dest.with_suffix(".yaml")
    yaml_path.write_text("\n".join([
        f"id: {dest.stem}",
        f"name: {label or dest.stem}",
        "type: keyframe",
        f"ref_image: {dest.name}",
        "",
        "brief: |",
        f"  Snapshot captured from {video_path.name} at {seconds:.2f}s.",
        "",
        "detail: |",
        f"  Snapshot captured from {video_path.name} at {seconds:.2f}s.",
        "",
        "tags: [video_snapshot, keyframe]",
        "",
    ]), encoding="utf-8")
    task_path = root / "task.yaml"
    task = read_yaml(task_path)
    asset = {"id": f"asset_{dest.stem}", "type": "keyframe", "label": label or dest.stem, "files": [{"path": dest.relative_to(root).as_posix(), "role": "reference"}]}
    task.setdefault("assets", []).append(asset)
    write_yaml(task_path, task)
    return {"asset": asset, "path": str(dest.resolve()), "relative_path": dest.relative_to(root).as_posix()}

def scan_public_assets() -> list[dict[str, Any]]:
    """Scan root-level assets directory for reference images and YAML."""
    import sys
    root_assets = Path(__file__).resolve().parents[2] / "assets"
    results = []
    for subdir_name in ["chars", "scenes", "props", "misc"]:
        subdir = root_assets / subdir_name
        if not subdir.exists():
            continue
        for path in sorted(subdir.glob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
                continue
            yaml_path = path.with_suffix(".yaml")
            yaml_data = {}
            if yaml_path.exists():
                yaml_data = read_yaml(yaml_path) or {}
            results.append({
                "name": path.name,
                "abs_path": str(path.resolve()),
                "type": subdir_name,
                "label": yaml_data.get("name") or path.stem,
                "brief": yaml_data.get("brief", ""),
                "has_yaml": yaml_path.exists(),
                "is_image": True,
            })
    return results
    yaml_path.write_text(content, encoding="utf-8")








