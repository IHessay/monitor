# 2027 届法学岗位招聘信息监控

基于 GitHub Actions + Python + 企业微信群机器人的微信公众号招聘信息监控工具。

## 功能

- 自动通过搜狗微信搜索发现法学招聘相关公众号；
- 每日定时抓取已确认公众号的最新文章；
- 按 2027 届、法学、招聘等关键词过滤；
- 去重后通过企业微信群机器人推送消息。

## 快速开始

1. Fork/克隆本仓库到 GitHub 公开仓库。
2. 在企业微信群里添加一个机器人，复制 Webhook Key。
3. 在仓库 **Settings → Secrets and variables → Actions** 中添加 `WECOM_WEBHOOK_KEY`。
4. 手动运行 `.github/workflows/discover.yml` 生成候选公众号列表 `data/candidates.json`。
5. 将确认的公众号名称写入 `config/monitor.yaml` 的 `monitor.accounts`。
6. 手动运行 `.github/workflows/monitor.yml` 测试推送。
7. 监控任务会在每天北京时间 07:05 自动运行。

## 本地干跑

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 只打印，不发送、不提交状态
$env:DRY_RUN="true"  # Windows PowerShell
# 或
DRY_RUN=true python -m src.main
```

## 注意事项

- 本工具仅用于个人求职，抓取频率低；
- 搜狗/微信有反爬机制，可能出现验证码导致偶发漏抓；
- 只推送文章标题和链接，不抓取全文。

## 目录

```text
├── .github/workflows/   GitHub Actions 工作流
├── src/                 Python 源码
├── config/              用户配置
├── data/                运行状态与候选账号（由机器人自动提交）
└── tests/               单元测试
```
