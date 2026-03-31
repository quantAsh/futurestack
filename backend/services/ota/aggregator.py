import asyncio
import os
from typing import List, Dict, Any, Optional
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import desc
import structlog

from backend.services.ota.providers.base import BaseOTAProvider, OTASearchResult
from backend.services.ota.providers.native import NativeProvider
from backend.services.ota.providers.manual import ManualProvider
from backend.utils.circuit_breaker import get_breaker, with_retry, CircuitOpenError
from backend import models

logger = structlog.get_logger("nomadnest.ota")


class AggregatorService:
    def __init__(self, db: Session):
        self.db = db
        self.providers: List[BaseOTAProvider] = self._init_providers()

    def _init_providers(self) -> List[BaseOTAProvider]:
        """Initialize all active providers from DB configuration"""
        providers = []

        # 1. Native Provider (Always active)
        providers.append(NativeProvider("native", {}, self.db))

        # 2. Manual/Partner Providers
        # Fetch active providers from DB
        db_providers = (
            self.db.query(models.OTAProvider)
            .filter(
                models.OTAProvider.is_active == True,
                models.OTAProvider.type == "affiliate",
            )
            .all()
        )

        for p in db_providers:
            providers.append(
                ManualProvider(p.id, {"commission_rate": p.commission_rate}, self.db)
            )

        # 3. Browser Provider — scrapes real Booking.com search results
        try:
            from backend.services.ota.providers.browser import BrowserProvider
            providers.append(BrowserProvider("booking_com", {"headless": True}))
            logger.info("booking_com_provider_enabled")
        except ImportError:
            logger.warning("playwright_not_installed", msg="Booking.com provider disabled")

        return providers

    async def _search_with_circuit_breaker(
        self,
        provider: BaseOTAProvider,
        location: str,
        check_in: date,
        check_out: date,
        guests: int,
        currency: str,
    ) -> List[OTASearchResult]:
        """
        Search a provider with circuit breaker and retry protection.
        """
        breaker = get_breaker(
            f"ota_{provider.name}",
            failure_threshold=5,
            recovery_timeout=60,
        )

        try:
            # Use circuit breaker with exponential backoff
            result = await breaker.call(
                with_retry,
                provider.search,
                location, check_in, check_out, guests, currency,
                max_retries=3,
                base_delay=1.0,
            )
            return result or []

        except CircuitOpenError:
            logger.warning(
                "ota_circuit_open",
                provider=provider.name,
                message="Circuit breaker open, skipping provider"
            )
            return []

        except Exception as e:
            logger.error(
                "ota_provider_error",
                provider=provider.name,
                error=str(e)
            )
            return []

    async def aggregate_search(
        self,
        location: str,
        check_in: date,
        check_out: date,
        guests: int = 1,
        currency: str = "USD",
        max_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Search all providers in parallel with circuit breaker protection.
        """
        search_tasks = [
            self._search_with_circuit_breaker(
                p, location, check_in, check_out, guests, currency
            )
            for p in self.providers
        ]

        # Run in parallel
        results_list = await asyncio.gather(*search_tasks, return_exceptions=True)

        unified_results: List[OTASearchResult] = []
        providers_succeeded = []

        for provider, res in zip(self.providers, results_list):
            if isinstance(res, Exception):
                logger.error("ota_aggregation_error", provider=provider.name, error=str(res))
                continue
            if res:
                unified_results.extend(res)
                providers_succeeded.append(provider.name)

        # Filter by price if needed
        if max_price:
            unified_results = [r for r in unified_results if r.total_price <= max_price]

        # Rank/Sort results by price
        unified_results.sort(key=lambda x: x.total_price)

        return {
            "results": [r.dict() for r in unified_results],
            "total_found": len(unified_results),
            "providers_searched": [p.name for p in self.providers],
            "providers_succeeded": providers_succeeded,
        }

