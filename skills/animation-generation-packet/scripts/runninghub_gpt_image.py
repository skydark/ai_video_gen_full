#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import time
import uuid
from pathlib import Path
from typing import Any
from urllib import request
from urllib.parse import urlparse


RUNNINGHUB_HOST = "https://www.runninghub.cn"
ENDPOINTS = {
    "text_to_image": "/openapi/v2/rhart-image-g-2/text-to-image",
    "image_to_image": "/openapi/v2/rhart-image-g-2/image-to-image",
}
DONE = {"SUCCESS", "FAILED", "FAILURE", "ERROR", "CANCELED", "CANCELLED"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare or submit RunningHub GPT-image storyboard jobs.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("prepare", help="Write job JSON and dry-run payloads. No upload or billing.")
    p.add_argument("--packet", required=True, help="Generation packet directory.")
    p.add_argument("--out", required=True, help="Output directory for RunningHub jobs.")
    p.add_argument("--task", action="append", help="Task id to prepare, e.g. TASK-01. Repeatable. Defaults to all tasks.")
    p.add_argument("--ref", action="append", default=[], help="Reference image mapping, e.g. protagonist=refs/protagonist.jpg. Repeatable.")
    p.add_argument("--aspect-ratio", default="16:9")
    p.add_argument("--resolution", default="2k")
    p.add_argument("--no-background", action="store_true", help="Do not prepare a text-to-image scene background job.")

    s = sub.add_parser("submit", help="Submit one prepared job. Requires --live and --confirm-cost.")
    s.add_argument("--job", required=True, help="Prepared job JSON path.")
    s.add_argument("--env", default=".env", help="Env file containing RUNNINGHUB_APIKEY.")
    s.add_argument("--live", action="store_true", help="Actually upload references and submit a paid RunningHub task.")
    s.add_argument("--confirm-cost", action="store_true", help="Required with --live to acknowledge billing.")
    s.add_argument("--poll", action="store_true", help="Poll and download after submit.")
    s.add_argument("--timeout", type=int, default=240)
    s.add_argument("--interval", type=int, default=5)

    q = sub.add_parser("poll", help="Poll an already submitted job and download outputs.")
    q.add_argument("--job", required=True)
    q.add_argument("--env", default=".env")
    q.add_argument("--timeout", type=int, default=240)
    q.add_argument("--interval", type=int, default=5)

    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args)
    elif args.command == "submit":
        submit(args)
    elif args.command == "poll":
        poll(args)


def prepare(args: argparse.Namespace) -> None:
    packet = Path(args.packet).resolve()
    out = Path(args.out).resolve()
    refs = parse_refs(args.ref)
    out.mkdir(parents=True, exist_ok=True)

    task_dirs = discover_task_dirs(packet, set(args.task or []))
    if not task_dirs:
        raise SystemExit(f"No task directories found in {packet}")

    plan_title = ""
    jobs: list[Path] = []
    if not args.no_background:
        first_task = read_json(task_dirs[0] / "task.json")
        plan_title = first_task.get("sequence_title", "动画场景")
        bg_prompt = build_background_prompt(first_task)
        jobs.append(write_job(out, "BG-001_battlefield_scene", "text_to_image", bg_prompt, [], args.aspect_ratio, args.resolution))

    refs = add_generated_scene_ref(out, refs)

    for task_dir in task_dirs:
        task = read_json(task_dir / "task.json")
        plan_title = plan_title or task.get("sequence_title", "动画分镜")
        prompt_path = task_dir / "imagegen" / "gpt_image_storyboard_grid_prompt.md"
        if not prompt_path.exists():
            continue
        prompt = prompt_path.read_text(encoding="utf-8")
        prompt = build_storyboard_prompt(task, prompt, refs)
        job_id = f"{task['task']['id']}_storyboard_grid"
        jobs.append(write_job(out, job_id, "image_to_image", prompt, refs, args.aspect_ratio, args.resolution))

    manifest = out / "README.md"
    manifest.write_text(build_readme(plan_title, jobs), encoding="utf-8")
    print(f"Prepared {len(jobs)} RunningHub job(s): {out}")


def submit(args: argparse.Namespace) -> None:
    if not args.live or not args.confirm_cost:
        raise SystemExit("Paid submit requires both --live and --confirm-cost.")
    job_path = Path(args.job).resolve()
    job = read_json(job_path)
    api_key = load_api_key(Path(args.env))

    image_urls = [upload_file(Path(ref["path"]), api_key) for ref in job.get("reference_images", [])]
    payload = payload_for_job(job, image_urls)
    response = post_json(job["endpoint"], payload, api_key)
    task_id = response.get("taskId") or (response.get("data") or {}).get("taskId")
    error_code = response.get("errorCode") or response.get("code")
    if error_code or not task_id:
        job["rh"] = {"status": "SUBMIT_FAILED", "last_submit_response": response}
        write_json(job_path, job)
        raise SystemExit(f"RunningHub did not create a task: {response}")

    job["rh"] = {
        "task_id": task_id,
        "status": response.get("status", "submitted"),
        "submitted_at_unix": int(time.time()),
        "last_submit_response": response,
    }
    write_json(job_path, job)
    print(f"Submitted {job['id']}: task_id={task_id}")
    if args.poll:
        poll(args)


def poll(args: argparse.Namespace) -> None:
    job_path = Path(args.job).resolve()
    job = read_json(job_path)
    api_key = load_api_key(Path(args.env))
    task_id = (job.get("rh") or {}).get("task_id")
    if not task_id:
        raise SystemExit(f"Job has no rh.task_id: {job_path}")

    deadline = time.monotonic() + args.timeout
    status = "UNKNOWN"
    last: dict[str, Any] = {}
    while True:
        last = post_json("/openapi/v2/query", {"taskId": task_id}, api_key)
        status = str(last.get("status") or (last.get("data") or {}).get("status") or "UNKNOWN")
        rh = job.setdefault("rh", {})
        rh["status"] = status
        rh["last_query_unix"] = int(time.time())
        rh["last_query_response"] = last
        write_json(job_path, job)
        if status in DONE or time.monotonic() >= deadline:
            break
        time.sleep(args.interval)

    downloaded = []
    if status == "SUCCESS":
        downloaded = download_results(job_path, job, last)
        job["outputs"] = [str(p) for p in downloaded]
        write_json(job_path, job)
    print(f"Poll {job['id']}: status={status}, downloaded={len(downloaded)}")


def parse_refs(values: list[str]) -> list[dict[str, str]]:
    refs = []
    for value in values:
        if "=" not in value:
            raise SystemExit(f"Invalid --ref, expected id=path: {value}")
        ref_id, raw = value.split("=", 1)
        path = Path(raw).resolve()
        if not path.exists():
            raise SystemExit(f"Reference image not found: {path}")
        refs.append({"id": ref_id.strip(), "path": str(path), "name": path.name})
    return refs


def add_generated_scene_ref(out: Path, refs: list[dict[str, str]]) -> list[dict[str, str]]:
    if any(ref["id"] == "scene" for ref in refs):
        return refs
    bg_outputs = out / "BG-001_battlefield_scene" / "outputs"
    if not bg_outputs.exists():
        return refs
    candidates = sorted(
        p for p in bg_outputs.iterdir()
        if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    )
    if not candidates:
        return refs
    scene = candidates[0].resolve()
    return [*refs, {"id": "scene", "path": str(scene), "name": scene.name}]


def discover_task_dirs(packet: Path, wanted: set[str]) -> list[Path]:
    dirs = []
    for child in sorted(packet.iterdir() if packet.exists() else []):
        task_json = child / "task.json"
        if not task_json.exists():
            continue
        task = read_json(task_json)
        task_id = task.get("task", {}).get("id")
        if wanted and task_id not in wanted:
            continue
        dirs.append(child)
    return dirs


def write_job(out: Path, job_id: str, mode: str, prompt: str, refs: list[dict[str, str]], aspect: str, resolution: str) -> Path:
    job_dir = out / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    job = {
        "id": job_id,
        "mode": mode,
        "endpoint": ENDPOINTS[mode],
        "prompt": prompt,
        "reference_images": refs,
        "rh": {"aspect_ratio": aspect, "resolution": resolution, "status": "DRY_RUN"},
    }
    job_path = job_dir / "job.json"
    write_json(job_path, job)
    dry = {
        "notes": [
            "Dry-run only. No file upload, network request, or RunningHub billing happened.",
            "For image_to_image, placeholder imageUrls preserve the local reference image order.",
        ],
        "job": job,
        "payload_preview": payload_for_job(job, [f"RH_UPLOAD_URL_{i+1}" for i, _ in enumerate(refs)]),
    }
    write_json(job_dir / "dry_run.json", dry)
    (job_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    return job_path


def payload_for_job(job: dict[str, Any], image_urls: list[str]) -> dict[str, Any]:
    rh = job.get("rh") or {}
    payload = {
        "prompt": job["prompt"],
        "aspectRatio": rh.get("aspect_ratio", "16:9"),
        "resolution": rh.get("resolution", "2k"),
    }
    if job["mode"] == "image_to_image":
        payload["imageUrls"] = image_urls
    return payload


def build_background_prompt(task: dict[str, Any]) -> str:
    segments = task.get("segments") or []
    focus = "；".join(s.get("prompt_focus", "") for s in segments if s.get("prompt_focus"))
    return f"""生成一张动画场景参考图，用于后续分镜和视频生成的背景一致性参考。

画面内容：灰暗天空下的战场，远处爆炸火光和浓烟，地面有破损金属残骸、尘土、战壕或废墟结构，空间纵深清楚。不要出现具体主角，不要出现文字。

用途：作为场景、光线、天气、空间结构参考图。画面需要清楚可读，方便后续把角色放入同一战场环境。

剧情氛围：{task.get('sequence_title', '动画场景')}。{focus}

风格：日本动画/漫剧制作参考图，低饱和、灰蓝烟尘、远处橙色爆炸光，16:9 横图，构图稳定。"""


def build_storyboard_prompt(task: dict[str, Any], markdown_prompt: str, refs: list[dict[str, str]]) -> str:
    characters = {c.get("id"): c for c in task.get("characters", [])}
    ref_lines = []
    for index, ref in enumerate(refs, start=1):
        c = characters.get(ref["id"])
        if ref["id"] == "scene":
            desc = "场景参考图，只用于战场环境、光线、天气和空间结构"
        elif c:
            desc = f"{c.get('name', ref['id'])}，{c.get('visual', '')}，只用于角色身份、颜色、轮廓和姿态参考"
        else:
            desc = f"{ref['id']} 参考图，只用于对应素材外观"
        ref_lines.append(f"参考图{index}（{ref['name']}）：{desc}。")

    clean_prompt = sanitize_storyboard_prompt(markdown_prompt)

    return f"""请根据以下参考图和分镜要求，生成一张便于检查的多宫格分镜草稿图。

参考图顺序：
{chr(10).join(ref_lines) if ref_lines else '无角色参考图；按文字生成临时草稿。'}

重要规则：参考图只用于锁定角色/场景外观；下面的分镜文字用于锁定分格数量、构图、左右关系、过肩方向、动作起止和镜头运动。不要把文件名、编号、制作说明或长段文字画进图片。

{clean_prompt}"""


def sanitize_storyboard_prompt(markdown_prompt: str) -> str:
    """Remove packet-local references before sending text to an image model."""
    kept: list[str] = []
    skipping_refs = False
    for raw in markdown_prompt.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith("# GPT-Image"):
            continue
        if stripped.startswith("## 使用参考图"):
            skipping_refs = True
            continue
        if skipping_refs and stripped.startswith("## "):
            skipping_refs = False
        if skipping_refs:
            continue
        if "placeholder" in stripped or "@构图参考图" in stripped:
            continue
        line = line.replace("GPT-Image", "图像模型")
        line = line.replace("可 review", "便于检查")
        line = line.replace("review", "检查")
        line = line.replace("contact sheet", "多宫格分镜图")
        line = line.replace("shot plan", "分镜设计")
        line = line.replace("使用构图参考图只锁定构图、机位、blocking、左右关系和运动方向，不作为画风参考。", "严格按分格文字锁定构图、机位、blocking、左右关系和运动方向。")
        kept.append(line)
    text = "\n".join(kept).strip()
    import re
    text = re.sub(r"\bTASK-\d+\b", "", text)
    text = re.sub(r"\bS\d{3}\b", "", text)
    return text + "\n"


def build_readme(title: str, jobs: list[Path]) -> str:
    lines = [f"# RunningHub GPT-image Jobs - {title}", "", "默认已生成 dry-run，不会扣费。", ""]
    lines.append("## Jobs")
    for job in jobs:
        lines.append(f"- `{job}`")
    lines.extend([
        "",
        "## Submit Example",
        "",
        "```bash",
        "python skills/animation-generation-packet/scripts/runninghub_gpt_image.py submit --job <job.json> --live --confirm-cost --poll",
        "```",
    ])
    return "\n".join(lines) + "\n"


def load_api_key(env_path: Path) -> str:
    env_path = env_path.resolve()
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() and key.strip() not in os.environ:
                os.environ[key.strip()] = value.strip().strip('"').strip("'")
    api_key = os.environ.get("RUNNINGHUB_APIKEY")
    if not api_key:
        raise SystemExit("RUNNINGHUB_APIKEY is missing. Add it to .env or environment.")
    return api_key


def upload_file(path: Path, api_key: str) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    boundary = f"----AnimationPrevis{uuid.uuid4().hex}"
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    body = multipart_body(boundary, "file", path.name, content_type, path.read_bytes())
    req = request.Request(
        f"{RUNNINGHUB_HOST}/openapi/v2/media/upload/binary",
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    data = urlopen_json(req)
    try:
        return data["data"]["download_url"]
    except KeyError as exc:
        raise RuntimeError(f"Upload response did not include data.download_url: {data}") from exc


def post_json(endpoint: str, payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    req = request.Request(
        f"{RUNNINGHUB_HOST}{endpoint}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    return urlopen_json(req)


def download_results(job_path: Path, job: dict[str, Any], response: dict[str, Any]) -> list[Path]:
    results = response.get("results") or (response.get("data") or {}).get("results") or []
    if not isinstance(results, list):
        raise RuntimeError(f"Unexpected results field: {results}")
    out = job_path.parent / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    downloaded = []
    for index, result in enumerate(results, start=1):
        if not isinstance(result, dict) or not result.get("url"):
            continue
        url = result["url"]
        suffix = extension_from_result(url, result.get("outputType"))
        path = out / f"candidate_{index:02d}{suffix}"
        req = request.Request(url, method="GET")
        with request.urlopen(req, timeout=180) as resp:
            path.write_bytes(resp.read())
        downloaded.append(path)
    return downloaded


def extension_from_result(url: str, output_type: object) -> str:
    if isinstance(output_type, str) and output_type:
        normalized = output_type.lower().lstrip(".")
        return ".jpg" if normalized == "jpeg" else f".{normalized}"
    return Path(urlparse(url).path).suffix or ".png"


def multipart_body(boundary: str, field: str, filename: str, content_type: str, content: bytes) -> bytes:
    return b"".join([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'.encode(),
        f"Content-Type: {content_type}\r\n\r\n".encode(),
        content,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])


def urlopen_json(req: request.Request) -> dict[str, Any]:
    with request.urlopen(req, timeout=90) as response:
        raw = response.read().decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected JSON object response, got: {raw}")
    return data


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
