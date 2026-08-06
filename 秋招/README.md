# 2027 届法学岗位招聘信息监控

基于 GitHub Actions + Python + 企业微信群机器人的微信公众号招聘信息监控工具。

## 功能

- 通过搜狗微信文章搜索关键词（如 `2027校园招聘`）召回相关公众号文章；
- 在搜索结果中按法学 / 法律岗位相关关键词过滤；
- 去重后通过企业微信群机器人推送消息；
- 不固定监控任何公众号，覆盖范围更广。

## 快速开始

1. Fork/克隆本仓库到 GitHub 公开仓库。
2. 在企业微信群里添加一个机器人，复制 Webhook Key。
3. 在仓库 **Settings → Secrets and variables → Actions** 中添加 `WECOM_WEBHOOK_KEY`。
4. （可选）编辑 `config/monitor.yaml` 中的 `search.queries` 调整搜索关键词。
5. 手动运行 `.github/workflows/monitor.yml` 测试推送。
6. 监控任务会在每天北京时间 07:05 自动运行。

## 配置说明

`config/monitor.yaml` 中关键字段：

```yaml
search:
  queries:                 # 搜狗微信文章搜索的查询词列表
    - "2027校园招聘"
    - "2027秋招"
    - "2027校招"
    - "2027届招聘"
  max_pages_per_query: 3   # 每个查询词最多翻几页
  max_articles_total: 100  # 本次运行最多处理多少篇文章
  send_empty_notice: false # 没有匹配时是否发送“今日无新岗位”

filter:
  law_keywords:            # 法律相关词（命中才推送）
    - 律所
    - 法务
    - 律师
    - 法律
    - 法学生
    - 法学
    - 红圈
  job_keywords:            # 岗位相关词
    - 招聘
    - 实习
    - 暑期
    - 校招
    - 秋招
    - 春招
    - 留用
    - 全职
    - 兼职
    - 助理
    - 授薪
  year_patterns:           # 届别匹配
    - "2027"
    - "2027届"
    - "27届"
  negative:                # 排除词
    - 培训课
    - 课程
    - 考研
    - 留学中介
    - 广告
```

匹配规则：
- 标题或摘要同时包含 **法律相关词 + 岗位词**，或
- 同时包含 **届别 + 岗位词**，
- 且不包含 **排除词**。

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
- 只推送文章标题和链接，不抓取全文；
- 首次运行会自动跳过历史旧文章，避免一次性推送大量过期内容。

## 目录

```text
├── .github/workflows/   GitHub Actions 工作流
├── src/                 Python 源码
├── config/              用户配置
├── data/                运行状态（由机器人自动提交）
└── tests/               单元测试
```
