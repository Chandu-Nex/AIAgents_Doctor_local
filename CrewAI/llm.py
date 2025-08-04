import requests
from langchain_core.language_models.llms import BaseLLM
from langchain_core.outputs import LLMResult
from typing import List, Any, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

class MedGemmaLLM(BaseLLM):
    def _generate(self, prompts: List[str], stop: Optional[List[str]] = None) -> LLMResult:
        prompt = prompts[0]  # Only handling single prompt at a time for simplicity
        url = "http://10.0.2.32:9001/v1/chat/completions"
        payload = {
            "model": "medgemma-4b-it",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": -1,
            "stream": False
        }
        headers = {"Content-Type": "application/json"}
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            result_text = data["choices"][0]["message"]["content"]
        except Exception as e:
            result_text = f"[MedGemma API Error]: {str(e)}"
        return LLMResult(generations=[[{"text": result_text}]])

    async def _agenerate(self, prompts: List[str], stop: Optional[List[str]] = None) -> LLMResult:
        with ThreadPoolExecutor() as executor:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(executor, lambda: self._generate(prompts, stop))

    @property
    def _llm_type(self) -> str:
        return "custom-medgemma"