import os
import re
import requests
import notify
from urllib.parse import urljoin, urlparse, parse_qs

BASE = "https://open.cd/"
PAGE_URL = urljoin(BASE, "plugin_sign-in.php")

# 优先用环境变量里的 cookie；没有就用你贴的字符串（注意：仓库/日志里不要泄露）
cookies = os.getenv("OPENCD_COOKIES")

# 通用头
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
base_headers = {
    "user-agent": UA,
    "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,sq;q=0.6",
    "dnt": "1",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "upgrade-insecure-requests": "1",
    "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "cookie": cookies,
}

res = ""

retry = 10

while retry > 0:
    retry -= 1

    # 1) 访问页面并提取验证码图片地址
    session = requests.Session()
    resp = session.get(PAGE_URL, headers={
        **base_headers,
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "referer": "https://open.cd/messages.php?action=viewmessage&id=27857301",
        "sec-fetch-dest": "iframe",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1",
    })

    if resp.status_code != 200:
        res = f"获取验证码路径失败, {resp.status_code}"
        continue

    # 更稳一点的正则：允许单/双引号和可选空格
    m = re.search(r'<img\s+src=[\'"]([^\'"]+)[\'"][^>]*?>', resp.text, flags=re.I)
    if not m:
        res = "没有在页面中找到 <img src=...> 验证码标签"
        continue

    img_src = m.group(1)
    img_url = urljoin(BASE, img_src)  # 处理相对路径，例如 image.php?action=regimage&imagehash=...

    # 解析 imagehash，方便命名
    parsed = urlparse(img_url)
    qs = parse_qs(parsed.query)
    imagehash = (qs.get("imagehash", ["unknown"])[0]).strip()

    # 2) 请求验证码图片并保存到本地
    img_headers = {
        **base_headers,
        "accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "referer": PAGE_URL,  # 与你 curl 的 referer 一致
        "sec-fetch-dest": "image",
        "sec-fetch-mode": "no-cors",
        "sec-fetch-site": "same-origin",
        "priority": "u=2, i",
    }

    img_resp = session.get(img_url, headers=img_headers, stream=True, timeout=20)

    if resp.status_code != 200:
        res = f"获取验证码失败, {img_resp.status_code}"
        continue

    filename = f"regimage_{imagehash}.png"

    with open(filename, "wb") as f:
        for chunk in img_resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    import ddddocr
    ocr = ddddocr.DdddOcr(show_ad=False)
    image = open(filename, "rb").read()
    imagestring = ocr.classification(image)
    os.remove(filename)

    # imagestring = input("input the imagestring: ")

    signin_url = urljoin(BASE, "plugin_sign-in.php?cmd=signin")
    data = {
        "imagehash": imagehash,
        "imagestring": imagestring,
    }
    signin_resp = session.post(signin_url, headers={
        **base_headers,
        "accept": "*/*",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "origin": "https://open.cd",
        "referer": "https://open.cd/messages.php?action=viewmessage&id=27857301",
        "x-requested-with": "XMLHttpRequest",
    }, data=data)

    try:

        print(signin_resp.json())

        result = signin_resp.json()

        if result["state"] == "success":
            signindays = result["signindays"]
            integral = result["integral"]
            res = f"签到成功, 连续签到{signindays}天, 签到获取魔力{integral}"
            break
        elif result["state"] == "false":
            res = "可能已经签到成功"
            retry -= 1
        else:
            res = f"签到失败, 原因{signin_resp.text}"
    except Exception as e:
        print(e)
        retry -= 1
        res = "原因解析错误 请查看日志"

    print(res)

print(res)

notify.send("opencd 签到", res)