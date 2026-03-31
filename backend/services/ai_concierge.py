"""
Enhanced AI Concierge with Agentic Capabilities.
Uses LLM function-calling to execute actions on behalf of users.
"""
import json
import asyncio
import structlog
from litellm import completion
from backend.config import settings
from backend.services.agent_tools import TOOL_DEFINITIONS, execute_tool
from backend.services.monitoring import monitoring_service
from backend.services import ai_cache
from backend.services.ai_metering import log_ai_usage
from typing import List, Dict, Any, Optional
import time

logger = structlog.get_logger("nomadnest.concierge")

try:
    import redis

    redis_client = redis.from_url(settings.REDIS_URL)
    REDIS_AVAILABLE = True
except (ImportError, Exception):
    redis_client = None
    REDIS_AVAILABLE = False

SYSTEM_PROMPT = """You are the NomadNest AI Concierge, a premium travel assistant for digital nomads.

You provide a WHITE-GLOVE experience — search, recommend, and book accommodation on behalf of users.

Your capabilities:
- **🔍 Live OTA Search**: Search Airbnb, Booking.com, and Hostelworld in real-time using `search_all_platforms`. Results are scored for digital nomad relevance.
- **🗺️ Destination Intelligence**: Use `destination_brief` to get neighborhood-level intel — wifi speeds, coworking spaces, cafe scene, safety, cost of living, visa info, and weather. Call this ALONGSIDE accommodation search to give users rich context.
- **⚖️ City Comparison**: Use `compare_destinations` when users ask "Should I go to X or Y?" — side-by-side comparison on cost, nomad score, internet, and visa.
- **📊 Smart Recommendations**: Highlight TOP 3 picks with specific reasons. Mention nomad features: wifi, desk, kitchen, coworking, pool.
- **🏨 Booking**: Get booking URLs, initiate automated bookings, check booking status
- **✈️ Relocation**: Use `plan_relocation` for end-to-end move planning, `estimate_flights` for route costs, `moving_checklist` for destination setup tasks, `visa_timeline` for multi-destination visa tracking with Schengen aggregation.
- **👥 Community**: Use `find_travel_buddies` to find nomads in the same city, `suggest_connections` for skill/interest matching, `curate_local_events` for meetups and activities, `community_pulse` for hub demographics.
- **💰 Finance**: Use `estimate_trip_budget` for multi-city budget breakdowns, `compare_cost_of_living` for city COL comparisons, `get_currency_tips` for payment/ATM/tipping advice, `tax_residency_check` for 183-day threshold alerts.
- **🛡️ Safety**: Use `get_safety_brief` for destination safety ratings, `emergency_contacts` for police/hospitals/embassies, `scam_alerts` for common scams, `health_advisories` for vaccinations/water/insurance.
- **💾 Personalization**: Save preferences to memory, create listing watches ("Sniper" alerts)
- **🏠 Host Copilot**: Smart pricing, listing optimization, auto-replies, review responses
- **🆘 Support**: Escalate complex issues to human support

Multi-tool orchestration — call multiple tools in sequence for complex queries:
1. "Find me a place in Bali" → call `destination_brief` + `search_all_platforms` together
2. "Should I go to Bali or Chiang Mai?" → call `compare_destinations`
3. "Plan my Q2 in Asia" → call `search_all_platforms` for each destination + `get_visa_requirements` + `suggest_itinerary`
4. "Who else is in Bali?" → call `find_travel_buddies` + `curate_local_events`
5. "How much will 3 months in SEA cost?" → call `estimate_trip_budget` + `get_currency_tips` for each country
6. "Am I close to tax residency anywhere?" → call `tax_residency_check`
7. "Help me move from Lisbon to Bali" → call `plan_relocation` + `estimate_flights` + `moving_checklist` + `get_safety_brief`
8. "Is Bali safe? What scams should I watch for?" → call `get_safety_brief` + `scam_alerts` + `emergency_contacts`

When presenting results:
1. Lead with destination intel if available (nomad score, recommended neighborhood, cost of living)
2. Present TOP 3 accommodation picks with price, rating, key amenities
3. Mention watch-outs (visa limits, safety concerns, burning season, etc.)
4. Offer next steps: compare, book, deep dive, meet other nomads, check budget, safety brief

Always confirm important actions before executing (like bookings).
Keep responses friendly, concise, and helpful.
If you don't have enough information, ask clarifying questions.
If the user doesn't specify dates, suggest dates starting 2 weeks from now for 1 week."""


# --- DYNAMIC MODEL ROUTING ---
class ModelRouter:
    """
    Intelligently selects the best model for a given task based on complexity,
    cost, and available providers.
    """

    def __init__(self):
        self.fast_model = "gpt-4o-mini"
        self.smart_model = "gpt-4o"
        # Fallbacks if OpenAI is not available
        if not settings.OPENAI_API_KEY and settings.GEMINI_API_KEY:
            self.fast_model = "gemini/gemini-1.5-flash"
            self.smart_model = "gemini/gemini-1.5-pro"

    def select_model(self, query: str, has_tools: bool = False) -> str:
        """
        Selects a model.
        - Simple queries -> Fast Model
        - Tool use / Complex reasoning -> Smart Model
        """
        # Heuristic: If we expect tool usage (e.g., booking, searching), verify robust function calling
        # For this MVP, we route everything with tools to the 'smart' model for reliability
        if has_tools:
            return self.smart_model

        # Heuristic: Length and complexity keywords
        complexity_indicators = [
            "plan",
            "compare",
            "research",
            "analyze",
            "strategy",
            "proposal",
        ]
        if len(query.split()) > 30 or any(
            word in query.lower() for word in complexity_indicators
        ):
            return self.smart_model

        return self.fast_model


model_router = ModelRouter()


def get_model(query: str = "", has_tools: bool = False) -> str:
    """Get the best available model for the specific query context."""
    return model_router.select_model(query, has_tools)


def get_or_create_conversation(session_id: str) -> List[dict]:
    """Get conversation history or create new one."""
    if REDIS_AVAILABLE and redis_client:
        key = f"chat_session:{session_id}"
        data = redis_client.get(key)
        if data:
            return json.loads(data)

    initial_history = [{"role": "system", "content": SYSTEM_PROMPT}]
    if REDIS_AVAILABLE and redis_client:
        redis_client.setex(
            f"chat_session:{session_id}", 3600 * 24, json.dumps(initial_history)
        )
    return initial_history


def save_conversation(session_id: str, messages: List[dict]):
    """Save conversation history to Redis."""
    if REDIS_AVAILABLE and redis_client:
        # Keep manageable length
        if len(messages) > 20:
            messages = [messages[0]] + messages[-19:]
        redis_client.setex(
            f"chat_session:{session_id}", 3600 * 24, json.dumps(messages)
        )


def clear_conversation(session_id: str):
    """Clear conversation history."""
    if REDIS_AVAILABLE and redis_client:
        redis_client.delete(f"chat_session:{session_id}")


def agentic_chat(
    query: str, session_id: str = "default", user_id: str = "user-1"
) -> dict:
    """
    Main agentic chat function with tool-calling support.
    Returns structured response with text and optional actions.
    """
    # --- Check cache first for cacheable queries ---
    try:
        cached_result = asyncio.get_event_loop().run_until_complete(
            ai_cache.get_cached_response(query)
        )
        if cached_result:
            cached_result["session_id"] = session_id
            return cached_result
    except RuntimeError:
        # No event loop running - try synchronously
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            cached_result = loop.run_until_complete(ai_cache.get_cached_response(query))
            if cached_result:
                cached_result["session_id"] = session_id
                return cached_result
        finally:
            loop.close()
    except Exception:
        pass  # Cache check failed, proceed normally

    # --- Tier-Aware Quota Enforcement ---
    user_tier = "free"
    try:
        from backend.services.ai_rate_limiter import (
            check_ai_quota, consume_ai_quota, get_user_tier, get_upgrade_prompt,
        )
        from backend.database import SessionLocal
        db = SessionLocal()
        try:
            user_tier = get_user_tier(db, user_id)
        finally:
            db.close()
        
        allowed, quota_info = check_ai_quota(user_id, tier=user_tier)
        if not allowed:
            upgrade_msg = get_upgrade_prompt(user_tier) or ""
            return {
                "response": (
                    f"⏳ You've used all your AI queries for today "
                    f"({quota_info.get('quota', '?')} per day on the "
                    f"**{user_tier.title()}** plan).\n\n{upgrade_msg}"
                ),
                "tool_calls": [],
                "session_id": session_id,
                "quota_exceeded": True,
                "quota_info": quota_info,
                "tier": user_tier,
            }
    except Exception as e:
        logger.warning("rate_limit_check_failed", error=str(e))  # Non-blocking

    # Determine model based on dynamic routing
    # We pass has_tools=True because TOOL_DEFINITIONS are always passed to this completion call
    model = get_model(query, has_tools=True)
    if not model:
        return {
            "response": "AI Concierge is offline (No API Key). Check out listings directly!",
            "actions": [],
            "tool_calls": [],
        }

    # Get conversation history
    messages = get_or_create_conversation(session_id)
    
    # --- MEMORY RETRIEVAL (RAG) ---
    try:
        from backend.services.memory_service import memory_service
        # Retrieve relevant memories for this user/query
        memories = memory_service.retrieve_relevant(user_id, query, limit=3)
        
        if memories:
            # Create a context string
            memory_block = "\n".join([f"- {m}" for m in memories])
            
            # Formulate a system message with context
            # We insert this right after the system prompt (index 0)
            context_msg = {
                "role": "system", 
                "content": f"RELEVANT MEMORIES (User Preferences/Facts):\n{memory_block}\nUse these to personalize your response."
            }
            
            # Insert into messages list for this turn only (don't save to Redis to avoid duplication)
            # messages[0] is system prompt, so insert at [1]
            messages.insert(1, context_msg)
            
    except Exception as e:
        logger.warning("memory_retrieval_failed", error=str(e))

    # Add user message
    messages.append({"role": "user", "content": query})

    start_time = time.time()
    try:
        # First LLM call - may include tool calls
        response = completion(
            model=model, messages=messages, tools=TOOL_DEFINITIONS, tool_choice="auto"
        )

        assistant_message = response.choices[0].message
        tool_results = []

        # Check if LLM wants to call tools
        if hasattr(assistant_message, "tool_calls") and assistant_message.tool_calls:
            # Execute each tool call
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)

                # Inject user_id for booking if needed
                if tool_name == "create_booking" and "user_id" not in arguments:
                    arguments["user_id"] = user_id

                # Execute tool
                result = execute_tool(tool_name, arguments)
                tool_results.append(
                    {"tool": tool_name, "arguments": arguments, "result": result}
                )

                # Add tool call and result to messages for context
                # Need to convert assistant_message to dict for history
                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "type": "function",
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": tool_call.function.arguments,
                                },
                            }
                        ],
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result),
                    }
                )

            # Second LLM call - generate response based on tool results
            final_response = completion(model=model, messages=messages)
            response_text = final_response.choices[0].message.content
            usage = final_response.usage
        else:
            # No tool calls, just use the response
            response_text = assistant_message.content
            usage = response.usage

        # Add assistant response to history
        messages.append({"role": "assistant", "content": response_text})

        # Save to Redis
        save_conversation(session_id, messages)

        # Log metrics
        duration_ms = (time.time() - start_time) * 1000
        monitoring_service.log_completion(
            model=model,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            duration_ms=duration_ms,
            session_id=session_id,
            user_id=user_id,
        )
        
        # Persist to database for cost tracking
        try:
            provider = "openai" if "gpt" in model else "google" if "gemini" in model else "unknown"
            log_ai_usage(
                endpoint="concierge",
                model=model.replace("gemini/", ""),  # Normalize model name
                provider=provider,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                latency_ms=int(duration_ms),
                user_id=user_id,
                success=True,
            )
        except Exception as e:
            logger.warning("ai_metering_failed", error=str(e))  # Non-blocking
        
        # Consume quota after successful request
        try:
            consume_ai_quota(user_id)
        except Exception:
            pass  # Non-blocking

        # --- Cache the response if no tool calls ---
        if not tool_results:
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(
                    ai_cache.cache_response(query, response_text, tool_results)
                )
                loop.close()
            except Exception:
                pass  # Cache storage failed, not critical

        # Append subtle upgrade prompt for free/nomad users
        upgrade_prompt = None
        try:
            upgrade_prompt = get_upgrade_prompt(user_tier)
        except Exception:
            pass

        return {
            "response": response_text,
            "tool_calls": tool_results,
            "session_id": session_id,
            "tier": user_tier,
            "upgrade_prompt": upgrade_prompt,
        }

    except Exception as e:
        logger.error("agentic_chat_error", error=str(e), exc_info=True)
        monitoring_service.log_error(model or "unknown", str(e), session_id, user_id)
        return {
            "response": f"I encountered an issue: {str(e)}. Please try again.",
            "tool_calls": [],
            "session_id": session_id,
        }


def simple_vibe_check(query: str) -> str:
    """Legacy simple chat for backwards compatibility."""
    result = agentic_chat(query)
    return result["response"]
