"""
Centralized Nomad Reference Data — Single Source of Truth.

All curated data for the NomadNest AI agent framework lives here.
Individual agents import from this module instead of embedding their own copies.

In production: move to database tables with admin UI for updates.
Until then, this file is the canonical source for all destination,
cost, safety, and community data.
"""


# --- From scout_agent.py ---

DESTINATION_DATA = {
    "bali": {
        "city": "Bali",
        "country": "Indonesia",
        "country_code": "ID",
        "neighborhoods": {
            "canggu": {
                "vibe": "Surf + startup culture",
                "wifi_avg_mbps": 35,
                "coworking_spaces": ["Dojo Bali", "Outpost Canggu", "BWork Bali"],
                "cafe_scene": "Excellent — dozens of laptop-friendly cafes",
                "walkability": 55,
                "safety": 75,
                "noise_level": "Moderate",
                "best_for": ["surfers", "entrepreneurs", "content creators"],
            },
            "ubud": {
                "vibe": "Wellness + creative retreat",
                "wifi_avg_mbps": 25,
                "coworking_spaces": ["Outpost Ubud", "Hubud", "Livit Hub"],
                "cafe_scene": "Good — quieter, more yoga/smoothie oriented",
                "walkability": 40,
                "safety": 85,
                "noise_level": "Low",
                "best_for": ["wellness seekers", "writers", "yoga practitioners"],
            },
            "seminyak": {
                "vibe": "Upscale beach + nightlife",
                "wifi_avg_mbps": 40,
                "coworking_spaces": ["Kumpul Coworking", "GoWork"],
                "cafe_scene": "Premium cafes, higher prices",
                "walkability": 50,
                "safety": 70,
                "noise_level": "High",
                "best_for": ["luxury travelers", "nightlife", "foodies"],
            },
        },
        "cost_of_living": {
            "rent_1br_center": 500,
            "rent_1br_outside": 300,
            "meal_inexpensive": 3,
            "meal_midrange": 12,
            "coffee": 2.5,
            "coworking_monthly": 120,
            "gym_monthly": 35,
            "transport_monthly": 60,
            "total_budget_estimate": 1200,
            "total_moderate_estimate": 1800,
            "total_comfort_estimate": 2800,
            "currency": "USD",
        },
        "internet": {
            "avg_speed_mbps": 30,
            "reliability": "Good in tourist areas, variable elsewhere",
            "sim_card": "Telkomsel or XL — $10/month for 30GB",
            "tip": "Always test wifi before booking. Fiber is common in Canggu/Seminyak.",
        },
        "visa": {
            "type": "Visa on Arrival",
            "duration_days": 30,
            "extendable": True,
            "extension_days": 30,
            "cost": 35,
            "nomad_visa": None,
            "tip": "B211A visa (60 days, remote work legal) available via sponsor.",
        },
        "weather_by_month": {
            "jan": {"temp_c": 27, "rain": "High", "best_for": "Off-season deals"},
            "feb": {"temp_c": 27, "rain": "High", "best_for": "Off-season deals"},
            "mar": {"temp_c": 28, "rain": "Moderate", "best_for": "Shoulder season"},
            "apr": {"temp_c": 28, "rain": "Low", "best_for": "Dry season begins"},
            "may": {"temp_c": 28, "rain": "Low", "best_for": "Peak dry season"},
            "jun": {"temp_c": 27, "rain": "Low", "best_for": "Peak dry season"},
            "jul": {"temp_c": 27, "rain": "Low", "best_for": "Peak season, busiest"},
            "aug": {"temp_c": 27, "rain": "Low", "best_for": "Peak season"},
            "sep": {"temp_c": 28, "rain": "Low", "best_for": "Shoulder season"},
            "oct": {"temp_c": 28, "rain": "Moderate", "best_for": "Shoulder season"},
            "nov": {"temp_c": 28, "rain": "High", "best_for": "Off-season begins"},
            "dec": {"temp_c": 27, "rain": "High", "best_for": "Off-season"},
        },
        "nomad_score": 88,
        "highlights": [
            "World-class surf in Canggu & Uluwatu",
            "Incredibly affordable — $1,200/mo comfortable",
            "Strong digital nomad community",
            "Excellent cafe & coworking scene",
            "Yoga, meditation, wellness culture in Ubud",
        ],
        "watch_outs": [
            "Traffic can be brutal — rent a scooter",
            "Visa runs every 30 days unless you get B211A",
            "Power outages in rural areas",
            "Rainy season (Nov–Mar) can disrupt plans",
        ],
    },
    "chiang mai": {
        "city": "Chiang Mai",
        "country": "Thailand",
        "country_code": "TH",
        "neighborhoods": {
            "nimman": {
                "vibe": "Trendy + digital nomad hub",
                "wifi_avg_mbps": 50,
                "coworking_spaces": ["Punspace", "CAMP", "Hub53"],
                "cafe_scene": "Best in the city — hipster & laptop-friendly",
                "walkability": 75,
                "safety": 90,
                "noise_level": "Moderate",
                "best_for": ["developers", "designers", "first-time nomads"],
            },
            "old_city": {
                "vibe": "Cultural + budget-friendly",
                "wifi_avg_mbps": 35,
                "coworking_spaces": ["Yellow Coworking", "Starwork"],
                "cafe_scene": "Traditional Thai + some modern cafes",
                "walkability": 80,
                "safety": 85,
                "noise_level": "Low",
                "best_for": ["culture lovers", "budget travelers", "photographers"],
            },
            "santitham": {
                "vibe": "Local + quiet residential",
                "wifi_avg_mbps": 40,
                "coworking_spaces": ["Alt_ChiangMai", "Mana Coworking"],
                "cafe_scene": "Growing, less crowded than Nimman",
                "walkability": 65,
                "safety": 90,
                "noise_level": "Low",
                "best_for": ["long-term stays", "families", "introverts"],
            },
        },
        "cost_of_living": {
            "rent_1br_center": 350,
            "rent_1br_outside": 200,
            "meal_inexpensive": 2,
            "meal_midrange": 8,
            "coffee": 2,
            "coworking_monthly": 80,
            "gym_monthly": 30,
            "transport_monthly": 40,
            "total_budget_estimate": 800,
            "total_moderate_estimate": 1200,
            "total_comfort_estimate": 2000,
            "currency": "USD",
        },
        "internet": {
            "avg_speed_mbps": 45,
            "reliability": "Excellent — Thailand has great fiber infrastructure",
            "sim_card": "AIS or DTAC — $12/month for unlimited data",
            "tip": "Many condos come with 100Mbps fiber included in rent.",
        },
        "visa": {
            "type": "Visa Exemption",
            "duration_days": 30,
            "extendable": True,
            "extension_days": 30,
            "cost": 0,
            "nomad_visa": {"name": "LTR Visa", "duration": "10 years", "min_income": 80000},
            "tip": "60-day tourist visa available at Thai embassy before travel.",
        },
        "weather_by_month": {
            "jan": {"temp_c": 22, "rain": "None", "best_for": "Cool season — perfect"},
            "feb": {"temp_c": 24, "rain": "None", "best_for": "Cool season"},
            "mar": {"temp_c": 28, "rain": "Low", "best_for": "Getting hot + burning season starts"},
            "apr": {"temp_c": 32, "rain": "Low", "best_for": "Songkran! Hot but fun"},
            "may": {"temp_c": 30, "rain": "Moderate", "best_for": "Rainy season starts"},
            "jun": {"temp_c": 28, "rain": "High", "best_for": "Lush green, fewer tourists"},
            "jul": {"temp_c": 28, "rain": "High", "best_for": "Off-season deals"},
            "aug": {"temp_c": 28, "rain": "High", "best_for": "Off-season deals"},
            "sep": {"temp_c": 27, "rain": "High", "best_for": "Rainiest month"},
            "oct": {"temp_c": 27, "rain": "Moderate", "best_for": "Rain easing"},
            "nov": {"temp_c": 25, "rain": "Low", "best_for": "Cool season begins"},
            "dec": {"temp_c": 22, "rain": "None", "best_for": "Best month — cool & dry"},
        },
        "nomad_score": 92,
        "highlights": [
            "Cheapest digital nomad hub in Asia — $800/mo possible",
            "Fast internet everywhere (50+ Mbps fiber)",
            "Amazing food — $2 street food, $8 restaurant",
            "Huge nomad community — meetups every week",
            "Temples, mountains, nature everywhere",
        ],
        "watch_outs": [
            "Burning season (Mar-Apr) — air quality drops severely",
            "Hot season (Mar-May) can be brutal — 35°C+",
            "Visa runs add up if staying 3+ months",
            "Less beach access — 8hrs to coast",
        ],
    },
    "lisbon": {
        "city": "Lisbon",
        "country": "Portugal",
        "country_code": "PT",
        "neighborhoods": {
            "alfama": {
                "vibe": "Historic + bohemian",
                "wifi_avg_mbps": 60,
                "coworking_spaces": ["Second Home", "Outsite Lisbon"],
                "cafe_scene": "Traditional pastelarias + modern third-wave",
                "walkability": 70,
                "safety": 80,
                "noise_level": "Moderate",
                "best_for": ["history lovers", "photographers", "writers"],
            },
            "santos": {
                "vibe": "Creative + startup hub",
                "wifi_avg_mbps": 80,
                "coworking_spaces": ["Village Underground", "Heden"],
                "cafe_scene": "Industrial-chic cafes, great for work",
                "walkability": 75,
                "safety": 85,
                "noise_level": "Moderate",
                "best_for": ["startup founders", "creatives", "entrepreneurs"],
            },
            "principe_real": {
                "vibe": "Upscale + leafy",
                "wifi_avg_mbps": 70,
                "coworking_spaces": ["Resvés", "Impact Hub"],
                "cafe_scene": "Brunch culture, upscale cafes",
                "walkability": 85,
                "safety": 90,
                "noise_level": "Low",
                "best_for": ["luxury nomads", "families", "long-term stays"],
            },
        },
        "cost_of_living": {
            "rent_1br_center": 1200,
            "rent_1br_outside": 800,
            "meal_inexpensive": 8,
            "meal_midrange": 20,
            "coffee": 1.5,
            "coworking_monthly": 200,
            "gym_monthly": 40,
            "transport_monthly": 40,
            "total_budget_estimate": 1800,
            "total_moderate_estimate": 2500,
            "total_comfort_estimate": 3500,
            "currency": "USD",
        },
        "internet": {
            "avg_speed_mbps": 70,
            "reliability": "Excellent — Portugal has top-tier EU infrastructure",
            "sim_card": "NOS or MEO — €15/month for 15GB",
            "tip": "Most apartments come with fiber. Cafes usually have strong wifi.",
        },
        "visa": {
            "type": "Schengen (visa-free for US/CAN/UK)",
            "duration_days": 90,
            "extendable": False,
            "extension_days": 0,
            "cost": 0,
            "nomad_visa": {"name": "D7 Visa", "duration": "1 year", "min_income": 760},
            "tip": "D7 visa (passive income) or D8 (digital nomad) available for longer stays.",
        },
        "weather_by_month": {
            "jan": {"temp_c": 12, "rain": "Moderate", "best_for": "Mild winter"},
            "feb": {"temp_c": 13, "rain": "Moderate", "best_for": "Quiet + affordable"},
            "mar": {"temp_c": 16, "rain": "Low", "best_for": "Spring starts"},
            "apr": {"temp_c": 18, "rain": "Low", "best_for": "Beautiful spring"},
            "may": {"temp_c": 21, "rain": "Low", "best_for": "Perfect weather"},
            "jun": {"temp_c": 25, "rain": "None", "best_for": "Summer begins"},
            "jul": {"temp_c": 28, "rain": "None", "best_for": "Peak summer"},
            "aug": {"temp_c": 28, "rain": "None", "best_for": "Hot + busy"},
            "sep": {"temp_c": 25, "rain": "None", "best_for": "Best month — warm, fewer tourists"},
            "oct": {"temp_c": 20, "rain": "Moderate", "best_for": "Fall shoulder"},
            "nov": {"temp_c": 15, "rain": "High", "best_for": "Off-season starts"},
            "dec": {"temp_c": 12, "rain": "High", "best_for": "Off-season deals"},
        },
        "nomad_score": 90,
        "highlights": [
            "European quality of life at relatively affordable prices",
            "Strong startup ecosystem — Web Summit host city",
            "Excellent weather 8 months of the year",
            "D7/D8 visa makes long-term stays legal",
            "English widely spoken, especially in tech circles",
        ],
        "watch_outs": [
            "Rents have risen sharply since 2020",
            "Schengen 90-day limit for non-EU without visa",
            "Hills everywhere — bring good shoes",
            "August can be oppressively hot (35°C+)",
        ],
    },
    "mexico city": {
        "city": "Mexico City",
        "country": "Mexico",
        "country_code": "MX",
        "neighborhoods": {
            "roma_norte": {
                "vibe": "Artsy + foodie paradise",
                "wifi_avg_mbps": 50,
                "coworking_spaces": ["WeWork Roma", "Homework", "Centraal"],
                "cafe_scene": "World-class — best in Latin America",
                "walkability": 90,
                "safety": 70,
                "noise_level": "Moderate",
                "best_for": ["foodies", "designers", "writers"],
            },
            "condesa": {
                "vibe": "Tree-lined + trendy",
                "wifi_avg_mbps": 55,
                "coworking_spaces": ["Impact Hub CDMX", "Público"],
                "cafe_scene": "Brunch culture, parks, dog-friendly",
                "walkability": 92,
                "safety": 72,
                "noise_level": "Low",
                "best_for": ["long-term nomads", "pet owners", "wellness"],
            },
        },
        "cost_of_living": {
            "rent_1br_center": 700,
            "rent_1br_outside": 400,
            "meal_inexpensive": 4,
            "meal_midrange": 15,
            "coffee": 3,
            "coworking_monthly": 150,
            "gym_monthly": 35,
            "transport_monthly": 30,
            "total_budget_estimate": 1200,
            "total_moderate_estimate": 1800,
            "total_comfort_estimate": 2800,
            "currency": "USD",
        },
        "internet": {
            "avg_speed_mbps": 50,
            "reliability": "Good in Roma/Condesa, variable elsewhere",
            "sim_card": "Telcel — $15/month for 6GB",
            "tip": "Fiber available in most modern apartments in Roma/Condesa.",
        },
        "visa": {
            "type": "Tourist Permit (FMM)",
            "duration_days": 180,
            "extendable": False,
            "extension_days": 0,
            "cost": 0,
            "nomad_visa": None,
            "tip": "180 days visa-free for US/CAN/EU. No digital nomad visa yet.",
        },
        "weather_by_month": {
            "jan": {"temp_c": 14, "rain": "None", "best_for": "Dry, cool"},
            "feb": {"temp_c": 16, "rain": "None", "best_for": "Dry, warming up"},
            "mar": {"temp_c": 19, "rain": "None", "best_for": "Perfect weather"},
            "apr": {"temp_c": 21, "rain": "Low", "best_for": "Best month"},
            "may": {"temp_c": 21, "rain": "Moderate", "best_for": "Rainy season starts"},
            "jun": {"temp_c": 19, "rain": "High", "best_for": "Afternoon downpours"},
            "jul": {"temp_c": 18, "rain": "High", "best_for": "Green + lush"},
            "aug": {"temp_c": 18, "rain": "High", "best_for": "Rainy but pleasant"},
            "sep": {"temp_c": 18, "rain": "High", "best_for": "Independence Day!"},
            "oct": {"temp_c": 17, "rain": "Moderate", "best_for": "Rain easing, Day of the Dead"},
            "nov": {"temp_c": 15, "rain": "Low", "best_for": "Dry season begins"},
            "dec": {"temp_c": 14, "rain": "None", "best_for": "Cool + festive"},
        },
        "nomad_score": 85,
        "highlights": [
            "180-day visa-free — longest in the Americas",
            "World-class food scene at budget prices",
            "Roma/Condesa is one of the most walkable nomad neighborhoods globally",
            "Close to US time zones — great for US remote workers",
            "Rich culture — museums, art, music, mezcal",
        ],
        "watch_outs": [
            "Altitude (2,240m) — takes a few days to adjust",
            "Air quality can be poor on some days",
            "Stay in known safe neighborhoods (Roma, Condesa, Polanco, Coyoacán)",
            "Earthquakes are a real risk — know your building's exit",
        ],
    },
}


# --- From finance_agent.py ---

COST_DATA = {
    "bali": {
        "city": "Bali", "country": "Indonesia", "currency": "IDR", "currency_name": "Indonesian Rupiah",
        "daily": {"budget": 40, "moderate": 60, "luxury": 95},
        "monthly": {"budget": 1200, "moderate": 1800, "luxury": 2800},
        "breakdown_moderate": {
            "rent": 500, "food": 360, "coworking": 120, "transport": 60,
            "coffee": 75, "entertainment": 150, "gym": 35, "phone_data": 10,
            "health_insurance": 100, "visa_costs": 18, "misc": 371,
        },
    },
    "chiang mai": {
        "city": "Chiang Mai", "country": "Thailand", "currency": "THB", "currency_name": "Thai Baht",
        "daily": {"budget": 27, "moderate": 40, "luxury": 67},
        "monthly": {"budget": 800, "moderate": 1200, "luxury": 2000},
        "breakdown_moderate": {
            "rent": 350, "food": 240, "coworking": 80, "transport": 40,
            "coffee": 60, "entertainment": 100, "gym": 30, "phone_data": 12,
            "health_insurance": 100, "visa_costs": 60, "misc": 128,
        },
    },
    "lisbon": {
        "city": "Lisbon", "country": "Portugal", "currency": "EUR", "currency_name": "Euro",
        "daily": {"budget": 60, "moderate": 83, "luxury": 117},
        "monthly": {"budget": 1800, "moderate": 2500, "luxury": 3500},
        "breakdown_moderate": {
            "rent": 1200, "food": 480, "coworking": 200, "transport": 40,
            "coffee": 45, "entertainment": 200, "gym": 40, "phone_data": 15,
            "health_insurance": 100, "visa_costs": 0, "misc": 180,
        },
    },
    "mexico city": {
        "city": "Mexico City", "country": "Mexico", "currency": "MXN", "currency_name": "Mexican Peso",
        "daily": {"budget": 40, "moderate": 60, "luxury": 93},
        "monthly": {"budget": 1200, "moderate": 1800, "luxury": 2800},
        "breakdown_moderate": {
            "rent": 700, "food": 360, "coworking": 150, "transport": 30,
            "coffee": 90, "entertainment": 150, "gym": 35, "phone_data": 15,
            "health_insurance": 100, "visa_costs": 0, "misc": 170,
        },
    },
    "bangkok": {
        "city": "Bangkok", "country": "Thailand", "currency": "THB", "currency_name": "Thai Baht",
        "daily": {"budget": 30, "moderate": 50, "luxury": 90},
        "monthly": {"budget": 900, "moderate": 1500, "luxury": 2700},
        "breakdown_moderate": {
            "rent": 500, "food": 300, "coworking": 100, "transport": 60,
            "coffee": 60, "entertainment": 150, "gym": 30, "phone_data": 12,
            "health_insurance": 100, "visa_costs": 60, "misc": 128,
        },
    },
    "barcelona": {
        "city": "Barcelona", "country": "Spain", "currency": "EUR", "currency_name": "Euro",
        "daily": {"budget": 65, "moderate": 100, "luxury": 160},
        "monthly": {"budget": 2000, "moderate": 3000, "luxury": 4800},
        "breakdown_moderate": {
            "rent": 1400, "food": 540, "coworking": 250, "transport": 50,
            "coffee": 50, "entertainment": 250, "gym": 45, "phone_data": 15,
            "health_insurance": 100, "visa_costs": 0, "misc": 300,
        },
    },
}

CURRENCY_TIPS = {
    "IDR": {
        "tips": [
            "Withdraw from ATMs, not exchange counters — better rates",
            "Use Wise or Revolut card — saves 2-3% vs bank cards",
            "Cash is still king for street food and small shops",
            "Max ATM withdrawal is usually 2.5M IDR (~$160). BCA ATMs allow 10M",
        ],
        "payment_apps": ["GoPay", "OVO", "Dana"],
        "tipping": "Not expected but appreciated (10-15k IDR)",
        "avoid": "Don't exchange money at the airport — rates are 10% worse",
    },
    "THB": {
        "tips": [
            "Use Wise card for best exchange rate — saves 3%+ vs Thai banks",
            "7-Eleven ATMs (yellow) have no foreign card fee, most others charge 220 THB",
            "QR payment is universal — link your Thai bank account",
            "Bangkok Bank is easiest for opening a foreigner account (bring passport + visa)",
        ],
        "payment_apps": ["PromptPay", "TrueMoney", "Rabbit LINE Pay"],
        "tipping": "Not expected. Round up at nice restaurants",
        "avoid": "Never use dynamic currency conversion at ATMs — always choose THB",
    },
    "EUR": {
        "tips": [
            "Contactless cards accepted almost everywhere",
            "Wise/Revolut for best USD→EUR rate — saves 1-2%",
            "MB Way (Portuguese payment app) works at most merchants",
            "Avoid tourist-area exchange shops — use ATMs from major banks",
        ],
        "payment_apps": ["MB Way", "Apple Pay", "Google Pay"],
        "tipping": "Round up 5-10% at restaurants",
        "avoid": "Skip 'DCC' (dynamic currency conversion) at payment terminals",
    },
    "MXN": {
        "tips": [
            "Use Wise or Revolut — Mexican bank ATMs charge 30-50 MXN per withdrawal",
            "Cash for taco stands and markets; card for restaurants",
            "BBVA Mexico ATMs have lowest foreign fees",
            "Uber/Didi work great and are very cheap",
        ],
        "payment_apps": ["Mercado Pago", "CoDi", "Apple Pay (limited)"],
        "tipping": "10-15% at restaurants, round up for deliveries",
        "avoid": "Don't carry large bills (500/1000 MXN) — small vendors can't break them",
    },
}

TAX_THRESHOLDS = {
    "Indonesia": {"days": 183, "rule": "183 days in any 12-month period", "risk": "Income tax on worldwide income"},
    "Thailand": {"days": 180, "rule": "180 days in a tax year (Jan-Dec)", "risk": "Income tax on Thai-sourced income (2024: also on remitted foreign income)"},
    "Portugal": {"days": 183, "rule": "183 days in any 12-month period", "risk": "NHR regime available — 20% flat rate for 10 years on qualifying income"},
    "Mexico": {"days": 183, "rule": "183 days in any 12-month period", "risk": "Tax resident status — income tax on worldwide income"},
    "Spain": {"days": 183, "rule": "183 days in a calendar year", "risk": "Income tax on worldwide income. Beckham Law may apply for remote workers."},
    "Germany": {"days": 183, "rule": "183 days + 'center of vital interests'", "risk": "Progressive income tax up to 45%"},
}


# --- From host_copilot.py ---

MARKET_RATES = {
    "chiang mai": {"low": 15, "mid": 40, "high": 80, "peak_months": [11, 12, 1, 2], "low_months": [5, 6, 7, 8, 9]},
    "bali": {"low": 20, "mid": 50, "high": 120, "peak_months": [6, 7, 8], "low_months": [1, 2, 3, 11]},
    "lisbon": {"low": 40, "mid": 80, "high": 150, "peak_months": [6, 7, 8, 9], "low_months": [11, 12, 1, 2]},
    "mexico city": {"low": 25, "mid": 55, "high": 100, "peak_months": [10, 11, 12, 3, 4], "low_months": [5, 6, 7, 8, 9]},
    "bangkok": {"low": 15, "mid": 35, "high": 75, "peak_months": [11, 12, 1, 2, 3], "low_months": [5, 6, 7, 8, 9]},
    "barcelona": {"low": 45, "mid": 90, "high": 180, "peak_months": [5, 6, 7, 8, 9], "low_months": [11, 12, 1, 2]},
    "berlin": {"low": 35, "mid": 70, "high": 130, "peak_months": [5, 6, 7, 8], "low_months": [11, 12, 1, 2]},
    "medellín": {"low": 18, "mid": 40, "high": 85, "peak_months": [12, 1, 6, 7], "low_months": [4, 5, 10, 11]},
}

AUTO_REPLY_TEMPLATES = {
    "wifi": {
        "question_patterns": ["wifi", "internet", "connection", "speed", "work calls", "video calls", "bandwidth"],
        "reply": "Great question! We have a dedicated fiber connection with backup 4G failover. Average speeds are {wifi_speed}Mbps download. Video calls run smoothly even during peak hours. We also provide a mobile hotspot as backup.",
        "default_wifi": "50+",
    },
    "checkin": {
        "question_patterns": ["check-in", "checkin", "arrive", "arrival", "check in", "early check", "late check"],
        "reply": "Check-in is from {checkin_time}. I'll send you the door code and detailed directions 24 hours before arrival. Early check-in may be available — just let me know your arrival time and I'll do my best to accommodate!",
        "default_checkin": "3:00 PM",
    },
    "checkout": {
        "question_patterns": ["check-out", "checkout", "departure", "leave", "late checkout"],
        "reply": "Check-out is at {checkout_time}. Late checkout until 2:00 PM is available for an additional $15 if the calendar allows. Just ask the day before and I'll confirm!",
        "default_checkout": "11:00 AM",
    },
    "extension": {
        "question_patterns": ["extend", "stay longer", "extension", "another week", "additional"],
        "reply": "We'd love to have you stay longer! We hold a rolling 7-day extension slot for current guests. Just let me know 72 hours before your current checkout and I'll lock in the dates. Extended stays of 30+ days get a {discount}% discount.",
        "default_discount": "10",
    },
    "coworking": {
        "question_patterns": ["coworking", "workspace", "desk", "office", "work from"],
        "reply": "The property has a dedicated workspace with a {desk_type}. For a change of scenery, the nearest coworking space is {cowork_name}, just {cowork_distance} away. We can arrange a day pass for you!",
        "default_desk_type": "standing desk and ergonomic chair",
        "default_cowork_name": "a great partner coworking space",
        "default_cowork_distance": "a 5-minute walk",
    },
    "laundry": {
        "question_patterns": ["laundry", "washing machine", "clothes", "washer"],
        "reply": "There's a washing machine in the unit. Detergent is provided. For dry cleaning or pressing, there's a laundry service within walking distance that offers pickup and delivery.",
    },
    "transport": {
        "question_patterns": ["transport", "airport", "taxi", "grab", "uber", "scooter", "bike", "getting around"],
        "reply": "We can arrange airport pickup for ${airport_cost}. For daily transport, {transport_tip}. I'll send you a local transport guide with the check-in instructions!",
        "default_airport_cost": "15-25",
        "default_transport_tip": "ride-hailing apps work great here, and scooter rentals start at $5/day",
    },
    "kitchen": {
        "question_patterns": ["kitchen", "cooking", "grocery", "food", "supermarket", "market"],
        "reply": "The kitchen is fully equipped with {kitchen_features}. The nearest supermarket is {market_distance} away. There's also a local market on {market_day} with fresh produce and street food!",
        "default_kitchen_features": "stove, fridge, microwave, coffee maker, and basic cookware",
        "default_market_distance": "a 3-minute walk",
        "default_market_day": "weekends",
    },
}


# --- From relocation_agent.py ---

FLIGHT_ROUTES = {
    ("bali", "chiang mai"): {"cost_range": (120, 250), "duration_hrs": 5, "airlines": ["AirAsia", "Thai Lion", "VietJet"], "layover": "Bangkok/KL", "tip": "Book 6-8 weeks ahead on AirAsia for $120-150"},
    ("bali", "lisbon"): {"cost_range": (400, 800), "duration_hrs": 18, "airlines": ["Qatar Airways", "Turkish Airlines", "Emirates"], "layover": "Doha/Istanbul/Dubai", "tip": "Turkish Airlines often has the best deals. Check for errors fares on Secret Flying."},
    ("bali", "mexico city"): {"cost_range": (500, 900), "duration_hrs": 24, "airlines": ["Cathay Pacific", "Japan Airlines", "ANA"], "layover": "Tokyo/Hong Kong + LAX", "tip": "This is a long haul. Consider breaking it up with a stop in Tokyo/Seoul."},
    ("bali", "bangkok"): {"cost_range": (80, 180), "duration_hrs": 4, "airlines": ["AirAsia", "Thai Lion", "Batik Air"], "layover": "Direct available", "tip": "Direct flights under $100 on AirAsia if booked early."},
    ("chiang mai", "lisbon"): {"cost_range": (350, 700), "duration_hrs": 14, "airlines": ["Turkish Airlines", "Qatar Airways", "Aeroflot"], "layover": "Istanbul/Doha/Moscow", "tip": "Turkish via Istanbul is usually cheapest and most comfortable."},
    ("chiang mai", "mexico city"): {"cost_range": (450, 850), "duration_hrs": 22, "airlines": ["ANA", "EVA Air", "Korean Air"], "layover": "Tokyo/Seoul + LAX", "tip": "Book with NomadFare or use Google Flights alerts."},
    ("chiang mai", "bangkok"): {"cost_range": (30, 80), "duration_hrs": 1.5, "airlines": ["AirAsia", "Nok Air", "Thai Smile"], "layover": "Direct", "tip": "Flights from $30 or take the sleeper train ($20, 13hrs) for the experience."},
    ("lisbon", "mexico city"): {"cost_range": (350, 650), "duration_hrs": 11, "airlines": ["TAP", "Iberia", "Aeromexico"], "layover": "Direct (TAP) or Madrid", "tip": "TAP has direct flights — grab the $350 fare when it appears."},
    ("lisbon", "barcelona"): {"cost_range": (30, 100), "duration_hrs": 2, "airlines": ["Ryanair", "Vueling", "TAP"], "layover": "Direct", "tip": "Ryanair has €20 fares regularly. Book carry-on only."},
    ("mexico city", "bangkok"): {"cost_range": (500, 900), "duration_hrs": 22, "airlines": ["Korean Air", "ANA", "Cathay Pacific"], "layover": "Seoul/Tokyo", "tip": "Korean Air via Seoul often has the best value and service."},
}

SETUP_CHECKLISTS = {
    "bali": {
        "before_arrival": [
            "Apply for B211A visa via agent ($300) if staying > 30 days",
            "Book first 3 nights near airport (Kuta/Seminyak) for arrival buffer",
            "Download Grab and Gojek apps for transport",
            "Get international driving permit for scooter rental",
        ],
        "first_48_hours": [
            "Buy local SIM (Telkomsel) at airport — $10 for 30GB",
            "Withdraw IDR from BCA ATM (highest limit: 10M IDR)",
            "Rent a scooter ($50-80/month) from your accommodation",
            "Join 'Digital Nomads Bali' Facebook group for event updates",
        ],
        "first_week": [
            "Scout coworking spaces — try day passes at Dojo, Outpost, BWork",
            "Set up GoPay/OVO for cashless payments",
            "Register at local banjar (village office) if staying in residential area",
            "Find your regular cafe for work — test wifi speeds",
        ],
        "ongoing": [
            "Visa extension at immigration office (if on VOA) — do it at day 25",
            "Join weekly nomad meetups (check Dojo Bali events)",
            "Set up a backup internet plan (mobile hotspot)",
        ],
    },
    "chiang mai": {
        "before_arrival": [
            "Get 60-day tourist visa at Thai embassy (or fly in for 30-day exempt)",
            "Book first stay in Nimman area — best for orientation",
            "Download Grab app (works for taxi and food delivery)",
            "Prepare passport photos (4x6cm) for any visa extensions",
        ],
        "first_48_hours": [
            "Buy AIS SIM at airport — $12 for unlimited data",
            "Open Bangkok Bank account (bring passport + visa + hotel booking)",
            "Join 'Chiang Mai Digital Nomads' Facebook group",
            "Visit Punspace or CAMP for coworking — both in Nimman",
        ],
        "first_week": [
            "Rent a scooter ($80/month) or buy a bicycle (3000 THB)",
            "Register for PromptPay (Thai mobile payment — needs bank account)",
            "Find your Sunday Night Market route (Walking Street, Old City)",
            "Try Muay Thai — Team Quest or Santai offer beginner classes",
        ],
        "ongoing": [
            "30-day visa extension at CMI immigration (1900 THB)",
            "Tuesday Nomad Coffee meetup at Ristr8to Lab",
            "Air quality check during burning season (Mar-Apr) — use AQI app",
        ],
    },
    "lisbon": {
        "before_arrival": [
            "Check Schengen 90/180 day count if non-EU",
            "Book first stay in Santos/Alfama — central and well-connected",
            "Get NIF (tax number) via ePortugal if staying long-term",
            "Consider D7 or D8 visa application if planning > 90 days",
        ],
        "first_48_hours": [
            "Buy NOS or MEO SIM at airport — €15/month for 15GB",
            "Get Viva Viagem transit card — load monthly pass (€40)",
            "Download MB Way for mobile payments (needs Portuguese bank)",
            "Walk Alfama → Santos → Príncipe Real to orient yourself",
        ],
        "first_week": [
            "Open Moey or ActivoBank account (digital, no fees, English)",
            "Join Second Home or Village Underground for coworking",
            "Get Time Out Market Lisbon loyalty card (worth it for regular lunches)",
            "Explore Mercado da Ribeira for affordable fresh groceries",
        ],
        "ongoing": [
            "Track Schengen days carefully — use the NomadNest visa tool",
            "Web Summit community events (year-round, not just November)",
            "Weekend trips: Sintra (45min), Porto (3hr train), Algarve (3hr)",
        ],
    },
    "mexico city": {
        "before_arrival": [
            "No visa needed for US/CAN/EU — 180-day FMM on arrival",
            "Book first stay in Roma Norte or Condesa — safest and best-connected",
            "Download Uber and Didi apps (both work great)",
            "Get international health insurance (SafetyWing or World Nomads)",
        ],
        "first_48_hours": [
            "Buy Telcel SIM at OXXO convenience store — $15/month for 6GB",
            "Get CDMX Metro card (MI) — $5 MXN per ride, incredibly cheap",
            "Walk Roma Norte → Condesa → Chapultepec to orient yourself",
            "Adjust to altitude (2,240m) — take it easy, drink lots of water",
        ],
        "first_week": [
            "Open Mercado Pago account for cashless payments",
            "Find your taco spot — Roma has incredible street tacos ($2-3 each)",
            "Visit WeWork Roma or Homework for coworking day passes",
            "Join 'Digital Nomads Mexico City' group for meetup schedules",
        ],
        "ongoing": [
            "Earthquake preparedness — know your building's exit route",
            "Weekend trips: Oaxaca (1hr flight), Teotihuacán (1hr bus)",
            "Thursday mezcal nights at various bars in Roma",
        ],
    },
}


# --- From safety_agent.py ---

SAFETY_DATA = {
    "bali": {
        "city": "Bali", "country": "Indonesia",
        "overall_rating": 8, "out_of": 10,
        "safety_level": "Safe",
        "summary": "Generally very safe for tourists and nomads. Petty theft exists in touristy areas. Traffic is the biggest risk — be careful on scooters.",
        "categories": {
            "violent_crime": {"rating": 9, "note": "Very rare for tourists"},
            "petty_theft": {"rating": 7, "note": "Bag snatching on scooters in Kuta/Seminyak. Use crossbody bags."},
            "traffic": {"rating": 5, "note": "Scooter accidents are the #1 risk. Wear a helmet, don't ride drunk."},
            "natural_disasters": {"rating": 7, "note": "Earthquake zone. Mt. Agung eruption risk. Check BMKG alerts."},
            "cyber_safety": {"rating": 7, "note": "Use VPN on public wifi. Avoid typing passwords in cafes over shoulders."},
        },
        "areas_to_avoid": ["Kuta at night (drunk tourists, scams)", "Quiet roads in rural areas after dark"],
        "safe_areas": ["Canggu", "Ubud", "Sanur", "Uluwatu"],
    },
    "chiang mai": {
        "city": "Chiang Mai", "country": "Thailand",
        "overall_rating": 9, "out_of": 10,
        "safety_level": "Very Safe",
        "summary": "One of the safest cities in Southeast Asia for nomads. Thai culture emphasizes hospitality. Main concerns: air quality in burning season and occasional transport scams.",
        "categories": {
            "violent_crime": {"rating": 9, "note": "Extremely rare. Thailand is very safe for tourists."},
            "petty_theft": {"rating": 8, "note": "Rare. Lock your accommodation. Don't flash expensive gear."},
            "traffic": {"rating": 6, "note": "Chaotic but slower than Bangkok. Grab/taxi is safest option."},
            "natural_disasters": {"rating": 8, "note": "Minimal risk. Occasional flooding in Sep-Oct."},
            "cyber_safety": {"rating": 7, "note": "Good internet infrastructure. VPN recommended."},
        },
        "areas_to_avoid": ["Loi Kroh Road (tourist trap bars)", "Walking alone in unlit moat areas late at night"],
        "safe_areas": ["Nimman", "Old City", "Santitham", "Chang Phueak"],
    },
    "lisbon": {
        "city": "Lisbon", "country": "Portugal",
        "overall_rating": 8, "out_of": 10,
        "safety_level": "Safe",
        "summary": "Very safe European capital. Pickpocketing on trams and in tourist areas is the main concern. Excellent infrastructure for nomads.",
        "categories": {
            "violent_crime": {"rating": 9, "note": "Very rare. Portugal is one of the safest countries in Europe."},
            "petty_theft": {"rating": 6, "note": "Pickpockets on Tram 28, in Alfama, and at Rossio. Watch your phone."},
            "traffic": {"rating": 7, "note": "Hills + cobblestones + trams. Walk carefully on wet days."},
            "natural_disasters": {"rating": 8, "note": "Low risk. Occasional earthquakes (rare)."},
            "cyber_safety": {"rating": 9, "note": "EU data protection (GDPR). Good public wifi security."},
        },
        "areas_to_avoid": ["Martim Moniz at night (pickpockets)", "Certain parts of Mouraria after dark"],
        "safe_areas": ["Santos", "Príncipe Real", "Chiado", "Alfama (daytime)"],
    },
    "mexico city": {
        "city": "Mexico City", "country": "Mexico",
        "overall_rating": 7, "out_of": 10,
        "safety_level": "Moderately Safe",
        "summary": "Safe in nomad-friendly neighborhoods (Roma, Condesa, Polanco). Exercise normal urban caution. Don't walk alone late in unfamiliar areas. Use Uber/Didi over regular taxis.",
        "categories": {
            "violent_crime": {"rating": 6, "note": "Low in tourist/nomad areas. Avoid outskirts and use registered transport."},
            "petty_theft": {"rating": 6, "note": "Phone theft common in metro/crowded areas. Keep phone in front pocket."},
            "traffic": {"rating": 6, "note": "Chaotic driving. Use ride-hailing, avoid driving yourself."},
            "natural_disasters": {"rating": 5, "note": "Earthquake zone. Know your building's nearest muster point."},
            "cyber_safety": {"rating": 7, "note": "VPN recommended. Be cautious with public wifi."},
        },
        "areas_to_avoid": ["Tepito", "Doctores at night", "Iztapalapa", "Regular street taxis (use Uber/Didi)"],
        "safe_areas": ["Roma Norte", "Condesa", "Polanco", "Coyoacán"],
    },
}

EMERGENCY_CONTACTS = {
    "bali": {
        "country": "Indonesia",
        "police": "110",
        "ambulance": "118 / 119",
        "fire": "113",
        "tourist_police": "+62 361 224111",
        "hospitals": [
            {"name": "BIMC Hospital Kuta", "type": "International", "phone": "+62 361 761263", "note": "Best for nomads — English-speaking, accepts international insurance"},
            {"name": "Siloam Hospital Bali", "type": "International", "phone": "+62 361 779900", "note": "Large hospital, 24/7 ER"},
        ],
        "embassy_tip": "Most embassies are in Jakarta (1.5hr flight). Australian consulate in Bali: +62 361 241118",
    },
    "chiang mai": {
        "country": "Thailand",
        "police": "191",
        "ambulance": "1669",
        "fire": "199",
        "tourist_police": "1155 (English-speaking)",
        "hospitals": [
            {"name": "Ram Hospital", "type": "Private International", "phone": "+66 53 920300", "note": "Preferred by expats — English staff, modern facilities"},
            {"name": "Maharaj Nakorn CM Hospital", "type": "Government", "phone": "+66 53 936150", "note": "Large public hospital, affordable but crowded"},
        ],
        "embassy_tip": "US Consulate in Chiang Mai: +66 53 107700. Most other embassies in Bangkok.",
    },
    "lisbon": {
        "country": "Portugal",
        "police": "112 (EU emergency number)",
        "ambulance": "112",
        "fire": "112",
        "tourist_police": "PSP Tourism: +351 21 347 4730",
        "hospitals": [
            {"name": "Hospital de Santa Maria", "type": "Public", "phone": "+351 21 780 5000", "note": "Largest hospital. ER can be slow but care is good."},
            {"name": "CUF Descobertas", "type": "Private", "phone": "+351 21 002 3010", "note": "Private, fast, accepts most travel insurance"},
        ],
        "embassy_tip": "US Embassy Lisbon: +351 21 727 3300. Most EU embassies nearby.",
    },
    "mexico city": {
        "country": "Mexico",
        "police": "911",
        "ambulance": "911",
        "fire": "911",
        "tourist_police": "LOCATEL: 55 5658 1111",
        "hospitals": [
            {"name": "Hospital Ángeles", "type": "Private", "phone": "+52 55 5516 9900", "note": "Premium private hospital, English-speaking doctors"},
            {"name": "American British Cowdray (ABC)", "type": "Private", "phone": "+52 55 5230 8000", "note": "Best in CDMX for foreigners. Expensive but excellent."},
        ],
        "embassy_tip": "US Embassy CDMX: +52 55 5080 2000. Open for emergencies 24/7.",
    },
}

SCAM_DATA = {
    "bali": {
        "scams": [
            {"name": "Money changer short-change", "risk": "High", "description": "Shops in Kuta/Seminyak use sleight of hand to short-change you during counting.", "prevention": "Use ATMs only. If you must exchange, use authorized BMC counters and count yourself."},
            {"name": "Scooter rental damage scam", "risk": "Medium", "description": "False damage claims on return. Photos of 'pre-existing' scratches shown on a different bike.", "prevention": "Take timestamped photos/video of the bike BEFORE riding. Use a reputable rental."},
            {"name": "Fake surf instructors", "risk": "Low", "description": "Unlicensed 'instructors' on Kuta beach charge tourists high prices for poor lessons.", "prevention": "Book through your accommodation or a verified surf school (Odysseys, Rip Curl School)."},
            {"name": "Overpriced taxi from airport", "risk": "Medium", "description": "Unlicensed drivers quote 3-5x normal rates outside the airport.", "prevention": "Use the official airport taxi counter inside arrivals, or grab once outside the airport zone."},
        ],
    },
    "chiang mai": {
        "scams": [
            {"name": "Tuk-tuk temple tour scam", "risk": "Medium", "description": "Driver offers cheap temple tour but detours to gem shops for commission.", "prevention": "Use Grab app for transport. If you want a tour, book through your hotel."},
            {"name": "Gem shop scam", "risk": "Medium", "description": "Friendly local recommends a 'government gem sale' with impossible deals.", "prevention": "There is no government gem sale. Never buy gems from strangers' recommendations."},
            {"name": "Fake monk solicitation", "risk": "Low", "description": "People dressed as monks ask for large donations on the street.", "prevention": "Real monks don't solicit money on the street. Politely decline."},
        ],
    },
    "lisbon": {
        "scams": [
            {"name": "Tram 28 pickpockets", "risk": "High", "description": "Organized pickpocket groups operate on the famous Tram 28 route targeting tourist phones/wallets.", "prevention": "Keep belongings in front pockets. Use zipped bags. Consider walking the route instead."},
            {"name": "Restaurant overcharging", "risk": "Medium", "description": "Appetizers/bread placed on table unasked — they're charged separately (€5-10).", "prevention": "Send them back if you don't want them. Ask for prices before ordering."},
            {"name": "Fake petitions", "risk": "Low", "description": "People ask you to sign a petition, then ask for money or pickpocket you while distracted.", "prevention": "Don't stop for petition solicitors. Keep walking."},
        ],
    },
    "mexico city": {
        "scams": [
            {"name": "Express kidnapping (taxi)", "risk": "Medium", "description": "Unmarked taxis may drive to ATMs and force withdrawals.", "prevention": "NEVER take a street taxi. Always use Uber, Didi, or InDrive."},
            {"name": "ATM skimming", "risk": "Medium", "description": "Card skimmers installed on ATMs, especially in tourist areas.", "prevention": "Use ATMs inside banks during business hours. Cover the keypad."},
            {"name": "Fake police", "risk": "Low", "description": "People impersonating police ask to 'check your wallet' for counterfeit bills.", "prevention": "Real police don't check wallets on the street. Ask for badge number, offer to go to the station."},
        ],
    },
}

HEALTH_DATA = {
    "bali": {
        "vaccinations": {
            "recommended": ["Hepatitis A", "Typhoid", "Tetanus-Diphtheria"],
            "consider": ["Japanese Encephalitis (if rural/long-term)", "Rabies (lots of stray dogs)"],
            "required": "None for most nationalities",
        },
        "water": "⚠️ Do NOT drink tap water. Buy bottled or use a SteriPen/LifeStraw.",
        "mosquitoes": "High risk for Dengue (especially rainy season Oct-Mar). Use DEET repellent, sleep with AC on.",
        "food_safety": "Street food is generally safe if cooked fresh. Avoid raw salads at cheap warungs.",
        "insurance_tip": "SafetyWing ($45/month) covers Bali. Add scooter coverage ($20 extra) — you'll need it.",
        "pharmacy": "Pharmacies (apotek) sell most medications OTC. Guardian and Kimia Farma are reliable chains.",
    },
    "chiang mai": {
        "vaccinations": {
            "recommended": ["Hepatitis A", "Typhoid", "Tetanus"],
            "consider": ["Japanese Encephalitis", "Rabies (temple dogs)"],
            "required": "None for most nationalities",
        },
        "water": "⚠️ Don't drink tap water. Refill stations everywhere (1-2 THB/liter).",
        "mosquitoes": "Dengue risk in rainy season (Jun-Oct). DEET repellent recommended.",
        "food_safety": "Street food is world-class AND safe. Night markets are fine — choose busy stalls.",
        "insurance_tip": "SafetyWing ($45/month) or WorldNomads. Thai hospitals are affordable even without insurance.",
        "pharmacy": "Boots and Fascino pharmacies are everywhere. Most meds available without prescription.",
        "special_notice": "🔥 Burning season (Feb-Apr): Air quality drops severely. Monitor AQI app. Consider an air purifier or N95 mask.",
    },
    "lisbon": {
        "vaccinations": {
            "recommended": ["Routine vaccinations up to date"],
            "consider": ["Hepatitis A (if eating street food frequently)"],
            "required": "None for EU/US/etc",
        },
        "water": "✅ Tap water is perfectly safe to drink. Bring a reusable bottle.",
        "mosquitoes": "Minimal risk. Occasional mosquitoes in summer but no tropical diseases.",
        "food_safety": "Excellent food safety standards. EU regulations apply.",
        "insurance_tip": "EU EHIC/GHIC card covers EU nationals. Others: SafetyWing or travel insurance with EU coverage.",
        "pharmacy": "Farmácias are well-stocked and pharmacists often speak English.",
    },
    "mexico city": {
        "vaccinations": {
            "recommended": ["Hepatitis A", "Typhoid", "Tetanus"],
            "consider": ["Hepatitis B (if long-term)"],
            "required": "None for most nationalities",
        },
        "water": "⚠️ Don't drink tap water. Even locals buy bottled (garrafón). Use it for brushing teeth too.",
        "mosquitoes": "Minimal mosquito risk at altitude (2,240m). Lower-altitude areas have Dengue risk.",
        "food_safety": "Street tacos are safe from busy stalls. Avoid market fruit drinks made with tap water/ice.",
        "insurance_tip": "SafetyWing ($45/month) works great. Mexican hospitals are excellent and affordable — ABC Hospital is top-tier.",
        "pharmacy": "Farmacias Similares ('Dr. Simi') is everywhere and very affordable. Doctors on-site ($3 consultation).",
        "special_notice": "🏔️ Altitude: 2,240m. Take it easy the first 2-3 days. Drink extra water. Avoid heavy exercise initially.",
    },
}


# --- From community_agent.py ---

LOCAL_EVENTS = {
    "bali": [
        {
            "name": "Canggu Cowork & Surf",
            "type": "networking",
            "frequency": "Weekly (Wednesdays)",
            "location": "Dojo Bali, Canggu",
            "description": "Morning surf session + afternoon coworking. Meet other nomads who code & ride waves.",
            "cost": "Free (coworking day pass included)",
            "best_for": ["developers", "surfers", "networking"],
        },
        {
            "name": "Ubud Digital Nomad Meetup",
            "type": "meetup",
            "frequency": "Monthly (1st Saturday)",
            "location": "Hubud, Ubud",
            "description": "Show & tell: nomads demo their projects. Plus Q&A on Bali visa, banking, health insurance.",
            "cost": "50k IDR (~$3)",
            "best_for": ["entrepreneurs", "freelancers", "community"],
        },
        {
            "name": "Bali Startup Grind",
            "type": "pitch",
            "frequency": "Monthly (3rd Thursday)",
            "location": "Outpost Canggu",
            "description": "Fireside chats with founders building from Bali. Networking drinks after.",
            "cost": "100k IDR (~$7)",
            "best_for": ["founders", "investors", "startup"],
        },
        {
            "name": "Yoga & Journal Morning",
            "type": "wellness",
            "frequency": "Daily",
            "location": "The Yoga Barn, Ubud",
            "description": "Group yoga followed by guided journaling. Perfect for starting the day mindfully.",
            "cost": "150k IDR (~$10)",
            "best_for": ["wellness", "yoga", "mindfulness"],
        },
    ],
    "chiang mai": [
        {
            "name": "Nomad Coffee Club",
            "type": "networking",
            "frequency": "Weekly (Tuesdays)",
            "location": "Ristr8to Lab, Nimman",
            "description": "Casual coffee meetup for remote workers. Bring your laptop, meet your tribe.",
            "cost": "Free (buy your own coffee)",
            "best_for": ["networking", "coffee lovers", "casual"],
        },
        {
            "name": "CM Hack Night",
            "type": "hackathon",
            "frequency": "Bi-weekly (Fridays)",
            "location": "Punspace, Nimman",
            "description": "Build something in 4 hours. Teams form on the spot. Pizza provided.",
            "cost": "Free",
            "best_for": ["developers", "designers", "builders"],
        },
        {
            "name": "Sunday Night Market Walk",
            "type": "cultural",
            "frequency": "Weekly (Sundays)",
            "location": "Walking Street, Old City",
            "description": "Group walk through the famous Sunday market. Food, crafts, live music.",
            "cost": "Free",
            "best_for": ["culture", "food", "photography"],
        },
        {
            "name": "Muay Thai Morning",
            "type": "fitness",
            "frequency": "MWF mornings",
            "location": "Team Quest Muay Thai",
            "description": "Group training session for all levels. Great way to meet active nomads.",
            "cost": "300 THB (~$9)",
            "best_for": ["fitness", "martial arts", "adventure"],
        },
    ],
    "lisbon": [
        {
            "name": "Lisbon Web Summit Afterwork",
            "type": "networking",
            "frequency": "Monthly",
            "location": "Village Underground, Santos",
            "description": "Tech drinks in Lisbon's most iconic co-work/event space. 200+ attendees.",
            "cost": "€5",
            "best_for": ["tech", "startup", "networking"],
        },
        {
            "name": "Pasteis & Portuguese",
            "type": "cultural",
            "frequency": "Weekly (Saturdays)",
            "location": "Alfama",
            "description": "Learn Portuguese over pastéis de nata. Native speakers teach conversational basics.",
            "cost": "€10",
            "best_for": ["language", "culture", "food"],
        },
        {
            "name": "Fado & Wine Evening",
            "type": "cultural",
            "frequency": "Monthly (last Friday)",
            "location": "Alfama",
            "description": "Intimate fado performance + wine tasting. Limited to 20 people.",
            "cost": "€25",
            "best_for": ["music", "wine", "culture"],
        },
    ],
    "mexico city": [
        {
            "name": "CDMX Dev & Mezcal",
            "type": "networking",
            "frequency": "Bi-weekly (Thursdays)",
            "location": "WeWork Roma",
            "description": "Developer meetup followed by mezcal tasting. Lightning talks welcome.",
            "cost": "Free (mezcal extra)",
            "best_for": ["developers", "networking", "mezcal"],
        },
        {
            "name": "Street Food Safari",
            "type": "cultural",
            "frequency": "Weekly (Saturdays)",
            "location": "Start at Roma Norte mercado",
            "description": "Guided tour of the best tacos, tlacoyos, and tamales. 3 hours, 8+ stops.",
            "cost": "$15 USD",
            "best_for": ["food", "culture", "adventure"],
        },
        {
            "name": "Condesa Park Run",
            "type": "fitness",
            "frequency": "Daily (7 AM)",
            "location": "Parque México, Condesa",
            "description": "5K group run through the most beautiful park in CDMX. All paces welcome.",
            "cost": "Free",
            "best_for": ["fitness", "running", "outdoor"],
        },
    ],
}

HUB_PROFILES = {
    "bali": {
        "active_nomads": 2400,
        "avg_stay_days": 45,
        "top_professions": ["Developer", "Designer", "Content Creator", "Marketer", "Consultant"],
        "top_interests": ["surfing", "yoga", "coworking", "entrepreneurship", "wellness"],
        "gender_split": {"male": 58, "female": 40, "other": 2},
        "avg_age": 31,
        "nationalities_count": 68,
        "top_nationalities": ["US", "UK", "DE", "AU", "NL"],
        "community_vibe": "Energetic surf-startup culture. Very social, lots of events.",
    },
    "chiang mai": {
        "active_nomads": 3100,
        "avg_stay_days": 90,
        "top_professions": ["Developer", "Writer", "Teacher", "Freelancer", "Designer"],
        "top_interests": ["coding", "Thai food", "temples", "trekking", "coffee"],
        "gender_split": {"male": 55, "female": 43, "other": 2},
        "avg_age": 29,
        "nationalities_count": 82,
        "top_nationalities": ["US", "UK", "DE", "RU", "FR"],
        "community_vibe": "Chill, budget-friendly, long-term stays. The OG nomad hub.",
    },
    "lisbon": {
        "active_nomads": 1800,
        "avg_stay_days": 60,
        "top_professions": ["Startup Founder", "Developer", "Designer", "PM", "Marketer"],
        "top_interests": ["startup", "Web Summit", "surfing", "wine", "architecture"],
        "gender_split": {"male": 52, "female": 46, "other": 2},
        "avg_age": 33,
        "nationalities_count": 55,
        "top_nationalities": ["US", "BR", "DE", "UK", "FR"],
        "community_vibe": "Startup-driven, European quality. Growing fast since Web Summit.",
    },
    "mexico city": {
        "active_nomads": 2000,
        "avg_stay_days": 60,
        "top_professions": ["Developer", "Writer", "Designer", "Consultant", "Artist"],
        "top_interests": ["food", "art", "mezcal", "running", "Spanish"],
        "gender_split": {"male": 50, "female": 48, "other": 2},
        "avg_age": 30,
        "nationalities_count": 45,
        "top_nationalities": ["US", "CA", "UK", "DE", "AR"],
        "community_vibe": "Foodie paradise with creative energy. Great for US-timezone workers.",
    },
}

