from typing import List

from fastapi import FastAPI
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from agent_src.graph import graph

app = FastAPI(title="Customer Support AI Assistant API", version="1.0.0")


class ChatRequest(BaseModel):
    messages: List[str]
    thread_id: str = "default"


@app.get("/")
async def root():
    return {"message": "Customer Support AI Assistant API", "status": "running", "docs": "/docs"}


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Process chat messages through the LangGraph
    """
    try:
        print(f"Received request: {request.messages}")
        human_messages = [HumanMessage(content=msg) for msg in request.messages]

        initial_state = {
            "messages": human_messages,
            "route": "",
            "intent": "",
            "missing_params": [],
            "present_params": {},
            "guardrail_decision": ""
        }

        print(f"Initial state: {initial_state}")
        result = graph.invoke(initial_state)
        print(f"Graph result: {result}")

        if result.get("messages") and len(result["messages"]) > 0:
            response_content = result["messages"][-1].content
            print(f"Response content: {response_content}")
            return {
                "response": response_content,
                "thread_id": request.thread_id,
            }
        else:
            print("No messages in result")
            return {"response": "No response generated", "thread_id": request.thread_id}

    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": f"Error processing request: {str(e)}"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
