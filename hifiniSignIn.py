import os
import re
import time
import json
import base64
import hashlib
import requests
from typing import Optional, Dict, Any, Union
from ddddocr import DdddOcr

DEBUG = False
LOG_FILE = "log.txt"

BASE_URL = "https://www.hifini.com"

URLS = {
    "login": "/user-login.htm",
    "captcha": "/gocaptcha/get-data?id=slide-default",
    "check_captcha": "/gocaptcha/check-data",
    "sign_page": "/sg_sign.htm",
    "sign_post": "/sg_sign.htm",
}

class HeaderManager:
    """统一管理请求头,支持 cookie、referer、content-type 动态组合。"""
    DEFAULT_HEADERS = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    }

    @classmethod
    def build(cls, *, cookie: Optional[str] = None, referer: Optional[str] = None,
              content_type: Optional[str] = None, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = cls.DEFAULT_HEADERS.copy()
        if cookie:
            headers["cookie"] = cookie
        if referer:
            headers["referer"] = referer
        if content_type:
            headers["content-type"] = content_type
        if extra:
            headers.update(extra)
        return headers

class HifiniClient:
    def __init__(self):
        self.session = requests.Session()
        self.notifications = []

    def _log(self, msg: str):
        self.notifications.append(msg)
        # with open(LOG_FILE, "a", encoding="utf-8") as f:
        #     f.write(msg + "\n")
        if DEBUG:
            print(msg)

    def convert_to_bytes(self, file: Union[str, bytes]) -> bytes:
        if isinstance(file, bytes):
            return file
        if os.path.isfile(file):
            with open(file, "rb") as f:
                return f.read()
        data = file.split(",")[1] if "," in file else file
        return base64.b64decode(data)

    def ocr_slide(self, target_file: Union[str, bytes], background_file: Union[str, bytes]) -> Optional[Dict[str, Any]]:
        target_bytes = self.convert_to_bytes(target_file)
        background_bytes = self.convert_to_bytes(background_file)
        ocr = DdddOcr(det=False, ocr=False, show_ad=False)
        return ocr.slide_match(target_bytes, background_bytes)

    def get_initial_cookies(self) -> Optional[str]:
        url = BASE_URL + URLS["login"]
        resp = self.session.get(url)
        if resp.status_code == 200:
            return resp.cookies.get("bbs_sid")
        self._log(f"获取初始cookies失败,状态码: {resp.status_code}")
        return None

    def get_captcha(self, cookies: str) -> Optional[Dict[str, Any]]:
        headers = HeaderManager.build(cookie=cookies, referer=f"{BASE_URL}/user-login.htm")
        resp = self.session.get(BASE_URL + URLS["captcha"], headers=headers)
        if resp.status_code != 200:
            self._log("获取验证码数据失败")
            return None
        data = resp.json().get("data", {})
        if not data:
            self._log("验证码数据为空")
            return None

        ocr_result = self.ocr_slide(data["thumb_image_base64"], data["master_image_base64"])
        if not ocr_result:
            self._log("OCR滑动验证失败")
            return None

        need_x = int(ocr_result["target"][0]) - int(ocr_result["target_x"])
        need_y = data["display_y"]

        captcha_payload = {
            "captchaKey": data["captcha_key"],
            "id": data["id"],
            "value": f"{need_x},{need_y}",
        }

        check_resp = self.session.post(BASE_URL + URLS["check_captcha"], headers=headers, json=captcha_payload)
        if check_resp.json().get("data") == "ok":
            return captcha_payload
        self._log("验证码校验失败")
        return None

    def login(self, cookies: str, captcha_key: str) -> Optional[str]:
        email = os.getenv("HIFINI_USER")
        password = os.getenv("HIFINI_PASS")
        if not email or not password:
            self._log("缺少环境变量 HIFINI_USER 或 HIFINI_PASS")
            return None

        headers = HeaderManager.build(cookie=cookies, referer=f"{BASE_URL}/user-login.htm", content_type="application/x-www-form-urlencoded")
        data = {
            "email": email,
            "password": hashlib.md5(password.encode("utf-8")).hexdigest(),
            "captchatokey": captcha_key,
        }
        resp = self.session.post(BASE_URL + URLS["login"], headers=headers, data=data)
        if resp.status_code != 200:
            self._log(f"登录请求失败,状态码: {resp.status_code}")
            return None

        bbs_token = resp.cookies.get("bbs_token")
        bbs_sid = resp.cookies.get("bbs_sid")
        if bbs_token and bbs_sid:
            return f"bbs_token={bbs_token};bbs_sid={bbs_sid}"
        self._log("登录未获取到有效cookies")
        return None

    def get_sign_value(self, cookies: str) -> Optional[str]:
        headers = HeaderManager.build(cookie=cookies, referer=f"{BASE_URL}{URLS['sign_page']}")
        resp = self.session.get(BASE_URL + URLS["sign_page"], headers=headers)
        if resp.status_code != 200:
            self._log(f"获取签到页面失败,状态码: {resp.status_code}")
            return None

        match = re.search(r'var sign = "([\da-f]+)"', resp.text)
        if match:
            return match.group(1)
        if '登录后查看' in resp.text:
            self._log("Cookie失效,请重新登录")
        else:
            self._log("未找到签到签名sign")
        return None

    def sign_in(self, sign: str, cookies: str, max_retries: int = 3) -> str:
        headers = HeaderManager.build(
            cookie=cookies,
            referer=BASE_URL,
            extra={"x-requested-with": "XMLHttpRequest"}
        )
        url = BASE_URL + URLS["sign_post"]
        msg = ""
        for attempt in range(1, max_retries + 1):
            try:
                data = {'sign': sign}
                resp = self.session.post(url, headers=headers, data=data, timeout=15, verify=False)
                text = resp.text.strip()
                if "今天已经签过啦！" in text:
                    msg = '已经签到过了,不再重复签到!'
                    break
                elif "成功" in text:
                    json_resp = json.loads(text)
                    msg = json_resp.get('message', '签到成功')
                    break
                elif "请登录后再签到!" in text:
                    msg = "Cookie未正确设置,请检查"
                    break
                elif "操作存在风险,请稍后重试" in text:
                    msg = "操作风险提示,稍后重试"
                else:
                    msg = f"未知异常: {text}"
                time.sleep(15)
            except Exception as e:
                msg = f"异常发生: {e}"
                time.sleep(20)
        self._log(msg)
        return msg

    def check_cookies(self, cookies: Optional[str]) -> bool:
        if not cookies:
            self._log("未设置cookies")
            return False
        headers = HeaderManager.build(cookie=cookies)
        resp = self.session.get(BASE_URL, headers=headers)
        if resp.status_code != 200:
            self._log("访问首页失败,检查网络")
            return False
        if "nav-item username" in resp.text:
            self._log("cookies有效")
            return True
        self._log("cookies无效")
        return False

    def update_cookies(self) -> Optional[str]:
        self._log("开始获取cookies...")
        sid = self.get_initial_cookies()
        if not sid:
            self._log("获取初始cookies失败")
            return None
        for attempt in range(3):
            captcha_data = self.get_captcha(sid)
            if captcha_data:
                self._log(f"第{attempt+1}次验证码认证成功")
                token = self.login(sid, captcha_data["captchaKey"])
                if token:
                    return token
                self._log("登录失败")
            else:
                self._log(f"第{attempt+1}次验证码认证失败")
            time.sleep(5)
        return None

    def sendNtf(self):
        TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
        TG_USER_ID =  os.getenv("TG_USER_ID")

        if TG_USER_ID == None:
            print("未设置 TG_USER_ID")
        
        if TG_BOT_TOKEN == None:
            print("未设置 TG_BOT_TOKEN")

        url=f'https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage'
        data={
            'chat_id' : TG_USER_ID,
            'text' : "\n".join(self.notifications),
        }
        requests.post(url=url,data=data)

    def updateQingLongCookies(self, cookies):
        def save_cookie_to_qinglong(var_name, cookie_value):
            """将Cookie保存到青龙面板环境变量"""
            import time

            # 获取青龙面板配置
            ql_url = os.environ.get("QL_URL")
            client_id = os.environ.get("QL_CLIENT_ID")
            client_secret = os.environ.get("QL_CLIENT_SECRET")

            if not all([ql_url, client_id, client_secret]):
                print("未设置青龙面板API配置,无法保存Cookie")
                return False

            # 获取青龙API令牌
            token_url = f"{ql_url}/open/auth/token"
            token_params = {
                'client_id': client_id,
                'client_secret': client_secret
            }

            try:
                token_resp = requests.get(token_url, params=token_params)
                token_data = token_resp.json()

                if token_data.get('code') != 200:
                    print(f"获取青龙面板令牌失败: {token_data}")
                    return False

                token = token_data['data']['token']

                # 设置API请求头
                headers = {
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                }

                # 查询变量是否存在
                envs_url = f"{ql_url}/open/envs"
                envs_resp = requests.get(envs_url, headers=headers)
                envs_data = envs_resp.json()

                if envs_data.get('code') != 200:
                    print(f"查询环境变量失败: {envs_data}")
                    return False

                # 查找指定变量
                env_id = None
                for env in envs_data['data']:
                    if env['name'] == var_name:
                        env_id = env['id']
                        break

                # 更新或创建变量
                remarks = f"HIFINI签到自动更新-{time.strftime('%Y-%m-%d %H:%M:%S')}"

                if env_id:  # 更新现有变量
                    update_data = {
                        "id": env_id,
                        "name": var_name,
                        "value": cookie_value,
                        "remarks": remarks
                    }
                    update_resp = requests.put(envs_url, headers=headers, json=update_data)
                    update_result = update_resp.json()

                    if update_result.get('code') == 200:
                        print(f"成功更新青龙环境变量: {var_name}")
                        return True
                    else:
                        print(f"更新环境变量失败: {update_result}")
                        return False
                else:  # 创建新变量
                    create_data = [{
                        "name": var_name,
                        "value": cookie_value,
                        "remarks": remarks
                    }]
                    create_resp = requests.post(envs_url, headers=headers, json=create_data)
                    create_result = create_resp.json()

                    if create_result.get('code') == 200:
                        print(f"成功创建青龙环境变量: {var_name}")
                        return True
                    else:
                        print(f"创建环境变量失败: {create_result}")
                        return False

            except Exception as e:
                print(f"调用青龙API出错: {e}")
                return False
        save_cookie_to_qinglong("HIFINI_COOKIES", cookies)

def main():
    # HIFINI_COOKIES 
    # HIFINI_USER
    # HIFINI_PASS

    # QL_CLIENT_ID
    # QL_CLIENT_SECRET
    # TG_BOT_TOKEN
    # TG_USER_ID

    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    client = HifiniClient()
    cookies = os.getenv("HIFINI_COOKIES")

    if not client.check_cookies(cookies):
        cookies = client.update_cookies()
        if not cookies:
            client._log("获取cookies失败,退出")
            return
        client.updateQingLongCookies(cookies)

    sign = client.get_sign_value(cookies)
    if not sign:
        client._log("未获取到签到签名,签到失败")
        return

    client.sign_in(sign, cookies)
    client.sendNtf()
    # print("\n日志已写入", LOG_FILE)



if __name__ == "__main__":
    main()
