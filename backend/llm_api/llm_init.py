import os
import httpx
from dataclasses import dataclass, field
from typing import Any, Optional, Type
from langchain_core.messages import BaseMessage


@dataclass
class LLMConfig:
    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    max_tokens: int = 4096
    provider: str = "openai"
    host_provider: str = "openai"


class LLMService:
    def __init__(self, config: LLMConfig, logger=None):
        self.config = config
        self.logger = logger
        self._llm = self._build_llm()

    def _build_llm(self):
        cfg = self.config
        # Corporate SSL inspection breaks certificate verification — disable verify for dev
        _http_client = httpx.Client(verify=False)
        _async_http_client = httpx.AsyncClient(verify=False)
        if cfg.host_provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=cfg.model,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                api_key=os.environ["ANTHROPIC_API_KEY"],
            )
        elif cfg.host_provider == "azure":
            from langchain_openai import AzureChatOpenAI
            return AzureChatOpenAI(
                azure_deployment=cfg.model,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                api_key=os.environ["AZURE_OPENAI_API_KEY"],
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
                http_client=_http_client,
                http_async_client=_async_http_client,
            )
        else:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=cfg.model,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                http_client=_http_client,
                http_async_client=_async_http_client,
            )

    def invoke_text(self, messages: list[BaseMessage], audit_ctx: dict = {}) -> str:
        response = self._llm.invoke(messages)
        return response.content

    def invoke_structured(self, messages: list[BaseMessage], output_schema: Type) -> Any:
        structured_llm = self._llm.with_structured_output(output_schema)
        return structured_llm.invoke(messages)
