# Customer Support AI Assistant

## Overview

AI-powered customer support assistant built with LangChain and LangGraph. Combines RAG (Retrieval Augmented Generation) for general knowledge queries with database tools for specific customer data operations.


## Features

- **🎯 Intent Classification**: Automatically routes customer requests to appropriate handlers
- **📦 Order Tracking**: Track orders by order ID or tracking number
- **🚚 Delivery Options**: Get shipping options and costs by region
- **💳 Payment Support**: Handle failed payments and retry procedures
- **↩️ Returns Processing**: Check return eligibility and process return requests
- **📚 RAG Knowledge Base**: Answer general questions using customer support documentation

## Architecture

The system uses a graph-based workflow with 4 main branches:

1. **RAG Agent** - Handles general policy questions using knowledge base
2. **React Tool Agent** - Uses database tools for specific customer queries
3. **General Response** - Handles greetings and casual conversation
4. **Cannot Help** - Politely declines out-of-scope requests


<img width="703" height="256" alt="Screenshot 2025-09-01 at 00 27 54" src="https://github.com/user-attachments/assets/69faa2aa-badd-43fb-a6ee-112866ab6e03" />

## Prerequisites

- **uv package manager**: Install from [docs.astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/)
- **just command runner**: Install from [github.com/casey/just](https://github.com/casey/just)
- **Docker & Docker Compose**: For PostgreSQL database

## Setup

### 1. Project Dependencies
```bash
git clone <repo>
cd complex-langgraph
uv sync  # Creates .venv and installs dependencies
```

### 2. Environment Configuration
```bash
cp .env.example .env
```

Add your OpenAI API key:
```
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/cs_support
```

### 3. Database Setup

Start PostgreSQL using Docker Compose:
```bash
docker-compose up -d
```

Seed the database with test data:
```bash
just seed-db
```

This creates:
- Customer tables with sample customers (Alice, Bob, Carlos, Diana, Eva)
- 5 sample orders with different statuses (Shipped, PendingPayment, Delivered, Canceled)
- Shipping methods for US domestic and international delivery
- Payment records including failed payments for testing
- Return requests and shipment tracking events

### 4. Knowledge Base

The RAG knowledge base is pre-embedded in `chroma_db/`. To re-embed from source:
```bash
just embed
```

This processes markdown files from `cs_knowledge_base/` covering:
- **Delivery**: Options, pricing, SLA policies
- **Payment**: Retry procedures, failure reasons, update methods
- **Returns**: Policy overview, process steps, refunds
- **Tracking**: Status definitions, tracking playbook

## Running the Application

### LangGraph Studio (Development)
```bash
just run-langgraph
```
Opens LangGraph Studio at http://localhost:2024 for debugging the conversation flow.

### Streamlit Interface
```bash
just app
```
Launches the Streamlit chat interface at http://localhost:8501.

## Test Cases & Examples

### 🔍 RAG Queries (Knowledge Base)

**Returns Policy:**
```
"Расскажи про политику возвратов"
"Сколько дней на возврат товара?"
"Кто оплачивает обратную доставку?"
```

**Delivery Information:**
```
"Какие есть варианты доставки?"
"Сроки международной доставки"
"Стоимость экспресс доставки"
```

**Payment Help:**
```
"Что делать если платёж не прошёл?"
"Как повторить оплату?"
"Почему карта была отклонена?"
```

### 🛠️ Database Tool Queries

**Order Tracking:**
```
"Где сейчас мой заказ 1001?"
"Статус заказа #1004?"
"Доставлен ли заказ 1003?"
```

**Delivery Options:**
```
"Какие есть варианты доставки по США?"
"Сколько стоит международная доставка?"
"Самый дешёвый способ доставки в Канаду?"
```

**Payment Issues:**
```
"Оплата по заказу 1002 не прошла. Что делать?"
"Могу ли я повторить оплату заказа 1002?"
"Почему списание не прошло по заказу #1002?"
```

**Returns:**
```
"Хочу вернуть товар из заказа 1003"
"Каков статус моего возврата по заказу 1003?"
"Можно ли сделать обмен по заказу 1003?"
```

### 💬 General Conversation
```
"Привет!"
"Что ты умеешь?"
"Спасибо за помощь"
```

## Database Schema

The system uses PostgreSQL with the following main tables:

- **customers**: Customer information (501-505 in test data)
- **orders**: Order records with status tracking (1001-1005 in test data)
- **products**: Product catalog (Headphones, Charger, Shoes)
- **payments**: Payment status and failure tracking
- **returns**: Return requests and approvals
- **shipping_methods**: Available delivery options by region
- **shipment_events**: Tracking history for shipped orders

## Development Commands

```bash
just lint          # Run code linting
just embed          # Re-embed knowledge base
just seed-db        # Reset and populate database
just run-langgraph  # Start LangGraph Studio
just app           # Start Streamlit interface
```

## Workflow Testing in LangGraph Studio

1. **Input → Messages**: Click **+ Message**
2. **Role**: Keep as **Human**
3. **Content**: Enter your test query
4. **Submit**: Click Submit button

**⚠️ Important**: Don't use the "Next" field - it's for internal routing only.

## Possible Improvements

1. Add real-time streaming in Streamlit interface
2. Implement guardrail system for quality control and human escalation
3. Add more sophisticated slot filling with validation
4. Expand knowledge base with more detailed support documentation
5. Add user authentication and session management
6. Implement audit logging for support interactions

7. Add multi-language support for international customers

