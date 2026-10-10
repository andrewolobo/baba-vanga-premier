"""One structured-output request to the Azure Foundry deployment (D7).

The official `openai` SDK, pointed at Foundry's OpenAI-compatible v1 route.
The Responses API's `parse` sends the Pydantic model as a strict JSON schema
and returns a validated instance.

Two kinds of retry, owned in two places:

- **Transport retries** (429, 5xx, timeouts, connection) are the SDK's own,
  with backoff (`TRANSPORT_RETRIES`).
- **Content retries**, where the validator rejected the answer, belong to
  `analyse.py`, because only it knows what was wrong.

Settings come from the environment (`engine.config`): the URI, the key and
the deployment name. Nothing here holds a secret.
"""

from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI
from pydantic import BaseModel

from engine import config

#: The task is to explain numbers it is given, not to work anything out.
REASONING_EFFORT = "low"
#: Seconds per request, and transport retries on top. Measured calls took
#: 7-15 s. These bound how far one stuck request can overrun the step's time
#: budget (`jobs.BUDGET_SECONDS`), which has to fit inside the cycle unit's
#: 30-minute timeout.
TIMEOUT_SECONDS = 90.0
TRANSPORT_RETRIES = 2
#: Reasoning tokens count against this, so it is generous. It is a ceiling on
#: a runaway, not a length instruction.
MAX_OUTPUT_TOKENS = 16000


@dataclass(frozen=True)
class Reply:
    #: The validated answer, or None when the model refused or the reply did
    #: not parse against the schema (`error` says which).
    parsed: BaseModel | None
    #: What the model returned, sent back to it with the errors on a retry.
    raw: str
    input_tokens: int
    output_tokens: int
    error: str | None = None


def base_url(uri: str) -> str:
    """The v1 base from whatever the portal showed: a trailing `/responses`
    (the full endpoint) is trimmed, because the SDK appends it."""
    uri = uri.strip().rstrip("/")
    if uri.endswith("/responses"):
        uri = uri[: -len("/responses")]
    return uri + "/"


def client() -> OpenAI:
    """A client for the configured deployment. Raises if it is not configured."""
    missing = [name for name, value in (("AZURE_FOUNDRY_URI", config.AZURE_FOUNDRY_URI),
                                        ("AZURE_FOUNDRY_KEY", config.AZURE_FOUNDRY_KEY),
                                        ("AZURE_MODEL", config.AZURE_MODEL)) if not value]
    if missing:
        raise RuntimeError(f"match analysis is not configured: set {', '.join(missing)}")
    return OpenAI(base_url=base_url(config.AZURE_FOUNDRY_URI), api_key=config.AZURE_FOUNDRY_KEY,
                  timeout=TIMEOUT_SECONDS, max_retries=TRANSPORT_RETRIES)


def ask(api, instructions: str, messages: list[dict], schema: type[BaseModel]) -> Reply:
    """One request: fixed instructions first (so the provider's prefix cache
    can apply), then the conversation so far.

    API errors (auth, quota, an outage the transport retries could not ride
    out) propagate. Whether that ends the analysis is the caller's decision.
    """
    try:
        response = api.responses.parse(
            model=config.AZURE_MODEL, instructions=instructions, input=messages,
            text_format=schema, reasoning={"effort": REASONING_EFFORT},
            max_output_tokens=MAX_OUTPUT_TOKENS, store=False)
    except ValueError as exc:  # pydantic's ValidationError and JSON errors both
        return Reply(None, "", 0, 0, f"the reply did not parse: {exc}")
    usage = response.usage
    tokens = (getattr(usage, "input_tokens", 0) or 0, getattr(usage, "output_tokens", 0) or 0)
    if response.output_parsed is None:
        return Reply(None, response.output_text or "", *tokens,
                     error="no structured answer (refused or incomplete)")
    return Reply(response.output_parsed, response.output_parsed.model_dump_json(), *tokens)
