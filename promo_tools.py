"""Tool definitions and dispatch for the PromoSensei agent.

`TOOLS` is the JSON-schema list handed to the Claude API. `run_tool` executes a
tool call by name and returns a JSON-serialisable result. Keeping the schemas
and the execution in one place means the agent loop stays generic.
"""

import json

import promo_data as data

# --------------------------------------------------------------------------
# Tool schemas (Anthropic tool-use format)
# --------------------------------------------------------------------------
TOOLS = [
    {
        "name": "search_products",
        "description": (
            "Semantic search over the promotional catalog by natural-language "
            "query. Use for open-ended requests like 'running shoes' or "
            "'face serum for oily skin' where meaning matters more than exact "
            "fields. Returns the most relevant products."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural-language search query."},
                "top_k": {"type": "integer", "description": "How many results (1-20, default 5)."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "filter_deals",
        "description": (
            "Filter the catalog by exact numeric/brand criteria, sorted by "
            "discount (highest first). Use when the user gives concrete "
            "constraints — a minimum discount, a price ceiling, a specific "
            "brand — e.g. 'Puma shoes under 3000 with at least 40% off'. "
            "Prefer this over search_products when the request is about "
            "thresholds rather than meaning."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "min_discount": {"type": "integer", "description": "Minimum discount percent."},
                "max_price": {"type": "number", "description": "Maximum price in rupees."},
                "min_price": {"type": "number", "description": "Minimum price in rupees."},
                "brand": {"type": "string", "description": "Brand name (substring match)."},
                "limit": {"type": "integer", "description": "Max results (1-25, default 10)."},
            },
            "required": [],
        },
    },
    {
        "name": "compare_products",
        "description": (
            "Look up several specific products by title and return them side "
            "by side (price, discount, tag) so you can compare value. Use when "
            "the user names or implies 2+ specific items to weigh against each "
            "other."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "titles": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Product titles or descriptions to compare.",
                },
            },
            "required": ["titles"],
        },
    },
    {
        "name": "deal_stats",
        "description": (
            "Aggregate statistics across the catalog (optionally scoped to one "
            "brand): product count, best discount, average discount, top deal, "
            "cheapest item. Use for overview questions like 'what's the biggest "
            "discount right now' or 'how many Nykaa deals are there'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "brand": {"type": "string", "description": "Optional brand to scope stats to."},
            },
            "required": [],
        },
    },
    {
        "name": "refresh_deals",
        "description": (
            "Scrape fresh promotional listings live and add them to the "
            "searchable catalog for the rest of this conversation. This is slow "
            "(opens a real browser, ~20-60s per site) — only use it when the "
            "user explicitly asks for the latest/current deals or says the data "
            "seems stale. Use source='all' to scrape all three sites at once "
            "(top few from each) when the user wants fresh deals across the "
            "board without naming a site."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "enum": ["flipkart", "nykaa", "puma", "all"],
                    "description": "Which site to re-scrape, or 'all' for every site.",
                },
                "max_items": {
                    "type": "integer",
                    "description": (
                        "Approx how many products to fetch (capped at 40). For a "
                        "single site the default is 20; for source='all' this is "
                        "the count per site (default 5)."
                    ),
                },
            },
            "required": ["source"],
        },
    },
]


def openai_tools():
    """Same tools in OpenAI/chat-completions function format, for the Portkey
    gateway path (which speaks the OpenAI API shape)."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in TOOLS
    ]


# --------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------
def run_tool(name, tool_input):
    """Execute a tool call, returning a JSON string for the tool_result block.

    Raises nothing — errors are returned as an {"error": ...} payload so the
    agent can read them and recover.
    """
    try:
        result = _dispatch(name, tool_input or {})
    except Exception as exc:  # surfaced to the model, not the user
        result = {"error": f"{type(exc).__name__}: {exc}"}
    return json.dumps(result, ensure_ascii=False, default=str)


def _dispatch(name, args):
    if name == "search_products":
        return data.search_products(args["query"], top_k=args.get("top_k", 5))
    if name == "filter_deals":
        return data.filter_deals(
            min_discount=args.get("min_discount"),
            max_price=args.get("max_price"),
            min_price=args.get("min_price"),
            brand=args.get("brand"),
            limit=args.get("limit", 10),
        )
    if name == "compare_products":
        return data.compare_products(args["titles"])
    if name == "deal_stats":
        return data.deal_stats(brand=args.get("brand"))
    if name == "refresh_deals":
        # Imported lazily so Playwright isn't required unless this tool runs.
        import live_scrape
        source = args["source"]
        # "all" scrapes every site, so the count is per-site — default 5, not 20.
        default_items = 5 if source == "all" else 20
        return live_scrape.refresh_deals(
            source, max_items=args.get("max_items", default_items))
    return {"error": f"unknown tool: {name}"}
