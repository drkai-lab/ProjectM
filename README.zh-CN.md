# Project W

Project W 是一个简单的监控面板。它会定期查看马来西亚政府机构及相关机构的网站，在发现页面更新或出现指定关键词时通知你。

## 可以做什么

- 自动定期检查已登记的网站
- 判断网页内容是否与上一次不同
- 搜索你指定的词语，例如“申请”“通行证”“费用”等
- 把更新和关键词命中结果发送到 Telegram
- 在浏览器中添加、删除或暂时停用监控网站和关键词
- 查看下次检查时间和最近的检查记录
- 使用登录链接或密码登录
- 支持日语、英语、中文、马来语和韩语界面

第一次启动时，系统会自动加入一批马来西亚政府部门和公共机构的网站，以及一些常用关键词。之后可以按需要修改。

## 页面说明

### 控制面板

这里会显示网站总数、当前启用的网站数、关键词数、最近的检查结果，以及下次检查时间。

### 网站

在这里管理要监控的URL。每个网站都可以设置显示名称、访问方式，以及是否启用。

### 设置

可以调整检查间隔、每天的执行时间和时区。管理员还可以添加用户、修改权限和冻结账号。

## 用户权限

- **管理员**：可以管理所有设置和用户
- **编辑者**：可以修改网站、关键词和检查计划
- **查看者**：主要用于查看结果

## 工作流程

1. Project W 访问所有已启用的网站。
2. 读取网页中的文字，并与上次保存的内容比较。
3. 如果内容发生变化，就搜索已登记的关键词。
4. 找到关键词时，保存网站地址、命中的词和一小段内容摘要。
5. 如果配置了 Telegram，就发送通知。

如果网站无法访问，系统也会把失败的网站和原因记录下来。过大的页面，以及图片、压缩包等非文字内容不会作为正常网页处理。

## 安装

### 需要准备什么

- Python 3.11 或更高版本
- `uv`
- 如果需要 Telegram 通知：Telegram Bot Token 和接收通知的聊天ID
- 如果需要通过邮件发送登录链接：Resend API Key

### 安装依赖

```bash
uv sync
```

### 环境变量

请把秘密信息放在 `.env` 文件或运行环境的环境变量中，不要直接写进源代码。

```dotenv
PW_ENV=development
PW_SECRET_KEY=一串足够长的随机字符串
PW_SUPERUSER_EMAIL=管理员邮箱
PW_SUPERUSER_PASSWORD=管理员密码
PW_PUBLIC_URL=http://localhost:8000

# 可选：Telegram 通知
PW_TELEGRAM_TOKEN=Telegram Bot Token
PW_TELEGRAM_CHAT_ID=接收通知的聊天ID
PW_NOTIFY_LANG=zh

# 可选：邮件登录链接
RESEND_API_KEY=Resend API Key
PW_MAIL_FROM=ProjectW <发件地址>
```

在生产环境中，`PW_SECRET_KEY`必须至少有32个字符，并且要设置 `PW_COOKIE_SECURE=1`。管理员邮箱和密码也必须填写。

### 启动

开发环境可以使用下面的命令启动：

```bash
uv run uvicorn app.main:app --reload
```

然后在浏览器中打开 `http://localhost:8000`。

## 数据保存位置

默认情况下，SQLite 数据库保存在 `data/projectw.db`。如需更换位置，可以设置：

```dotenv
PW_DATA_DIR=/path/to/data
# 或者
PW_DB_URL=sqlite:////path/to/projectw.db
```

监控记录、网站、关键词和用户设置都会保存在这个数据库中。

## 健康检查

```text
GET /api/health
```

服务正常时，会返回 `ok` 和下次检查时间。

## 测试

```bash
uv run pytest
```

## 使用时请注意

- 只能登记公开的HTTP或HTTPS网站。
- localhost、内网和私有IP地址会被拒绝。
- 不要把密码、签名密钥或 Telegram Token 提交到Git仓库。
- Project W 只是帮助你发现网页变化。涉及重要手续或截止日期时，请务必直接查看官方网页。

## 技术简介

Project W 是一个由 FastAPI、SQLAlchemy、SQLite、APScheduler 和 Jinja2 组成的服务器应用。它支持在手机上使用的PWA界面，并通过HTTP方式获取网页；在可用的环境中，也可以使用更接近真实浏览器的访问方式。
