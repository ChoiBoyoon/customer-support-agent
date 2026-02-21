# guardrail -> check if the topic is appropriate, and reject if necessary
import streamlit as st
from agents import Agent, Handoff, RunContextWrapper, input_guardrail, Runner, GuardrailFunctionOutput, handoff
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX #when agent has handoff, it is recommended to put this on the top of your agent instructions
from agents.extensions import handoff_filters
from models import UserAccountContext, InputGuardRailOutput, HandoffData
from my_agents.account_agent import account_agent
from my_agents.billing_agent import billing_agent
from my_agents.order_agent import order_agent
from my_agents.technical_agent import technical_agent

input_guardrail_agent = Agent(
    name="Input Guardrail Agent",
    instructions="""
        Ensure the user's request specifically pertains to User Account details, Billing inquiries, Order information, or Technical Support issues, and is not off-topic. 
        If the request is off-topic, return a reason for the tripwire. 
        You can make small conversation with the user, specially at the beginning of the conversation, but don't help with requests that are not related to User Account details, Billing inquiries, Order information, or Technical Support issues.
    """,
    output_type=InputGuardRailOutput,
)

@input_guardrail
async def off_topic_guardrail(wrapper: RunContextWrapper[UserAccountContext], agent: Agent[UserAccountContext], input):
    result = await Runner.run(input_guardrail_agent, input, context=wrapper.context,)
    return GuardrailFunctionOutput( #mandatory
        output_info=result.final_output, 
        tripwire_triggered=result.final_output.is_off_topic
    )

def dynamic_triage_agent_instructions(wrapper: RunContextWrapper[UserAccountContext], agent: Agent[UserAccountContext]):
    return f"""
    {RECOMMENDED_PROMPT_PREFIX}

    You are a customer support agent. You ONLY help customers with their questions about their User Account, Billing, Orders, or Technical Support.
    You call customers by their name.
    The customer's name is: {wrapper.context.name}.
    The customer's email is: {wrapper.context.email}.
    The customer's tier is: {wrapper.context.tier}.

    YOUR MAIN JOB: Classify the customer's issue and route them to the right specialist.

    ISSUE CLASSIFICATION GUIDE:
    🔨 TECHNICAL SUPPORT - Route here for:
    - Product not working, errors, bugs
    - App crashes, loading issues, performance problems
    - Feature questions, how-to help
    - Integration or setup problems
    - "The app won't load", "Getting error message", "How do I..."

    💰 BILLING SUPPORT - Route here for:
    - Payment issues, failed charges, refunds
    - Subscription questions, plan changes, cancellations
    - Invoice problems, billing disputes
    - Credit card updates, payment method changes
    - "I was charged twice", "Cancel my subscription", "Need a refund"

    📦 ORDER MANAGEMENT - Route here for;
    - Order status, shipping, delivery questions
    - Returns, exchanges, missing items
    - Tracking numbers, delivery problems
    - Product availability, reorders
    - "Where's my order?", "Want to return this", "Wrong item shipped"

    👤 ACCOUNT MANAGEMENT - Route here for:
    - Login problems, password resets, account access
    - Profile updates, email changes, account settings
    - Account security, two-factor authentication
    - Account deletion, data export requests
    - "Can't log in", "Forgot password", "Change my email"

    CLASSIFICATION PROCESS:
    1. Listen to the customer's issue
    2. Ask clarifying questions if the category isn't clear
    3. Classify into ONE of the four categories above
    4. Explain why you're routing them: "I'll connect you with our [category] specialist who can help with [specific issue]"
    5. Route to the appropriate specialist agent

    SPECIAL HANDLING:
    - Premium/Enterprise customers: Mention their priority status when routing
    - Multiple issues: Handle the most urgent first, note others for follow-up
    - Unclear issues: Ask 1-2 clarifying questions before routing
    """

def handle_handoff(wrapper: RunContextWrapper[UserAccountContext], input_data: HandoffData):
    with st.sidebar:
        st.write(f"""
            Handing off to {input_data.to_agent_name}
            Reason: {input_data.reason}
            Issue type: {input_data.issue_type}
            Description: {input_data.issue_description}
        """)

def make_handoff(agent):
    return handoff(
        agent=agent,
        on_handoff=handle_handoff, #handoff가 발생할 때 실행되는 함수
        input_type=HandoffData,
        input_filter=handoff_filters.remove_all_tools #handoff를 할 때 대화 history를 전부 넘기지 X. tools 사용 기록을 지운 뒤 보냄
    )

triage_agent = Agent(
    name="Triage Agent",
    instructions=dynamic_triage_agent_instructions, #string or function(callable)
    input_guardrails=[off_topic_guardrail],
    handoffs=[
            make_handoff(account_agent),
            make_handoff(billing_agent),
            make_handoff(order_agent),
            make_handoff(technical_agent),
        ]
    )