import os
import shlex
import json
import requests
import notify

curl_cmd = os.getenv("CURL_YYBPC")
if not curl_cmd:
    raise RuntimeError("环境变量 CURL_YYBPC 未设置")

# 拆分 curl 参数
parts = shlex.split(curl_cmd)

url = None
headers = {}
data = None

i = 0
while i < len(parts):
    part = parts[i]

    # URL
    if part.startswith("http"):
        url = part

    # Header
    elif part in ("-H", "--header"):
        key, value = parts[i + 1].split(":", 1)
        headers[key.strip()] = value.strip()
        i += 1

    # Data
    elif part in ("--data", "--data-raw", "--data-binary"):
        data = parts[i + 1]
        i += 1

    i += 1

if not url:
    raise RuntimeError("未能从 curl 中解析出 URL")

# Content-Length 交给 requests 计算，避免问题
headers.pop("Content-Length", None)

# JSON body
json_data = None
if data:
    try:
        json_data = json.loads(data)
    except json.JSONDecodeError:
        json_data = None

try:
    resp = requests.post(
        url,
        headers=headers,
        json=json_data if json_data else None,
        data=None if json_data else data,
        timeout=15
    )

    result_text = resp.text
    print("Status:", resp.status_code)
    print("Response:", result_text)

    # ✅ 成功 / 失败统一通知
    notify.send(
        "yybpc 签到结果",
        f"HTTP {resp.status_code}\n{result_text}",
        False
    )

except Exception as e:
    # ❌ 异常通知
    notify.send(
        "yybpc 签到异常",
        str(e),
        True
    )
    raise
