# AI SQL Assistant

An AI-powered assistant that converts natural language queries to SQL using Google Gemini + LangGraph.

## 📂 Project Structure

- `sql-assistance-frontend/`: UI built with HTML, CSS, JS
- `sql-assistance-backend/`: Python backend using LangGraph, SQLAlchemy, Google Gemini

## 🔐 Setup

### 1. Clone & Install Dependencies

```bash
cd sql_agent_-backend
pip install -r requirements.txt
```

## ⚙️ Backend Setup

> Located in `sql_agent_backend`

### 1. 🔧 Prerequisites

- Python 3.8+
- PostgreSQL (with an existing database)
- Google AI Key (for Gemini)
- `psycopg2` and `langchain` dependencies

---

### 2. 📦 Install Dependencies

```bash
cd sql_agent_backend
python -m venv venv
source venv/bin/activate  # For Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. 📁 Environment Variables
Create a .env file in the project root 
You can use .env.example as a template
```bash
cp .env.example .env
```

4. 🚀 Run Frontend
Simply open the HTML file in your browser:
open index.html

Then from sql_agent_backend:

```bash

python sql_agent.py
```
This will:

Load schema from PostgreSQL

Run LangGraph to interpret user prompts

Generate & validate SQL

Execute and return results
