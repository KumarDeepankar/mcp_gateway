# himan_ai/agentic_assistant/gemini_query_agent/eval_interactions.py
import time
import uuid
import aiohttp
import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from settings import EVAL_SERVICE_URL

# Re-defining models from eval_service to avoid direct dependency
class ComprehensiveEvaluationPayload(BaseModel):
    question: str
    agent_answer: str
    past_steps: List[Dict[str, Any]]
    turn_sources: List[Dict[str, Any]]
    ground_truth: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

async def log_comprehensive_evaluation(
    http_session: aiohttp.ClientSession,
    question: str,
    final_answer: str,
    past_steps: List[Dict[str, Any]],
    turn_sources: List[Dict[str, Any]],
    ground_truth: Optional[str] = None,
):
    """
    Logs a comprehensive set of metrics for a single turn to the evaluation service.
    """
    if not EVAL_SERVICE_URL:
        print("EVAL_SERVICE_URL not set. Skipping evaluation logging.")
        return

    eval_payload = ComprehensiveEvaluationPayload(
        question=question,
        agent_answer=final_answer,
        past_steps=past_steps,
        turn_sources=turn_sources,
        ground_truth=ground_truth
    )

    eval_endpoint = f"{EVAL_SERVICE_URL}/agent/evaluate_comprehensive"
    try:
        payload_json = eval_payload.model_dump(mode='json')
        async with http_session.post(eval_endpoint, json=payload_json) as response:
            if response.status == 200:
                print(f"Successfully logged comprehensive evaluation for question.")
            else:
                response_text = await response.text()
                print(f"Error logging comprehensive evaluation: {response.status} - {response_text}")
    except Exception as e:
        print(f"Exception while calling comprehensive evaluation service: {e}")