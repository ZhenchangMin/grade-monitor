# -*- coding: utf-8 -*-
"""ehall 成绩自动监控（多渠道通知）。

监控金智教育 EMAP 框架高校（南京大学等）的 ehall 成绩查询接口：
定时轮询 -> 与本地基线对比 -> 发现新成绩通过可插拔渠道（Server酱 / 邮件 …）推送。

所有站点相关配置（接口地址、请求体、字段名、凭证等）都放在 config.yaml，
本文件只负责逻辑，方便跨校适配。用法：

    python3 -u grade_monitor.py            # 读取当前目录 config.yaml
    python3 -u grade_monitor.py -c my.yaml # 指定配置文件
"""

import argparse
import json
import os
import random
import sys
import time

import requests

try:
    import yaml
except ImportError:  # 友好提示缺依赖
    print("缺少依赖 pyyaml，请先执行: pip install -r requirements.txt")
    sys.exit(1)

from notifiers import build_notifiers, broadcast


DEFAULT_CONFIG_PATH = "config.yaml"


def load_config(path):
    """读取 YAML 配置，缺失或格式错误时给出友好提示并退出。"""
    if not os.path.exists(path):
        print(f"找不到配置文件: {path}")
        print("请复制 config.example.yaml 为 config.yaml 并填入你的接口与凭证。")
        sys.exit(1)
    try:
        with open(path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"配置文件解析失败（YAML 语法错误）: {e}")
        sys.exit(1)
    if not isinstance(cfg, dict):
        print(f"配置文件内容异常，应为键值映射: {path}")
        sys.exit(1)
    return cfg


class GradeMonitor:
    """ehall 成绩监控器。

    把已跑通原型的核心逻辑收拢到一个类里，配置全部由外部注入。
    重构时严格保留原型中的关键行为（见 HANDOFF 第三节踩坑记录）：
    - 用 requests.Session 自动跟随 _WEU 滚动令牌
    - POST 携带原样复制的 raw_payload
    - 非 JSON 响应视为失效并打印诊断
    - 只拿到 models 元数据时列出可用子接口帮助定位
    """

    def __init__(self, config):
        api = config.get("api", {})
        cred = config.get("credentials", {})
        fields = config.get("fields", {})

        self.api_url = api.get("api_url", "")
        self.warmup_url = api.get("warmup_url", "")
        self.cookie_domain = api.get("cookie_domain", "")
        self.raw_payload = api.get("raw_payload", "")

        self.cookie = cred.get("cookie", "")

        # 可插拔通知渠道：读取 notifiers 段，构建所有 enabled 的渠道
        self.notifiers = build_notifiers(config.get("notifiers", {}))

        # 字段名可配置，方便其他学校适配（他们的字段名可能不同）
        self.f_term = fields.get("term", "XNXQDM")
        self.f_course_no = fields.get("course_no", "KCH")
        self.f_course_name = fields.get("course_name", "KCM")
        self.f_score = fields.get("score", "ZCJ")
        self.f_credit = fields.get("credit", "XF")

        self.poll_interval_minutes = config.get("poll_interval_minutes", 15)
        self.state_file = config.get("state_file", "grades_seen.json")

        self._validate()

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        # 成绩接口固定请求头
        self.request_headers = {
            "Referer": self.warmup_url,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }

    def _validate(self):
        """启动前校验必填项，缺失则 fail fast。"""
        required = {
            "api.api_url": self.api_url,
            "api.warmup_url": self.warmup_url,
            "api.raw_payload": self.raw_payload,
            "credentials.cookie": self.cookie,
        }
        missing = [k for k, v in required.items() if not v or "在这里粘贴" in str(v)]
        if missing:
            print("以下配置项缺失或仍是占位符，请在 config.yaml 中填写：")
            for k in missing:
                print(f"  - {k}")
            sys.exit(1)
        if not self.notifiers:
            print("警告：没有启用任何通知渠道，发现新成绩时将只在日志中打印。")
            print("请在 config.yaml 的 notifiers 段启用至少一个渠道（serverchan / email）。")

    # ---------- 会话 ----------

    def init_session(self):
        """装入 Cookie 并预热首页建立会话；之后服务器下发的新令牌自动跟随更新。"""
        for pair in self.cookie.strip().split(";"):
            if "=" in pair:
                name, _, value = pair.strip().partition("=")
                self.session.cookies.set(name, value, domain=self.cookie_domain)
        try:
            r = self.session.get(self.warmup_url, timeout=20)
            print(f"预热请求: 状态码 {r.status_code}, 最终URL {r.url[:80]}")
        except requests.RequestException as e:
            print(f"预热请求失败: {e}")

    # ---------- 通知 ----------

    def notify(self, title, content):
        """向所有已启用的通知渠道广播。"""
        broadcast(self.notifiers, title, content)

    # ---------- 抓取 ----------

    def fetch_grades(self):
        """请求成绩接口，成功返回 rows 列表，失效/异常返回 None（并打印诊断）。"""
        resp = self.session.post(
            self.api_url, headers=self.request_headers,
            data=self.raw_payload.strip().encode("utf-8"), timeout=20,
        )
        ctype = resp.headers.get("Content-Type", "")
        if "json" not in ctype or "authserver" in resp.url:
            print(f"---- 诊断 ----\n状态码:{resp.status_code} URL:{resp.url}\n"
                  f"Content-Type:{ctype}\n{resp.text[:300]}")
            return None
        try:
            data = resp.json()
        except Exception:
            print(f"JSON解析失败: {resp.text[:300]}")
            return None

        rows = None
        for val in data.get("datas", {}).values():
            if isinstance(val, dict) and "rows" in val:
                rows = val["rows"]
                break
        if rows is None:
            models = data.get("models")
            if models:  # 打到了元数据接口，列出所有子接口帮助定位
                print("这是模块元数据接口，可用子接口：")
                for m in models:
                    print(f"  - {m.get('name'):<16} {m.get('url')}")
            else:
                print(f"返回结构异常: {json.dumps(data, ensure_ascii=False)[:500]}")
            return None
        return rows

    # ---------- 成绩处理 ----------

    def course_key(self, row):
        """课程唯一标识：学年学期 + 课程号（课程号缺失时退回课程名）。"""
        term = row.get(self.f_term, "")
        no = row.get(self.f_course_no, row.get(self.f_course_name, ""))
        return f"{term}-{no}"

    def format_course(self, row):
        name = row.get(self.f_course_name, "未知课程")
        score = row.get(self.f_score, "?")
        credit = row.get(self.f_credit, "?")
        return f"{name}: {score} (学分 {credit})"

    def load_state(self):
        if os.path.exists(self.state_file):
            with open(self.state_file, encoding="utf-8") as f:
                return set(json.load(f))
        return None

    def save_state(self, keys):
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(sorted(keys), f, ensure_ascii=False, indent=2)

    # ---------- 主循环 ----------

    def run(self):
        cookie_dead = False
        started_ok = False
        print(f"开始监控，每 {self.poll_interval_minutes} 分钟检查一次。")
        self.init_session()
        while True:
            try:
                rows = self.fetch_grades()
                if rows is None:
                    if not cookie_dead:
                        self.notify("成绩监控：Cookie 已失效", "请重新复制 Cookie 更新配置。")
                        cookie_dead = True
                else:
                    if not started_ok:
                        started_ok = True
                        print(f"✅ 启动成功：拿到 {len(rows)} 门课。")
                    cookie_dead = False
                    current = {self.course_key(r): r for r in rows}
                    seen = self.load_state()
                    if seen is None:
                        self.save_state(current.keys())
                        print(f"首次运行，记录 {len(current)} 门课作为基线。")
                    else:
                        new = set(current) - seen
                        if new:
                            self.notify(
                                f"出新成绩了！({len(new)} 门)",
                                "\n\n".join(self.format_course(current[k]) for k in new),
                            )
                            self.save_state(current.keys())
                        else:
                            print(f"{time.strftime('%H:%M:%S')} 无新成绩 (共 {len(current)} 门)")
            except requests.RequestException as e:
                print(f"网络错误: {e}")
            except KeyboardInterrupt:
                print("\n已停止监控。")
                sys.exit(0)
            time.sleep(self.poll_interval_minutes * 60 + random.randint(0, 60))


def parse_args():
    parser = argparse.ArgumentParser(description="ehall 成绩自动监控（Server酱通知版）")
    parser.add_argument("-c", "--config", default=DEFAULT_CONFIG_PATH,
                        help=f"配置文件路径（默认 {DEFAULT_CONFIG_PATH}）")
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config(args.config)
    monitor = GradeMonitor(config)
    monitor.run()


if __name__ == "__main__":
    main()
