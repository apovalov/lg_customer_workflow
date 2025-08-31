embed:
    python -m scripts.chunk_and_embed_to_chroma



lint:
    uv run ruff check --fix

run-langgraph:
    uv run langgraph dev

api:
    uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

seed-db:
    uv run python -m scripts.seed_postgres_cs

app:
    #!/bin/bash
    echo "🧠 Starting LangGraph dev server..."
    # uv run langgraph dev &
    # LANGGRAPH_PID=$!
    echo "🚀 Starting FastAPI server..."
    uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
    API_PID=$!
    echo "📊 Services started - LangGraph (PID: $LANGGRAPH_PID), FastAPI (PID: $API_PID)"
    echo "⏳ Waiting for servers to start..."
    sleep 5
    echo "🎨 Starting Streamlit app..."
    uv run streamlit run streamlit_app.py
