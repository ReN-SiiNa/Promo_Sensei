"""PromoSensei — agentic deal assistant (Streamlit UI).

Runs the manual Claude tool-use agent and streams its reasoning + tool calls so
you can watch it think, not just read the final answer. Runs locally with no
GPU: the LLM is the hosted Claude API and only the small embedding model runs
on-device.

Run with:  streamlit run app.py
Needs ANTHROPIC_API_KEY (env or .env). Build the index first if missing:
    python faiss_index_builder.py
"""

import json
import os

import streamlit as st
from dotenv import load_dotenv

from promo_agent import run_agent

load_dotenv(override=True)  # .env wins over any stale shell/OS vars

st.set_page_config(page_title="PromoSensei", page_icon="🎯", layout="centered")
st.title("🎯 PromoSensei")
st.caption("An AI agent that searches, filters, and compares live promotional deals.")

# --- sidebar --------------------------------------------------------------
with st.sidebar:
    st.header("About")
    st.markdown(
        "Ask about deals across **Flipkart**, **Nykaa**, and **Puma**. "
        "The agent picks its own tools — semantic search, structured "
        "filtering, comparison, stats, and (on request) a live re-scrape."
    )
    st.markdown("**Try:**")
    st.markdown(
        "- Puma shoes under ₹3000 with at least 40% off\n"
        "- What's the single biggest discount right now?\n"
        "- Compare a face serum and a moisturiser deal\n"
        "- Any fresh Nykaa deals? (live scrape)"
    )
    if not os.getenv("ANTHROPIC_API_KEY"):
        st.warning("ANTHROPIC_API_KEY not set — the agent won't run. "
                   "Add it to your environment or a .env file.")
    if st.button("Clear conversation"):
        st.session_state.clear()
        st.rerun()

# --- state ----------------------------------------------------------------
if "display" not in st.session_state:
    st.session_state.display = []   # rendered chat turns
if "history" not in st.session_state:
    st.session_state.history = []   # message history passed back to the agent

TOOL_LABELS = {
    "search_products": "🔎 Semantic search",
    "filter_deals": "🎯 Filtering deals",
    "compare_products": "⚖️ Comparing products",
    "deal_stats": "📊 Aggregating stats",
    "refresh_deals": "🕷️ Live re-scrape",
}


def render_turn(turn):
    """Re-render a stored chat turn (user or assistant)."""
    with st.chat_message(turn["role"]):
        if turn["role"] == "user":
            st.markdown(turn["content"])
            return
        for step in turn.get("steps", []):
            _render_step(step)
        if turn.get("answer"):
            st.markdown(turn["answer"])


def _render_step(step):
    kind = step["type"]
    if kind == "thinking":
        with st.expander("💭 Reasoning", expanded=False):
            st.markdown(step["text"])
    elif kind == "tool_use":
        label = TOOL_LABELS.get(step["name"], f"🔧 {step['name']}")
        with st.expander(f"{label}", expanded=False):
            st.markdown("**Input**")
            st.json(step["input"])
            if "result" in step:
                st.markdown("**Result**")
                _show_result(step["result"])
    elif kind == "error":
        st.error(step["text"])


def _show_result(raw):
    try:
        st.json(json.loads(raw))
    except (json.JSONDecodeError, TypeError):
        st.code(str(raw))


# --- replay prior conversation -------------------------------------------
for turn in st.session_state.display:
    render_turn(turn)

# --- new input ------------------------------------------------------------
query = st.chat_input("Ask about current promotions…")
if query:
    st.session_state.display.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        steps = []            # collected for re-render on rerun
        pending_tool = None   # tool_use awaiting its result
        answer_text = ""

        think_buf = ""        # accumulates thinking_delta until a `thinking` event
        think_box = None      # live placeholder for streaming reasoning
        text_buf = ""         # accumulates text_delta until `text`/`answer`
        answer_box = None     # live placeholder for the streaming answer

        for event in run_agent(query, history=st.session_state.history):
            etype = event["type"]

            if etype == "thinking_delta":
                if think_box is None:
                    think_box = st.expander("💭 Reasoning", expanded=True).empty()
                think_buf += event["text"]
                think_box.markdown(think_buf)

            elif etype == "thinking":
                # complete reasoning block — finalize the live box and store it
                if think_box is not None:
                    think_box.markdown(event["text"])
                    think_box = None
                    think_buf = ""
                steps.append({"type": "thinking", "text": event["text"]})

            elif etype == "text_delta":
                if answer_box is None:
                    answer_box = st.empty()
                text_buf += event["text"]
                answer_box.markdown(text_buf)

            elif etype == "tool_use":
                pending_tool = {"type": "tool_use", "name": event["name"],
                                "input": event["input"]}

            elif etype == "tool_result":
                if pending_tool is not None:
                    pending_tool["result"] = event["result"]
                    steps.append(pending_tool)
                    _render_step(pending_tool)
                    pending_tool = None

            elif etype == "text":
                # complete interim narration before more tool calls; the
                # streamed text_buf becomes stale once tools run, so drop it
                answer_box = None
                text_buf = ""

            elif etype == "answer":
                answer_text = event["text"]
                if answer_box is not None:
                    answer_box.markdown(answer_text)
                elif answer_text:
                    st.markdown(answer_text)
                st.session_state.history = event["messages"]

            elif etype == "error":
                steps.append({"type": "error", "text": event["text"]})
                st.error(event["text"])

    st.session_state.display.append(
        {"role": "assistant", "steps": steps, "answer": answer_text})
