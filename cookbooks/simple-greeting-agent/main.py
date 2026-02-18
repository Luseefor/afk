from afk.agents import Agent
from afk.core import Runner

agent = Agent(
    name="ticket-classifier",
    model="ollama_chat/gpt-oss:20b",
    instructions="""
    Read the support ticket and classify it as exactly one of:
    billing, technical, account, or other.
    Output only the category name.
    """,
)

runner = Runner()
result = runner.run_sync(agent, user_message="I can't log into my account")
print(result.final_text)  # "account"
