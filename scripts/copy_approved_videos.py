#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

"""Copy approved project videos and referenced voices into target directories."""

from __future__ import annotations

import argparse
import re
import shutil
from dataclasses import dataclass
from pathlib import Path


DEFAULT_BASE_DIR = Path(r"E:\VideoProjects\BSDAnime")
DEFAULT_VOICE_DIR = Path(r"D:\galgame\GIGA\BSD\extracted\Voice1")
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
VERSION_PATTERN = re.compile(r"^(?P<base>.+?)(?:_v(?P<version>\d+))?$")
SCENE_PATTERN = re.compile(r"^bsd_\d+_\d+_(?P<scene>\d+)(?:_v\d+)?$")
VOICE_ID_PATTERN = re.compile(r"@v(?P<voice_id>[A-Za-z0-9]+)")


@dataclass(frozen=True)
class ProjectMatch:
    requested_name: str
    project_dir: Path
    version: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy approved videos from selected projects into a target directory."
    )
    parser.add_argument(
        "projects",
        nargs="+",
        help="Project names such as bsd_1_7_5 or bsd_1_7_10.",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=DEFAULT_BASE_DIR,
        help=rf"Workspace parent directory. Default: {DEFAULT_BASE_DIR}",
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=None,
        help="Destination root directory. Default: E:\\VideoProjects\\BSDAnime",
    )
    parser.add_argument(
        "--projects-dir",
        type=Path,
        default=None,
        help="Projects directory. Default: <base-dir>\\ai_video_gen_full\\projects",
    )
    parser.add_argument(
        "--scripts-dir",
        type=Path,
        default=None,
        help="Script markdown directory. Default: <base-dir>\\ai_video_gen_full\\bsd_anime_script",
    )
    parser.add_argument(
        "--voice-dir",
        type=Path,
        default=DEFAULT_VOICE_DIR,
        help=rf"Voice source directory. Default: {DEFAULT_VOICE_DIR}",
    )
    parser.add_argument(
        "--refresh-voice-cache",
        action="store_true",
        help="Rebuild filelist.lst under the voice source directory.",
    )
    parser.add_argument(
        "--dryrun",
        "--dry-run",
        action="store_true",
        help="Print planned copies without writing files.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing destination files.",
    )
    return parser.parse_args()


def project_base_and_version(name: str) -> tuple[str, int]:
    match = VERSION_PATTERN.match(name)
    if not match:
        return name, 0
    return match.group("base"), int(match.group("version") or 0)


def find_latest_project(projects_dir: Path, requested_name: str) -> ProjectMatch | None:
    requested_base, requested_version = project_base_and_version(requested_name)
    matches: list[ProjectMatch] = []

    for candidate in projects_dir.iterdir():
        if not candidate.is_dir():
            continue
        candidate_base, candidate_version = project_base_and_version(candidate.name)
        if candidate_base == requested_base:
            matches.append(ProjectMatch(requested_name, candidate, candidate_version))

    if requested_version:
        exact = [match for match in matches if match.version == requested_version]
        if exact:
            return exact[0]

    if not matches:
        return None
    return max(matches, key=lambda match: (match.version, match.project_dir.name))


def iter_video_files(project_dir: Path) -> list[Path]:
    videos_dir = project_dir / "task_project" / "approved" / "videos"
    if not videos_dir.is_dir():
        return []
    return sorted(
        path for path in videos_dir.iterdir() if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )


def scene_number_for(project_name: str) -> str:
    match = SCENE_PATTERN.match(project_name)
    if not match:
        raise ValueError(f"Cannot infer scene number from project name: {project_name}")
    return match.group("scene")


def scene_dir_for(target_root: Path, project_dir: Path) -> Path:
    return target_root / "Route1" / "Chap7" / f"s{scene_number_for(project_dir.name)}"


def voice_dir_for(target_root: Path, project_dir: Path) -> Path:
    return target_root / "Route1" / "Chap7" / f"v{scene_number_for(project_dir.name)}"


def destination_for(target_root: Path, project_dir: Path, source_file: Path) -> Path:
    return scene_dir_for(target_root, project_dir) / source_file.name


def copy_file(source_file: Path, destination: Path, dryrun: bool, overwrite: bool) -> bool:
    if destination.exists() and not overwrite:
        print(f"  SKIP exists: {destination.name}")
        return False

    print(f"  COPY {source_file.name} -> {destination.name}")
    if not dryrun:
        shutil.copy2(source_file, destination)
    return True


def copy_videos(
    project_matches: list[ProjectMatch], target_root: Path, dryrun: bool, overwrite: bool
) -> tuple[int, int]:
    planned_count = 0
    copied_count = 0

    if dryrun:
        print(f"DRYRUN target root: {target_root}")
    else:
        target_root.mkdir(parents=True, exist_ok=True)

    for project_match in project_matches:
        video_files = iter_video_files(project_match.project_dir)
        if not video_files:
            print(f"WARN no videos: {project_match.project_dir}")
            continue

        project_target_dir = scene_dir_for(target_root, project_match.project_dir)
        if not dryrun:
            project_target_dir.mkdir(parents=True, exist_ok=True)

        print(
            f"PROJECT {project_match.requested_name} -> "
            f"{project_match.project_dir.name} -> {project_target_dir}"
        )
        for source_file in video_files:
            destination = destination_for(target_root, project_match.project_dir, source_file)
            planned_count += 1
            if copy_file(source_file, destination, dryrun, overwrite):
                copied_count += 1

    action = "planned" if dryrun else "copied"
    print(f"DONE {action}: {copied_count}/{planned_count} videos")
    return copied_count, planned_count


def voice_script_path(scripts_dir: Path, project_name: str) -> Path:
    project_base, _ = project_base_and_version(project_name)
    return scripts_dir / f"{project_base}.md"


def extract_voice_ids(script_path: Path) -> list[str]:
    content = script_path.read_text(encoding="utf-8")
    voice_ids = VOICE_ID_PATTERN.findall(content)
    return list(dict.fromkeys(voice_ids))


def voice_cache_path(voice_dir: Path) -> Path:
    return voice_dir / "filelist.lst"


def scan_voice_files(voice_dir: Path) -> list[Path]:
    return sorted(path for path in voice_dir.rglob("*.aac") if path.is_file())


def write_voice_cache(voice_dir: Path, voice_files: list[Path]) -> None:
    cache_path = voice_cache_path(voice_dir)
    lines = [str(path.relative_to(voice_dir)) for path in voice_files]
    cache_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_voice_index(voice_dir: Path, dryrun: bool, refresh_cache: bool) -> dict[str, Path]:
    cache_path = voice_cache_path(voice_dir)
    if refresh_cache or not cache_path.is_file():
        print(f"VOICE cache scan: {voice_dir}")
        voice_files = scan_voice_files(voice_dir)
        if not dryrun:
            write_voice_cache(voice_dir, voice_files)
            print(f"VOICE cache wrote: {cache_path}")
    else:
        voice_files = []
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                voice_files.append(voice_dir / line)

    voice_index: dict[str, Path] = {}
    duplicate_ids: list[str] = []
    for voice_file in voice_files:
        voice_id = voice_file.stem
        if voice_id in voice_index:
            duplicate_ids.append(voice_id)
            continue
        voice_index[voice_id] = voice_file

    if duplicate_ids:
        print(f"WARN duplicate voice ids ignored: {', '.join(sorted(set(duplicate_ids)))}")
    return voice_index


def copy_voices(
    project_matches: list[ProjectMatch],
    scripts_dir: Path,
    voice_index: dict[str, Path],
    target_root: Path,
    dryrun: bool,
    overwrite: bool,
) -> tuple[int, int]:
    planned_count = 0
    copied_count = 0

    for project_match in project_matches:
        script_path = voice_script_path(scripts_dir, project_match.project_dir.name)
        if not script_path.is_file():
            print(f"WARN no script: {script_path}")
            continue

        voice_ids = extract_voice_ids(script_path)
        if not voice_ids:
            print(f"WARN no voice ids: {script_path}")
            continue

        project_target_dir = voice_dir_for(target_root, project_match.project_dir)
        if not dryrun:
            project_target_dir.mkdir(parents=True, exist_ok=True)

        print(
            f"VOICES {script_path.name} -> "
            f"{project_match.project_dir.name} -> {project_target_dir}"
        )
        for voice_id in voice_ids:
            source_file = voice_index.get(voice_id)
            if source_file is None:
                print(f"  WARN missing voice: {voice_id}")
                continue

            destination = project_target_dir / source_file.name
            planned_count += 1
            if copy_file(source_file, destination, dryrun, overwrite):
                copied_count += 1

    action = "planned" if dryrun else "copied"
    print(f"DONE {action}: {copied_count}/{planned_count} voices")
    return copied_count, planned_count


def main() -> int:
    args = parse_args()
    base_dir = args.base_dir.resolve()
    projects_dir = (args.projects_dir or base_dir / "ai_video_gen_full" / "projects").resolve()
    scripts_dir = (args.scripts_dir or base_dir / "ai_video_gen_full" / "bsd_anime_script").resolve()
    target_root = (args.target_dir or base_dir).resolve()
    voice_dir = args.voice_dir.resolve()

    if not projects_dir.is_dir():
        raise SystemExit(f"Projects directory not found: {projects_dir}")
    if not scripts_dir.is_dir():
        raise SystemExit(f"Script directory not found: {scripts_dir}")
    if not voice_dir.is_dir():
        raise SystemExit(f"Voice directory not found: {voice_dir}")

    project_matches: list[ProjectMatch] = []
    missing_projects: list[str] = []
    for requested_project in args.projects:
        project_match = find_latest_project(projects_dir, requested_project)
        if project_match is None:
            missing_projects.append(requested_project)
        else:
            project_matches.append(project_match)

    if missing_projects:
        print(f"WARN missing projects: {', '.join(missing_projects)}")
    if not project_matches:
        raise SystemExit("No matching projects found.")

    copy_videos(project_matches, target_root, args.dryrun, args.overwrite)
    voice_index = load_voice_index(voice_dir, args.dryrun, args.refresh_voice_cache)
    copy_voices(project_matches, scripts_dir, voice_index, target_root, args.dryrun, args.overwrite)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
