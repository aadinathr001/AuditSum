import asyncio
from app.llm.mock import MockProvider

async def main():
    provider = MockProvider()
    result = await provider.complete(system="Summarize this.", user="Hello world. This is a test document.")
    print(result)

asyncio.run(main())