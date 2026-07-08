# -*- coding: utf-8 -*-
"""通知渠道的统一接口。

每个渠道（Server酱、邮件、后续的 Bark/Telegram 等）实现一个 Notifier 子类，
只需实现 send()。主程序通过 factory 构建一个 Notifier 列表并广播，
新增渠道不改主逻辑，符合可插拔设计。
"""

from abc import ABC, abstractmethod


class Notifier(ABC):
    """通知渠道基类。"""

    # 渠道名，用于日志展示；子类覆盖
    name = "base"

    @abstractmethod
    def send(self, title: str, content: str) -> bool:
        """发送一条通知。成功返回 True，失败返回 False（不应抛异常）。"""
        raise NotImplementedError
