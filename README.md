# ehall 成绩监控 (grade-monitor)

EMAP 框架高校（南京大学等）的 **ehall 成绩**：定时轮询成绩查询接口，与本地基线对比，发现新成绩就通过可插拔通知渠道（[Server酱](https://sct.ftqq.com/) 微信推送、邮件）提醒。

> ⚠️ **免责声明**：本工具仅供查询**本人**成绩使用，只读，不修改任何数据。请设置合理的轮询间隔，勿对学校服务器造成压力。使用者需自行承担合规责任。

---

## 一、安装

```bash
git clone https://github.com/ZhenchangMin/grade-monitor.git
cd grade-monitor
pip install -r requirements.txt
```

依赖：`requests`、`PyYAML`。

## 二、配置

复制配置模板，然后填入你自己的接口参数与凭证：

```bash
cp config.example.yaml config.yaml
```

需要用浏览器 F12（开发者工具）抓取以下三样，填进 `config.yaml`：

1. **`api.api_url`**（成绩数据接口）
   登录 ehall 打开成绩查询页，F12 → **网络(Network)** → 刷新页面 → 找到 `cjcx.do` 请求，复制其完整 URL。
   > 注意是 `.../modules/cjcx/cjcx.do` 这一层，**不是**上一层的 `.../modules/cjcx.do`（那是模块元数据接口，不含成绩）。如果脚本日志打印"这是模块元数据接口，可用子接口"，说明你填错成上一层了，按提示里列出的子接口地址改正。

2. **`api.raw_payload`**（请求体）
   选中该 `cjcx.do` 请求 → **负载(Payload)** → **查看源代码(view source)** → 原样复制整段（是一串 URL 编码的文本，含 `SHOWMAXCJ` / `CJXZ` / `XNXQDM` 过滤条件）。
   > 里面的 `XNXQDM` 指定了学年学期，**换学期需要重新抓取更新**。缺失或参数错误接口会返回 404。

3. **`credentials.cookie`**（会话 Cookie）
   F12 → **网络** → 任一请求 → **请求头(Request Headers)** → **Cookie**，整行复制。
   > **复制 Cookie 后请尽快启动脚本并关闭浏览器标签页**，否则浏览器会把令牌刷走导致刚复制的 Cookie 提前失效。

### 配置通知渠道

`config.yaml` 的 `notifiers` 段支持多渠道，可同时启用；发现新成绩时会**广播给所有启用的渠道**。把想用渠道的 `enabled` 设为 `true` 即可。

- **Server酱**（微信推送）：去 <https://sct.ftqq.com/> 注册拿到 SendKey，填入 `notifiers.serverchan.send_key`。
- **邮件**（SMTP，用 Python 标准库、无额外依赖）：填 `notifiers.email`。以常见邮箱为例：

  | 邮箱 | smtp_host | 端口 | 加密设置 | password 填什么 |
  | --- | --- | --- | --- | --- |
  | QQ 邮箱 | `smtp.qq.com` | 465 | `use_ssl: true` | 授权码（非登录密码） |
  | 163 邮箱 | `smtp.163.com` | 465 | `use_ssl: true` | 授权码 |
  | Gmail | `smtp.gmail.com` | 587 | `use_ssl: false` + `use_starttls: true` | 应用专用密码 |
  | Outlook | `smtp.office365.com` | 587 | `use_ssl: false` + `use_starttls: true` | 账号密码 |

  > 多数邮箱要求先在设置里开启 SMTP 并生成**授权码/应用专用密码**，直接用登录密码会认证失败。`to_addrs` 可填多个收件人。

一个都不启用也能跑，只是发现新成绩时仅打印到日志，不推送。

## 三、运行

**前台运行**（调试用，能直接看日志）：

```bash
python3 -u grade_monitor.py
```

指定配置文件：

```bash
python3 -u grade_monitor.py -c /path/to/config.yaml
```

**后台常驻**（服务器长期运行）：

```bash
nohup python3 -u grade_monitor.py > grade.log 2>&1 &
```

> 必须加 `-u`（禁用输出缓冲），否则 `print` 会被缓冲，日志长时间空白。

首次运行会把当前所有课程记录为基线（`grades_seen.json`），不推送；之后出现新课程才推送。看到 `✅ 启动成功：拿到 N 门课` 说明链路正常。

## 四、安全须知（重要）

**凭证一旦进入 git 历史很难彻底清除。** 本仓库已通过 `.gitignore` 忽略 `config.yaml` / `grades_seen.json` / `*.log`。发布前务必确认：

```bash
git status   # 确认输出里没有 config.yaml
```

只提交 `config.example.yaml`，**绝不提交填了真实 Cookie / SendKey 的 `config.yaml`**。

## 五、常见问题

| 现象 | 原因与处理 |
| --- | --- |
| 日志打印诊断、收到"Cookie 已失效"推送 | Cookie 过期或被浏览器刷走，重新复制 Cookie 更新 `config.yaml` 并重启 |
| "这是模块元数据接口，可用子接口……" | `api_url` 填成了上一层，按打印出的子接口地址改正 |
| 接口返回 404 页面 | `raw_payload` 缺失或参数错误，重新从 F12 负载→查看源代码原样复制 |
| 跳转到 authserver | 未登录 / 会话失效，重新登录 ehall 抓 Cookie |
| 后台运行日志长时间空白 | 忘了加 `-u`，用 `python3 -u` 重跑 |