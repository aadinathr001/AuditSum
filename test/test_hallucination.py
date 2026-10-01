import asyncio
import json
from unittest import result
from app.db import engine
from sqlalchemy.orm import Session

from app.models import DocumentContent, Citation
from app.llm.mock import MockProvider
from app.pipeline.citations import verify_quote

async def main():
    with Session(engine) as session:
        content = session.get(DocumentContent, 1)  # change to a real document_id you have

        provider = MockProvider(hallucinate=True)
        # result = await provider.complete(system="Summarize.", user=content.text)
        # parsed = json.loads(result.text)

        result = await provider.complete(system="Summarize.", user=content.text)

        print("RAW RESPONSE:")
        print(result.text)

        parsed = json.loads(result.text)

        for kp in parsed["key_points"]:
            verified, start, end = verify_quote(content.text, kp["quote"])
            print(f"quote={kp['quote']!r} verified={verified}")

asyncio.run(main())