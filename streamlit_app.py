import requests
import streamlit as st

# FastAPI server configuration
API_BASE_URL = "http://localhost:8000"

st.set_page_config(page_title="Customer Support AI Assistant", page_icon="🛍️", layout="wide")

st.title("🛍️ Customer Support AI Assistant")
st.markdown("Задайте вопрос о заказе, доставке, платежах или возврате - я помогу найти ответ!")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Чем могу помочь?"):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                message_history = [
                    msg["content"]
                    for msg in st.session_state.messages
                    if msg["role"] == "user"
                ]

                # Make API call to FastAPI server
                payload = {
                    "messages": message_history,
                    "thread_id": "streamlit_session",
                }

                response = requests.post(
                    f"{API_BASE_URL}/chat", json=payload, timeout=30
                )

                if response.status_code == 200:
                    result = response.json()
                    ai_response = result.get("response", "No response received")
                else:
                    ai_response = f"API Error: {response.status_code} - {response.text}"

                st.markdown(ai_response)

                # Add assistant response to chat history
                st.session_state.messages.append(
                    {"role": "assistant", "content": ai_response}
                )

            except requests.exceptions.ConnectionError:
                error_msg = "❌ Could not connect to API server. Make sure it's running with: `just api`"
                st.error(error_msg)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_msg}
                )
            except requests.exceptions.Timeout:
                error_msg = "⏱️ Request timed out. Please try again."
                st.error(error_msg)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_msg}
                )
            except Exception as e:
                error_msg = f"Sorry, I encountered an error: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_msg}
                )

# Sidebar with information
with st.sidebar:
    st.header("О системе")
    st.write("Этот ИИ-ассистент специализируется на поддержке клиентов и может:")
    st.write("• Отследить статус заказа")
    st.write("• Рассчитать варианты доставки")
    st.write("• Помочь с проблемами платежей")
    st.write("• Оформить возврат товара")
    st.write("• Ответить на общие вопросы")

    # API Status check
    st.header("API Status")
    try:
        health_response = requests.get(f"{API_BASE_URL}/", timeout=5)
        if health_response.status_code == 200:
            st.success("✅ API Server Online")
        else:
            st.error("❌ API Server Error")
    except Exception:
        st.error("❌ API Server Offline")
        st.info("Start with: `just api`")

    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()
