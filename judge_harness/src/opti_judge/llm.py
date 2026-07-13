"""Pluggable judge-model client. Judges are pinned strong models (never the
loop's cheap executor — ADR-0016 economics); the exact pin is Open Question 17.

Providers:

- ``fixture``           — deterministic canned outputs for tests; never trusted.
- ``command``           — run a local command; JSON request on stdin, JSON
                          response on stdout. This is the hook for the project
                          owner's external model runner.
- ``openai-compatible`` — stdlib urllib POST to ``{base_url}/chat/completions``
                          reading JUDGE_MODEL / JUDGE_BASE_URL / JUDGE_API_KEY
                          env vars (no key ever appears in files or traces).

Every response is wrapped in a provenance envelope: provider, model
identifier, and a prompt checksum, so judge outputs are pinned and
reproducible like verifier results.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import urllib.request
from dataclasses import dataclass
from typing import Any


class JudgeModelError(RuntimeError):
    """Model invocation failed — consumers treat the judgment as absent, never as a score."""


@dataclass(slots=True)
class ModelResponse:
    text: str
    provider: str
    model: str
    prompt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "prompt_sha256": self.prompt_sha256,
        }


def _digest(messages: list[dict[str, str]]) -> str:
    return hashlib.sha256(
        json.dumps(messages, sort_keys=True).encode("utf-8")
    ).hexdigest()


def call_model(messages: list[dict[str, str]], config: dict[str, Any]) -> ModelResponse:
    provider = str(config.get("provider", "fixture"))
    digest = _digest(messages)

    if provider == "fixture":
        canned = config.get("responses") or {}
        text = canned.get(digest) or canned.get("default") or json.dumps(
            {"opinion": "undecidable", "confidence": 0.0, "rationale": "fixture default"}
        )
        return ModelResponse(text=text, provider="fixture", model="fixture", prompt_sha256=digest)

    if provider == "command":
        command = config.get("command")
        if not command:
            raise JudgeModelError("command provider requires 'command'")
        request = json.dumps({"messages": messages})
        proc = subprocess.run(
            command, shell=True, input=request, capture_output=True, text=True, timeout=300
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            raise JudgeModelError(
                f"judge command failed (exit {proc.returncode}): {proc.stderr[-300:]}"
            )
        return ModelResponse(
            text=proc.stdout.strip(),
            provider="command",
            model=str(config.get("model_label", "command")),
            prompt_sha256=digest,
        )

    if provider == "openai-compatible":
        base_url = os.environ.get("JUDGE_BASE_URL") or config.get("base_url")
        model = os.environ.get("JUDGE_MODEL") or config.get("model")
        api_key = os.environ.get("JUDGE_API_KEY")
        if not base_url or not model:
            raise JudgeModelError(
                "openai-compatible provider needs JUDGE_BASE_URL and JUDGE_MODEL "
                "(judge pin per ADR-0017: Codex sub-agent, preset GPT-5.6 Sol Ultra)"
            )
        body = json.dumps(
            {"model": model, "messages": messages, "temperature": 0}
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{base_url.rstrip('/')}/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {api_key}"} if api_key else {}),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 — single boundary, re-raised typed
            raise JudgeModelError(f"judge endpoint call failed: {exc}") from exc
        try:
            text = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise JudgeModelError(f"unexpected endpoint response shape: {exc}") from exc
        return ModelResponse(
            text=text, provider="openai-compatible", model=str(model), prompt_sha256=digest
        )

    raise JudgeModelError(f"unknown judge model provider: {provider}")
