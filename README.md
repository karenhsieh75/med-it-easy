# 🩺 Med It Easy

**Med It Easy** is an AI-powered clinical decision support system designed to streamline the interaction between patients and doctors. By utilizing Large Language Models (LLMs), the platform offers:

- **Interactive Patient Interface**: Enables users to easily schedule appointments and articulate symptoms through an AI chatbot that asks smart follow-up questions.
- **Physician Support**: Provides doctors with structured medical summaries and preliminary disease predictions to assist in diagnosis.
- **Enhanced Efficiency**: Aims to alleviate clinical workloads and improve the overall quality of healthcare services.

## 🚀 Getting Start

### Install uv
Follow the official installation guide:  
👉 [https://docs.astral.sh/uv/getting-started/installation/#installation-methods](https://docs.astral.sh/uv/getting-started/installation/)

### Install dependencies

```bash
uv sync
```

## ▶️ Run the App
### Start the backend

```bash
uv run uvicorn app.main:app --reload
```

Swagger Docs: http://localhost:8000/docs
