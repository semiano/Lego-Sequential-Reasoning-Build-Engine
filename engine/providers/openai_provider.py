from __future__ import annotations

import json
from pathlib import Path
import asyncio
import random
import uuid
import os
import re
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

import httpx
from jsonschema import ValidationError, validate

from engine.providers.base import LLMProvider


class OpenAIProvider(LLMProvider):
    _semaphore: asyncio.Semaphore | None = None

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        temperature: float = 0.3,
        max_tokens: int = 1200,
        trace_dir: Path | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.trace_dir = trace_dir
        if self.trace_dir is not None:
            self.trace_dir.mkdir(parents=True, exist_ok=True)
        if OpenAIProvider._semaphore is None:
            limit = int(os.getenv("LLM_CONCURRENCY", "2"))
            OpenAIProvider._semaphore = asyncio.Semaphore(max(1, limit))

    @staticmethod
    def _parse_retry_after(header_value: str | None) -> float | None:
        if not header_value:
            return None
        value = header_value.strip()
        if value.isdigit():
            return float(value)
        try:
            retry_at = parsedate_to_datetime(value)
            now = datetime.now(timezone.utc)
            return max(0.0, (retry_at - now).total_seconds())
        except Exception:
            return None

    @staticmethod
    def _sanitize_schema(schema: dict) -> dict:
        def _clean(value):
            if isinstance(value, dict):
                cleaned = {}
                for key, inner in value.items():
                    if key == "$schema":
                        continue
                    cleaned[key] = _clean(inner)

                if cleaned.get("type") == "object" and isinstance(cleaned.get("properties"), dict):
                    property_keys = list(cleaned["properties"].keys())
                    existing_required = cleaned.get("required")
                    if isinstance(existing_required, list):
                        required_set = list(dict.fromkeys([*existing_required, *property_keys]))
                    else:
                        required_set = property_keys
                    cleaned["required"] = required_set

                return cleaned
            if isinstance(value, list):
                return [_clean(item) for item in value]
            return value

        return _clean(schema)

    @staticmethod
    def _normalize_schema_name(raw_name: str) -> str:
        name = re.sub(r"[^A-Za-z0-9_-]", "_", raw_name).strip("_")
        if not name:
            name = "structured_output"
        return name[:64]

    async def _call_responses(self, system_prompt: str, user_prompt: str, schema: dict) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        sanitized_schema = self._sanitize_schema(schema)
        schema_name = self._normalize_schema_name(str(sanitized_schema.get("title") or "structured_output"))
        base_payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_output_tokens": self.max_tokens,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
            ],
        }
        payload = {
            **base_payload,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": sanitized_schema,
                    "strict": True,
                }
            },
        }

        max_retries = 4
        base_delay = 1.5
        semaphore = OpenAIProvider._semaphore or asyncio.Semaphore(2)
        async with semaphore:
            async with httpx.AsyncClient(timeout=90) as client:
                last_client_error = ""
                for attempt in range(max_retries + 1):
                    response = await client.post(f"{self.base_url}/responses", headers=headers, json=payload)
                    if response.status_code < 400:
                        return response.json()

                    response_body = response.text
                    retryable = response.status_code in {408, 409, 425, 429, 500, 502, 503, 504}
                    if not retryable:
                        if response.status_code == 400:
                            last_client_error = response_body
                            break
                        response.raise_for_status()

                    if attempt >= max_retries:
                        response.raise_for_status()

                    retry_after_seconds = self._parse_retry_after(response.headers.get("Retry-After"))
                    if retry_after_seconds is not None:
                        delay = retry_after_seconds
                    else:
                        delay = base_delay * (2**attempt) + random.uniform(0.0, 0.8)
                    await asyncio.sleep(delay)

                if last_client_error:
                    raise ValueError(f"OpenAI responses 400 with strict schema payload: {last_client_error}")

        raise RuntimeError("OpenAI request failed after retries")

    @staticmethod
    def _extract_text(payload: dict) -> str:
        output = payload.get("output", [])
        for item in output:
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    return content["text"]
        if payload.get("output_text"):
            return payload["output_text"]
        raise ValueError("No text output from model")

    def _write_trace(self, response_payload: dict, content_text: str) -> None:
        if self.trace_dir is None:
            return
        trace_path = self.trace_dir / f"llm_raw_{uuid.uuid4().hex}.json"
        trace_path.write_text(
            json.dumps({"response": response_payload, "content_text": content_text}, indent=2),
            encoding="utf-8",
        )

    async def generate_json(self, system_prompt: str, user_prompt: str, schema: dict) -> dict:
        repair_prompt = user_prompt
        last_error = ""
        for attempt in range(3):
            print("\n=== LLM REQUEST BEGIN ===", flush=True)
            print(f"model={self.model} attempt={attempt + 1}", flush=True)
            print("--- system_prompt ---", flush=True)
            print(system_prompt, flush=True)
            print("--- user_prompt ---", flush=True)
            print(repair_prompt, flush=True)
            print("=== LLM REQUEST END ===\n", flush=True)

            response_payload = await self._call_responses(system_prompt=system_prompt, user_prompt=repair_prompt, schema=schema)
            content_text = self._extract_text(response_payload)
            self._write_trace(response_payload, content_text)

            print("\n=== LLM RESPONSE BEGIN ===", flush=True)
            print(content_text, flush=True)
            print("=== LLM RESPONSE END ===\n", flush=True)

            try:
                parsed = json.loads(content_text)
                validate(parsed, schema)
                return parsed
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = str(exc)
                print(f"LLM validation error: {last_error}", flush=True)
                if attempt >= 2:
                    break
                repair_prompt = (
                    f"{user_prompt}\n\n"
                    "Your previous response was invalid JSON or schema-invalid. "
                    f"Error: {last_error}\n"
                    "Return ONLY valid JSON matching the required schema."
                )

        raise ValueError(f"Model response validation failed after retries: {last_error}")
