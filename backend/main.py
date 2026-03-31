import asyncio
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.config import settings
from backend.middleware.rate_limit import RateLimitMiddleware
from backend.middleware.logging import RequestLoggingMiddleware
from backend.middleware.tracing import TracingMiddleware
from backend.middleware.security import SecurityHeadersMiddleware
from backend.config.observability import setup_logging, setup_tracing
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Configure Observability (Logging & Tracing) early
setup_logging()
tracer = setup_tracing()

import structlog
logger = structlog.get_logger("futurestack.startup")

# Initialize Sentry if DSN is provided
if settings.SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            integrations=[FastApiIntegration()],
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0,
            environment=settings.ENVIRONMENT,
        )
    except ImportError:
        pass

app = FastAPI(
    title="FutureStack",
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    description="""
FutureStack — Civic Infrastructure Tech Marketplace.

Enabling communities to discover, fund, govern, and deploy infrastructure solutions
across water, energy, AI, food security, education, and automated transport.

### Key Features:
* **Infrastructure Projects**: Plan, fund, build, and monitor community infrastructure.
* **Solution Marketplace**: Discover vetted vendors across 6 verticals.
* **DAO Governance**: Stake tokens, vote on projects, transparent treasury.
* **Fractional Investment**: Own shares in infrastructure with booking discounts.
* **AI Concierge**: Infrastructure planning assistant powered by Gemini.
* **RFP System**: Communities post needs, vendors bid.
* **Impact Dashboards**: Real-time metrics (kWh, liters, students served).
    """,
    contact={
        "name": "FutureStack Support",
        "url": "https://futurestack.dev/support",
        "email": "support@futurestack.dev",
    },
    license_info={
        "name": "Private",
    },
    openapi_tags=[
        {"name": "auth", "description": "Authentication and user identity management"},
        {"name": "infrastructure", "description": "Community infrastructure project management"},
        {"name": "marketplace", "description": "Solution vendor marketplace"},
        {"name": "rfp", "description": "Requests for proposals and vendor bidding"},
        {"name": "impact", "description": "Impact metrics and dashboards"},
        {"name": "dao", "description": "Governance, staking, and treasury"},
        {"name": "investments", "description": "Fractional infrastructure ownership"},
        {"name": "monitoring", "description": "System health and performance metrics"},
    ]
)

# Instrument FastAPI with OpenTelemetry Tracing
FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer)


# Create database tables
def init_db():
    from backend import models
    from backend.database import engine

    try:
        models.Base.metadata.create_all(bind=engine)
        logger.info("database_initialized")
    except Exception as e:
        logger.error("database_init_failed", error=str(e))


def run_enrichment_sync():
    """Sync enriched_retreats.csv data into DB on startup, then enrich remaining listings."""
    import datetime
    try:
        from backend.services.enrichment_service import sync_enriched_data
        stats = sync_enriched_data()
        if stats.get("loaded", 0) > 0:
            logger.info("enrichment_sync_complete", **{k: v for k, v in stats.items() if k != 'loaded'})
    except Exception as e:
        logger.warning("enrichment_sync_skipped", error=str(e))

    # Also enrich seed_data listings that weren't covered by CSV enrichment
    try:
        from backend.database import SessionLocal
        from backend import models
        db = SessionLocal()
        unenriched = db.query(models.Listing).filter(
            models.Listing.booking_url.is_(None)
        ).all()
        if unenriched:
            enriched_count = 0
            for listing in unenriched:
                # Give each listing a booking URL (internal link or construct from name)
                listing.booking_url = f"https://nomadnest.ai/book/{listing.id}"
                # Ensure they have a last_enriched_at timestamp
                listing.last_enriched_at = datetime.datetime.now(datetime.timezone.utc)
                enriched_count += 1
            db.commit()
            logger.info("auto_enrichment_complete", count=enriched_count)
        db.close()
    except Exception as e:
        logger.warning("auto_enrichment_skipped", error=str(e))


init_db()
run_enrichment_sync()

from backend.errors import NomadNestError


# NomadNest specific exception handler
@app.exception_handler(NomadNestError)
async def nomadnest_exception_handler(request: Request, exc: NomadNestError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {"message": exc.message, "code": exc.code, "details": exc.details}
        },
    )


# Global fallback exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log the full traceback for non-custom exceptions
    import traceback

    traceback.print_exc()

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "An unexpected internal server error occurred.",
                "code": "INTERNAL_ERROR",
                "details": {"path": str(request.url.path)},
            }
        },
    )


# CORS
_dev_origins = [
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    # Capacitor iOS WebView origins
    "capacitor://localhost",
    "ionic://localhost",
]

def _get_cors_origins():
    """Build CORS origin list based on environment."""
    if settings.ENVIRONMENT == "development":
        return ["*"]
    
    # Production: use explicit origins only
    origins = [
        settings.FRONTEND_URL,
        "capacitor://localhost",  # Always needed for iOS native app
        "ionic://localhost",
    ]
    
    # Add any custom origins from ALLOWED_ORIGINS env var
    if settings.ALLOWED_ORIGINS:
        origins.extend([o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()])
    
    return origins

# Request logging and other middlewares
from backend.middleware.xss import XSSMiddleware
from starlette.middleware.gzip import GZipMiddleware

# GZip compression for responses > 500 bytes (reduces bandwidth 60-80%)
app.add_middleware(GZipMiddleware, minimum_size=500)

# Skip BaseHTTPMiddleware stack during testing — these cause anyio.WouldBlock
# with sync TestClient due to a known Starlette compatibility issue.
if not os.environ.get("TESTING"):
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(XSSMiddleware)
    app.add_middleware(TracingMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    # Rate limiting - strict in production, relaxed for development
    limit = 200 if settings.ENVIRONMENT == "production" else 6000
    app.add_middleware(RateLimitMiddleware, requests_per_minute=limit, burst_size=50 if settings.ENVIRONMENT == "production" else 100)

# CORS (Added last to be outermost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_api_version_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-API-Version"] = settings.VERSION
    return response


# Prometheus Instrumentation
from prometheus_fastapi_instrumentator import Instrumentator

instrumentator = Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_respect_env_var=True,
    should_instrument_requests_inprogress=True,
    excluded_handlers=[".*metrics"],
    env_var_name="ENABLE_METRICS",
    inprogress_name="http_requests_inprogress",
    inprogress_labels=True,
)

@app.on_event("startup")
async def startup_event():
    instrumentator.instrument(app).expose(
        app, endpoint="/api/v1/monitoring/metrics", tags=["monitoring"]
    )

    # --- Resilient background task runner ---
    async def run_with_recovery(name: str, coro_fn, interval_seconds: int):
        """
        Crash-recovery wrapper for background loops.
        - Retries on unhandled exceptions (with exponential backoff, max 5 min)
        - Uses Redis distributed lock so only one replica runs each loop
        - Gracefully stops on CancelledError
        """
        import structlog
        _log = structlog.get_logger(f"nomadnest.bg.{name}")
        backoff = 60  # seconds

        # Try to acquire distributed lock via Redis
        try:
            from backend.utils.cache import redis_client as _redis
        except ImportError:
            _redis = None

        while True:
            try:
                # Distributed lock: only one replica runs this loop
                if _redis:
                    lock_key = f"bg_lock:{name}"
                    acquired = await _redis.set(lock_key, "1", ex=interval_seconds + 30, nx=True)
                    if not acquired:
                        _log.debug("bg_lock_held_by_another_replica", task=name)
                        await asyncio.sleep(interval_seconds)
                        continue

                await asyncio.sleep(interval_seconds)
                await coro_fn()

                # Renew lock after successful run
                if _redis:
                    await _redis.set(lock_key, "1", ex=interval_seconds + 30)

                backoff = 60  # reset backoff on success

            except asyncio.CancelledError:
                _log.info("bg_task_cancelled", task=name)
                break
            except Exception as e:
                _log.error("bg_task_error", task=name, error=str(e), retry_in=backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 300)  # exponential backoff, max 5 min

    # --- Proactive AI: push notifications ---
    async def _proactive_cycle():
        from backend.services.proactive_ai import generate_proactive_notifications
        from backend.socket_server import emit_proactive_insight
        from backend.database import get_db_context
        from backend import models as _m

        with get_db_context() as db:
            users = db.query(_m.User).filter(
                _m.User.created_at > __import__('datetime').datetime.utcnow() - __import__('datetime').timedelta(days=30)
            ).limit(100).all()
            user_ids = [u.id for u in users]

        for uid in user_ids:
            try:
                notifications = await generate_proactive_notifications(uid)
                for notif in notifications:
                    await emit_proactive_insight(uid, notif)
            except Exception:
                pass  # individual user failures shouldn't kill the loop

    asyncio.create_task(run_with_recovery("proactive_ai", _proactive_cycle, 3600))

    # --- Serendipity Engine: periodic connection suggestions ---
    async def _serendipity_cycle():
        from backend.services.serendipity import create_serendipity_notifications
        from backend.database import get_db_context
        from backend import models as _m

        with get_db_context() as db:
            users = db.query(_m.User).limit(100).all()
            user_ids = [u.id for u in users]

        for uid in user_ids:
            try:
                create_serendipity_notifications(uid)
            except Exception:
                pass

    asyncio.create_task(run_with_recovery("serendipity", _serendipity_cycle, 3600))

    # --- Stuck Job Reaper: clean up hung agent jobs ---
    async def _reaper_cycle():
        from backend.tasks.stuck_job_reaper import reap_stuck_jobs
        reap_stuck_jobs()

    asyncio.create_task(run_with_recovery("stuck_job_reaper", _reaper_cycle, 300))

    # --- Ensure dynamic tables exist (needed for session/cache fallbacks) ---
    try:
        from backend.models import (
            UserSession, AICacheEntry,
            TokenStake, TreasuryAllocation, HubFinancials, BuybackOrder,
        )
        from backend.models_civic import (
            InfrastructureProject, SolutionListing, ProjectSolution,
            CommunityRFP, VendorProposal, ImpactMetric,
        )
        from backend.database import engine
        for tbl in [
            UserSession, AICacheEntry, TokenStake, TreasuryAllocation, HubFinancials, BuybackOrder,
            InfrastructureProject, SolutionListing, ProjectSolution,
            CommunityRFP, VendorProposal, ImpactMetric,
        ]:
            tbl.__table__.create(bind=engine, checkfirst=True)
    except Exception as e:
        logger.debug("dynamic_table_check", note=str(e))

    # --- AI Cache Cleanup: purge expired entries periodically ---
    async def _cache_cleanup_cycle():
        from backend.services.ai_cache import _db_cleanup_expired
        _db_cleanup_expired()

    asyncio.create_task(run_with_recovery("ai_cache_cleanup", _cache_cleanup_cycle, 3600))


@app.get("/")
def read_root():
    return {"message": "Welcome to FutureStack — Civic Infrastructure Tech Marketplace", "version": settings.VERSION}


# Import and register routers
from backend.routers import (
    auth,
    listings,
    concierge,
    users,
    bookings,
    hubs,
    experiences,
    notifications,
    availability,
    oauth,
    pricing,
    neighborhoods,
    tasks,
    reviews,
    subscriptions,
    skills,
    journeys,
    negotiations,
    analytics,
    hub_intel,
    creator,
    ar,
    web3,
    dao,
    agent_jobs,
    investments,
    ota,
    search,
    ai_proxy,
    monitoring,
    health,
    messages,
    applications,
    services,
    events,
    culture,
    passport,
    networks,
)
from backend.routers import enrichment as enrichment_router

# Health
app.include_router(health.router, tags=["health"])

# Auth routes
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(oauth.router, prefix="/api/v1/auth", tags=["oauth"])

# Monitoring
app.include_router(monitoring.router, prefix="/api/v1/monitoring", tags=["monitoring"])

# Admin & Security
from backend.routers import admin
from backend.routers import admin_backup
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(admin_backup.router, prefix="/api/v1", tags=["admin", "backup"])

# Core resources
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(listings.router, prefix="/api/v1/listings", tags=["listings"])
app.include_router(bookings.router, prefix="/api/v1/bookings", tags=["bookings"])
app.include_router(ota.router, prefix="/api/v1/ota", tags=["ota"])
app.include_router(hubs.router, prefix="/api/v1/hubs", tags=["hubs"])
app.include_router(
    experiences.router, prefix="/api/v1/experiences", tags=["experiences"]
)
app.include_router(
    neighborhoods.router, prefix="/api/v1/neighborhoods", tags=["neighborhoods"]
)

# Community
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(reviews.router, prefix="/api/v1/reviews", tags=["reviews"])
app.include_router(skills.router, prefix="/api/v1/skills", tags=["skills"])

# Features
app.include_router(
    notifications.router, prefix="/api/v1/notifications", tags=["notifications"]
)
app.include_router(
    availability.router, prefix="/api/v1/availability", tags=["availability"]
)
app.include_router(pricing.router, prefix="/api/v1/pricing", tags=["pricing"])
app.include_router(concierge.router, prefix="/api/v1/concierge", tags=["concierge"])

# Phase 7: 100x Features
app.include_router(
    subscriptions.router, prefix="/api/v1/subscriptions", tags=["subscriptions"]
)
app.include_router(journeys.router, prefix="/api/v1/journeys", tags=["journeys"])
app.include_router(
    negotiations.router, prefix="/api/v1/negotiations", tags=["negotiations"]
)

# Phase 8: Backlog Features
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
app.include_router(hub_intel.router, prefix="/api/v1/hub-intel", tags=["hub-intel"])
app.include_router(creator.router, prefix="/api/v1/creator", tags=["creator"])

# Cultural Experiences & Nomad Passport (Quantum Temple Inspired)
app.include_router(culture.router, prefix="/api/v1/culture", tags=["culture"])
app.include_router(passport.router, prefix="/api/v1/passport", tags=["passport"])

# Co-Living Networks & Partnerships
app.include_router(networks.router, prefix="/api/v1/networks", tags=["networks"])

# Phase 9: Future Tech Features
app.include_router(ar.router, prefix="/api/v1/ar", tags=["ar"])
app.include_router(web3.router, prefix="/api/v1/web3", tags=["web3"])
app.include_router(dao.router, prefix="/api/v1/dao", tags=["dao"])

# AI Agent Jobs (Browser Automation)
app.include_router(agent_jobs.router, prefix="/api/v1/agent-jobs", tags=["agent-jobs"])

# Enrichment & Data Pipeline
app.include_router(enrichment_router.router, prefix="/api/v1/enrichment", tags=["enrichment"])

# Micro-Investments
app.include_router(
    investments.router, prefix="/api/v1/investments", tags=["investments"]
)

# --- Civic Infrastructure Verticals ---
from backend.routers import infrastructure, marketplace, rfp, impact, advisor, calculators
app.include_router(infrastructure.router, prefix="/api/v1/infra", tags=["infrastructure"])
app.include_router(marketplace.router, prefix="/api/v1/marketplace", tags=["marketplace"])
app.include_router(rfp.router, prefix="/api/v1/rfp", tags=["rfp"])
app.include_router(impact.router, prefix="/api/v1/impact", tags=["impact"])
app.include_router(advisor.router, prefix="/api/v1/infra", tags=["advisor"])
app.include_router(calculators.router, prefix="/api/v1/infra", tags=["calculators"])

# Search
app.include_router(search.router, prefix="/api/v1/search", tags=["search"])

# Rust Crawler Engine (OTA Search + Security)
from backend.routers import crawler as crawler_router
app.include_router(crawler_router.router, prefix="/api/v1/crawler", tags=["crawler"])

# AI Proxy
app.include_router(ai_proxy.router, prefix="/api/v1/ai", tags=["ai"])

# Phase 13: Messaging & Applications
app.include_router(messages.router, prefix="/api/v1", tags=["messages"])
app.include_router(applications.router, prefix="/api/v1", tags=["applications"])

# Services & Events
app.include_router(services.router, tags=["services"])
app.include_router(events.router, tags=["events"])

# Human-in-the-Loop Escalations
from backend.routers import escalations
app.include_router(escalations.router, prefix="/api/v1", tags=["escalations"])

# Notification Preferences
from backend.routers import notification_preferences
app.include_router(notification_preferences.router, prefix="/api/v1/notifications/preferences", tags=["notifications"])

# Networks (Co-Living Partnerships) - Already registered above at /api/v1/networks (line 287)
# Duplicate registration removed: was using prefix="/api/v1" which caused /{network_id}
# to intercept ALL /api/v1/* paths (e.g. /api/v1/users → "Network not found").



# Wallet (Web3 Transactions)
from backend.routers import wallet
app.include_router(wallet.router, prefix="/api/v1", tags=["wallet"])

# SBTs (Achievement Badges)
from backend.routers import sbts
app.include_router(sbts.router, prefix="/api/v1", tags=["sbts"])

# Contribution Pathways (Gamification)
from backend.routers import pathways
app.include_router(pathways.router, prefix="/api/v1", tags=["pathways"])

# Waitlist
from backend.routers import waitlist
app.include_router(waitlist.router, prefix="/api/v1", tags=["waitlist"])

# Campaigns (Marketing)
from backend.routers import campaigns
app.include_router(campaigns.router, prefix="/api/v1", tags=["campaigns"])



# Premium Media (Voice & Avatar)
from backend.routers import premium_media
app.include_router(premium_media.router, prefix="/api/v1", tags=["premium-media"])

# Revenue & Affiliates
from backend.routers import revenue, affiliates
app.include_router(revenue.router, prefix="/api/v1/revenue", tags=["revenue"])
app.include_router(affiliates.router, prefix="/api/v1/affiliates", tags=["affiliates"])

# $NEST Token
from backend.routers import nest
app.include_router(nest.router, prefix="/api/v1/nest", tags=["nest-token"])

# Growth Analytics
from backend.routers import growth
app.include_router(growth.router, prefix="/api/v1/growth", tags=["growth"])


# Server-Sent Events (Replaced Socket.IO for Cloud Run compatibility)
# ============================================================================

from backend.routers import sse
app.include_router(sse.router, prefix="/api/v1", tags=["sse"])


# WOW Features: Quick Wins
# ============================================================================

from backend.routers import price_alerts
app.include_router(price_alerts.router, tags=["price-alerts"])

from backend.routers import cost_of_living
app.include_router(cost_of_living.router, tags=["cost-of-living"])

from backend.routers import nomad_map
app.include_router(nomad_map.router, tags=["nomad-map"])

from backend.routers import visa
app.include_router(visa.router, tags=["visa"])

from backend.routers import social
app.include_router(social.router, tags=["social"])

from backend.routers import trips
app.include_router(trips.router, tags=["trips"])

from backend.routers import coworking
app.include_router(coworking.router, tags=["coworking"])

from backend.routers import autonomous
app.include_router(autonomous.router, tags=["autonomous"])

# (duplicate price_alerts registration removed — already registered on line 409)

from backend.routers import video_tours
app.include_router(video_tours.router, tags=["video-tours"])

# ============================================================================
# WebSocket Support (Socket.IO with Redis adapter for horizontal scaling)
# ============================================================================
from backend.socket_server import socket_app
app.mount("/ws", socket_app)
