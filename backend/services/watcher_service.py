"""
Watcher Service for Sniper Mode.
Manages search watches and notifies users of new findings.
Persists watches to a JSON file for MVP simplicity.
"""
import json
import os
import asyncio
import structlog
from typing import List, Dict, Optional
from datetime import datetime
from uuid import uuid4
from backend.services.crawler import crawler_service

logger = structlog.get_logger("nomadnest.watcher")

WATCH_FILE = "./data/search_watches.json"

class WatcherService:
    def __init__(self, persistence_file: str = WATCH_FILE):
        self.persistence_file = persistence_file
        self.watches = self._load_watches()
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.persistence_file), exist_ok=True)

    def _load_watches(self) -> Dict[str, dict]:
        """Load watches from file."""
        if not os.path.exists(self.persistence_file):
            return {}
        try:
            with open(self.persistence_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error("load_watches_failed", error=str(e))
            return {}

    def _save_watches(self):
        """Save watches to file."""
        try:
            with open(self.persistence_file, "w") as f:
                json.dump(self.watches, f, indent=2)
        except Exception as e:
            logger.error("save_watches_failed", error=str(e))

    def create_watch(self, user_id: str, criteria: dict) -> dict:
        """Create a new search watch."""
        watch_id = str(uuid4())
        watch = {
            "id": watch_id,
            "user_id": user_id,
            "criteria": criteria,
            "created_at": datetime.utcnow().isoformat(),
            "last_checked_at": None,
            "last_notification_at": None,
            "active": True
        }
        self.watches[watch_id] = watch
        self._save_watches()
        logger.info("watch_created", user_id=user_id, criteria=criteria)
        return watch

    def get_user_watches(self, user_id: str) -> List[dict]:
        """Get all watches for a user."""
        return [w for w in self.watches.values() if w["user_id"] == user_id and w.get("active", True)]

    def delete_watch(self, user_id: str, watch_id: str) -> bool:
        """Delete/Deactivate a watch."""
        if watch_id in self.watches and self.watches[watch_id]["user_id"] == user_id:
            self.watches[watch_id]["active"] = False
            self._save_watches()
            return True
        return False

    async def check_watches(self) -> List[dict]:
        """
        Run searches for all active watches and generate notifications.
        Returns a list of 'notifications' generated.
        """
        notifications = []
        
        for watch_id, watch in self.watches.items():
            if not watch.get("active", True):
                continue
                
            criteria = watch["criteria"]
            location = criteria.get("location")
            if not location:
                continue
                
            logger.info("checking_watch", watch_id=watch_id, location=location)
            
            # Run the crawler
            # In a real system, we'd check for *new* items since last_checked_at
            # Here for MVP, we just search and assume top result matches are worth notifying if price matches
            results = await crawler_service.search_combined(location)
            
            # Simple Filter Logic (e.g. max_price)
            max_price = criteria.get("max_price")
            matches = []
            for item in results:
                price = item.price_per_month
                if price and max_price and price <= max_price:
                    matches.append(item)
                elif not max_price:
                    matches.append(item)
            
            if matches:
                # Mock notification
                top_match = matches[0]
                notification = {
                    "user_id": watch["user_id"],
                    "watch_id": watch_id,
                    "message": f"Sniper Alert! Found {top_match.name} in {location} for ${top_match.price_per_month}/mo. Matches your watch.",
                    "match": top_match.to_dict()
                }
                notifications.append(notification)
                
                # Update timestamp
                watch["last_checked_at"] = datetime.utcnow().isoformat()
                self._save_watches()
        
        return notifications

# Singleton
watcher_service = WatcherService()
