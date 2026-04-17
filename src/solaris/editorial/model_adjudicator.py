# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable
import urllib.error
import urllib.request

from solaris.editorial.adjudication import AdjudicationContext, AdjudicationResult


REQUEST_TIMEOUT_SECONDS = 20.0
MAX_RATIONALE_CHARS = 280
SYSTEM_PROMPT = """You are a cautious Solaris editorial adjudicator.

You are not the final authority. You are advising a deterministic editorial engine about an ambiguous memory artifact.

Return only valid JSON with this exact shape:
{"action":"promote|leave_candidate|retire","confidence":0.0,"rationale":"short audit rationale"}

Rules:
- Choose only from the allowed_actions list provided by the user.
- Prefer leave_candidate when uncertain.
- Do not invent facts, provenance, or evidence.
- Keep rationale short, concrete, and audit-friendly.
- Confidence must be a number from 0.0 to 1.0.
"""


def _compact(text: Any) -> str:
    return " ".join(str(text or "").split()).strip()


def _truncate(text: Any, *, limit: int = MAX_RATIONALE_CHARS) -> str:
    normalized = _compact(text)
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 1)].rstrip() + "..."


def _chat_completions_url(base_url: str) -> str:
    normalized = str(base_url or "").strip().rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return normalized + "/chat/completions"


def _default_transport(
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _extract_content(payload: dict[str, Any]) -> str:
    choices = list(payload.get("choices") or [])
    if not choices:
        raise ValueError("No choices returned from adjudication provider.")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text)
            elif isinstance(item, str) and item.strip():
                parts.append(item)
        if parts:
            return "\n".join(parts)
    raise ValueError("No textual content returned from adjudication provider.")


def build_adjudication_prompt(context: AdjudicationContext) -> str:
    factors = {
        key: round(float(value), 4)
        for key, value in dict(context.factors or {}).items()
        if isinstance(value, (int, float))
    }
    body = {
        "artifact_type": context.artifact_type,
        "kind": context.kind,
        "canonical_text": context.canonical_text,
        "policy_profile": context.policy_profile,
        "policy_version": context.policy_version,
        "remember_score": round(float(context.remember_score), 4),
        "influence_score": round(float(context.influence_score), 4),
        "current_rule_action": context.current_action,
        "allowed_actions": list(context.allowed_actions),
        "supporting_event_count": len(list(context.supporting_event_ids or [])),
        "factors": factors,
        "current_state": dict(context.current_state or {}),
    }
    return json.dumps(body, ensure_ascii=True, indent=2, sort_keys=True)


@dataclass(slots=True)
class OpenAICompatibleAdjudicator:
    model: str
    base_url: str
    api_key: str = ""
    timeout_seconds: float = REQUEST_TIMEOUT_SECONDS
    prompt_version: str = "solaris_editorial_adjudication_v1"
    transport: Callable[..., dict[str, Any]] | None = None

    def adjudicate(self, context: AdjudicationContext) -> AdjudicationResult | None:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_adjudication_prompt(context)},
            ],
        }
        try:
            raw = (self.transport or _default_transport)(
                url=_chat_completions_url(self.base_url),
                headers=headers,
                payload=payload,
                timeout_seconds=max(1.0, float(self.timeout_seconds)),
            )
            parsed = json.loads(_extract_content(raw))
            action = str(parsed.get("action") or "").strip()
            if action not in context.allowed_actions:
                raise ValueError(f"Unsupported adjudication action: {action or '<empty>'}")
            try:
                confidence = max(0.0, min(1.0, float(parsed.get("confidence"))))
            except Exception:
                confidence = 0.0
            rationale = _truncate(parsed.get("rationale") or "No rationale provided.")
            return AdjudicationResult(
                action=action,
                confidence=confidence,
                rationale=rationale,
                source="model",
                model=self.model,
                prompt_version=self.prompt_version,
            )
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError, KeyError, json.JSONDecodeError) as exc:
            return AdjudicationResult(
                action=context.current_action,
                confidence=0.0,
                rationale=_truncate(f"adjudication_error: {exc}"),
                source="model_error",
                model=self.model,
                prompt_version=self.prompt_version,
            )
