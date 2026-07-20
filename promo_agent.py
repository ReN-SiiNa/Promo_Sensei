"""The PromoSensei agent — a hand-written tool-use loop.

This is deliberately the *manual* agentic loop (not an SDK tool runner): the
call → detect tool calls → execute → feed results → repeat cycle is written out
so the control flow is fully visible. The agent decides which tools to call, in
what order, and loops until it has enough to answer.

Two backends, chosen by environment:

- **Direct Anthropic** (default): the Anthropic SDK against the Messages API,
  with adaptive thinking.
- **Portkey gateway**: the `portkey_ai` SDK against your Portkey gateway, using
  the OpenAI-style chat.completions + function-calling shape. Selected when
  PORTKEY_API_KEY is set.

Both funnel through the same tool dispatch (`promo_tools.run_tool`) and emit the
same event stream, so the Streamlit UI is backend-agnostic.

`run_agent()` is a generator yielding event dicts. Responses stream, so the
incremental *_delta events arrive first, then the matching complete event:
    {"type": "thinking_delta", "text": ...}   # incremental reasoning token(s)
    {"type": "thinking", "text": ...}          # complete reasoning block
    {"type": "text_delta", "text": ...}        # incremental answer token(s)
    {"type": "tool_use", "name": ..., "input": {...}}
    {"type": "tool_result", "name": ..., "result": <str>}
    {"type": "text", "text": ...}              # complete interim narration
    {"type": "answer", "text": ..., "messages": [...]}
    {"type": "error", "text": ...}
"""

import json
import os

from promo_tools import TOOLS, openai_tools, run_tool

# Direct-Anthropic model (adaptive thinking). Overridable via ANTHROPIC_MODEL.
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")
MAX_TOKENS = 4096
MAX_TURNS = 8  # safety cap on the tool-use loop

SYSTEM_PROMPT = (
    "You are PromoSensei, an assistant that helps shoppers find the best "
    "promotional deals across Flipkart, Nykaa, and Puma.\n\n"
    "You have tools to search, filter, compare, and aggregate a catalog of "
    "scraped product deals, plus a slow live re-scrape tool. Decide which "
    "tools to use and in what order:\n"
    "- Use filter_deals for concrete constraints (min discount, price ceiling, "
    "brand).\n"
    "- Use search_products for open-ended, meaning-based queries.\n"
    "- Use compare_products when weighing specific items against each other.\n"
    "- Use deal_stats for overview/aggregate questions.\n"
    "- Only use refresh_deals when the user explicitly wants fresh/live data; "
    "it is slow.\n\n"
    "You may chain several tool calls to fully answer a question (e.g. get "
    "stats, then filter). Prices are in Indian rupees (₹). Ground every claim "
    "in tool results — never invent products, prices, or discounts. When you "
    "present deals, be concise: lead with the best options, include the "
    "discount and price, and link when available."
)


def _use_portkey():
    return bool(os.getenv("PORTKEY_API_KEY"))


def run_agent(user_query, history=None):
    """Run one agentic turn, yielding UI events. `history` is the message list
    from a prior turn's answer event (backend-specific shape); pass it back for
    multi-turn context."""
    try:
        if _use_portkey():
            yield from _run_portkey(user_query, history)
        else:
            yield from _run_anthropic(user_query, history)
    except Exception as exc:  # noqa: BLE001 — surface any backend error to the UI
        yield {"type": "error", "text": f"{type(exc).__name__}: {exc}"}


# ==========================================================================
# Backend 1: direct Anthropic Messages API
# ==========================================================================
def _run_anthropic(user_query, history):
    import anthropic

    client = anthropic.Anthropic()
    messages = list(history or [])
    messages.append({"role": "user", "content": user_query})

    for _turn in range(MAX_TURNS):
        with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            thinking={"type": "adaptive", "display": "summarized"},
            tools=TOOLS,
            messages=messages,
        ) as stream:
            for event in stream:
                if event.type != "content_block_delta":
                    continue
                delta = event.delta
                if getattr(delta, "type", None) == "thinking_delta":
                    yield {"type": "thinking_delta", "text": delta.thinking}
                elif getattr(delta, "type", None) == "text_delta":
                    yield {"type": "text_delta", "text": delta.text}
            response = stream.get_final_message()

        is_final = response.stop_reason != "tool_use"

        # Finalize each complete block so the UI can store it for re-render.
        # The final answer's text is delivered via `answer`, not `text`.
        for block in response.content:
            if block.type == "thinking" and getattr(block, "thinking", ""):
                yield {"type": "thinking", "text": block.thinking}
            elif block.type == "text" and block.text and not is_final:
                yield {"type": "text", "text": block.text}

        if is_final:
            answer = "".join(b.text for b in response.content if b.type == "text").strip()
            messages.append({"role": "assistant", "content": response.content})
            yield {"type": "answer", "text": answer, "messages": messages}
            return

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            yield {"type": "tool_use", "name": block.name, "input": block.input}
            result = run_tool(block.name, block.input)
            yield {"type": "tool_result", "name": block.name, "result": result}
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })
        messages.append({"role": "user", "content": tool_results})

    yield {"type": "error", "text": f"Stopped after {MAX_TURNS} tool-use turns without a final answer."}


# ==========================================================================
# Backend 2: Portkey gateway (OpenAI chat.completions + function calling)
# ==========================================================================
def _portkey_client():
    from portkey_ai import Portkey

    kwargs = {"api_key": os.environ["PORTKEY_API_KEY"]}
    base_url = os.getenv("PORTKEY_GATEWAY_URL")
    if base_url:
        kwargs["base_url"] = base_url
    if os.getenv("PORTKEY_VIRTUAL_KEY"):
        kwargs["virtual_key"] = os.getenv("PORTKEY_VIRTUAL_KEY")
    if os.getenv("PORTKEY_CONFIG"):
        kwargs["config"] = os.getenv("PORTKEY_CONFIG")
    return Portkey(**kwargs)


def _run_portkey(user_query, history):
    # Model slug for your gateway, e.g. "@dsvertex/anthropic.claude-3-5-sonnet-v2@20241022"
    model = os.getenv("PORTKEY_MODEL")
    if not model:
        yield {"type": "error", "text": (
            "PORTKEY_MODEL is not set. Set it to your gateway's model slug, e.g. "
            "@dsvertex/anthropic.claude-3-5-sonnet-v2@20241022"
        )}
        return

    if os.getenv("PROMO_DEBUG"):
        print(
            f"[PromoSensei] Portkey backend → model={model!r} "
            f"gateway={os.getenv('PORTKEY_GATEWAY_URL') or '(default)'}",
            flush=True,
        )

    client = _portkey_client()
    messages = list(history or [])
    if not messages:
        messages.append({"role": "system", "content": SYSTEM_PROMPT})
    messages.append({"role": "user", "content": user_query})

    tools = openai_tools()

    for _turn in range(MAX_TURNS):
        stream = client.chat.completions.create(
            model=model,
            max_tokens=MAX_TOKENS,
            messages=messages,
            tools=tools,
            stream=True,
        )

        # Accumulate streamed deltas: text arrives whole-ish, tool calls arrive
        # as fragments keyed by index that must be stitched together.
        content_parts = []
        tool_acc = {}  # index -> {"id", "name", "arguments"}
        for chunk in stream:
            if not getattr(chunk, "choices", None):
                continue
            delta = chunk.choices[0].delta
            if getattr(delta, "content", None):
                content_parts.append(delta.content)
                yield {"type": "text_delta", "text": delta.content}
            for tc in getattr(delta, "tool_calls", None) or []:
                slot = tool_acc.setdefault(
                    tc.index, {"id": None, "name": "", "arguments": ""})
                if getattr(tc, "id", None):
                    slot["id"] = tc.id
                fn = getattr(tc, "function", None)
                if fn is not None:
                    if getattr(fn, "name", None):
                        slot["name"] = fn.name
                    if getattr(fn, "arguments", None):
                        slot["arguments"] += fn.arguments

        content = "".join(content_parts)
        tool_calls = [tool_acc[i] for i in sorted(tool_acc)]

        if not tool_calls:
            answer = content.strip()
            messages.append({"role": "assistant", "content": content})
            yield {"type": "answer", "text": answer, "messages": messages}
            return

        # Preserve the assistant turn (with its tool_calls) verbatim.
        messages.append({
            "role": "assistant",
            "content": content,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                }
                for tc in tool_calls
            ],
        })

        # Execute each tool call; OpenAI shape returns one tool message per call.
        for tc in tool_calls:
            name = tc["name"]
            try:
                args = json.loads(tc["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            yield {"type": "tool_use", "name": name, "input": args}
            result = run_tool(name, args)
            yield {"type": "tool_result", "name": name, "result": result}
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })

    yield {"type": "error", "text": f"Stopped after {MAX_TURNS} tool-use turns without a final answer."}
