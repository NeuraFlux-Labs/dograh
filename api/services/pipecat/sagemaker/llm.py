#
# Copyright (c) 2024-2025, SalesPyper
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import json
from typing import AsyncGenerator, List, Optional

from loguru import logger

from pipecat.frames.frames import (
    Frame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    TextFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.services.llm_service import LLMService

try:
    import aioboto3
except ModuleNotFoundError as e:
    logger.error(f"Exception: {e}")
    logger.error(
        "In order to use SageMaker services, you need to `pip install aioboto3`."
    )
    raise Exception(f"Missing module: {e}")


class SageMakerLLMService(LLMService):
    def __init__(
        self,
        *,
        endpoint_name: str,
        region_name: str = "us-east-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        model_kwargs: Optional[dict] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self._endpoint_name = endpoint_name
        self._region_name = region_name
        self._model_kwargs = model_kwargs or {}
        
        self._session = aioboto3.Session()
        self._aws_params = {
            "region_name": self._region_name,
            "aws_access_key_id": aws_access_key_id,
            "aws_secret_access_key": aws_secret_access_key,
        }

    def can_generate_metrics(self) -> bool:
        return True

    async def _process_context(self, context: LLMContext):
        await self.push_frame(LLMFullResponseStartFrame())
        
        prompt = ""
        for message in context.messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            prompt += f"{role}: {content}\n"
        prompt += "assistant: "

        payload = {
            "inputs": prompt,
            "parameters": self._model_kwargs
        }

        try:
            async with self._session.client("sagemaker-runtime", **self._aws_params) as client:
                response = await client.invoke_endpoint(
                    EndpointName=self._endpoint_name,
                    ContentType="application/json",
                    Body=json.dumps(payload)
                )

                body = await response["Body"].read()
                result = json.loads(body.decode())
                
                text = ""
                if isinstance(result, list) and len(result) > 0:
                    text = result[0].get("generated_text", "")
                elif isinstance(result, dict):
                    text = result.get("generated_text", "") or result.get("output", "") or result.get("text", "")
                
                if text:
                    if text.startswith(prompt):
                        text = text[len(prompt):].strip()
                    
                    await self.push_frame(TextFrame(text))
        except Exception as e:
            logger.error(f"SageMaker LLM error: {e}")
            await self.push_error(f"SageMaker LLM error: {e}")
        finally:
            await self.push_frame(LLMFullResponseEndFrame())
