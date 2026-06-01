from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any
from urllib import request
from urllib.parse import urlparse

from .project_io import build_request, create_dryrun, list_runs, now_id, now_iso, read_yaml, unique_path, write_json, write_yaml


RUNNINGHUB_HOST = "https://www.runninghub.cn"
RUNNINGHUB_GPT_IMAGE = {
    "text_to_image": "/openapi/v2/rhart-image-g-2/text-to-image",
    "image_to_image": "/openapi/v2/rhart-image-g-2/image-to-image",
}
RUNNINGHUB_SEEDANCE = "/openapi/v2/rhart-video/sparkvideo-2.0/multimodal-video"
DONE = {"SUCCESS", "FAILED", "FAILURE", "ERROR", "CANCELED", "CANCELLED"}


def run_job(root: Path, job_id: str, confirm_live: bool = False, timeout: int = 420, interval: int = 8) -> dict[str, Any]:
    job = read_yaml(root / "jobs" / job_id / "job.yaml")
    provider = job.get("provider", "dryrun")
    if provider == "dryrun":
        return create_dryrun(root, job_id)
    if not confirm_live:
        raise RuntimeError("Live provider requires confirm_live=true.")
    run_id, run_dir, out_dir = create_run_dir(root, job)
    mark_job_running(root, job, run_id)
    request_data = build_request(root, job)
    job = {**job, "params": request_data.get("params", job.get("params", {}))}
    request_data.update({"run_id": run_id, "created_at": now_iso(), "status": "submitted"})
    write_yaml(run_dir / "request.yaml", request_data)

    def bg_worker(worker_fn, cost_unit):
        try:
            payload, response, cost = worker_fn(root, job, run_dir, out_dir, timeout, interval)
            finish_run(root, job, run_id, run_dir, request_data, payload, response, cost)
        except Exception as exc:
            (run_dir / "error.txt").write_text(f"{type(exc).__name__}: {exc}", encoding="utf-8")
            try:
                finish_run(root, job, run_id, run_dir, request_data, {}, {"status": "FAILED", "error": str(exc)}, {"currency": "credits", "actual": None, "provider_unit": cost_unit})
            except Exception:
                pass

    if provider == "dreamina_image":
        fn, cu = _run_dreamina_image_bg, "dreamina_credits"
    elif provider == "dreamina_video":
        fn, cu = _run_dreamina_video_bg, "dreamina_credits"
    elif provider == "runninghub_gpt_image":
        fn, cu = _run_runninghub_gpt_image_sync, "runninghub_wallet"
    elif provider == "runninghub_seedance":
        fn, cu = _run_runninghub_seedance_sync, "runninghub_wallet"
    else:
        raise RuntimeError(f"Unsupported provider: {provider}")

    threading.Thread(target=bg_worker, args=(fn, cu), daemon=True).start()
    return {"job": job, "run": {"id": run_id, "status": "submitted"}}


def create_run_dir(root: Path, job: dict[str, Any]) -> tuple[str, Path, Path]:
    run_id = f"run_{now_id()}"
    run_dir = root / "jobs" / job["id"] / "runs" / run_id
    out_dir = run_dir / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    return run_id, run_dir, out_dir


def finish_run(root: Path, job: dict[str, Any], run_id: str, run_dir: Path, request_data: dict[str, Any], payload: dict[str, Any], response: dict[str, Any], cost: dict[str, Any]) -> dict[str, Any]:
    request_data.update({"run_id": run_id, "created_at": now_iso(), "status": response.get("status", "submitted")})
    write_yaml(run_dir / "request.yaml", request_data)
    write_json(run_dir / "payload.json", payload)
    write_json(run_dir / "response.json", response)
    write_yaml(run_dir / "cost.yaml", cost)
    job_path = root / "jobs" / job["id"] / "job.yaml"
    current = read_yaml(job_path)
    st = str(response.get("status", "")).upper()
    current["status"] = "succeeded" if st in {"SUCCESS", "SUCCEEDED"} else ("failed" if st in {"FAILED", "FAILURE", "ERROR"} else "submitted")
    runs = current.setdefault("runs", [])
    if run_id not in runs:
        runs.append(run_id)
    current["latest_run"] = run_id
    current["updated_at"] = now_iso()
    write_yaml(job_path, current)
    return {"job": current, "run": list_runs(job_path.parent)[-1]}


def _build_dreamina_image_cmd(root: Path, job: dict[str, Any]) -> list[str]:
    refs = existing_ref_paths(root, job)
    params = job.get("params", {}) or {}
    cmd = [dreamina_bin(), "image2image" if refs else "text2image", f"--prompt={job.get('prompt', '')}", f"--poll={int(params.get('poll_seconds', 300))}"]
    if refs: cmd.append("--images=" + ",".join(str(p) for p in refs[:10]))
    if params.get("aspect_ratio"): cmd.append(f"--ratio={params['aspect_ratio']}")
    if params.get("resolution"): cmd.append(f"--resolution_type={params['resolution']}")
    if params.get("model_version"): cmd.append(f"--model_version={params['model_version']}")
    return cmd


def _build_dreamina_video_cmd(root: Path, job: dict[str, Any]) -> list[str]:
    refs = existing_ref_paths(root, job)
    if not refs: raise RuntimeError("Dreamina video requires at least one reference image/video.")
    params = job.get("params", {}) or {}
    cmd = [dreamina_bin(), "multimodal2video", f"--prompt={job.get('prompt', '')}", f"--poll={int(params.get('poll_seconds', 420))}"]
    for path in refs[:9]: cmd.extend(["--image", str(path)])
    if params.get("duration_limit"): cmd.append(f"--duration={int(params['duration_limit'])}")
    if params.get("aspect_ratio"): cmd.append(f"--ratio={params['aspect_ratio']}")
    if params.get("model_version"): cmd.append(f"--model_version={params['model_version']}")
    cmd.append(f"--video_resolution={params.get('video_resolution', '720p')}")
    return cmd


def _run_dreamina_bg(root: Path, job: dict[str, Any], run_dir: Path, out_dir: Path, timeout: int, interval: int, cmd: list[str], cost_unit: str) -> tuple[dict, dict, dict]:
    """Run dreamina CLI command, poll, query results, return (payload, response, cost)."""
    cmd_str = " ".join(f'"{c}"' if " " in c else c for c in cmd)
    (run_dir / "command.txt").write_text(cmd_str, encoding="utf-8")
    stdout_f = (run_dir / "stdout.txt").open("wb")
    stderr_f = (run_dir / "stderr.txt").open("wb")
    proc = subprocess.Popen(cmd, stdout=stdout_f, stderr=stderr_f)
    proc.wait(timeout=900)
    stdout_f.close(); stderr_f.close()
    out_text = (run_dir / "stdout.txt").read_text(encoding="utf-8") if (run_dir / "stdout.txt").exists() else ""
    err_text = (run_dir / "stderr.txt").read_text(encoding="utf-8") if (run_dir / "stderr.txt").exists() else ""
    submit_id = extract_submit_id(out_text + "\n" + err_text)
    response = {"status": "SUBMITTED", "returncode": proc.returncode, "submit_id": submit_id}
    dr = _parse_dreamina_output(out_text)
    if dr:
        response["fail_reason"] = dr.get("fail_reason")
        response["credit_count"] = dr.get("credit_count")
        gs = dr.get("gen_status", "")
        if gs == "success": response["status"] = "SUCCESS"
        elif gs in ("fail", "failed", "failure", "error"): response["status"] = "FAILED"
    if submit_id:
        dcmd = [dreamina_bin(), "query_result", f"--submit_id={submit_id}", f"--download_dir={out_dir}"]
        payload = {"command": cmd, "download_command": dcmd}
        dproc = subprocess.run(dcmd, text=True, capture_output=True, timeout=600, encoding="utf-8", errors="replace")
        (run_dir / "query_stdout.txt").write_text(dproc.stdout or "", encoding="utf-8")
        (run_dir / "query_stderr.txt").write_text(dproc.stderr or "", encoding="utf-8")
        qr = _parse_dreamina_output(dproc.stdout or "")
        if qr:
            response["fail_reason"] = qr.get("fail_reason") or response.get("fail_reason")
            response["credit_count"] = qr.get("credit_count") or response.get("credit_count")
            gs2 = qr.get("gen_status", "")
            if gs2 == "success": response["status"] = "SUCCESS"
            elif gs2 in ("fail", "failed", "failure", "error"): response["status"] = "FAILED"
        elif dproc.returncode != 0: response["status"] = "FAILED"
        elif response.get("status") not in ("FAILED", "SUCCESS"): response["status"] = "SUCCESS"
    elif proc.returncode != 0:
        response["status"] = "FAILED"
        response["fail_reason"] = err_text.strip() or f"exit code {proc.returncode}"
    else:
        payload = {"command": cmd}
    cost = {"currency": "credits", "estimated": None, "actual": response.get("credit_count"), "provider_unit": cost_unit}
    return payload, response, cost


def retry_download_outputs(root: Path, job_id: str, run_id: str) -> dict[str, Any]:
    job_dir = root / "jobs" / job_id
    run_dir = job_dir / "runs" / run_id
    out_dir = run_dir / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    job = read_yaml(job_dir / "job.yaml")
    provider = str(job.get("provider") or "")
    response_path = run_dir / "response.json"
    response = json.loads(response_path.read_text(encoding="utf-8")) if response_path.exists() else {}
    payload_path = run_dir / "payload.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8")) if payload_path.exists() else {}

    downloaded: list[Path] = []
    if provider.startswith("runninghub"):
        final = response.get("query_response") or response
        downloaded = download_runninghub_results(out_dir, final)
    elif provider.startswith("dreamina"):
        submit_id = response.get("submit_id") or extract_submit_id(json.dumps(response, ensure_ascii=False))
        if not submit_id:
            raise RuntimeError("Dreamina submit_id not found in run response.")
        command = [dreamina_bin(), "query_result", f"--submit_id={submit_id}", f"--download_dir={out_dir}"]
        proc = subprocess.run(command, text=True, capture_output=True, timeout=600, encoding="utf-8", errors="replace")
        (run_dir / "retry_query_stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
        (run_dir / "retry_query_stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or f"query_result failed: {proc.returncode}").strip())
        payload["retry_download_command"] = command
        write_json(payload_path, payload)
        downloaded = [p for p in out_dir.iterdir() if p.is_file()]
    else:
        raise RuntimeError(f"Retry download is not supported for provider: {provider}")

    if not downloaded:
        raise RuntimeError("Provider reported success, but no downloadable output was found.")
    response["status"] = response.get("status") or "SUCCESS"
    response["outputs"] = [str(path) for path in downloaded]
    response["retried_download_at"] = now_iso()
    write_json(response_path, response)
    return {"downloaded": [str(path) for path in downloaded], "run": list_runs(job_dir)[-1]}


def _run_dreamina_image_bg(root, job, run_dir, out_dir, timeout, interval):
    return _run_dreamina_bg(root, job, run_dir, out_dir, timeout, interval, _build_dreamina_image_cmd(root, job), "dreamina_credits")


def _run_dreamina_video_bg(root, job, run_dir, out_dir, timeout, interval):
    return _run_dreamina_bg(root, job, run_dir, out_dir, timeout, interval, _build_dreamina_video_cmd(root, job), "dreamina_credits")


def mark_job_running(root: Path, job: dict[str, Any], run_id: str) -> None:
    job_path = root / "jobs" / job["id"] / "job.yaml"
    current = read_yaml(job_path)
    current["status"] = "submitted"
    runs = current.setdefault("runs", [])
    if run_id not in runs:
        runs.append(run_id)
    current["latest_run"] = run_id
    current["updated_at"] = now_iso()
    write_yaml(job_path, current)


def _run_runninghub_gpt_image_sync(root, job, run_dir, out_dir, timeout, interval):
    api_key = load_api_key(root)
    refs = existing_ref_paths(root, job)
    image_urls = [upload_file(path, api_key) for path in refs[:10]]
    mode = "image_to_image" if image_urls else "text_to_image"
    params = job.get("params", {}) or {}
    payload = {"prompt": job.get("prompt", ""), "aspectRatio": params.get("aspect_ratio", "16:9"), "resolution": params.get("resolution", "2k")}
    if image_urls: payload["imageUrls"] = image_urls
    submit_resp = post_json(RUNNINGHUB_GPT_IMAGE[mode], payload, api_key)
    task_id = submit_resp.get("taskId") or (submit_resp.get("data") or {}).get("taskId")
    if not task_id: raise RuntimeError(f"RunningHub did not create a task: {submit_resp}")
    write_json(run_dir / "payload.json", payload)
    write_runninghub_progress(run_dir, submit_resp, {"status": "SUBMITTED", "taskId": task_id})
    final = poll_runninghub(task_id, api_key, timeout, interval, lambda query: write_runninghub_progress(run_dir, submit_resp, query))
    downloaded = download_runninghub_results(out_dir, final)
    response = {"status": str(final.get("status") or (final.get("data") or {}).get("status") or "SUBMITTED"), "submit_response": submit_resp, "query_response": final, "outputs": [str(p) for p in downloaded]}
    usage = final.get("usage") or {}
    cost_actual = usage.get("thirdPartyConsumeMoney") or usage.get("consumeMoney")
    if cost_actual is not None: cost_actual = float(cost_actual)
    cost = {"currency": "CNY", "estimated": params.get("cost_estimate"), "actual": cost_actual, "provider_unit": "runninghub_wallet"}
    return payload, response, cost


def _run_runninghub_seedance_sync(root, job, run_dir, out_dir, timeout, interval):
    api_key = load_api_key(root)
    params = job.get("params", {}) or {}
    image_refs, video_refs, audio_refs = split_multimodal_refs(existing_ref_paths(root, job))
    image_urls = [upload_file(path, api_key) for path in image_refs[:9]]
    video_urls = [upload_file(path, api_key) for path in video_refs[:3]]
    audio_urls = [upload_file(path, api_key) for path in audio_refs[:3]]
    payload = {"prompt": job.get("prompt", ""), "resolution": params.get("resolution", "720p"), "duration": str(int(params.get("duration_limit", params.get("duration", 5)))), "imageUrls": image_urls, "videoUrls": video_urls, "audioUrls": audio_urls, "generateAudio": bool(params.get("generate_audio", True)), "ratio": params.get("aspect_ratio", "adaptive"), "realPersonMode": bool(params.get("real_person_mode", True)), "conversionSlots": params.get("conversion_slots", ["all"]), "returnLastFrame": bool(params.get("return_last_frame", False)), "seed": int(params.get("seed", -1) or -1)}
    submit_resp = post_json(RUNNINGHUB_SEEDANCE, payload, api_key)
    task_id = submit_resp.get("taskId") or (submit_resp.get("data") or {}).get("taskId")
    if not task_id: raise RuntimeError(f"RunningHub Seedance did not create a task: {submit_resp}")
    write_json(run_dir / "payload.json", payload)
    write_runninghub_progress(run_dir, submit_resp, {"status": "SUBMITTED", "taskId": task_id})
    final = poll_runninghub(task_id, api_key, timeout, interval, lambda query: write_runninghub_progress(run_dir, submit_resp, query))
    downloaded = download_runninghub_results(out_dir, final)
    response = {"status": str(final.get("status") or (final.get("data") or {}).get("status") or "SUBMITTED"), "submit_response": submit_resp, "query_response": final, "outputs": [str(p) for p in downloaded]}
    cost = {"currency": "CNY", "estimated": params.get("cost_estimate"), "actual": None, "provider_unit": "runninghub_wallet"}
    return payload, response, cost


def _parse_dreamina_output(text: str) -> dict[str, Any] | None:
    """Try to extract gen_status, fail_reason, credit_count from dreamina JSON output."""
    if not text:
        return None
    try:
        # Strip rtk noise prefix lines
        cleaned = re.sub(r'^\[rtk\].*?\n', '', text, flags=re.MULTILINE).strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start:end + 1])
    except (json.JSONDecodeError, TypeError):
        pass
    return None




def split_multimodal_refs(paths: list[Path]) -> tuple[list[Path], list[Path], list[Path]]:
    images, videos, audios = [], [], []
    for path in paths:
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
            images.append(path)
        elif suffix == ".mp4":
            videos.append(path)
        elif suffix in {".mp3", ".wav"}:
            audios.append(path)
    return images, videos, audios


def _resolve_bin_path(raw: str) -> str:
    """Resolve a binary path, trying .exe on Windows if needed."""
    if Path(raw).exists():
        return raw
    if os.name == "nt":
        with_exe = raw + ".exe"
        if Path(with_exe).exists():
            return with_exe
        without_exe = raw.removesuffix(".exe")
        if without_exe != raw and Path(without_exe).exists():
            return without_exe
    return raw


def dreamina_bin() -> str:
    env = os.environ.get("DREAMINA_BIN")
    if env:
        return _resolve_bin_path(env)
    cwd = Path.cwd()
    for _ in range(5):
        env_file = cwd / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("DREAMINA_BIN="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        return _resolve_bin_path(val)
        if cwd.parent == cwd:
            break
        cwd = cwd.parent
    return _resolve_bin_path(r"C:\Users\chchen1\bin\dreamina")


def extract_submit_id(text: str) -> str | None:
    patterns = [r'"submit_id"\s*:\s*"([^"]+)"', r'"submitId"\s*:\s*"([^"]+)"', r"submit_id[=:]\s*([A-Za-z0-9_-]+)", r"submitId[=:]\s*([A-Za-z0-9_-]+)"]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def existing_ref_paths(root: Path, job: dict[str, Any]) -> list[Path]:
    paths = []
    for ref in job.get("refs", []) or []:
        raw = ref.get("source_path") or ref.get("local_copy") or ref.get("path")
        if not raw:
            continue
        path = (root / raw).resolve()
        if path.exists() and path.is_file():
            paths.append(path)
    return paths


def find_env_upwards(start: Path) -> Path | None:
    current = start.resolve()
    for _ in range(10):
        candidate = current / ".env"
        if candidate.exists():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def load_api_key(root: Path) -> str:
    env_path = find_env_upwards(root)
    if env_path:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    api_key = os.environ.get("RUNNINGHUB_APIKEY")
    if not api_key:
        raise RuntimeError("RUNNINGHUB_APIKEY is missing. Add it to project .env, or any parent directory, or environment.")
    return api_key


def upload_file(path: Path, api_key: str) -> str:
    boundary = f"----GenUI{uuid.uuid4().hex}"
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    body = multipart_body(boundary, "file", path.name, content_type, path.read_bytes())
    req = request.Request(f"{RUNNINGHUB_HOST}/openapi/v2/media/upload/binary", data=body, method="POST", headers={"Authorization": f"Bearer {api_key}", "Content-Type": f"multipart/form-data; boundary={boundary}"})
    data = urlopen_json(req)
    return data["data"]["download_url"]


def post_json(endpoint: str, payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    url = endpoint if endpoint.startswith("http") else f"{RUNNINGHUB_HOST}{endpoint}"
    req = request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), method="POST", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    return urlopen_json(req)


def poll_runninghub(task_id: str, api_key: str, timeout: int, interval: int, on_update=None) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last = {}
    while True:
        last = post_json("/openapi/v2/query", {"taskId": task_id}, api_key)
        status = str(last.get("status") or (last.get("data") or {}).get("status") or "UNKNOWN")
        if on_update:
            on_update(last)
        if status in DONE or time.monotonic() >= deadline:
            return last
        time.sleep(interval)


def write_runninghub_progress(run_dir: Path, submit_response: dict[str, Any], query_response: dict[str, Any]) -> None:
    status = str(query_response.get("status") or (query_response.get("data") or {}).get("status") or "SUBMITTED")
    write_json(run_dir / "response.json", {"status": status, "submit_response": submit_response, "query_response": query_response})
    if status.upper() not in DONE:
        job_path = run_dir.parents[1] / "job.yaml"
        job = read_yaml(job_path)
        job["status"] = status.lower()
        job["updated_at"] = now_iso()
        write_yaml(job_path, job)


def download_runninghub_results(out_dir: Path, response: dict[str, Any]) -> list[Path]:
    results = response.get("results") or (response.get("data") or {}).get("results") or []
    downloaded = []
    for index, result in enumerate(results, start=1):
        if not isinstance(result, dict) or not result.get("url"):
            continue
        url = result["url"]
        suffix = extension_from_result(url, result.get("outputType"))
        path = unique_path(out_dir / f"candidate_{index:02d}{suffix}")
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
    return b"".join([f"--{boundary}\r\n".encode(), f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'.encode(), f"Content-Type: {content_type}\r\n\r\n".encode(), content, b"\r\n", f"--{boundary}--\r\n".encode()])


def urlopen_json(req: request.Request) -> dict[str, Any]:
    with request.urlopen(req, timeout=90) as response:
        raw = response.read().decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected JSON object response, got: {raw}")
    return data
