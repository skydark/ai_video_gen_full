#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["python-dotenv", "requests"]
# ///

"""分析单张图片并输出到文件"""
import base64, json, sys
from pathlib import Path
import requests
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

img = sys.argv[1]
with open(img, "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

prompt = """请分析这张角色设定图，用中文回答。按以下格式输出：
【简短描述】1-2句话概括关键视觉特征
【详细描述】完整视觉描述，类似生成prompt（发色发型、瞳色、服装、体型、配饰）
【服装标签】关键词标签，逗号分隔
只输出以上格式，不要额外说明。"""

r = requests.post(
    "https://www.dmxapi.cn/v1/chat/completions",
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {__import__('os').environ['DMXAPI_KEY']}"},
    json={"model": "qwen3.6-plus", "temperature": 0.1, "messages": [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
    ]}]},
    timeout=180,
)
d = r.json()
content = d["choices"][0]["message"]["content"]
tokens = d.get("usage", {}).get("total_tokens", 0)

out = Path(img).with_suffix(".txt")
out.write_text(content, encoding="utf-8")
print(f"OK: {out} ({tokens} tokens)")
