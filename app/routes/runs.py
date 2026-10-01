import os
from dotenv import load_dotenv
load_dotenv()
import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db import get_session
from app.security.auth import get_current_user
from app.models import Document, DocumentContent, Run, RunStep, Citation
from app.audit.service import append_event
from app.llm.openai_compat import make_groq_provider
from app.pipeline.citations import verify_quote
from app.pipeline.prompts import SUMMARIZE_SYSTEM_PROMPT
from app.pipeline.tokens import choose_strategy
from app.pipeline.summarize import run_map_reduce
from app.pipeline.run_service import execute_run
from app.rate_limit import limiter
from fastapi import Request
from app.rate_limit import limiter, RUN_RATE_LIMIT

router = APIRouter(prefix="/documents", tags=["runs"])

@router.post("/{document_id}/runs")
@limiter.limit(RUN_RATE_LIMIT)
async def create_run(
    request: Request,
    document_id: int,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.owner_id != current_user["id"] and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not your document")

    if document.status == "denied":
        raise HTTPException(status_code=400, detail="Cannot summarize a denied document")

    run = await execute_run(session, document=document, actor_id=current_user["id"], actor_role=current_user["role"])

    return {
        "run_id": run.id, "status": run.status, "strategy": run.strategy,
        "result": run.parsed_result,
        "citation_verification_rate": f"{run.verified_count}/{run.total_count}",
    }

@router.get("/{document_id}/runs/{run_id}")
def get_run(
    document_id: int,
    run_id: int,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    run = session.get(Run, run_id)

    if run is None or run.document_id != document_id:
        raise HTTPException(
            status_code=404,
            detail="Run not found",
        )

    if (
        run.requested_by != current_user["id"]
        and current_user["role"] not in ("admin", "auditor")
    ):
        raise HTTPException(
            status_code=403,
            detail="Not your run",
        )

    steps = session.scalars(
        select(RunStep).where(
            RunStep.run_id == run_id
        )
    ).all()

    return {
        "run_id": run.id,
        "status": run.status,
        "provider": run.provider,
        "model": run.model,
        "strategy": run.strategy,
        "result": run.result_json,
        "total_prompt_tokens": run.total_prompt_tokens,
        "total_completion_tokens": run.total_completion_tokens,
        "steps": [
            {
                "step_index": s.step_index,
                "kind": s.kind,
                "output_text": s.output_text,
            }
            for s in steps
        ],
    }