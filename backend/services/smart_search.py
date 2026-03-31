import json
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, cast, String, func
from backend.models import Listing
from backend.database import get_db
import structlog
import litellm
from litellm import completion
import os

logger = structlog.get_logger("nomadnest.smart_search")

# Drop incompatible params for Gemini
litellm.drop_params = True


class SmartSearchService:
    def __init__(self):
        self.model = "gemini/gemini-2.0-flash-exp"

    def _extract_filters(self, query: str) -> dict:
        """
        Uses an LLM to extract structured filters from a natural language query.
        """
        system_prompt = """
        You are an intelligent search assistant for a travel platform.
        Extract search filters from the user's natural language query.
        
        Available fields to filter on:
        - min_price: float
        - max_price: float
        - location: str (city or country)
        - amenities: list[str] (e.g., "wifi", "pool", "kitchen")
        - keywords: list[str] (general keywords to match against description/name)
        
        Return a JSON object with these keys. If a field is not mentioned, use null.
        
        Example: "I want a cheap place in Bali with a pool under $500"
        Output: {
            "min_price": null,
            "max_price": 500,
            "location": "Bali",
            "amenities": ["pool"],
            "keywords": ["cheap"]
        }
        """

        try:
            response = completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query},
                ],
            )
            content = response.choices[0].message.content

            # Clean up potential markdown code blocks
            if "```json" in content:
                content = content.replace("```json", "").replace("```", "")
            elif "```" in content:
                content = content.replace("```", "")

            return json.loads(content)
        except Exception as e:
            logger.error("filter_extraction_failed", error=str(e))
            # Fallback to mostly empty filters if LLM fails
            return {
                "keywords": [query],
                "min_price": None,
                "max_price": None,
                "location": None,
                "amenities": [],
            }

    def search_listings(self, query: str, db: Session) -> List[Listing]:
        """
        Performs a smart search on listings using extracted filters.
        """
        filters = self._extract_filters(query)
        logger.info("search_filters_extracted", query=query, filters=filters)

        query_db = db.query(Listing)

        # Apply Location Filter
        if filters.get("location"):
            loc = filters["location"].lower()
            query_db = query_db.filter(
                or_(
                    func.lower(Listing.city).contains(loc),
                    func.lower(Listing.country).contains(loc),
                )
            )

        # Apply Price Filters
        if filters.get("min_price") is not None:
            query_db = query_db.filter(Listing.price_usd >= filters["min_price"])

        if filters.get("max_price") is not None:
            query_db = query_db.filter(Listing.price_usd <= filters["max_price"])

        # Apply Amenities Filter
        if filters.get("amenities"):
            for amenity in filters["amenities"]:
                # Simple string matching on the array elements
                query_db = query_db.filter(
                    cast(Listing.features, String).ilike(f"%{amenity}%")
                )

        # Apply Keywords matching (Name & Description)
        if filters.get("keywords"):
            for keyword in filters["keywords"]:
                kw = keyword.lower()
                query_db = query_db.filter(
                    or_(
                        func.lower(Listing.name).contains(kw),
                        func.lower(Listing.description).contains(kw),
                    )
                )

        return query_db.all()


# Singleton instance
smart_search_service = SmartSearchService()
