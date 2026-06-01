from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


def main() -> None:
    parser = argparse.ArgumentParser(description="Import generation_packet_* into an AI Video GenUI task project.")
    parser.add_argument("--packet", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--assets", help="Optional reference asset directory to copy into assets/misc.")
    parser.add_argument("--shot-plan", dest="shot_plan", help="Optional project/storyboard directory containing shot_plan.json.")
    parser.add_argument("--previs", dest="legacy_previs", help=argparse.SUPPRESS)
    args = parser.parse_args()
    packet = Path(args.packet).resolve()
    out = Path(args.out).resolve()
    shot_plan_dir = Path(args.shot_plan or args.legacy_previs).resolve() if (args.shot_plan or args.legacy_previs) else None
    if not packet.exists():
        raise SystemExit(f"Packet not found: {packet}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "jobs").mkdir(exist_ok=True)
    (out / "assets" / "characters").mkdir(parents=True, exist_ok=True)
    (out / "assets" / "scenes").mkdir(parents=True, exist_ok=True)
    (out / "assets" / "misc").mkdir(parents=True, exist_ok=True)
    (out / "approved" / "images").mkdir(parents=True, exist_ok=True)
    (out / "approved" / "videos").mkdir(parents=True, exist_ok=True)
    (out / "logs").mkdir(exist_ok=True)

    assets = []
    if args.assets:
        assets.extend(copy_assets(Path(args.assets).resolve(), out))

    jobs = []
    for task_dir in sorted(p for p in packet.iterdir() if p.is_dir() and (p / "task.json").exists()):
        task = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
        jobs.extend(create_jobs(out, task_dir, task))

    title = infer_title(packet)
    project = {
        "schema_version": 1,
        "project": {
            "id": out.name,
            "title": title,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "source": {"generation_packet_dir": str(packet), **({"shot_plan_dir": str(shot_plan_dir)} if shot_plan_dir else {})},
        },
        "settings": {
            "default_provider": "dryrun",
            "live_requires_confirm": True,
            "max_concurrent_jobs": 1,
            "approved_naming": "{job_id}_{kind}_take_{take:03d}{ext}",
        },
        "assets": assets,
        "jobs": [{"id": job["id"], "kind": job["kind"], "title": job["title"], "provider": job["provider"], "status": job["status"]} for job in jobs],
    }
    write_yaml(out / "task.yaml", project)
    if not (out / "task.initial.yaml").exists():
        write_yaml(out / "task.initial.yaml", project)
    print(f"Imported {len(jobs)} jobs into {out}")


def infer_title(packet: Path) -> str:
    for task_json in packet.glob("*/task.json"):
        data = json.loads(task_json.read_text(encoding="utf-8"))
        if data.get("sequence_title"):
            return data["sequence_title"]
    return packet.name


def copy_assets(src: Path, out: Path) -> list[dict[str, Any]]:
    if not src.exists():
        return []
    assets = []
    for path in sorted(p for p in src.rglob("*") if p.is_file()):
        dest = out / "assets" / "misc" / path.name
        shutil.copy2(path, dest)
        assets.append({
            "id": safe_id(path.stem),
            "type": "misc",
            "label": path.stem,
            "files": [{"path": dest.relative_to(out).as_posix(), "role": "reference"}],
            "notes": "Imported reference asset.",
        })
    return assets


def create_jobs(out: Path, task_dir: Path, task: dict[str, Any]) -> list[dict[str, Any]]:
    task_id = task.get("task", {}).get("id") or safe_id(task_dir.name)
    task_title = task.get("task", {}).get("title") or task_dir.name
    image_prompt = read_text(task_dir / "imagegen" / "gpt_image_storyboard_grid_prompt.md")
    seedance_prompt = read_text(task_dir / "seedance" / "seedance_prompt.md")
    refs = initial_refs(task)
    jobs = []
    jobs.append(write_job(out, {
        "id": safe_id(f"{task_id}_image_grid"),
        "kind": "image",
        "title": f"{task_title} - 多宫格分镜图",
        "provider": "dryrun",
        "status": "ready",
        "version": 1,
        "refs": refs,
        "prompt": image_prompt,
        "params": {"aspect_ratio": "16:9", "resolution": "2k"},
        "source": {"packet_task_dir": str(task_dir), "task_id": task_id},
        "runs": [],
    }))
    jobs.append(write_job(out, {
        "id": safe_id(f"{task_id}_video"),
        "kind": "video",
        "title": f"{task_title} - 视频片段",
        "provider": "dryrun",
        "status": "ready",
        "version": 1,
        "refs": refs,
        "prompt": seedance_prompt,
        "params": {"duration_limit": 15, "aspect_ratio": "16:9"},
        "source": {"packet_task_dir": str(task_dir), "task_id": task_id},
        "runs": [],
    }))
    return jobs


def initial_refs(task: dict[str, Any]) -> list[dict[str, Any]]:
    refs = []
    for character in task.get("characters", []) or []:
        if character.get("role") == "threat":
            continue
        refs.append({"asset_id": f"asset_{safe_id(character.get('id') or character.get('name'))}", "usage": "identity", "label": character.get("visual") or character.get("name")})
    refs.append({"asset_id": "asset_scene", "usage": "scene", "label": "场景参考"})
    return refs


def write_job(out: Path, job: dict[str, Any]) -> dict[str, Any]:
    job_dir = out / "jobs" / job["id"]
    (job_dir / "refs").mkdir(parents=True, exist_ok=True)
    (job_dir / "runs").mkdir(parents=True, exist_ok=True)
    write_yaml(job_dir / "job.yaml", job)
    return job


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def safe_id(value: object) -> str:
    text = str(value or "job")
    return "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in text).strip("_") or "job"


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


if __name__ == "__main__":
    main()
