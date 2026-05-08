# Backend

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment

```bash
cp backend/.env.example .env
```

默认 `.env.example` 里的数据库指向 PostgreSQL。若仅做本地 Demo，可以继续使用代码中的 SQLite 默认值。
若要启用真实 AI 总结，可额外配置：

```bash
FUNDING_LLM_BASE_URL=https://your-openai-compatible-endpoint
FUNDING_LLM_API_KEY=your_api_key
FUNDING_LLM_MODEL=your_model_name
```

未配置时，系统会自动使用本地兜底总结逻辑，保证分析接口可用。

## Init Database

```bash
PYTHONPATH=backend python -m app.scripts.init_db
```

## Migration

```bash
alembic -c backend/alembic.ini upgrade head
```

V1 表结构迁移文件位于 [20260506_0001_schema_v1.py](file:///Users/bytedance/Documents/Trae/Funding/backend/migrations/versions/20260506_0001_schema_v1.py)。

## Run

```bash
PYTHONPATH=backend uvicorn app.main:app --reload --port 8000
```

## API

- `GET /api/v1/health`
- `GET /api/v1/funds/{code}`
- `GET /api/v1/analysis/{code}`
- `GET /api/v1/recommendations?strategy=balanced`
- `GET /api/v1/portfolio`
- `POST /api/v1/portfolio/holdings`
- `POST /api/v1/ocr/simulate`
- `GET /api/v1/ocr/{job_id}`
- `POST /api/v1/ocr/{job_id}/confirm`
