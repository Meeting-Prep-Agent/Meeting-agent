import os
import json
from typing import List, Dict, Any, Optional
from groq import AsyncGroq
from backend.config import settings
from backend.utils.logger import logger

class GroqService:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        if not self.api_key:
            logger.error("GROQ_API_KEY not found in settings")
            raise ValueError("GROQ_API_KEY is not set. Please configure GROQ_API_KEY in your environment.")
        self.client = AsyncGroq(api_key=self.api_key)
        
        # Primary model configurations
        self.models = {
            "FAST": "openai/gpt-oss-20b",
            "STRATEGIC": "openai/gpt-oss-120b"
        }

    async def _run_completion(self, messages: List[Dict[str, str]], model_key: str = "FAST", json_mode: bool = True):
        target_model = self.models.get(model_key, self.models["FAST"])

        try:
            response = await self.client.chat.completions.create(
                messages=messages,
                model=target_model,
                response_format={"type": "json_object"} if json_mode else None,
                temperature=0.1,
                timeout=10.0
            )
        except Exception as err:
            logger.error(f"Groq API call with model {target_model} failed: {err}")
            raise err

        content = response.choices[0].message.content
        if json_mode:
            try:
                return json.loads(content)
            except Exception as parse_err:
                logger.error(f"Failed to parse LLM JSON output: {content}")
                raise ValueError(f"LLM output was not valid JSON: {parse_err}")
        return content

    async def extract_meeting_data(self, transcript: str) -> Dict[str, Any]:
        """
        Performs REAL LLM extraction on raw meeting transcript.
        NO mock fallbacks. If Groq fails, exception is raised.
        """
        prompt = """
        You are an expert business intelligence analyst. Analyze the following raw meeting transcript.
        Return ONLY a JSON object with:
        - summary: A concise, accurate factual recap of the meeting (2-4 sentences).
        - sentiment_score: Float between -1.0 (negative) and 1.0 (positive).
        - key_topics: List of concise string topics discussed.
        - tone_analysis: Descriptive tone (e.g. "Collaborative", "Cautious & Detailed", "Focused").
        - commitments: List of objects with { "owner": "User"|"ContactName", "description": "...", "due_date": "ISO 8601 YYYY-MM-DD or null", "priority": "High"|"Medium"|"Low" }.
        - behavioral_signals: Object with { 
            "communication_style": "Analytical"|"Assertive"|"Amiable"|"Expressive",
            "decision_pattern": "Factual description of decision pattern",
            "hot_button_topics": ["topic1", ...],
            "preferred_communication": "Email"|"Call"|"In-person"
          }
        """
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Transcript:\n{transcript}"}
        ]

        logger.info(f"Executing real Groq LLM meeting data extraction...")
        result = await self._run_completion(messages, model_key="FAST", json_mode=True)
        return result

    async def generate_prep_brief(
        self, 
        contact_profile: Dict[str, Any], 
        open_commitments: List[Dict[str, Any]], 
        meeting_history: List[Dict[str, Any]], 
        context: str = ""
    ) -> Dict[str, Any]:
        """
        Synthesizes tactical preparation brief. NO mock fallbacks.
        """
        prompt = """
        You are a senior executive meeting strategist. Generate a high-leverage preparation brief.
        Return ONLY a JSON object with:
        - last_meeting_summary: A clear recap of past interactions.
        - recommended_strategy: A 2-3 sentence strategic recommendation grounded strictly in the provided data.
        - talking_points: List of tactical talking points (3-5 items).
        - red_flags: List of warning signals/risks (0-3 items).
        - success_factors: List of key success drivers (2-4 items).
        """
        data_packet = {
            "contact_profile": contact_profile,
            "open_commitments": open_commitments,
            "meeting_history": meeting_history,
            "meeting_context": context
        }
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Context Data:\n{json.dumps(data_packet)}"}
        ]

        logger.info(f"Executing real Groq LLM strategic brief synthesis...")
        result = await self._run_completion(messages, model_key="STRATEGIC", json_mode=True)
        return result
