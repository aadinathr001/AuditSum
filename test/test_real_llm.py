import asyncio

from dotenv import load_dotenv
load_dotenv()
from app.llm.openai_compat import make_groq_provider

async def main():
    provider = make_groq_provider()
    result = await provider.complete(
        system="You are a helpful assistant. Respond in one short sentence.",
        user="What is the capital of France?",
    )
    print(result)

asyncio.run(main())