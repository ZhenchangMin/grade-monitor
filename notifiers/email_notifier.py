# -*- coding: utf-8 -*-
"""邮件通知渠道（SMTP）。使用 Python 标准库，无额外依赖。

支持两种加密方式：
- SSL（如 QQ 邮箱 465 端口）：use_ssl: true
- STARTTLS（如 Gmail/Outlook 587 端口）：use_ssl: false + use_starttls: true
"""

import smtplib
from email.header import Header
from email.mime.text import MIMEText

from .base import Notifier


class EmailNotifier(Notifier):
    name = "email"

    def __init__(self, smtp_host, smtp_port, username, password, from_addr,
                 to_addrs, use_ssl=True, use_starttls=False, timeout=15):
        if not smtp_host:
            raise ValueError("email.smtp_host 未配置")
        if not password or "在这里粘贴" in str(password):
            raise ValueError("email.password 未配置或仍是占位符（多数邮箱需用授权码而非登录密码）")
        # to_addrs 允许字符串或列表
        if isinstance(to_addrs, str):
            to_addrs = [to_addrs]
        if not to_addrs:
            raise ValueError("email.to_addrs 未配置收件人")

        self.smtp_host = smtp_host
        self.smtp_port = int(smtp_port)
        self.username = username
        self.password = password
        self.from_addr = from_addr or username
        self.to_addrs = list(to_addrs)
        self.use_ssl = use_ssl
        self.use_starttls = use_starttls
        self.timeout = timeout

    def _connect(self):
        if self.use_ssl:
            return smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=self.timeout)
        server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.timeout)
        if self.use_starttls:
            server.starttls()
        return server

    def send(self, title: str, content: str) -> bool:
        msg = MIMEText(content, "plain", "utf-8")
        msg["Subject"] = Header(title, "utf-8")
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)
        try:
            server = self._connect()
            try:
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.sendmail(self.from_addr, self.to_addrs, msg.as_string())
            finally:
                server.quit()
            return True
        except Exception as e:
            print(f"[email] 发送失败: {e}")
            return False
