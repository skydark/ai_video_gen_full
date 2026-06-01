from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .project_io import add_asset, approve_output, create_job, create_project, delete_asset, delete_job, delete_run_record, export_deliverables, export_iteration_brief, generate_video_thumbnail, load_project, move_job_in_task, open_directory, promote_output_to_asset, read_asset_yaml, save_asset_yaml, save_job, save_review, scan_deliverables, scan_public_assets, unique_path, capture_video_snapshot
from .providers import retry_download_outputs, run_job


APP_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = APP_DIR / "dist"

app = FastAPI(title="AI Video GenUI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProjectRequest(BaseModel):
    root: str


class ProjectListRequest(BaseModel):
    base: str | None = None


class FsListRequest(BaseModel):
    path: str | None = None


class JobSaveRequest(BaseModel):
    root: str
    job: dict[str, Any]


class JobActionRequest(BaseModel):
    root: str
    job_id: str
    confirm_live: bool = False
    timeout: int = 420
    interval: int = 8


class CreateJobRequest(BaseModel):
    root: str
    kind: str = "image"
    title: str | None = None


class DeleteJobRequest(BaseModel):
    root: str
    job_id: str


class MoveJobRequest(BaseModel):
    root: str
    job_id: str
    direction: str = "up"


class AddAssetRequest(BaseModel):
    root: str
    path: str
    type: str = "misc"
    label: str | None = None


class DeleteAssetRequest(BaseModel):
    root: str
    path: str


class OpenDirRequest(BaseModel):
    path: str


class DeliverExportRequest(BaseModel):
    root: str
    files: list[str]
    target_dir: str


class ApproveRequest(BaseModel):
    root: str
    job_id: str
    run_id: str
    output_name: str


class SnapshotRequest(BaseModel):
    root: str
    path: str
    seconds: float = 0
    label: str | None = None


class PromoteRequest(BaseModel):
    root: str
    job_id: str
    run_id: str
    output_name: str
    asset_type: str = "storyboard"
    usage: str = "composition"
    label: str = ""
    bind_mode: str = "next"
    target_job_ids: list[str] = []
    approve: bool = False


class ReviewSaveRequest(BaseModel):
    root: str
    review: dict[str, Any]


class ReviewExportRequest(BaseModel):
    root: str


class CreateProjectRequest(BaseModel):
    name: str
    parent_path: str
    title: str | None = None


class AssetYamlRequest(BaseModel):
    path: str


class AssetYamlSaveRequest(BaseModel):
    path: str
    content: str


class DeleteRunRequest(BaseModel):
    root: str
    job_id: str
    run_id: str


class DeleteAssetRequest(BaseModel):
    root: str
    path: str


class UploadAssetRequest(BaseModel):
    root: str
    name: str
    asset_type: str
    brief: str = ""
    detail: str = ""
    tags: str = ""
    subdir: str = ""


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/project/load")
def api_load_project(req: ProjectRequest) -> dict[str, Any]:
    root = Path(req.root).resolve()
    if not (root / "task.yaml").exists():
        raise HTTPException(status_code=404, detail=f"task.yaml not found in {root}")
    return load_project(root)


@app.post("/api/project/recent")
def api_recent_projects(req: ProjectListRequest) -> dict[str, Any]:
    base = Path(req.base).resolve() if req.base else APP_DIR.parent / "projects"
    projects = []
    if base.exists():
        for task_path in sorted(base.rglob("task.yaml"), key=lambda p: p.parent.stat().st_mtime, reverse=True):
            root = task_path.parent
            projects.append({"root": str(root), "name": root.parent.name if root.name == "task_project" else root.name, "mtime": root.stat().st_mtime})
            if len(projects) >= 80:
                break
    return {"base": str(base), "projects": projects}


@app.post("/api/project/browse")
def api_browse_project() -> dict[str, str]:
    if not os.name == "nt":
        raise HTTPException(status_code=400, detail="Folder picker is currently implemented for Windows only")
    script = "Add-Type -AssemblyName System.Windows.Forms; $d=New-Object System.Windows.Forms.FolderBrowserDialog; $d.Description='Select task_project folder'; if($d.ShowDialog() -eq 'OK'){ $d.SelectedPath }"
    proc = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", script], text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    path = (proc.stdout or "").strip().splitlines()[-1] if (proc.stdout or "").strip() else ""
    if not path:
        return {"root": ""}
    root = Path(path).resolve()
    if root.name != "task_project" and (root / "task_project" / "task.yaml").exists():
        root = root / "task_project"
    if not (root / "task.yaml").exists():
        raise HTTPException(status_code=400, detail=f"task.yaml not found in {root}")
    return {"root": str(root)}


@app.post("/api/fs/list-dirs")
def api_list_dirs(req: FsListRequest) -> dict[str, Any]:
    current = Path(req.path).resolve() if req.path else APP_DIR.parent / "projects"
    if not current.exists() or not current.is_dir():
        current = APP_DIR.parent / "projects"
    dirs = []
    for child in sorted((p for p in current.iterdir() if p.is_dir()), key=lambda p: p.name.lower()):
        dirs.append({
            "name": child.name,
            "path": str(child.resolve()),
            "has_task": (child / "task.yaml").exists(),
            "has_task_project": (child / "task_project" / "task.yaml").exists(),
        })
    parent = str(current.parent.resolve()) if current.parent != current else ""
    return {"path": str(current.resolve()), "parent": parent, "dirs": dirs, "has_task": (current / "task.yaml").exists()}


@app.post("/api/job/save")
def api_save_job(req: JobSaveRequest) -> dict[str, Any]:
    root = Path(req.root).resolve()
    job_id = req.job.get("id")
    if not job_id:
        raise HTTPException(status_code=400, detail="job.id is required")
    job = save_job(root, job_id, req.job)
    return {"job": job, "project": load_project(root)}


@app.post("/api/job/create")
def api_create_job(req: CreateJobRequest) -> dict[str, Any]:
    root = Path(req.root).resolve()
    job = create_job(root, req.kind, req.title)
    return {"job": job, "project": load_project(root)}


@app.post("/api/job/delete")
def api_delete_job(req: DeleteJobRequest) -> dict[str, Any]:
    root = Path(req.root).resolve()
    delete_job(root, req.job_id)
    return {"project": load_project(root)}


@app.post("/api/job/move")
def api_move_job(req: MoveJobRequest) -> dict[str, Any]:
    root = Path(req.root).resolve()
    move_job_in_task(root, req.job_id, req.direction)
    return {"project": load_project(root)}


@app.post("/api/job/dryrun")
def api_dryrun(req: JobActionRequest) -> dict[str, Any]:
    root = Path(req.root).resolve()
    try:
        result = run_job(root, req.job_id, confirm_live=False, timeout=req.timeout, interval=req.interval)
    except (FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"result": result, "project": load_project(root)}


@app.post("/api/job/run")
def api_run_job(req: JobActionRequest) -> dict[str, Any]:
    root = Path(req.root).resolve()
    try:
        result = run_job(root, req.job_id, confirm_live=req.confirm_live, timeout=req.timeout, interval=req.interval)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"result": result, "project": load_project(root)}


@app.post("/api/run/retry-download")
def api_retry_download(req: DeleteRunRequest) -> dict[str, Any]:
    root = Path(req.root).resolve()
    try:
        result = retry_download_outputs(root, req.job_id, req.run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"result": result, "project": load_project(root)}


@app.post("/api/output/approve")
def api_approve(req: ApproveRequest) -> dict[str, Any]:
    root = Path(req.root).resolve()
    try:
        result = approve_output(root, req.job_id, req.run_id, req.output_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"result": result, "project": load_project(root)}


@app.post("/api/output/promote")
def api_promote(req: PromoteRequest) -> dict[str, Any]:
    root = Path(req.root).resolve()
    try:
        result = promote_output_to_asset(
            root=root,
            source_job_id=req.job_id,
            run_id=req.run_id,
            output_name=req.output_name,
            asset_type=req.asset_type,
            usage=req.usage,
            label=req.label,
            bind_mode=req.bind_mode,
            target_job_ids=req.target_job_ids,
            approve=req.approve,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"result": result, "project": load_project(root)}


@app.post("/api/review/save")
def api_save_review(req: ReviewSaveRequest) -> dict[str, Any]:
    root = Path(req.root).resolve()
    review = save_review(root, req.review)
    return {"review": review, "project": load_project(root)}


@app.post("/api/review/export-brief")
def api_export_review_brief(req: ReviewExportRequest) -> dict[str, Any]:
    root = Path(req.root).resolve()
    result = export_iteration_brief(root)
    return {"result": result, "project": load_project(root)}


@app.post("/api/asset/add")
def api_add_asset(req: AddAssetRequest) -> dict[str, Any]:
    root = Path(req.root).resolve()
    try:
        asset = add_asset(root, Path(req.path).resolve(), req.type, req.label)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"asset": asset, "project": load_project(root)}


@app.post("/api/asset/delete")
def api_delete_asset(req: DeleteAssetRequest) -> dict[str, Any]:
    root = Path(req.root).resolve()
    try:
        delete_asset(root, req.path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"project": load_project(root)}


@app.post("/api/open-dir")
def api_open_dir(req: OpenDirRequest) -> dict[str, str]:
    try:
        open_directory(Path(req.path).resolve())
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok"}


@app.post("/api/deliver/list")
def api_deliver_list(req: ProjectRequest) -> dict[str, Any]:
    root = Path(req.root).resolve()
    return {"items": scan_deliverables(root)}


@app.post("/api/deliver/export")
def api_deliver_export(req: DeliverExportRequest) -> dict[str, Any]:
    root = Path(req.root).resolve()
    result = export_deliverables(root, req.files, Path(req.target_dir).resolve())
    return {"result": result}


@app.get("/api/file")
def api_file(path: str) -> FileResponse:
    target = Path(path).resolve()
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(target)


@app.post("/api/project/create")
def api_create_project(req: CreateProjectRequest) -> dict[str, Any]:
    project = create_project(Path(req.parent_path).resolve(), req.name, req.title)
    return {"project": project, "root": str(project["root"])}


@app.post("/api/asset/read-yaml")
def api_read_asset_yaml(req: AssetYamlRequest) -> dict[str, Any]:
    content = read_asset_yaml(Path(req.path).resolve())
    return {"path": req.path, "content": content}


@app.post("/api/asset/save-yaml")
def api_save_asset_yaml(req: AssetYamlSaveRequest) -> dict[str, Any]:
    save_asset_yaml(Path(req.path).resolve(), req.content)
    return {"status": "ok", "path": req.path}


@app.post("/api/run/delete")
def api_delete_run(req: DeleteRunRequest) -> dict[str, Any]:
    root = Path(req.root).resolve()
    delete_run_record(root, req.job_id, req.run_id)
    return {"project": load_project(root)}


@app.post("/api/run/thumbnail")
def api_generate_thumbnail(req: ApproveRequest) -> dict[str, Any]:
    root = Path(req.root).resolve()
    thumb = generate_video_thumbnail(root, req.job_id, req.run_id, req.output_name)
    return {"thumbnail": thumb, "project": load_project(root)}


@app.post("/api/assets/public")
def api_public_assets() -> list[dict[str, Any]]:
    return scan_public_assets()


@app.post("/api/asset/copy-to-project")
def api_copy_asset(req: AddAssetRequest) -> dict[str, Any]:
    root = Path(req.root).resolve()
    src = Path(req.path).resolve()
    asset = add_asset(root, src, req.type, req.label)
    return {"asset": asset, "project": load_project(root)}



@app.post("/api/video/capture-snapshot")
def api_capture_video_snapshot(req: SnapshotRequest) -> dict[str, Any]:
    root = Path(req.root).resolve()
    try:
        result = capture_video_snapshot(root, Path(req.path), req.seconds, req.label)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"result": result, "project": load_project(root)}
@app.post("/api/asset/upload-form")
async def api_upload_asset_form(
    root: str = Form(...),
    name: str = Form(""),
    asset_type: str = Form("misc"),
    brief: str = Form(""),
    detail: str = Form(""),
    tags: str = Form(""),
    file: UploadFile = File(None),
):
    import shutil
    proot = Path(root).resolve()
    subdirs = {"character": "characters", "scene": "scenes", "prop": "props"}
    target_subdir = subdirs.get(asset_type, "misc")
    dest_dir = proot / "assets" / target_subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    if file and file.filename:
        content = await file.read()
        dest = unique_path_file(dest_dir / file.filename)
        dest.write_bytes(content)
        yaml_path = dest.with_suffix(".yaml")
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        yaml_text = "\n".join([
            f"# {asset_type} asset: {name or dest.stem}",
            f"id: {dest.stem}",
            f"name: {name or dest.stem}",
            f"type: {asset_type}",
            f"ref_image: {dest.name}",
            "",
            "brief: |",
            f"  {brief or '待补充'}",
            "",
            "detail: |",
            f"  {detail or '待补充'}",
            "",
            f"tags: {tag_list or []}",
            "",
        ])
        yaml_path.write_text(yaml_text, encoding="utf-8")
        from .project_io import read_yaml as _ry, write_yaml as _wy
        task_path = proot / "task.yaml"
        task = _ry(task_path)
        asset_entry = {"id": f"asset_{dest.stem}", "type": asset_type, "label": name or dest.stem, "files": [{"path": dest.relative_to(proot).as_posix(), "role": "reference"}]}
        task.setdefault("assets", []).append(asset_entry)
        _wy(task_path, task)
        return {"asset": asset_entry, "project": load_project(proot)}
    return {"error": "No file uploaded"}


def unique_path_file(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    i = 2
    while True:
        c = path.with_name(f"{stem}_{i}{suffix}")
        if not c.exists():
            return c
        i += 1


if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")






