#
# Copyright (c) 2024-2025, SalesPyper
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import json
from typing import AsyncGenerator, Optional

from loguru import logger

from pipecat.frames.frames import (
    ErrorFrame,
    Frame,
    TTSAudioRawFrame,
    TTSStoppedFrame,
)
from pipecat.services.tts_service import TTSService

try:
    import aioboto3
except ModuleNotFoundError as e:
    logger.error(f"Exception: {e}")
    logger.error(
        "In order to use SageMaker services, you need to `pip install aioboto3`."
    )
    raise Exception(f"Missing module: {e}")


class SageMakerTTSService(TTSService):
    def __init__(
        self,
        *,
        endpoint_name: str,
        region_name: str = "us-east-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        language_code: str = "hi-IN",
        voice_id: str = "default",
        model_kwargs: Optional[dict] = None,
        sample_rate: int = 16000,
        **kwargs
    ):
        super().__init__(**kwargs)
        self._endpoint_name = endpoint_name
        self._region_name = region_name
        self._language_code = language_code
        self._voice_id = voice_id
        self._model_kwargs = model_kwargs or {}
        self._sample_rate = sample_rate

        self._session = aioboto3.Session()
        self._aws_params = {
            "region_name": self._region_name,
            "aws_access_key_id": aws_access_key_id,
            "aws_secret_access_key": aws_secret_access_key,
        }

    def can_generate_metrics(self) -> bool:
        return True

    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame | None, None]:
        logger.debug(f"Generating TTS via SageMaker [{text}]")

        payload = {
            "inputs": text,
            "language": self._language_code,
            "voice": self._voice_id,
            **self._model_kwargs
        }

        try:
            async with self._session.client("sagemaker-runtime", **self._aws_params) as client:
                response = await client.invoke_endpoint(
                    EndpointName=self._endpoint_name,
                    ContentType="application/json",
                    Body=json.dumps(payload)
                )

                audio_data = await response["Body"].read()
                
                if audio_data:
                    yield TTSAudioRawFrame(
                        audio=audio_data,
                        sample_rate=self._sample_rate,
                        num_channels=1,
                        context_id=context_id
                    )
                
                yield TTSStoppedFrame(context_id=context_id)
        except Exception as e:
            logger.error(f"SageMaker TTS error: {e}")
            yield ErrorFrame(error=f"SageMaker TTS error: {e}")
            yield TTSStoppedFrame(context_id=context_id)
