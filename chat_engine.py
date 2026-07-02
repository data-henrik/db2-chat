"""
chat_engine.py — Ollama tool-calling loop with streaming final response.

Usage:
    from chat_engine import chat_stream

    for chunk in chat_stream(messages, model, conv_id, save_fn):
        print(chunk, end="", flush=True)

Status events (prefixed with "[STATUS] ") are interspersed with text chunks
and carry structured information for the activity panel in the frontend.
They are never saved to history and must be filtered out by the consumer.

Status event format:
    [STATUS] model:<name>
    [STATUS] state:thinking | state:generating | state:error
    [STATUS] tool:<name>:<json-args>
    [STATUS] tool_done:<name>
"""

from __future__ import annotations

import json
from typing import Callable, Iterator

import ollama

from config import config
from tools import TOOL_DEFINITIONS, call_tool

# Client is created lazily on first use so a missing/slow Ollama instance
# does not block Flask startup and timeouts are applied per-request.
_OLLAMA_TIMEOUT = 120  # seconds; covers slow local model inference


def _client() -> ollama.Client:
    return ollama.Client(host=config.ollama_host, timeout=_OLLAMA_TIMEOUT)


def chat_stream(
    messages: list,
    model: str,
    conv_id: str,
    save_fn: Callable[[str, object], None],
    _is_recursive: bool = False,
) -> Iterator[str]:
    """Stream the assistant reply, transparently executing any tool calls first.

    Parameters
    ----------
    messages:
        Conversation history in Ollama message format.
    model:
        Ollama model name to use.
    conv_id:
        Conversation identifier (used indirectly via *save_fn*).
    save_fn:
        Callable with signature ``save_fn(role, content)`` that persists a
        message.  Typically ``functools.partial(history.save_message, conv_id)``.
    _is_recursive:
        Internal flag set after tool results have been appended.  On recursive
        calls we skip the keepalive/model status events (already emitted) and
        do NOT offer tools again — the model must now produce its final text
        answer, not another tool call.

    Yields
    ------
    str
        Text chunks of the assistant response, followed by ``"[DONE]"`` as the
        final sentinel value.  Status events are prefixed with ``"[STATUS] "``.
    """
    try:
        client = _client()

        if not _is_recursive:
            # Keepalive flush: forces Flask/WSGI to open the socket immediately
            # before the blocking Ollama call so the browser never stalls.
            yield "\x00"
            yield f"[STATUS] model:{model}"

        if not _is_recursive:
            # ── First call: non-streaming with tools so we can detect tool calls ─
            yield "[STATUS] state:thinking"
            response = client.chat(
                model=model,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                stream=False,
            )

            # ── Handle tool calls ───────────────────────────────────────────────
            if response.message.tool_calls:
                # Append the assistant message that contains the tool_calls so the
                # model receives the full round-trip on the next iteration.
                assistant_msg = {
                    "role": "assistant",
                    "content": response.message.content or "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            }
                        }
                        for tc in response.message.tool_calls
                    ],
                }
                messages.append(assistant_msg)
                # Always persist the assistant turn so load_history sees a valid
                # assistant-with-tool_calls entry before each tool result row.
                save_fn("assistant", assistant_msg)

                for tc in response.message.tool_calls:
                    name = tc.function.name
                    arguments = tc.function.arguments  # dict

                    yield f"[STATUS] tool:{name}:{json.dumps(arguments, ensure_ascii=False)}"
                    result = call_tool(name, arguments)
                    yield f"[STATUS] tool_done:{name}"

                    # Append the tool result so the model has context.
                    messages.append({"role": "tool", "content": result})
                    save_fn("tool", result)

                # After tool results are appended, ask the model to produce its
                # final answer.  _is_recursive=True prevents re-offering tools,
                # which causes some models to echo the tool result JSON verbatim.
                yield from chat_stream(messages, model, conv_id, save_fn, _is_recursive=True)
                return

            # No tool calls — emit the content from the already-complete response
            # and then stream the full answer freshly so the user sees it token
            # by token (the non-streaming call returned the whole text at once).
            yield "[STATUS] state:generating"
            full_response = ""

            stream = client.chat(model=model, messages=messages, stream=True)
            for chunk in stream:
                text = chunk.message.content or ""
                full_response += text
                if text:
                    yield text

            save_fn("assistant", full_response)
            yield "[DONE]"

        else:
            # ── Recursive call: tool results are in messages; generate final answer
            # Do NOT pass tools — prevents models from echoing tool result JSON.
            yield "[STATUS] state:generating"
            full_response = ""

            stream = client.chat(model=model, messages=messages, stream=True)

            for chunk in stream:
                text = chunk.message.content or ""
                full_response += text
                if text:
                    yield text

            save_fn("assistant", full_response)
            yield "[DONE]"

    except Exception as e:  # noqa: BLE001
        yield "[STATUS] state:error"
        yield f"Error: {e}"
        yield "[DONE]"
