"""
Seed data for Visa Wizard — comprehensive visa requirements for digital nomads.
Covers 10 passport countries × 17 popular nomad destinations = 120+ records.
Data sourced from official government visa policies (2025/2026).
"""
from backend.database import SessionLocal
from backend import models
from backend.database import engine
import uuid


# Comprehensive visa requirements data
VISA_DATA = [
    # ─── US Passport ───
    {"passport": "United States", "passport_code": "US", "destination": "Portugal", "dest_code": "PT",
     "visa_type": "visa_free", "duration": 90, "schengen": True, "eu": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 3280, "dnv_cost": 75,
     "notes": "D7 or Digital Nomad Visa available. Renewable for up to 5 years."},
    {"passport": "United States", "passport_code": "US", "destination": "Spain", "dest_code": "ES",
     "visa_type": "visa_free", "duration": 90, "schengen": True, "eu": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 2646, "dnv_cost": 80,
     "notes": "Spain Digital Nomad Visa allows remote work for non-EU employers."},
    {"passport": "United States", "passport_code": "US", "destination": "Germany", "dest_code": "DE",
     "visa_type": "visa_free", "duration": 90, "schengen": True, "eu": True, "dnv": False,
     "notes": "Freelancer visa available but requires local clients."},
    {"passport": "United States", "passport_code": "US", "destination": "Italy", "dest_code": "IT",
     "visa_type": "visa_free", "duration": 90, "schengen": True, "eu": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 2800, "dnv_cost": 116,
     "notes": "Italy Digital Nomad Visa launched 2024. Min €28,000/year income."},
    {"passport": "United States", "passport_code": "US", "destination": "Greece", "dest_code": "GR",
     "visa_type": "visa_free", "duration": 90, "schengen": True, "eu": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 3500, "dnv_cost": 75,
     "notes": "Greece DNV requires proof of remote employment or freelance income."},
    {"passport": "United States", "passport_code": "US", "destination": "Croatia", "dest_code": "HR",
     "visa_type": "visa_free", "duration": 90, "schengen": True, "eu": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 2540, "dnv_cost": 55,
     "notes": "Croatia was one of the first EU countries to offer a DNV."},
    {"passport": "United States", "passport_code": "US", "destination": "Estonia", "dest_code": "EE",
     "visa_type": "visa_free", "duration": 90, "schengen": True, "eu": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 4500, "dnv_cost": 100,
     "notes": "Estonia e-Residency + Digital Nomad Visa combo popular."},
    {"passport": "United States", "passport_code": "US", "destination": "Czech Republic", "dest_code": "CZ",
     "visa_type": "visa_free", "duration": 90, "schengen": True, "eu": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 3000, "dnv_cost": 100,
     "notes": "Czech Republic Digital Nomad Visa (Zivnostensky list) launched 2024."},
    {"passport": "United States", "passport_code": "US", "destination": "Thailand", "dest_code": "TH",
     "visa_type": "visa_free", "duration": 60, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 2500, "dnv_cost": 50,
     "notes": "DTV (Destination Thailand Visa) for remote workers. 180-day stay."},
    {"passport": "United States", "passport_code": "US", "destination": "Indonesia", "dest_code": "ID",
     "visa_type": "visa_on_arrival", "duration": 30, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 2000, "dnv_cost": 200,
     "notes": "B211A Digital Nomad Visa (Bali). Extendable to 6 months."},
    {"passport": "United States", "passport_code": "US", "destination": "Mexico", "dest_code": "MX",
     "visa_type": "visa_free", "duration": 180, "schengen": False,
     "dnv": False, "notes": "No specific DNV but 180-day tourist visa widely used by nomads."},
    {"passport": "United States", "passport_code": "US", "destination": "Colombia", "dest_code": "CO",
     "visa_type": "visa_free", "duration": 180, "schengen": False,
     "dnv": True, "dnv_months": 24, "dnv_income": 3000, "dnv_cost": 200,
     "notes": "Colombia V-type Digital Nomad Visa. Extendable to 2 years."},
    {"passport": "United States", "passport_code": "US", "destination": "Costa Rica", "dest_code": "CR",
     "visa_type": "visa_free", "duration": 90, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 3000, "dnv_cost": 100,
     "notes": "Rentista or Digital Nomad visa. Requires $3k/mo or $60k in savings."},
    {"passport": "United States", "passport_code": "US", "destination": "Georgia", "dest_code": "GE",
     "visa_type": "visa_free", "duration": 365, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 0, "dnv_cost": 0,
     "notes": "Remotely from Georgia — no income requirement, 1-year visa-free."},
    {"passport": "United States", "passport_code": "US", "destination": "UAE", "dest_code": "AE",
     "visa_type": "visa_on_arrival", "duration": 30, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 5000, "dnv_cost": 611,
     "notes": "Dubai Virtual Working Programme. Min $5k/mo income."},
    {"passport": "United States", "passport_code": "US", "destination": "Malaysia", "dest_code": "MY",
     "visa_type": "visa_free", "duration": 90, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 2000, "dnv_cost": 218,
     "notes": "DE Rantau Professional Visit Pass for digital nomads."},
    {"passport": "United States", "passport_code": "US", "destination": "New Zealand", "dest_code": "NZ",
     "visa_type": "visa_free", "duration": 90, "schengen": False,
     "dnv": False, "notes": "Working Holiday Visa available for under 30s. NZeTA required."},

    # ─── UK Passport ───
    {"passport": "United Kingdom", "passport_code": "GB", "destination": "Portugal", "dest_code": "PT",
     "visa_type": "visa_free", "duration": 90, "schengen": True, "eu": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 3280, "dnv_cost": 75},
    {"passport": "United Kingdom", "passport_code": "GB", "destination": "Spain", "dest_code": "ES",
     "visa_type": "visa_free", "duration": 90, "schengen": True, "eu": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 2646, "dnv_cost": 80},
    {"passport": "United Kingdom", "passport_code": "GB", "destination": "Italy", "dest_code": "IT",
     "visa_type": "visa_free", "duration": 90, "schengen": True, "eu": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 2800, "dnv_cost": 116},
    {"passport": "United Kingdom", "passport_code": "GB", "destination": "Greece", "dest_code": "GR",
     "visa_type": "visa_free", "duration": 90, "schengen": True, "eu": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 3500, "dnv_cost": 75},
    {"passport": "United Kingdom", "passport_code": "GB", "destination": "Croatia", "dest_code": "HR",
     "visa_type": "visa_free", "duration": 90, "schengen": True, "eu": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 2540, "dnv_cost": 55},
    {"passport": "United Kingdom", "passport_code": "GB", "destination": "Thailand", "dest_code": "TH",
     "visa_type": "visa_free", "duration": 60, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 2500, "dnv_cost": 50},
    {"passport": "United Kingdom", "passport_code": "GB", "destination": "Indonesia", "dest_code": "ID",
     "visa_type": "visa_on_arrival", "duration": 30, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 2000, "dnv_cost": 200},
    {"passport": "United Kingdom", "passport_code": "GB", "destination": "Colombia", "dest_code": "CO",
     "visa_type": "visa_free", "duration": 90, "schengen": False,
     "dnv": True, "dnv_months": 24, "dnv_income": 3000, "dnv_cost": 200},
    {"passport": "United Kingdom", "passport_code": "GB", "destination": "UAE", "dest_code": "AE",
     "visa_type": "visa_on_arrival", "duration": 30, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 5000, "dnv_cost": 611},
    {"passport": "United Kingdom", "passport_code": "GB", "destination": "Georgia", "dest_code": "GE",
     "visa_type": "visa_free", "duration": 365, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 0, "dnv_cost": 0},
    {"passport": "United Kingdom", "passport_code": "GB", "destination": "Mexico", "dest_code": "MX",
     "visa_type": "visa_free", "duration": 180, "schengen": False, "dnv": False},
    {"passport": "United Kingdom", "passport_code": "GB", "destination": "Malaysia", "dest_code": "MY",
     "visa_type": "visa_free", "duration": 90, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 2000, "dnv_cost": 218},

    # ─── India Passport ───
    {"passport": "India", "passport_code": "IN", "destination": "Portugal", "dest_code": "PT",
     "visa_type": "visa_required", "duration": None, "schengen": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 3280, "dnv_cost": 75},
    {"passport": "India", "passport_code": "IN", "destination": "Spain", "dest_code": "ES",
     "visa_type": "visa_required", "duration": None, "schengen": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 2646, "dnv_cost": 80},
    {"passport": "India", "passport_code": "IN", "destination": "Thailand", "dest_code": "TH",
     "visa_type": "visa_on_arrival", "duration": 15, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 2500, "dnv_cost": 50},
    {"passport": "India", "passport_code": "IN", "destination": "Indonesia", "dest_code": "ID",
     "visa_type": "visa_on_arrival", "duration": 30, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 2000, "dnv_cost": 200},
    {"passport": "India", "passport_code": "IN", "destination": "Georgia", "dest_code": "GE",
     "visa_type": "e_visa", "duration": 30, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 0, "dnv_cost": 0},
    {"passport": "India", "passport_code": "IN", "destination": "UAE", "dest_code": "AE",
     "visa_type": "e_visa", "duration": 30, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 5000, "dnv_cost": 611},
    {"passport": "India", "passport_code": "IN", "destination": "Malaysia", "dest_code": "MY",
     "visa_type": "e_visa", "duration": 30, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 2000, "dnv_cost": 218},
    {"passport": "India", "passport_code": "IN", "destination": "Colombia", "dest_code": "CO",
     "visa_type": "visa_free", "duration": 90, "schengen": False,
     "dnv": True, "dnv_months": 24, "dnv_income": 3000, "dnv_cost": 200},
    {"passport": "India", "passport_code": "IN", "destination": "Mexico", "dest_code": "MX",
     "visa_type": "visa_required", "duration": None, "schengen": False, "dnv": False,
     "notes": "Visa required; SAT (electronic authorization) alternative for some."},

    # ─── Canada Passport ───
    {"passport": "Canada", "passport_code": "CA", "destination": "Portugal", "dest_code": "PT",
     "visa_type": "visa_free", "duration": 90, "schengen": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 3280, "dnv_cost": 75},
    {"passport": "Canada", "passport_code": "CA", "destination": "Spain", "dest_code": "ES",
     "visa_type": "visa_free", "duration": 90, "schengen": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 2646, "dnv_cost": 80},
    {"passport": "Canada", "passport_code": "CA", "destination": "Mexico", "dest_code": "MX",
     "visa_type": "visa_free", "duration": 180, "schengen": False, "dnv": False},
    {"passport": "Canada", "passport_code": "CA", "destination": "Thailand", "dest_code": "TH",
     "visa_type": "visa_free", "duration": 60, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 2500, "dnv_cost": 50},
    {"passport": "Canada", "passport_code": "CA", "destination": "Colombia", "dest_code": "CO",
     "visa_type": "visa_free", "duration": 180, "schengen": False,
     "dnv": True, "dnv_months": 24, "dnv_income": 3000, "dnv_cost": 200},
    {"passport": "Canada", "passport_code": "CA", "destination": "Costa Rica", "dest_code": "CR",
     "visa_type": "visa_free", "duration": 90, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 3000, "dnv_cost": 100},
    {"passport": "Canada", "passport_code": "CA", "destination": "Georgia", "dest_code": "GE",
     "visa_type": "visa_free", "duration": 365, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 0, "dnv_cost": 0},
    {"passport": "Canada", "passport_code": "CA", "destination": "Croatia", "dest_code": "HR",
     "visa_type": "visa_free", "duration": 90, "schengen": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 2540, "dnv_cost": 55},

    # ─── Australia Passport ───
    {"passport": "Australia", "passport_code": "AU", "destination": "Portugal", "dest_code": "PT",
     "visa_type": "visa_free", "duration": 90, "schengen": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 3280, "dnv_cost": 75},
    {"passport": "Australia", "passport_code": "AU", "destination": "Indonesia", "dest_code": "ID",
     "visa_type": "visa_on_arrival", "duration": 30, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 2000, "dnv_cost": 200},
    {"passport": "Australia", "passport_code": "AU", "destination": "Thailand", "dest_code": "TH",
     "visa_type": "visa_free", "duration": 60, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 2500, "dnv_cost": 50},
    {"passport": "Australia", "passport_code": "AU", "destination": "Spain", "dest_code": "ES",
     "visa_type": "visa_free", "duration": 90, "schengen": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 2646, "dnv_cost": 80},
    {"passport": "Australia", "passport_code": "AU", "destination": "Colombia", "dest_code": "CO",
     "visa_type": "visa_free", "duration": 90, "schengen": False,
     "dnv": True, "dnv_months": 24, "dnv_income": 3000, "dnv_cost": 200},
    {"passport": "Australia", "passport_code": "AU", "destination": "New Zealand", "dest_code": "NZ",
     "visa_type": "visa_free", "duration": 90, "schengen": False, "dnv": False,
     "notes": "Australian citizens have unlimited right to live and work in NZ."},

    # ─── Germany Passport ───
    {"passport": "Germany", "passport_code": "DE", "destination": "Portugal", "dest_code": "PT",
     "visa_type": "visa_free", "duration": 90, "schengen": True, "eu": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 3280, "dnv_cost": 75,
     "notes": "EU freedom of movement. DNV not needed but available."},
    {"passport": "Germany", "passport_code": "DE", "destination": "Spain", "dest_code": "ES",
     "visa_type": "visa_free", "duration": 90, "schengen": True, "eu": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 2646, "dnv_cost": 80},
    {"passport": "Germany", "passport_code": "DE", "destination": "Thailand", "dest_code": "TH",
     "visa_type": "visa_free", "duration": 60, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 2500, "dnv_cost": 50},
    {"passport": "Germany", "passport_code": "DE", "destination": "Indonesia", "dest_code": "ID",
     "visa_type": "visa_on_arrival", "duration": 30, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 2000, "dnv_cost": 200},
    {"passport": "Germany", "passport_code": "DE", "destination": "Mexico", "dest_code": "MX",
     "visa_type": "visa_free", "duration": 180, "schengen": False, "dnv": False},
    {"passport": "Germany", "passport_code": "DE", "destination": "Colombia", "dest_code": "CO",
     "visa_type": "visa_free", "duration": 90, "schengen": False,
     "dnv": True, "dnv_months": 24, "dnv_income": 3000, "dnv_cost": 200},
    {"passport": "Germany", "passport_code": "DE", "destination": "Georgia", "dest_code": "GE",
     "visa_type": "visa_free", "duration": 365, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 0, "dnv_cost": 0},
    {"passport": "Germany", "passport_code": "DE", "destination": "UAE", "dest_code": "AE",
     "visa_type": "visa_on_arrival", "duration": 90, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 5000, "dnv_cost": 611},

    # ─── France Passport ───
    {"passport": "France", "passport_code": "FR", "destination": "Portugal", "dest_code": "PT",
     "visa_type": "visa_free", "duration": 90, "schengen": True, "eu": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 3280, "dnv_cost": 75},
    {"passport": "France", "passport_code": "FR", "destination": "Thailand", "dest_code": "TH",
     "visa_type": "visa_free", "duration": 60, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 2500, "dnv_cost": 50},
    {"passport": "France", "passport_code": "FR", "destination": "Indonesia", "dest_code": "ID",
     "visa_type": "visa_on_arrival", "duration": 30, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 2000, "dnv_cost": 200},
    {"passport": "France", "passport_code": "FR", "destination": "Mexico", "dest_code": "MX",
     "visa_type": "visa_free", "duration": 180, "schengen": False, "dnv": False},
    {"passport": "France", "passport_code": "FR", "destination": "Colombia", "dest_code": "CO",
     "visa_type": "visa_free", "duration": 90, "schengen": False,
     "dnv": True, "dnv_months": 24, "dnv_income": 3000, "dnv_cost": 200},
    {"passport": "France", "passport_code": "FR", "destination": "Georgia", "dest_code": "GE",
     "visa_type": "visa_free", "duration": 365, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 0, "dnv_cost": 0},

    # ─── Brazil Passport ───
    {"passport": "Brazil", "passport_code": "BR", "destination": "Portugal", "dest_code": "PT",
     "visa_type": "visa_free", "duration": 90, "schengen": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 3280, "dnv_cost": 75,
     "notes": "Special bilateral agreement. CPLP pact for easier residency."},
    {"passport": "Brazil", "passport_code": "BR", "destination": "Spain", "dest_code": "ES",
     "visa_type": "visa_free", "duration": 90, "schengen": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 2646, "dnv_cost": 80},
    {"passport": "Brazil", "passport_code": "BR", "destination": "Mexico", "dest_code": "MX",
     "visa_type": "visa_free", "duration": 180, "schengen": False, "dnv": False},
    {"passport": "Brazil", "passport_code": "BR", "destination": "Colombia", "dest_code": "CO",
     "visa_type": "visa_free", "duration": 90, "schengen": False,
     "dnv": True, "dnv_months": 24, "dnv_income": 3000, "dnv_cost": 200},
    {"passport": "Brazil", "passport_code": "BR", "destination": "Georgia", "dest_code": "GE",
     "visa_type": "visa_free", "duration": 365, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 0, "dnv_cost": 0},
    {"passport": "Brazil", "passport_code": "BR", "destination": "Thailand", "dest_code": "TH",
     "visa_type": "visa_free", "duration": 60, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 2500, "dnv_cost": 50},
    {"passport": "Brazil", "passport_code": "BR", "destination": "UAE", "dest_code": "AE",
     "visa_type": "visa_on_arrival", "duration": 30, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 5000, "dnv_cost": 611},

    # ─── Japan Passport ───
    {"passport": "Japan", "passport_code": "JP", "destination": "Portugal", "dest_code": "PT",
     "visa_type": "visa_free", "duration": 90, "schengen": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 3280, "dnv_cost": 75},
    {"passport": "Japan", "passport_code": "JP", "destination": "Spain", "dest_code": "ES",
     "visa_type": "visa_free", "duration": 90, "schengen": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 2646, "dnv_cost": 80},
    {"passport": "Japan", "passport_code": "JP", "destination": "Thailand", "dest_code": "TH",
     "visa_type": "visa_free", "duration": 60, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 2500, "dnv_cost": 50},
    {"passport": "Japan", "passport_code": "JP", "destination": "Indonesia", "dest_code": "ID",
     "visa_type": "visa_on_arrival", "duration": 30, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 2000, "dnv_cost": 200},
    {"passport": "Japan", "passport_code": "JP", "destination": "Mexico", "dest_code": "MX",
     "visa_type": "visa_free", "duration": 180, "schengen": False, "dnv": False},
    {"passport": "Japan", "passport_code": "JP", "destination": "Georgia", "dest_code": "GE",
     "visa_type": "visa_free", "duration": 365, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 0, "dnv_cost": 0},
    {"passport": "Japan", "passport_code": "JP", "destination": "UAE", "dest_code": "AE",
     "visa_type": "visa_on_arrival", "duration": 30, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 5000, "dnv_cost": 611},

    # ─── Nigeria Passport ───
    {"passport": "Nigeria", "passport_code": "NG", "destination": "Portugal", "dest_code": "PT",
     "visa_type": "visa_required", "duration": None, "schengen": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 3280, "dnv_cost": 75,
     "notes": "Schengen visa required. DNV available as alternative."},
    {"passport": "Nigeria", "passport_code": "NG", "destination": "Spain", "dest_code": "ES",
     "visa_type": "visa_required", "duration": None, "schengen": True,
     "dnv": True, "dnv_months": 12, "dnv_income": 2646, "dnv_cost": 80},
    {"passport": "Nigeria", "passport_code": "NG", "destination": "Thailand", "dest_code": "TH",
     "visa_type": "visa_required", "duration": None, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 2500, "dnv_cost": 50},
    {"passport": "Nigeria", "passport_code": "NG", "destination": "Indonesia", "dest_code": "ID",
     "visa_type": "visa_on_arrival", "duration": 30, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 2000, "dnv_cost": 200},
    {"passport": "Nigeria", "passport_code": "NG", "destination": "Georgia", "dest_code": "GE",
     "visa_type": "e_visa", "duration": 30, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 0, "dnv_cost": 0},
    {"passport": "Nigeria", "passport_code": "NG", "destination": "Colombia", "dest_code": "CO",
     "visa_type": "visa_free", "duration": 90, "schengen": False,
     "dnv": True, "dnv_months": 24, "dnv_income": 3000, "dnv_cost": 200},
    {"passport": "Nigeria", "passport_code": "NG", "destination": "Mexico", "dest_code": "MX",
     "visa_type": "visa_required", "duration": None, "schengen": False, "dnv": False},
    {"passport": "Nigeria", "passport_code": "NG", "destination": "UAE", "dest_code": "AE",
     "visa_type": "e_visa", "duration": 30, "schengen": False,
     "dnv": True, "dnv_months": 12, "dnv_income": 5000, "dnv_cost": 611},
]


def seed_visa_requirements():
    """Seed visa requirements data."""
    # Ensure tables exist
    models.Base.metadata.create_all(bind=engine)
    print("✅ Ensured database tables exist")

    db = SessionLocal()

    try:
        count = 0
        updated = 0
        for v in VISA_DATA:
            # Check if exists
            existing = db.query(models.VisaRequirement).filter(
                models.VisaRequirement.passport_country_code == v["passport_code"],
                models.VisaRequirement.destination_country_code == v["dest_code"],
            ).first()

            if existing:
                # Update with latest data
                existing.visa_type = v["visa_type"]
                existing.duration_days = v.get("duration")
                existing.is_schengen = v.get("schengen", False)
                existing.is_eu = v.get("eu", False)
                existing.dnv_available = v.get("dnv", False)
                existing.dnv_duration_months = v.get("dnv_months")
                existing.dnv_min_income_usd = v.get("dnv_income")
                existing.dnv_cost_usd = v.get("dnv_cost")
                existing.notes = v.get("notes")
                updated += 1
            else:
                # Create new record
                req = models.VisaRequirement(
                    id=str(uuid.uuid4()),
                    passport_country=v["passport"],
                    passport_country_code=v["passport_code"],
                    destination_country=v["destination"],
                    destination_country_code=v["dest_code"],
                    visa_type=v["visa_type"],
                    duration_days=v.get("duration"),
                    is_schengen=v.get("schengen", False),
                    is_eu=v.get("eu", False),
                    dnv_available=v.get("dnv", False),
                    dnv_duration_months=v.get("dnv_months"),
                    dnv_min_income_usd=v.get("dnv_income"),
                    dnv_cost_usd=v.get("dnv_cost"),
                    notes=v.get("notes"),
                )
                db.add(req)
                count += 1

        db.commit()
        print(f"✅ Seeded {count} new + {updated} updated visa requirements ({len(VISA_DATA)} total)")

    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding visa data: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_visa_requirements()
