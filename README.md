# 🩺 Med It Easy

**Med It Easy** is an AI-powered clinical decision support system designed to streamline the interaction between patients and doctors. By utilizing Large Language Models (LLMs), the platform offers:

- **Interactive Patient Interface**: Enables users to easily schedule appointments and articulate symptoms through an AI chatbot that asks smart follow-up questions.
- **Physician Support**: Provides doctors with structured medical summaries and preliminary disease predictions to assist in diagnosis.
- **Enhanced Efficiency**: Aims to alleviate clinical workloads and improve the overall quality of healthcare services.

## 📁 Project Structure

```
med-it-easy/
├── app/
│   ├── main.py              # FastAPI 應用程式入口
│   ├── database.py          # 資料庫連線設定
│   ├── models.py            # SQLModel 資料模型定義
│   ├── utils.py             # 共用工具函式
│   │
│   ├── routers/             # API 路由模組
│   │   ├── user.py          # 使用者相關 API（註冊、登入）
│   │   ├── appointment.py   # 預約掛號 API
│   │   ├── symptoms.py      # 症狀記錄 API
│   │   ├── ai.py            # AI 聊天機器人 API
│   │   ├── medical_records.py # 病歷管理 API
│   │   └── analysis.py      # 分析功能 API（膚色分析等）
│   │
│   ├── services/            # 商業邏輯服務
│   │   ├── ai_service.py    # AI 摘要與疾病預測服務
│   │   ├── skin_tone.py     # 膚色分析服務
│   │   └── card_generator.py # 卡片生成服務
│   │
│   └── assets/              # 靜態資源（字型、圖片等）
│
├── static/                  # 前端靜態檔案
│   └── index.html
│
├── seed_data.py             # 測試資料初始化腳本
├── pyproject.toml           # 專案依賴設定
└── med-it-easy.db           # SQLite 資料庫
```

## 🚀 Getting Start

### Install uv
Follow the official installation guide:  
👉 [https://docs.astral.sh/uv/getting-started/installation/#installation-methods](https://docs.astral.sh/uv/getting-started/installation/)

### Install dependencies

```bash
uv sync
```

### Environment Setup
Create a `.env` file in the root directory and add your Google Gemini API key:

```bash
GOOGLE_API_KEY=
```


### Mock database

```bash
uv run seed_data.py
```
<!-- 安裝 vscode SQLite Viewer 的 extension 則可以看到完整 med-it-easy.db-->

### 關鍵套件
```bash
pip install -r requirements.txt
```


### Start the app

```bash
uv run uvicorn app.main:app --reload
```

Web Page: http://localhost:8000  
  
Swagger Docs: http://localhost:8000/docs

