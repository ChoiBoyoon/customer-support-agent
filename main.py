import dotenv
dotenv.load_dotenv()

from openai import OpenAI
import asyncio
import streamlit as st
from agents import Agent, Runner, SQLiteSession, InputGuardrailTripwireTriggered
from models import UserAccountContext
from my_agents.triage_agent import triage_agent


st.set_page_config(
    page_title="Customer Support Agent",
    layout="wide" #reduce the whitespace
)

client = OpenAI()

user_account_ctx = UserAccountContext( # in real-world situation, you need to preload this info from your db
    customer_id=1,
    name="boyoon",
    tier="basic"
)

if "session" not in st.session_state: #딱 한 번만 실행됨!
    st.session_state["session"] = SQLiteSession(
        "chat-history", 
        "chat-gpt-clone-memory.db",
    )
session = st.session_state["session"]

if "agent" not in st.session_state:
    st.session_state["agent"]=triage_agent

async def paint_history():
    messages = await session.get_items()
    for message in messages:
        if "role" in message:
            with st.chat_message(message["role"]):
                if message["role"]=="user":
                    st.write(message["content"])
                else:
                    if message["type"]=="message":
                        st.write(message["content"][0]["text"])

asyncio.run(paint_history())

async def run_agent(message):
    with st.chat_message("ai"):
        text_placeholder=st.empty()
        response=""

        st.session_state["text_placeholder"]=text_placeholder

        try:
            stream = Runner.run_streamed(
                st.session_state["agent"],
                message,
                session=session,
                context=user_account_ctx #function tools get this cxt, not llm nodel
            )

            async for event in stream.stream_events():
                if event.type=="raw_response_event":

                    if event.data.type=="response.output_text.delta":
                        response+=event.data.delta
                        text_placeholder.write(response)
                elif event.type=="agent_updated_stream_event":
                    if st.session_state["agent"].name != event.new_agent.name:
                        st.write(f"🤖 Transfered from {st.session_state["agent"].name} to {event.new_agent.name}")
                        st.session_state["agent"]=event.new_agent

                        text_placeholder=st.empty()
                        response=""

        except InputGuardrailTripwireTriggered:
            st.write("I can't help you with that.")


message = st.chat_input("Write a message to your assistant.")

if message:
    if "text_placeholder" in st.session_state:
        st.session_state["text_placeholder"].empty()
    
    if message:
        with st.chat_message("human"):
            st.write(message)
        asyncio.run(run_agent(message))

with st.sidebar:
    reset = st.button("Reset memory")
    if reset:
        asyncio.run(session.clear_session())
    st.write(asyncio.run(session.get_items()))