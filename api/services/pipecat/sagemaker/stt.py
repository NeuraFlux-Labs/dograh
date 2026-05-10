#
# Copyright (c) 2024-2025, SalesPyper
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import json
from typing import AsyncGenerator, Optional

from loguru import logger

from pipecat.frames.frames import (
    Frame,
    TranscriptionFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.stt_service import STTService
from pipecat.utils.time import time_now_iso8601

try:
    import aioboto3
except ModuleNotFoundError as e:
    logger.error(f"Exception: {e}")
    logger.error(
        "In order to use SageMaker services, you need to `pip install aioboto3`."
    )
    raise Exception(f"Missing module: {e}")


class SageMakerSTTService(STTService):
    def __init__(
        self,
        *,
        endpoint_name: str,
        region_name: str = "us-east-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        language_code: str = "hi-IN",
        model_kwargs: Optional[dict] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self._endpoint_name = endpoint_name
        self._region_name = region_name
        self._language_code = language_code
        self._model_kwargs = model_kwargs or {}

        self._session = aioboto3.Session()
        self._aws_params = {
            "region_name": self._region_name,
            "aws_access_key_id": aws_access_key_id,
            "aws_secret_access_key": aws_secret_access_key,
        }
        self._audio_buffer = bytearray()

    def can_generate_metrics(self) -> bool:
        return True

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, VADUserStartedSpeakingFrame):
            self._audio_buffer = bytearray()
        elif isinstance(frame, VADUserStoppedSpeakingFrame):
            await self._run_inference()

    async def _run_inference(self):
        if not self._audio_buffer:
            return

        try:
            async with self._session.client("sagemaker-runtime", **self._aws_params) as client:
                # Most STT custom containers on SageMaker accept raw audio bytes 
                # with specific content-type or a JSON with base64.
                # We'll use application/octet-stream as a default for raw PCM.
                response = await client.invoke_endpoint(
                    EndpointName=self._endpoint_name,
                    ContentType="application/octet-stream",
                    Body=bytes(self._audio_buffer),
                    CustomAttributes=f"language={self._language_code}"
                )

                body = await response["Body"].read()
                result = json.loads(body.decode())
                transcript = result.get("text", "") or result.get("transcript", "") or result.get("generated_text", "")

                if transcript:
                    await self.push_frame(TranscriptionFrame(transcript, "", time_now_iso8601()))
        except Exception as e:
            logger.error(f"SageMaker STT error: {e}")
        finally:
            self._audio_buffer = bytearray()

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame | None, None]:
        self._audio_buffer.extend(audio)
        yield None
