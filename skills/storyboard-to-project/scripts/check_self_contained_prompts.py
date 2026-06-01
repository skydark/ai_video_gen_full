#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

VOICE_RE = re.compile(r"@?v\d{5,}", re.IGNORECASE)
ABSTRACT_RE = re.compile(r"(参考(原文|剧本|上文|前文|shot_plan|review)|同上|如上|该对白|这句台词|语音编号|voice\s*id|voice_id)", re.IGNORECASE)
PROMPT_KEYS = {"prompt", "video_prompt", "visual_action", "camera_motion", "lighting", "avoid", "prompt_preview"}


def load(path: Path):
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    if path.suffix.lower() in {".yaml", ".yml"}:
        if yaml is None:
            raise SystemExit("PyYAML is required for YAML files")
        return yaml.safe_load(text)
    return text


def walk(value, location=""):
    if isinstance(value, dict):
        for key, child in value.items():
            child_location = f"{location}.{key}" if location else str(key)
            yield from walk(child, child_location)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, f"{location}[{index}]")
    elif isinstance(value, str):
        yield location, value


def is_prompt_location(location: str) -> bool:
    parts = re.split(r"[.\[\]]+", location)
    return any(part in PROMPT_KEYS for part in parts) or "jobs" in parts


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: check_self_contained_prompts.py <file-or-dir> [...]")
        return 2
    files: list[Path] = []
    for arg in argv[1:]:
        path = Path(arg)
        if path.is_dir():
            files.extend(p for p in path.rglob("*") if p.suffix.lower() in {".json", ".yaml", ".yml"})
        else:
            files.append(path)
    problems: list[str] = []
    for path in files:
        if not path.exists() or path.name.startswith("review_snapshot"):
            continue
        try:
            data = load(path)
        except Exception as exc:
            problems.append(f"{path}: cannot parse: {exc}")
            continue
        for location, text in walk(data):
            if not is_prompt_location(location):
                continue
            if VOICE_RE.search(text):
                if not re.search(r"[「『\"]", text) and not re.search(r"[ぁ-んァ-ン一-龥]", text):
                    problems.append(f"{path}:{location}: voice id appears without concrete dialogue text")
                else:
                    problems.append(f"{path}:{location}: remove voice id from generation prompt; keep only spoken text")
            if ABSTRACT_RE.search(text):
                problems.append(f"{path}:{location}: prompt depends on external context or abstract symbol")
    if problems:
        print("Self-contained prompt check failed:")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print("Self-contained prompt check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
