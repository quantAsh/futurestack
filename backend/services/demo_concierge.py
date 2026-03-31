"""
Demo AI Concierge Service.
Provides contextual AI-like responses using real database data.
Used when no LLM API key is available.
"""
import re
from typing import List, Dict, Any, Optional
from collections import defaultdict
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend import models

# In-memory session store for demo concierge conversation context
_session_memory: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
    "last_location": None,
    "last_query": None,
    "last_listings": [],
    "turn_count": 0,
})


def get_db() -> Session:
    """Get database session."""
    return SessionLocal()


def search_listings(query: str, db: Session) -> List[Dict]:
    """Search listings by city, country, or name."""
    query_lower = query.lower()
    
    listings = db.query(models.Listing).all()
    results = []
    
    for listing in listings:
        if (
            query_lower in (listing.city or "").lower()
            or query_lower in (listing.country or "").lower()
            or query_lower in (listing.name or "").lower()
        ):
            results.append({
                "id": listing.id,
                "name": listing.name,
                "city": listing.city,
                "country": listing.country,
                "price_usd": listing.price_usd,
                "property_type": listing.property_type,
            })
    
    return results[:5]  # Limit to 5 results


def get_hubs(db: Session) -> List[Dict]:
    """Get all hubs."""
    hubs = db.query(models.Hub).limit(5).all()
    return [
        {
            "id": h.id,
            "name": h.name,
            "type": h.type,
            "mission": (h.mission[:100] + "...") if h.mission and len(h.mission) > 100 else h.mission,
        }
        for h in hubs
    ]


def get_services(hub_id: Optional[str], db: Session) -> List[Dict]:
    """Get services, optionally filtered by hub."""
    query = db.query(models.Service)
    if hub_id:
        query = query.filter(models.Service.hub_id == hub_id)
    services = query.limit(5).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "price": s.price,
        }
        for s in services
    ]


def get_events(db: Session) -> List[Dict]:
    """Get upcoming events."""
    events = db.query(models.CommunityEvent).limit(5).all()
    return [
        {
            "id": e.id,
            "name": e.name,
            "date": e.date.isoformat() if e.date else None,
            "location": e.location,
        }
        for e in events
    ]


def get_user_bookings(user_id: str, db: Session) -> List[Dict]:
    """Get bookings for a user."""
    bookings = db.query(models.Booking).filter(models.Booking.user_id == user_id).all()
    results = []
    for b in bookings:
        listing = db.query(models.Listing).filter(models.Listing.id == b.listing_id).first()
        results.append({
            "id": b.id,
            "listing_name": listing.name if listing else "Unknown",
            "start_date": b.start_date.strftime("%Y-%m-%d") if b.start_date else None,
            "end_date": b.end_date.strftime("%Y-%m-%d") if b.end_date else None,
            "price": b.total_price_usd,
        })
    return results


def extract_location_from_query(query: str) -> Optional[str]:
    """Extract location mentions from query."""
    # Map of recognized terms → search strings (lowercase)
    locations = {
        "lisbon": "lisbon",
        "bali": "bali",
        "berlin": "berlin",
        "chiang mai": "chiang mai",
        "mexico city": "mexico city",
        "arizona": "arizona",
        "ericeira": "ericeira",
        "santa teresa": "santa teresa",
        # Countries / regions
        "thailand": "thailand",
        "portugal": "portugal",
        "indonesia": "indonesia",
        "mexico": "mexico",
        "germany": "germany",
        "costa rica": "costa rica",
        "southeast asia": "thailand",  # proxy to our SE Asia hub
        "south east asia": "thailand",
        "asia": "thailand",
    }
    query_lower = query.lower()
    # Prefer longer matches first (e.g. "chiang mai" before "mai")
    for term in sorted(locations.keys(), key=len, reverse=True):
        if term in query_lower:
            return locations[term]
    return None


def demo_chat(query: str, session_id: str = "default", user_id: str = "user-1") -> Dict[str, Any]:
    """
    Demo concierge chat that uses real database data.
    Pattern-matches queries to provide contextual responses.
    Maintains session memory for multi-turn conversations.
    """
    db = get_db()
    query_lower = query.lower()
    response_text = ""
    tool_calls = []
    
    # Get session context
    session = _session_memory[session_id]
    session["turn_count"] += 1
    is_followup = session["turn_count"] > 1
    
    # Detect follow-up patterns
    followup_patterns = ["compare", "what about", "how about", "more", "tell me more",
                         "which one", "difference", "vs", "versus", "other",
                         "alternatively", "instead", "similar", "also"]
    is_followup_query = any(p in query_lower for p in followup_patterns) and is_followup
    
    try:
        # First: check if a location is mentioned — if so, always try to show listings there
        location = extract_location_from_query(query)
        
        # Handle follow-up queries using session context
        if is_followup_query and not location and session["last_location"]:
            prev_location = session["last_location"]
            prev_listings = session["last_listings"]
            
            # Comparison request — find a second city to compare
            if any(w in query_lower for w in ["compare", "vs", "versus", "difference"]):
                # Get listings from a different city for comparison
                compare_cities = ["lisbon", "chiang mai", "bali", "berlin", "ubud", "scottsdale"]
                other_city = None
                for c in compare_cities:
                    if c != prev_location.lower():
                        other_listings = search_listings(c, db)
                        if other_listings:
                            other_city = c
                            break
                
                if other_city and other_listings:
                    prev_avg = sum(l['price_usd'] for l in prev_listings if l['price_usd']) / max(len(prev_listings), 1)
                    other_avg = sum(l['price_usd'] for l in other_listings if l['price_usd']) / max(len(other_listings), 1)
                    diff_pct = ((other_avg - prev_avg) / prev_avg * 100) if prev_avg else 0
                    
                    response_text = f"📊 **Side-by-Side: {prev_location.title()} vs {other_city.title()}**\n\n"
                    response_text += f"**{prev_location.title()}** — {len(prev_listings)} stays, avg **${prev_avg:,.0f}/mo**\n"
                    for l in prev_listings[:3]:
                        response_text += f"  • {l['name']} — ${l['price_usd']:,}/mo\n"
                    response_text += f"\n**{other_city.title()}** — {len(other_listings)} stays, avg **${other_avg:,.0f}/mo**\n"
                    for l in other_listings[:3]:
                        response_text += f"  • {l['name']} — ${l['price_usd']:,}/mo\n"
                    response_text += f"\n💰 **Price difference**: {other_city.title()} is **{abs(diff_pct):.0f}%** {'more' if diff_pct > 0 else 'less'} expensive than {prev_location.title()}\n"
                    response_text += f"\n🎯 Want a deeper dive into either city, or shall I check availability?"
            # More/detail request
            elif any(w in query_lower for w in ["more", "tell me more", "detail", "what about"]):
                response_text = f"🔍 **Deep Dive: {prev_location.title()}**\n\n"
                for l in prev_listings:
                    eth_price = round(l['price_usd'] * 0.0003, 2) if l['price_usd'] else 0
                    response_text += f"**{l['name']}**\n"
                    response_text += f"  💰 ${l['price_usd']:,}/mo (~{eth_price} ETH)\n"
                    response_text += f"  🏷️ Type: {l['property_type']}\n"
                    response_text += f"  ✅ Fast WiFi, coworking space, fully furnished\n\n"
                response_text += f"📋 **Tips for {prev_location.title()}**:\n"
                response_text += f"• Best for nomads who want affordable luxury\n"
                response_text += f"• Peak season: Nov-Feb | Low season: Jun-Aug\n"
                response_text += f"• Avg coworking day pass: $10-15\n\n"
                response_text += "🎯 Ready to book, or want to compare with another city?"
            
            if response_text:
                session["last_query"] = query
                return {
                    "response": response_text,
                    "tool_calls": tool_calls,
                    "session_id": session_id,
                    "demo_mode": True,
                }
        
        # Pattern: Listings/accommodations search (or location mentioned)
        if any(word in query_lower for word in [
            "listing", "stay", "accommodation", "place", "where", "find",
            "looking for", "recommend", "suggest", "option", "space",
            "wifi", "remote work", "quiet", "nomad", "digital nomad",
            "month", "budget", "affordable", "cheap", "price", "pricing",
            "compare", "comparison", "best", "top", "properties",
            "yoga", "wellness", "retreat", "meditation", "ayurved",
            "coworking", "co-working", "internet", "speed",
            "safety", "safe", "walkab", "visa",
            "eth", "crypto", "bitcoin", "web3", "blockchain",
            "occupancy", "low season", "improve", "optimize", "host",
        ]) or (location and not any(word in query_lower for word in ["hub", "community", "event", "service", "booking"])):
            if location:
                listings = search_listings(location, db)
                if listings:
                    # Richer response with analysis
                    avg_price = sum(l['price_usd'] for l in listings if l['price_usd']) / max(len(listings), 1)
                    response_text = f"🏠 **{location.title()} — {len(listings)} Stays Found**\n\n"
                    response_text += f"📊 Average monthly rate: **${avg_price:,.0f}/mo**\n\n"
                    for l in listings:
                        eth_price = round(l['price_usd'] * 0.0003, 2) if l['price_usd'] else 0
                        response_text += f"• **{l['name']}** — ${l['price_usd']:,}/mo (~{eth_price} ETH)\n"
                        response_text += f"  Type: {l['property_type']}\n"
                    response_text += f"\n🌐 **Local Intel**: {location.title()} offers excellent infrastructure for digital nomads "
                    response_text += f"with walkable neighborhoods, reliable fiber internet, and vibrant coworking scenes.\n\n"
                    response_text += "💡 I can compare pricing across cities, check availability, or help you book!"
                    tool_calls = [{"tool": "search_listings", "arguments": {"location": location}, "result": listings}]
                else:
                    # Show alternatives when location has no listings
                    all_listings = db.query(models.Listing).limit(5).all()
                    response_text = f"📍 We don't have listings specifically in {location.title()} yet, but here are nearby alternatives:\n\n"
                    for l in all_listings:
                        response_text += f"• **{l.name}** in {l.city}, {l.country} — ${l.price_usd:,}/mo\n"
                    response_text += f"\n💡 Would you like me to compare these options or explore a different region?"
            else:
                # No location specified — broader search based on keywords
                listings = db.query(models.Listing).limit(8).all()
                response_text = "🌍 **NomadNest Global Inventory**\n\n"
                if any(w in query_lower for w in ["compare", "comparison", "vs", "versus"]):
                    response_text = "📊 **Market Comparison**\n\n"
                elif any(w in query_lower for w in ["yoga", "wellness", "retreat", "meditation"]):
                    response_text = "🧘 **Wellness & Retreat Stays**\n\n"
                elif any(w in query_lower for w in ["eth", "crypto", "web3"]):
                    response_text = "💎 **Properties Available for Crypto Booking**\n\n"
                elif any(w in query_lower for w in ["occupancy", "host", "improve", "optimize", "low season"]):
                    response_text = "📈 **Host Intelligence Report**\n\n"
                    response_text += "Based on market analysis across our network:\n\n"
                    response_text += "• **Seasonal pricing**: Reduce rates 15-20% during low season (May-Sep for Europe, Nov-Feb for SE Asia)\n"
                    response_text += "• **Minimum stay flexibility**: Offering 2-week minimums increases bookings by ~30%\n"
                    response_text += "• **Community events**: Hubs hosting weekly events see 25% higher retention\n"
                    response_text += "• **Digital nomad packages**: Bundle WiFi guarantees + coworking access for premium pricing\n\n"
                
                by_city = {}
                for l in listings:
                    city = l.city or "Unknown"
                    if city not in by_city:
                        by_city[city] = []
                    by_city[city].append(l)
                
                for city, city_listings in by_city.items():
                    avg = sum(l.price_usd for l in city_listings if l.price_usd) / max(len(city_listings), 1)
                    response_text += f"**{city}** — {len(city_listings)} stays, avg ${avg:,.0f}/mo\n"
                    for l in city_listings[:2]:
                        response_text += f"  • {l.name} — ${l.price_usd:,}/mo\n"
                    response_text += "\n"
                response_text += "💡 Tell me your preferred city, budget, or vibe and I'll narrow it down!"

        # Pattern: Hubs
        elif any(word in query_lower for word in ["hub", "community", "coliving", "co-living"]):
            hubs = get_hubs(db)
            if location:
                # Filter hubs by location if mentioned
                filtered = [h for h in hubs if location.lower() in (h.get("name", "") + " " + h.get("type", "")).lower()]
                if filtered:
                    hubs = filtered
            response_text = "🏢 Here are our co-living hubs:\n\n"
            for h in hubs:
                response_text += f"• **{h['name']}** ({h['type']})\n"
                if h.get('mission'):
                    response_text += f"  _{h['mission']}_\n"
            tool_calls = [{"tool": "get_hubs", "arguments": {}, "result": hubs}]

        # Pattern: Services
        elif any(word in query_lower for word in ["service", "amenity", "offer", "include"]):
            services = get_services(None, db)
            response_text = "🛎️ Services available at our hubs:\n\n"
            for s in services:
                price_str = "Free" if s["price"] == 0 else f"${s['price']}"
                response_text += f"• **{s['name']}** ({price_str}) - {s['description']}\n"
            tool_calls = [{"tool": "get_services", "arguments": {}, "result": services}]

        # Pattern: Events
        elif any(word in query_lower for word in ["event", "happening", "meetup", "activity", "activities"]):
            events = get_events(db)
            response_text = "📅 Upcoming community events:\n\n"
            for e in events:
                response_text += f"• **{e['name']}** at {e['location']} ({e['date'][:10] if e['date'] else 'TBD'})\n"
            tool_calls = [{"tool": "get_events", "arguments": {}, "result": events}]

        # Pattern: Bookings
        elif any(word in query_lower for word in ["booking", "reservation", "my stay", "booked"]):
            bookings = get_user_bookings(user_id, db)
            if bookings:
                response_text = "📋 Your bookings:\n\n"
                for b in bookings:
                    response_text += f"• **{b['listing_name']}**: {b['start_date']} to {b['end_date']} (${b['price']})\n"
            else:
                response_text = "You don't have any bookings yet. Would you like me to help you find a place to stay? 🏠"
            tool_calls = [{"tool": "get_bookings", "arguments": {"user_id": user_id}, "result": bookings}]

        # Pattern: Book something
        elif any(word in query_lower for word in ["book", "reserve", "want to stay"]):
            # Import booking tools
            from backend.services.concierge_tools import search_bookable_listings
            
            # Extract location if mentioned
            bookable = search_bookable_listings(location=location)
            
            if bookable:
                response_text = "🎫 **Bookable Retreats Available:**\n\n"
                for listing in bookable[:5]:
                    dates_str = ", ".join(listing.get("upcoming_dates", [])[:2]) if listing.get("upcoming_dates") else "Flexible dates"
                    price_str = listing.get("price_range") or "Contact for pricing"
                    response_text += f"• **{listing['name']}**\n"
                    response_text += f"  📅 {dates_str} | 💰 {price_str}\n"
                    response_text += f"  🔗 [Book now]({listing['booking_url']})\n\n"
                response_text += "💬 To book, tell me the retreat name and your preferred dates!"
                tool_calls = [{"tool": "search_bookable_listings", "arguments": {"location": location}, "result": bookable}]
            else:
                response_text = "🎫 I'd love to help you book a stay! Here's how:\n\n"
                response_text += "1. Tell me **where** you'd like to go (e.g., 'Lisbon', 'Bali')\n"
                response_text += "2. Tell me your **dates** (when you want to arrive/leave)\n"
                response_text += "3. I'll find the best options for you!\n\n"
                response_text += "💬 Try saying: *'Find me a place in Lisbon for next month'*"

        # Pattern: Help/capabilities
        elif any(word in query_lower for word in ["help", "what can you", "how", "capabilities"]):
            response_text = "👋 Hi! I'm the NomadNest AI Concierge. Here's what I can help with:\n\n"
            response_text += "🏠 **Find Listings** - Search for stays in specific cities\n"
            response_text += "🏢 **Explore Hubs** - Discover our co-living communities\n"
            response_text += "🛎️ **Services** - See what amenities are available\n"
            response_text += "📅 **Events** - Find community activities and meetups\n"
            response_text += "📋 **Bookings** - Check your reservations\n\n"
            response_text += "💬 Just ask me anything!"

        # Default: If a location is in the query, try search; otherwise show greeting
        else:
            if location:
                # Try a search anyway
                listings = search_listings(location, db)
                if listings:
                    avg_price = sum(l['price_usd'] for l in listings if l['price_usd']) / max(len(listings), 1)
                    response_text = f"🏠 **{location.title()} — {len(listings)} Options**\n\n"
                    response_text += f"📊 Average: **${avg_price:,.0f}/mo**\n\n"
                    for l in listings:
                        eth_price = round(l['price_usd'] * 0.0003, 2) if l['price_usd'] else 0
                        response_text += f"• **{l['name']}** — ${l['price_usd']:,}/mo (~{eth_price} ETH) | {l['property_type']}\n"
                    response_text += "\n💡 Want details, availability, or a comparison with another city?"
                    tool_calls = [{"tool": "search_listings", "arguments": {"location": location}, "result": listings}]
                else:
                    hubs = get_hubs(db)
                    response_text = f"📍 We're expanding to {location.title()} soon! Meanwhile, here are our active hubs:\n\n"
                    for h in hubs:
                        response_text += f"• **{h['name']}** ({h['type']})\n"
                    response_text += "\n💡 Want me to search a different location?"
            else:
                # Default: Search all listings to always provide value
                listings = db.query(models.Listing).limit(5).all()
                response_text = "I've analyzed the request. Here's what I found across our global network:\n\n"
                for l in listings:
                    response_text += f"• **{l.name}** in {l.city}, {l.country} — ${l.price_usd:,}/mo\n"
                response_text += "\n🌍 We operate across Southeast Asia, Europe, and the Americas.\n"
                response_text += "💡 Tell me your destination, budget, or what you're looking for!"

    finally:
        db.close()

    # Save session context for future turns
    if location:
        session["last_location"] = location
    if tool_calls:
        for tc in tool_calls:
            if tc.get("result"):
                session["last_listings"] = tc["result"]
    session["last_query"] = query

    return {
        "response": response_text,
        "tool_calls": tool_calls,
        "session_id": session_id,
        "demo_mode": True,
    }
