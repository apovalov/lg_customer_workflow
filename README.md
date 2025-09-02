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
- **👤 Customer Context**: Personalized experience with automatic customer identification
- **🛠️ Unified Tool Access**: React agent can access both database tools and knowledge base

## Architecture

The system uses a graph-based workflow with 4 main branches:

1. **RAG Agent** - Handles general policy questions using knowledge base
2. **React Tool Agent** - Uses comprehensive tools for customer queries (database + RAG + customer-specific)
3. **General Response** - Handles greetings and casual conversation
4. **Cannot Help** - Politely declines out-of-scope requests

### Customer Context Features

- **Automatic Customer Identification**: Default customer_id is injected into customer-specific tools
- **Personalized Queries**: Support for "my orders", "my payments" type questions
- **Multi-Customer Support**: Easy switching between customer contexts for testing


<img width="703" height="306" alt="Screenshot 2025-09-01 at 00 27 54" src="https://github.com/user-attachments/assets/69faa2aa-badd-43fb-a6ee-112866ab6e03" />

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

**Personal Queries (automatically use current customer context):**
```
"Какие у меня заказы?"
"В каком статусе мои заказы?"
"Какие у меня проблемы с оплатой?"
"Есть ли у меня возвраты?"
"Покажи мою историю заказов"
"Могу ли я вернуть свой заказ?"
```

**Combined Queries (RAG + Personal Data):**
```
"Что такое политика возвратов и могу ли я вернуть свой заказ?"
"Расскажи про варианты доставки и когда придет мой заказ?"
"Как повторить оплату и какие у меня проблемы с платежами?"
"Объясни процедуру возврата для моего заказа 1003"
```

**Order Tracking (specific order IDs):**
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

## Example Interactions

### Personal Query Example
**Query:** "Какие у меня заказы?"
**Response:** *Uses tool_get_my_orders automatically*
```
У вас есть один заказ:
- Номер заказа: 1001
- Статус: Отправлен
- Дата заказа: 30 июля 2025
- Сумма: 59.99 USD
- Номер отслеживания: TRK1001
- Перевозчик: UPS
- Ожидаемая дата доставки: 5 августа 2025
```

### Combined Query Example
**Query:** "Что такое политика возвратов и могу ли я вернуть свой заказ?"
**Response:** *Uses both retrieve_support_docs and customer tools*
```
Политика возвратов позволяет вернуть товар в течение 30 дней с момента доставки...

Для вашего заказа 1001:
- Заказ был доставлен более 30 дней назад
- Возврат возможен с дополнительными условиями
- Рекомендуем связаться с поддержкой для индивидуального решения
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

## Customer Context Configuration

The system uses a default customer_id for personalized queries. You can change the current customer by modifying the `DEFAULT_CUSTOMER_ID` in `agent_src/graph.py`:

```python
# Available test customers:
# 501 = Alice Johnson (New York, US) - has order 1001 (Shipped)
# 502 = Bob Smith (San Francisco, US) - has order 1002 (PendingPayment)
# 503 = Carlos Diaz (Madrid, ES) - has order 1003 (Delivered)
# 504 = Diana Lee (Toronto, CA) - has order 1004 (Shipped)
# 505 = Eva Nowak (Warsaw, PL) - has order 1005 (Canceled)
DEFAULT_CUSTOMER_ID = 501  # Change this to test different customers
```

## Development Commands

```bash
just lint          # Run code linting
just embed          # Re-embed knowledge base
just seed-db        # Reset and populate database
just run-langgraph  # Start LangGraph Studio
just app           # Start Streamlit interface
```

### Testing New Features

To test the new customer-context and RAG integration features:

```bash
# Test personal queries (automatically uses current customer)
uv run python -c "
from agent_src.graph import graph
from langchain_core.messages import HumanMessage
result = graph.invoke({'messages': [HumanMessage(content='Какие у меня заказы?')]})
print(result['messages'][-1].content)
"

# Test combined RAG + personal data
uv run python -c "
from agent_src.graph import graph
from langchain_core.messages import HumanMessage
result = graph.invoke({'messages': [HumanMessage(content='Что такое политика возвратов и есть ли у меня возвраты?')]})
print(result['messages'][-1].content)
"
```

## Workflow Testing in LangGraph Studio

1. **Input → Messages**: Click **+ Message**
2. **Role**: Keep as **Human**
3. **Content**: Enter your test query
4. **Submit**: Click Submit button

## Recent Improvements (Completed)

✅ **Enhanced React Tool Agent**: Now has access to both database tools and RAG knowledge base
✅ **Customer Context Injection**: Automatic customer_id injection for personalized queries
✅ **New Customer-Specific Tools**:
  - `tool_get_my_orders` - Get all orders for current customer
  - `tool_get_my_order_status` - Get specific order status for current customer
  - `tool_get_my_payments` - Get payment history for current customer
  - `tool_get_my_returns` - Get return requests for current customer
✅ **Unified Tool Access**: Single agent can handle both specific data queries and general policy questions
✅ **Improved Prompts**: Updated to reflect new capabilities and tool selection strategies

## Possible Future Improvements

1. Add real-time streaming in Streamlit interface
2. Implement user authentication and session management for dynamic customer_id assignment
3. Add more sophisticated slot filling with validation
4. Expand knowledge base with more detailed support documentation
5. Implement guardrail system for quality control and human escalation
6. Implement audit logging for support interactions
7. Add multi-language support for international customers
8. Add conversation memory to maintain context across multiple interactions




