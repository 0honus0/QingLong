import os
import requests
import re
import notify

from shlex import split

def parse_curl(curl_command: str):
    """解析 curl 命令为 url, headers, cookies"""
    tokens = split(curl_command)
    url = None
    headers = {}
    cookies = {}

    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("curl"):
            url = tokens[i+1].strip("'\"")
            i += 2
            continue
        if token == "-H":
            header_str = tokens[i+1].strip("'\"")
            if ":" in header_str:
                k, v = header_str.split(":", 1)
                headers[k.strip()] = v.strip()
            i += 2
            continue
        if token == "-b":
            cookie_str = tokens[i+1].strip("'\"")
            for pair in cookie_str.split(";"):
                if "=" in pair:
                    ck, cv = pair.strip().split("=", 1)
                    cookies[ck] = cv
            i += 2
            continue
        i += 1

    return url, headers, cookies

def fetch_from_env():
    curl_cmd = os.environ.get("FETCH_HHCLUB")
    if not curl_cmd:
        raise ValueError("环境变量 FETCH_HHCLUB 未设置")

    url, headers, cookies = parse_curl(curl_cmd)

    # 用 requests 发送请求
    resp = requests.get(url=url, headers=headers, cookies=cookies)
    return resp.text

if __name__ == "__main__":
    res = ""
    try:
        res = fetch_from_env()
        pattern = re.compile(
            r'<p class="register-now-info register-info">'
            r'(这是您的第\d+次签到，已连续签到\d+天，本次签到获得\d+个憨豆。你目前拥有补签卡\d+张。)'
            r'</p>'
        )
        match = re.search(pattern, res)
        if match:
            res = match.group(1)
        else:
            res = "未匹配到签到信息，请检查环境变量 FETCH_HHCLUB 的值是否正确。"
        
    except Exception as e:
        res = f"Error fetching data: {e}"
    
    notify.send("hhclub", res)

    print(res)
