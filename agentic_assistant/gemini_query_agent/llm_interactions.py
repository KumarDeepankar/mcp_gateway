# agentic_assistant/gemini_query_agent/llm_interactions.py
import asyncio
import json
from typing import List, Dict, Any
import google.generativeai as genai
from langchain_core.runnables import RunnableConfig

from settings import gemini_model
from .utils import create_fallback_response
from .llm_models import UnifiedPlannerDecisionOutput


def _extract_system_instruction(messages: List[Dict[str, str]]) -> str:
    """Extract and combine all system messages."""
    system_messages = [msg["content"] for msg in messages if msg["role"] == "system"]
    return "\n\n".join(system_messages)


def _convert_to_gemini_messages(messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Convert conversation messages to Gemini format."""
    gemini_messages = []
    for msg in messages:
        if msg["role"] == "user":
            gemini_messages.append({'role': 'user', 'parts': [{'text': msg["content"]}]})
        elif msg["role"] == "assistant":
            gemini_messages.append({'role': 'model', 'parts': [{'text': msg["content"]}]})
    return gemini_messages


def _clean_json_response(response_text: str) -> str:
    """Clean JSON response from markdown formatting."""
    response_text = response_text.strip()
    if response_text.startswith("```json"):
        response_text = response_text[7:].strip()
    if response_text.endswith("```"):
        response_text = response_text[:-3].strip()
    return response_text


async def call_llm_with_structured_output(
        messages: List[Dict[str, str]],
        output_model: type,
        config: RunnableConfig,
        max_retries: int = 1
) -> Any:
    """Call LLM with structured output."""
    if not gemini_model:
        return create_fallback_response(output_model, messages, "Gemini model unavailable.")

    system_instruction = _extract_system_instruction(messages)
    gemini_messages = _convert_to_gemini_messages(messages)

    if not gemini_messages:
        return create_fallback_response(output_model, messages, "No conversation messages.")

    temperature = 0.2 if output_model == UnifiedPlannerDecisionOutput else 0.3
    generation_config = genai.types.GenerationConfig(
        temperature=temperature,
        response_mime_type="application/json"
    )

    for attempt in range(max_retries + 1):
        try:
            # Try native system instruction first, fallback to prepending
            try:
                response = await gemini_model.generate_content_async(
                    gemini_messages,
                    generation_config=generation_config,
                    system_instruction=system_instruction
                )
            except:
                if system_instruction and gemini_messages[0]['role'] == 'user':
                    original = gemini_messages[0]['parts'][0]['text']
                    gemini_messages[0]['parts'][0]['text'] = f"{system_instruction}\n\n{original}"

                response = await gemini_model.generate_content_async(
                    gemini_messages,
                    generation_config=generation_config
                )

            response_text = _clean_json_response(response.text)
            json_data = json.loads(response_text)
            return output_model(**json_data)

        except Exception as e:
            if attempt == max_retries:
                return create_fallback_response(output_model, messages, f"Error: {type(e).__name__}")
            await asyncio.sleep(0.5 * (attempt + 1))