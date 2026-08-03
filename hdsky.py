from typing import Any
import requests
import json
import base64
import os
import notify

cookies: Any = os.getenv("HDSKY_COOKIES")
tt_userid = os.getenv("TT_USERID")
tt_apikey = os.getenv("TT_APIKEY")

# 🧠 第三方验证码识别（图鉴识图平台）
def recognize_captcha(image_bytes, userid, apikey, proxies={}):
    url = 'http://api.ttshitu.com/base64'
    headers = {'Content-Type': 'application/json;charset=UTF-8'}
    data = {
        'username': userid,
        'password': apikey,
        'image': base64.b64encode(image_bytes).decode('utf-8'),
        'typeid': "7",
    }

    response = requests.post(url, headers=headers, data=json.dumps(data), proxies=proxies)
    result = response.json()
    # print(result)

    if result["code"] == "-1":
        print("识图平台返回错误，终止程序")
        os._exit(0)
    return result['data']['result']

# 🔁 主流程
def hdsky():
    retry = 10
    success = False

    # 创建 Session 管理整个流程
    session = requests.Session()

    # 设置统一请求头（除特殊请求）
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.101 Safari/537.36',
        'Referer': 'https://hdsky.me/torrents.php',
        'Origin': 'https://hdsky.me',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'en,zh-CN;q=0.9,zh;q=0.8',
        'Cookie': cookies,
    })

    while retry > 0 and not success:
        # Step 1: 获取验证码 imagehash
        imagehash_url = "https://hdsky.me/image_code_ajax.php"
        session.headers.update({'X-Requested-With': 'XMLHttpRequest'})
        res = session.post(imagehash_url, data={'action': 'new'})
        code = res.json().get("code")
        print(f"[验证码 CODE] {code}")

        # Step 2: 获取验证码图片内容
        image_url = "https://hdsky.me/image.php"
        params = {'action': 'regimage', 'imagehash': code}
        session.headers.pop('Content-Type', None)  # 避免 GET 请求时携带多余头
        image_response = session.get(image_url, params=params)

        # 保存验证码图片（可选）
        # with open("image.png", "wb") as f:
        #     f.write(image_response.content)
        # captcha_text = input("input code: ")
        # os.remove("image.png")

        # Step 3: 调用识别平台
        switch : int = 0

        captcha_text = None

        if switch == 1:
            captcha_text = recognize_captcha(image_response.content, tt_userid, tt_apikey)
        else:
            with open("./image.png", "wb+") as f:
                f.write(image_response.content)

            import ddddocr
            ocr = ddddocr.DdddOcr(show_ad=False)
            image = open("./image.png", "rb").read()
            captcha_text = ocr.classification(image)
            os.remove("./image.png")

        print(f"[识别结果] {captcha_text}")

        # Step 4: 提交签到表单
        signup_url = "https://hdsky.me/showup.php"
        session.headers.update({
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest'
        })
        post_data = {
            'action': 'showup',
            'imagehash': code,
            'imagestring': captcha_text
        }
        result = session.post(signup_url, data=post_data)
        print(f"[签到结果] {result.text}")
        message = result.json().get("message")
        print(f"[签到反馈] {message}")

        # Step 5: 判断签到是否成功
        if isinstance(message, int):
            success = True
        else:
            retry -= 1

    if success:
        print("✅ HDSky 签到成功")
        notify.send("hesky", f"✅ HDSky 签到成功 获得 {message} 魔力值")
    else:
        print("❌ HDSky 签到失败")
        notify.send("hesky", "❌ HDSky 签到失败")

# ▶️ 运行
hdsky()
