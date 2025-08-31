from typing import Literal
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, ValidationError, field_validator

from agent_src.prompts import (
    UNIFIED_INTENT_CLASSIFIER_PROMPT,
    REACT_TOOL_AGENT_PROMPT,
    RAG_AGENT_PROMPT,
    GENERAL_RESPONSE_PROMPT
)
from agent_src.tools import (
    retrieve_support_docs,
    # Database tools
    tool_track_order_basic,
    tool_track_by_tracking_no,
    tool_track_latest_status,
    tool_delivery_options_by_region,
    tool_cheapest_delivery,
    tool_estimate_delivery_cost,
    tool_last_payment_status,
    tool_can_retry_payment,
    tool_payment_retry_steps,
    tool_last_return_status,
    tool_return_eligibility,
    tool_request_return_label,
)
from config import settings

# --- LLM Setup ---
llm = ChatOpenAI(
    model=settings.model_name,
    temperature=settings.temperature,
    api_key=settings.openai_api_key,
)

# Tool definitions
database_tools = [
    tool_track_order_basic,
    tool_track_by_tracking_no,
    tool_track_latest_status,
    tool_delivery_options_by_region,
    tool_cheapest_delivery,
    tool_estimate_delivery_cost,
    tool_last_payment_status,
    tool_can_retry_payment,
    tool_payment_retry_steps,
    tool_last_return_status,
    tool_return_eligibility,
    tool_request_return_label,
]

rag_tools = [retrieve_support_docs]
all_tools = database_tools + rag_tools


# --- State Definition ---
class SupportState(MessagesState):
    """State for customer support workflow - contains messages only"""
    pass

# Global variable to store routing decision (temporary solution)
_routing_decision = "general"


# --- Helper Functions ---
def get_last_human_message(state: SupportState) -> str:
    """Extract the last human message content from state, handling both string and list formats"""
    for i, msg in enumerate(reversed(state["messages"])):
        msg_type = getattr(msg, 'type', 'unknown')
        msg_class = msg.__class__.__name__

        # Try different ways to identify human messages
        if (hasattr(msg, 'type') and msg.type == 'human') or msg_class == 'HumanMessage':
            content = msg.content
            if isinstance(content, list):
                result = " ".join(str(item) for item in content if isinstance(item, str))
            else:
                result = str(content)
            return result
    return ""


# --- Intent Classification ---
class IntentClassification(BaseModel):
    next: Literal["rag", "tools", "general", "cannot_help"]

    @field_validator("next")
    @classmethod
    def validate_next(cls, v):
        v = v.strip().lower()
        if v not in ("rag", "tools", "general", "cannot_help"):
            raise ValueError("Must be 'rag', 'tools', 'general', or 'cannot_help'")
        return v


def unified_intent_classifier(state: SupportState) -> dict:
    """Single-step classification replacing the 3-node cascade"""
    global _routing_decision

    # Check if messages exist
    if not state["messages"]:
        _routing_decision = "general"
        return {}

    # Get the last human message
    user_msg = get_last_human_message(state)
    if not user_msg:
        _routing_decision = "general"
        return {}

    prompt = ChatPromptTemplate.from_messages([
        ("system", UNIFIED_INTENT_CLASSIFIER_PROMPT),
        ("user", "{question}"),
    ])
    llm_input = prompt.format_messages(question=user_msg)
    response = llm.invoke(llm_input)
    answer = response.content.strip().lower()

    try:
        parsed = IntentClassification(next=answer)
        _routing_decision = parsed.next
        return {}
    except ValidationError as e:
        # Default to general for invalid responses
        _routing_decision = "general"
        return {}


def rag_agent(state: SupportState):
    """Deterministic knowledge base retrieval - no tools, direct search"""
    user_msg = get_last_human_message(state)
    if not user_msg:
        return {"messages": [AIMessage(content="Не могу обработать запрос без сообщения.")]}

    try:
        # Direct knowledge base search (deterministic)
        from clients.vector_db import vector_db_client
        from config import settings

        retrieved_docs = vector_db_client.similarity_search(user_msg, k=settings.top_k)

        # Build context from retrieved chunks
        context = "\n".join([doc.page_content for doc in retrieved_docs])

        # Generate response with context
        prompt = ChatPromptTemplate.from_messages([
            ("system", RAG_AGENT_PROMPT),
            ("user", "Context:\n{context}\n\nUser question: {question}")
        ])

        llm_input = prompt.format_messages(context=context, question=user_msg)
        response = llm.invoke(llm_input)

        return {"messages": [response]}

    except Exception as e:
        return {"messages": [AIMessage(content="Извините, не могу получить информацию из базы знаний. Попробуйте переформулировать вопрос.")]}


def react_tool_agent(state: SupportState):
    """Intelligent database tool usage with self-managed parameter extraction"""
    # Check if we just came back from tools (last message has tool results)
    if (state["messages"] and
        hasattr(state["messages"][-1], '__class__') and
        state["messages"][-1].__class__.__name__ == 'ToolMessage'):
        # We have tool results, let LLM format a nice response
        response = llm.invoke(state["messages"])
        return {"messages": [response]}
    else:
        # First time here, bind all database tools and let React agent decide
        tool_llm = llm.bind_tools(database_tools)

        # Add system message for React agent behavior
        system_message = SystemMessage(content=REACT_TOOL_AGENT_PROMPT)
        messages_with_system = [system_message] + state["messages"]

        response = tool_llm.invoke(messages_with_system)
        return {"messages": [response]}


def general_response(state: SupportState):
    """Handle casual conversation and capability questions"""
    if not state["messages"]:
        return {"messages": [AIMessage(content="Привет! Чем могу помочь?")]}

    # Get the last human message
    user_msg_raw = get_last_human_message(state)
    if not user_msg_raw:
        return {"messages": [AIMessage(content="Привет! Чем могу помочь?")]}

    user_msg = user_msg_raw.lower()

    # Detect specific types of general requests
    if any(word in user_msg for word in ["привет", "здравствуй", "добрый", "hello", "hi"]):
        response = "Привет! Я ассистент поддержки клиентов. Могу помочь с заказами, доставкой, платежами и возвратами. Что вас интересует?"
    elif any(word in user_msg for word in ["что можешь", "что умеешь", "возможности", "помощь", "help"]):
        response = "Я помогаю с:\n• Отслеживанием заказов\n• Вариантами доставки\n• Вопросами по оплате\n• Возвратами товаров\n• Общими вопросами поддержки\n\nО чем хотите узнать?"
    elif any(word in user_msg for word in ["спасибо", "благодарю", "thanks"]):
        response = "Пожалуйста! Если возникнут еще вопросы - обращайтесь."
    elif any(word in user_msg for word in ["интересного", "interesting", "расскажешь", "tell me"]):
        response = "Могу рассказать о наших сервисах поддержки клиентов! Мы помогаем отслеживать заказы, выбирать варианты доставки, решать вопросы с оплатой и оформлять возвраты. Есть конкретные вопросы?"
    else:
        # Fallback to LLM for other general queries
        prompt = ChatPromptTemplate.from_messages([
            ("system", GENERAL_RESPONSE_PROMPT),
            ("user", "{message}")
        ])
        # Use the same user message we found earlier (without .lower())
        original_msg = user_msg_raw
        llm_input = prompt.format_messages(message=original_msg)
        response = llm.invoke(llm_input).content

    return {"messages": [AIMessage(content=response)]}


def cannot_help(state: SupportState):
    """Polite refusal with capability explanation"""

    # Static response explaining system limitations
    response_content = "Извините, я могу помочь только с вопросами поддержки клиентов: отслеживание заказов, варианты доставки, вопросы по оплате, возвраты и общие вопросы о сервисе. Есть ли что-то из этого, с чем я могу помочь?"

    return {"messages": [AIMessage(content=response_content)]}


# --- Conditional Logic Functions ---
def routing_condition(state: SupportState):
    """Route based on classification decision"""
    global _routing_decision
    return _routing_decision

def tools_or_end_condition(state: SupportState):
    """Check if we need tools or should end"""
    last_message = state["messages"][-1] if state["messages"] else None

    # If last message has tool calls, go to tools
    if last_message and hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    else:
        return END


# --- Build the graph ---
graph_builder = StateGraph(SupportState)

# Add the 4 core nodes
graph_builder.add_node("unified_intent_classifier", unified_intent_classifier)
graph_builder.add_node("rag_agent", rag_agent)
graph_builder.add_node("react_tool_agent", react_tool_agent)
graph_builder.add_node("general_response", general_response)
graph_builder.add_node("cannot_help", cannot_help)

# Add tool execution node
graph_builder.add_node("tools", ToolNode(all_tools))

# Add edges
graph_builder.add_edge(START, "unified_intent_classifier")

# Single 4-way routing from classifier
graph_builder.add_conditional_edges(
    "unified_intent_classifier",
    routing_condition,
    {
        "rag": "rag_agent",
        "tools": "react_tool_agent",
        "general": "general_response",
        "cannot_help": "cannot_help"
    },
)

# RAG agent goes directly to end (no tools needed)
graph_builder.add_edge("rag_agent", END)

# React tool agent can use database tools
graph_builder.add_conditional_edges(
    "react_tool_agent",
    tools_or_end_condition,
    {"tools": "tools", END: END}
)

# Simple nodes go directly to end
graph_builder.add_edge("general_response", END)
graph_builder.add_edge("cannot_help", END)

# After tools execution, always return to React agent
graph_builder.add_edge("tools", "react_tool_agent")

# Compile the graph - LangGraph Studio provides its own checkpointer automatically
graph = graph_builder.compile()