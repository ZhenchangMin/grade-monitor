# -*- coding: utf-8 -*-
"""Server酱 通知渠道（微信推送）。https://sct.ftqq.com/"""

import requests

from .base import Notifier


class ServerChanNotifier(Notifier):
    name = "serverchan"

    def __init__(self, send_key: str, timeout: int = 10):
        if not send_key or "在这里粘贴" in send_key:
            raise ValueError("serverchan.send_key 未配置或仍是占位符")
        self.send_key = send_key
        self.timeout = timeout

    def send(self, title: str, content: str) -> bool:
        try:
            resp = requests.post(
                f"https://sctapi.ftqq.com/{self.send_key}.send",
                data={"title": title, "desp": content}, timeout=self.timeout,
            )
            code = resp.json().get("code")
            if code != 0:
                print(f"[serverchan] 返回异常: {resp.text[:200]}")
                return False
            return True
        except Exception as e:
            print(f"[serverchan] 推送失败: {e}")
            return False
