import asyncio
from afk.agents import Agent
from afk.core import Runner

agent = Agent(name="tutor", model="ollama_chat/gpt-oss:20b", instructions="You are a Python tutor.")

async def main():
    runner = Runner()
    thread = "session-42"

    r1 = await runner.run(agent, user_message="What are generators?", thread_id=thread)
    print(r1.final_text)

    # Turn 2 — the agent remembers Turn 1
    r2 = await runner.run(agent, user_message="Show me an example", thread_id=thread)
    print(r2.final_text)

asyncio.run(main())