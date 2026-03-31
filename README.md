# FutureStack

Civic Infrastructure Tech Marketplace — enabling communities to discover, fund, govern, and deploy solutions across water, energy, AI infrastructure, food security, education, and automated transport.

## Architecture

Built on a battle-tested platform core (auth, DAO governance, fractional investments, AI concierge, WebSocket notifications) with domain-specific infrastructure verticals.

## Quick Start

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

## Infrastructure Verticals

| Vertical | Description |
|----------|-------------|
| 💧 Water | Purification, distribution, desalination, rainwater harvesting |
| ⚡ Energy | Solar, wind, microgrids, battery storage, smart metering |
| 🤖 AI Infrastructure | Edge compute, community AI, data centers, connectivity |
| 🌾 Food Security | Vertical farms, hydroponics, supply chain, cold storage |
| 📚 Education | E-learning platforms, maker spaces, vocational training |
| 🚗 Transport | EV fleets, autonomous shuttles, bike-share, route optimization |

## Platform Features

- **Solution Marketplace** — vetted vendors list infrastructure products & services
- **Community Projects** — plan, fund, build, and monitor infrastructure
- **DAO Governance** — stake tokens, vote on projects, transparent treasury
- **Fractional Investment** — invest in infrastructure with booking discounts
- **AI Concierge** — "What solar setup fits our 500-person village?"
- **RFP System** — communities post needs, vendors bid
- **Impact Dashboards** — real-time metrics (kWh, liters, students served)

## Stack

- **Backend**: FastAPI + SQLAlchemy (PostgreSQL / SQLite fallback)
- **AI**: Gemini via LiteLLM with tool-calling concierge
- **Real-time**: Socket.IO WebSocket notifications
- **Governance**: DAO voting + STACK token staking
- **Investments**: Fractional ownership + buyback pool
