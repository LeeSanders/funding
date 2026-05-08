# Funding

这是一个基于真实基金数据的基金研究工作台，包含以下核心能力：

- 单基金分析：根据基金代码拉取真实数据，输出技术面、消息面、风险项和操作建议
- 持仓实时估值：支持持仓录入、盘中估值刷新、正式净值切换和收益联动
- OCR 识别：上传持仓截图，自动识别基金代码、金额和收益并导入持仓
- 基金推荐中心：基于真实市场候选池生成推荐列表，并给出推荐分和推荐原因

## 项目结构

- `frontend/`: React + Vite + TypeScript 前端工程
- `frontend/public/workspace/index.html`: 当前主工作台页面
- `backend/`: FastAPI 后端、模型、服务和迁移文件
- `database/`: 数据库结构文档和 SQL
- `prototype/`: 早期原型页面
- `PRD.md`: 产品需求文档

## 运行环境

建议本地准备以下环境：

- `Python 3.9+`
- `Node.js 18+`
- `npm`

默认情况下，后端会直接使用本地 SQLite：

- 数据库文件：`backend/funding.db`

如果你后续想切换 PostgreSQL，再配置 `.env` 即可。

## 一步步启动服务

### 1. 安装后端依赖

在项目根目录执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 初始化数据库

如果你只是本地直接跑，默认用 SQLite，不需要额外配数据库。

```bash
source .venv/bin/activate
PYTHONPATH=backend python -m app.scripts.init_db
```

如果你想按迁移文件执行，也可以用：

```bash
source .venv/bin/activate
alembic -c backend/alembic.ini upgrade head
```

### 3. 启动后端服务

```bash
source .venv/bin/activate
PYTHONPATH=backend uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload
```

启动成功后可访问：

- 接口文档：`http://127.0.0.1:8002/docs`
- 健康检查：`http://127.0.0.1:8002/api/v1/health`

### 4. 启动前端服务

新开一个终端，进入项目根目录后执行：

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5175
```

启动成功后可访问：

- 前端首页：`http://127.0.0.1:5175/`
- 工作台：`http://127.0.0.1:5175/workspace/index.html?apiBase=http://127.0.0.1:8002/api/v1`

## 可选环境变量

项目根目录可创建 `.env` 文件，格式示例见 `backend/.env.example`。

最常见的配置项如下：

```env
FUNDING_APP_NAME=Funding Backend
FUNDING_API_PREFIX=/api/v1
FUNDING_DATABASE_URL=sqlite:///./backend/funding.db
FUNDING_LLM_BASE_URL=
FUNDING_LLM_API_KEY=
FUNDING_LLM_MODEL=
FUNDING_LLM_TIMEOUT_SECONDS=20
```

说明：

- 不写 `.env` 也能直接跑，默认就是本地 SQLite
- 如果配置了兼容 OpenAI 的模型服务，AI 总结会走真实模型
- 如果不配置模型，系统会使用本地兜底总结逻辑

## 常用开发命令

### 后端

```bash
source .venv/bin/activate
PYTHONPATH=backend uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload
```

### 前端

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5175
```

### 构建前端

```bash
cd frontend
npm run build
```

## 常见问题

### 1. 页面打开后没有数据

先确认两个服务都正常启动：

- 前端：`http://127.0.0.1:5175`
- 后端：`http://127.0.0.1:8002/docs`

然后确认工作台 URL 里带了 `apiBase`：

```text
http://127.0.0.1:5175/workspace/index.html?apiBase=http://127.0.0.1:8002/api/v1
```

### 2. OCR 或推荐功能比较慢

首次请求会去抓真实基金数据，速度会受外部数据源影响。后续同类请求通常会更快。

### 3. 想切换数据库到 PostgreSQL

在根目录 `.env` 里把 `FUNDING_DATABASE_URL` 改成 PostgreSQL 连接串即可，例如：

```env
FUNDING_DATABASE_URL=postgresql+psycopg://funding:funding@127.0.0.1:5432/funding
```

## 如何上传到你自己的 GitHub

如果你不会用 GitHub，可以按下面的步骤来：

### 第一步：去 GitHub 新建一个空仓库

1. 打开 [GitHub](https://github.com)
2. 登录你的个人账号
3. 点击右上角 `+`
4. 选择 `New repository`
5. 仓库名可以填：`Funding`
6. 选择 `Public` 或 `Private`
7. 不要勾选 `Add a README file`
8. 点击 `Create repository`

创建完后，你会看到一个仓库地址，类似：

```text
https://github.com/你的用户名/Funding.git
```

### 第二步：把这个仓库地址发给我

你只需要把类似下面这一行发给我：

```text
https://github.com/你的用户名/Funding.git
```

### 第三步：我帮你执行本地 Git 初始化和推送

拿到仓库地址后，我会继续帮你做这些事情：

```bash
git init
git add .
git commit -m "feat: initialize funding workspace"
git branch -M main
git remote add origin <你的 GitHub 仓库地址>
git push -u origin main
```

如果 GitHub 在推送时要求登录，我也会继续告诉你下一步怎么点、怎么填。
