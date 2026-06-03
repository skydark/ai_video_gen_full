#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["python-dotenv", "requests"]
# ///

"""
批量分析 assets 中的角色/场景图片，使用 DMXAPI 视觉模型。
为每个图片生成简短描述 + 详细生成prompt描述。
"""
import base64
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

API_KEY = os.environ.get("DMXAPI_KEY", "")
API_URL = "https://www.dmxapi.cn/v1/chat/completions"
MODEL = "qwen3.6-plus"

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"

CHAR_PROMPT = """请分析这张角色设定图/参考图，用中文回答。按以下格式输出：

【角色名推测】根据文件名或图中角色特征推测角色名
【简短描述】1-2句话，概括角色的关键视觉特征（性别、年龄段、发色发型、服装风格、整体气质），用于AI快速识别
【详细描述】一段完整的角色视觉描述，类似生成prompt。包含：发色、发型细节、瞳色、肤色、面部特征、服装款式和颜色（上衣/下装/外套/鞋）、体型、配饰、站姿。描述要具体、客观，可以直接用作AI图像生成的identity prompt
【服装标签】列出服装的关键词标签，逗号分隔

只输出以上格式，不要额外说明。"""

SCENE_PROMPT = """请分析这张场景参考图，用中文回答。按以下格式输出：

【场景名推测】根据文件名或图中场景特征推测场景名
【简短描述】1-2句话，概括场景的关键视觉特征（地点类型、时间/光线、空间大小、氛围），用于AI快速识别
【详细描述】一段完整的场景视觉描述，类似生成prompt。包含：空间结构（室内/室外、房间布局、建筑风格）、光线来源和色调、关键家具/道具、材质质感、色彩倾向、天气/时间。描述要具体、客观，可以直接用作AI图像生成的scene prompt
【场景标签】列出场景的关键词标签，逗号分隔

只输出以上格式，不要额外说明。"""


def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze_image(image_path: str, is_character: bool = True) -> str:
    """调用 DMXAPI 分析单张图片"""
    ext = Path(image_path).suffix.lower()
    mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"

    image_data = encode_image(image_path)
    prompt = CHAR_PROMPT if is_character else SCENE_PROMPT

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{image_data}"},
                    },
                ],
            }
        ],
        "temperature": 0.1,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }

    print(f"  分析中: {Path(image_path).name} ...")
    resp = requests.post(API_URL, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    result = resp.json()

    if "choices" in result and len(result["choices"]) > 0:
        content = result["choices"][0]["message"]["content"]
        tokens = result.get("usage", {}).get("total_tokens", 0)
        print(f"    完成 ({tokens} tokens)")
        return content
    else:
        error = result.get("error", {})
        raise RuntimeError(f"API返回异常: {error}")


def parse_analysis(text: str) -> dict:
    """解析模型输出为结构化字典"""
    result = {}
    current_key = None
    key_map = {
        "【角色名推测】": "name_guess",
        "【场景名推测】": "name_guess",
        "【简短描述】": "brief",
        "【详细描述】": "detail",
        "【服装标签】": "tags",
        "【场景标签】": "tags",
    }
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        matched = False
        for tag, key in key_map.items():
            if line.startswith(tag):
                current_key = key
                value = line[len(tag):].strip()
                if value:
                    result[current_key] = value
                matched = True
                break
        if matched:
            continue
        if current_key and line:
            if current_key in result:
                result[current_key] += "\n" + line
            else:
                result[current_key] = line
    return result


def main():
    if not API_KEY:
        print("错误: .env 中未找到 DMXAPI_KEY")
        sys.exit(1)

    tasks = []

    # 收集角色图片
    chars_dir = ASSETS_DIR / "chars"
    if chars_dir.exists():
        for img in sorted(chars_dir.glob("*")):
            if img.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                tasks.append((str(img), True))

    # 收集场景图片
    scenes_dir = ASSETS_DIR / "scenes"
    if scenes_dir.exists():
        for img in sorted(scenes_dir.glob("*")):
            if img.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                tasks.append((str(img), False))

    print(f"共 {len(tasks)} 张图片待分析\n")

    for image_path, is_char in tasks:
        try:
            # 输出到图片同目录的 yaml 文件
            yaml_path = Path(image_path).with_suffix(".yaml")
            # 如果已存在且不覆盖，则跳过
            if yaml_path.exists():
                print(f"  已存在，跳过: {yaml_path.name}\n")
                continue

            raw = analyze_image(image_path, is_char)
            parsed = parse_analysis(raw)

            asset_type = "character" if is_char else "scene"
            name = parsed.get("name_guess", Path(image_path).stem)

            yaml_content = f"""# {asset_type} asset: {name}
id: {Path(image_path).stem}
name: {name}
type: {asset_type}
ref_image: {Path(image_path).name}

brief: |
  {parsed.get('brief', '待补充')}

detail: |
  {parsed.get('detail', '待补充')}

tags: [{parsed.get('tags', '')}]
"""
            yaml_path.write_text(yaml_content, encoding="utf-8")
            print(f"  -> 已写入 {yaml_path.name}\n")

        except Exception as e:
            print(f"  失败: {e}\n")


if __name__ == "__main__":
    main()
