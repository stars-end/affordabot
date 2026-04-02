"""Client for Z.ai GLM-OCR layout parsing."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


DEFAULT_LAYOUT_PARSING_URL = "https://api.z.ai/api/paas/v4/layout_parsing"


class ZaiLayoutParsingError(RuntimeError):
    """Raised when the GLM-OCR layout parsing API fails."""


@dataclass(frozen=True)
class ZaiLayoutParsingResult:
    markdown: str
    model: str | None = None
    request_id: str | None = None
    usage: dict[str, Any] | None = None
    data_info: dict[str, Any] | None = None


class ZaiLayoutParsingClient:
    """Minimal sync client for the GLM-OCR layout parsing API."""

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str = DEFAULT_LAYOUT_PARSING_URL,
        timeout: float = 120.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("ZAI_API_KEY")
        self.endpoint = endpoint
        self.timeout = timeout

    def _require_api_key(self) -> str:
        if not self.api_key:
            raise ZaiLayoutParsingError("ZAI_API_KEY is not set")
        return self.api_key

    @staticmethod
    def _encode_file_base64(file_path: str | Path) -> str:
        content = Path(file_path).read_bytes()
        return base64.b64encode(content).decode("utf-8")

    def parse_file(
        self,
        file_ref: str,
        *,
        model: str = "glm-ocr",
        start_page_id: int | None = None,
        end_page_id: int | None = None,
        return_crop_images: bool = False,
        need_layout_visualization: bool = False,
        request_id: str | None = None,
        user_id: str | None = None,
    ) -> ZaiLayoutParsingResult:
        api_key = self._require_api_key()
        payload: dict[str, Any] = {
            "model": model,
            "file": file_ref,
            "return_crop_images": return_crop_images,
            "need_layout_visualization": need_layout_visualization,
        }
        if start_page_id is not None:
            payload["start_page_id"] = start_page_id
        if end_page_id is not None:
            payload["end_page_id"] = end_page_id
        if request_id:
            payload["request_id"] = request_id
        if user_id:
            payload["user_id"] = user_id

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if response.status_code != 200:
            raise ZaiLayoutParsingError(
                f"GLM-OCR request failed: {response.status_code} {response.text}"
            )

        data = response.json()
        markdown = (data.get("md_results") or "").strip()
        if not markdown:
            raise ZaiLayoutParsingError("GLM-OCR response missing md_results")

        return ZaiLayoutParsingResult(
            markdown=markdown,
            model=data.get("model"),
            request_id=data.get("request_id"),
            usage=data.get("usage"),
            data_info=data.get("data_info"),
        )

    def parse_path(
        self,
        file_path: str | Path,
        *,
        model: str = "glm-ocr",
        start_page_id: int | None = None,
        end_page_id: int | None = None,
    ) -> ZaiLayoutParsingResult:
        encoded = self._encode_file_base64(file_path)
        return self.parse_file(
            encoded,
            model=model,
            start_page_id=start_page_id,
            end_page_id=end_page_id,
        )
