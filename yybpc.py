import os
import time
import requests
import notify

# 从环境变量中获取 Qm-User-Token
qm_user_token = os.getenv('QM_USER_TOKEN')
if not qm_user_token:
    raise ValueError("环境变量 QM_USER_TOKEN 未设置")

# 请求 URL
url = "https://webapi.qmai.cn/web/cmk-center/sign/takePartInSign"

# 请求头
headers = {
    "Accept": "v=1.0",
    "content-type": "application/json",
    "Qm-From": "wechat",
    "Qm-From-Type": "catering",
    "store-id": "216652",
    "Qm-User-Token": qm_user_token,
    "Accept-Encoding": "gzip,compress,br,deflate",
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.59(0x18003b2e) NetType/4G Language/zh_CN",
    "Referer": "https://servicewechat.com/wx3423ef0c7b7f19af/72/page-frame.html"
}

# 请求数据
payload = {
    "activityId": "1146457634812837889",
    "storeId": "216652",
    "appid": "wx3423ef0c7b7f19af",
    "timestamp": int(round(time.time() * 1000)), 
    "signature": "EBA56881738B83395EA62AE498901308",
    "v": 1,
    "data": "U7sVjNKDNVxOcmf6Z7gsPOGHiin/A5Zf5n0Z2xVrXyz6mG2mdZAMdlxiVFb6FwSyh5ehvdqw+bNlnwhcDISSwLGnot5ADP2Ev7TBafW3QfRFGY6acZzM/rXztymh5qvFuMtNC+xfYiUcgaaf4ouDhNU21VdyL+XfL6A8d/mkX+T3smi6woEgqMJdLVxBKYGaMeXOSysfXtw4jEmuwD7W9+vY1SoTeiT51rGlDOZbQQQ=",
    "version": 2
}

# 发送 POST 请求
response = requests.post(url, headers=headers, json=payload)

# 打印响应内容
res = response.json()
print(res)

notify.send("yybpc签到", str(res), False)