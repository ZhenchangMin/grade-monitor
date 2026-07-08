# -*- coding: utf-8 -*-
"""通知渠道包。

对外暴露 build_notifiers()：读取 config 的 notifiers 段，
构建所有 enabled 的渠道；以及 broadcast()：向多个渠道广播一条通知。
"""

from .base import Notifier
from .serverchan import ServerChanNotifier
from .email_notifier import EmailNotifier

# 渠道名 -> 构造函数（接收该渠道的 config 子字典，已去掉 enabled 键）
_REGISTRY = {
    "serverchan": lambda c: ServerChanNotifier(send_key=c.get("send_key", "")),
    "email": lambda c: EmailNotifier(
        smtp_host=c.get("smtp_host", ""),
        smtp_port=c.get("smtp_port", 465),
        username=c.get("username", ""),
        password=c.get("password", ""),
        from_addr=c.get("from_addr", ""),
        to_addrs=c.get("to_addrs", []),
        use_ssl=c.get("use_ssl", True),
        use_starttls=c.get("use_starttls", False),
    ),
}


def build_notifiers(notifiers_config: dict) -> list:
    """根据配置构建启用的通知渠道列表。

    notifiers_config 形如 {"serverchan": {"enabled": true, ...}, "email": {...}}。
    只构建 enabled 为 true 的渠道；某个渠道配置不全会打印警告并跳过，不影响其他渠道。
    """
    notifiers = []
    if not notifiers_config:
        return notifiers
    for name, conf in notifiers_config.items():
        if not isinstance(conf, dict) or not conf.get("enabled"):
            continue
        factory = _REGISTRY.get(name)
        if factory is None:
            print(f"[通知] 未知渠道 '{name}'，已跳过。可用：{', '.join(_REGISTRY)}")
            continue
        try:
            notifiers.append(factory(conf))
            print(f"[通知] 已启用渠道: {name}")
        except Exception as e:
            print(f"[通知] 渠道 '{name}' 初始化失败，已跳过: {e}")
    return notifiers


def broadcast(notifiers: list, title: str, content: str) -> None:
    """向所有渠道广播一条通知，单个失败不影响其他。"""
    print(f"[通知] {title}\n{content}")
    for n in notifiers:
        ok = n.send(title, content)
        if not ok:
            print(f"[通知] 渠道 {n.name} 发送失败。")


__all__ = ["Notifier", "build_notifiers", "broadcast"]
