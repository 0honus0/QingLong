import os
import time
import hashlib
import json
import notify

import requests

# 机场地址（尾部不要带 /）
URL = os.environ.get("URL", "").rstrip("/")
# 账号配置：一行账号，一行密码
CONFIG = os.environ.get("CONFIG", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

msg = []


def solve_pow(session):
    """SSPanel PoW 登录防机器人：POST /auth/pow_challenge 获取挑战并求解 nonce。

    页面 worker 算法：
      prefix = str(timestamp) + ip + str(difficulty) + salt
      threshold = floor(0xFFFFFF / difficulty)
      从 n=0 递增，SHA-256(prefix + n) 前 3 字节组成的 24 位整数 < threshold 即成功
    """
    r = session.post(f"{URL}/auth/pow_challenge", timeout=30)
    r.raise_for_status()
    c = r.json()
    prefix = f"{c['timestamp']}{c['ip']}{c['difficulty']}{c['salt']}"
    threshold = 0xFFFFFF // c["difficulty"]
    nonce = 0
    while nonce < 50_000_000:
        h = hashlib.sha256(f"{prefix}{nonce}".encode()).digest()
        if (h[0] << 16) | (h[1] << 8) | h[2] < threshold:
            return {
                "pow_timestamp": c["timestamp"],
                "pow_ip": c["ip"],
                "pow_difficulty": c["difficulty"],
                "pow_salt": c["salt"],
                "pow_signature": c["signature"],
                "pow_nonce": nonce,
            }
        nonce += 1
    raise RuntimeError("PoW solve failed (50M tries)")


def sign(order, user, pwd):
    global msg
    session = requests.Session()
    session.headers.update({"origin": URL, "referer": f"{URL}/auth/login", **HEADERS})
    try:
        print(f"===账号{order}进行登录...===")
        print(f"账号：{user}")
        # 1. 建立会话 cookie
        session.get(f"{URL}/auth/login", timeout=30)
        time.sleep(0.5)
        # 2. 求解 PoW
        pow_fields = solve_pow(session)
        print(f"PoW 求解成功 nonce={pow_fields['pow_nonce']}")
        # 3. 求解后延迟 ~2 秒再提交，否则服务器报"操作过快"
        time.sleep(2)
        data = {"email": user, "passwd": pwd, "code": "", "remember_me": ""}
        data.update(pow_fields)
        res = session.post(f"{URL}/auth/login", data=data, timeout=30).text
        print(res)
        resp = json.loads(res)
        print(resp.get("msg"))
        if resp.get("ret") != 1:
            msg += [{"name": "登录信息", "value": f"登录失败: {resp.get('msg')}"}]
            return
        msg += [{"name": "登录信息", "value": "登录成功"}]
        # 4. 签到
        time.sleep(1)
        res2 = session.post(f"{URL}/user/checkin", timeout=30).text
        print(res2)
        result = json.loads(res2)
        print(result.get("msg"))
        msg += [{"name": "签到信息", "value": result.get("msg")}]
    except Exception as ex:
        print(f"出现如下异常{ex}")
        msg += [{"name": "签到信息", "value": f"签到失败: {ex}"}]
    finally:
        print(f"===账号{order}签到结束===")


def main():
    if not URL or not CONFIG:
        print("缺少 URL 或 CONFIG 环境变量")
        return "缺少 URL 或 CONFIG 环境变量"
    lines = CONFIG.splitlines()
    if len(lines) % 2 != 0 or len(lines) == 0:
        print("配置文件格式错误")
        return "配置文件格式错误"
    for i in range(0, len(lines), 2):
        sign(i // 2, lines[i], lines[i + 1])
    return "\n".join([f"{one.get('name')}: {one.get('value')}" for one in msg])


if __name__ == "__main__":
    print(" 机场签到开始 ".center(60, "="))
    res = main()
    print(res)
    notify.send("机场签到", res)
    print(" 机场签到结束 ".center(60, "="), "\n")
