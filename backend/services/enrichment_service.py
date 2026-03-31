"""
Enrichment Service.
Syncs scraped wellness retreat data from CSV into the database listings.
"""
import csv
import datetime
import json
import re
import structlog
from pathlib import Path
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from backend.database import engine, SessionLocal, IS_SQLITE
from backend import models

logger = structlog.get_logger("nomadnest.enrichment")


def get_db() -> Session:
    """Get database session with SQLite WAL mode for concurrent access."""
    db = SessionLocal()
    if IS_SQLITE:
        try:
            db.execute(models.Base.metadata.tables['listings'].select().limit(0))
        except Exception:
            pass
    return db


def load_enriched_csv(csv_path: str = None) -> List[Dict]:
    """Load enriched retreat data from CSV."""
    if csv_path is None:
        csv_path = Path(__file__).resolve().parents[2] / "data" / "enriched_retreats.csv"
    else:
        csv_path = Path(csv_path)
    
    if not csv_path.exists():
        logger.error("enriched_csv_not_found", path=str(csv_path))
        return []
    
    retreats = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                retreats.append(row)
        logger.info("csv_loaded", count=len(retreats), path=str(csv_path))
    except Exception as e:
        logger.error("csv_read_error", error=str(e), path=str(csv_path))
    
    return retreats


def parse_list_field(value: str) -> List[str]:
    """Parse a stringified list field from CSV."""
    if not value or value == "":
        return []
    try:
        # Try JSON parsing first
        return json.loads(value.replace("'", '"'))
    except:
        # Fall back to comma separation
        return [v.strip() for v in value.split(",") if v.strip()]


def parse_json_field(value: str) -> Dict:
    """Parse a stringified JSON field from CSV."""
    if not value or value == "":
        return {}
    try:
        return json.loads(value.replace("'", '"'))
    except:
        return {}


def find_or_create_listing(db: Session, retreat_data: Dict) -> Optional[models.Listing]:
    """Find existing listing by name/URL or create a new one."""
    place_name = retreat_data.get("place_name", "").strip()
    source_url = retreat_data.get("source_url", "").strip()
    
    if not place_name:
        return None
    
    # Try exact substring match first
    existing = db.query(models.Listing).filter(
        models.Listing.name.ilike(f"%{place_name}%")
    ).first()
    
    if existing:
        return existing
    
    # Try matching by significant words in name (3+ chars, not common words)
    stop_words = {'the', 'and', 'for', 'stay', 'at', 'exclusive', 'in', 'of', 'a', 'an'}
    words = [w for w in re.split(r'\W+', place_name.lower()) if len(w) >= 3 and w not in stop_words]
    for word in words:
        match = db.query(models.Listing).filter(
            models.Listing.name.ilike(f"%{word}%")
        ).first()
        if match:
            return match
    
    # Create new listing
    slug = re.sub(r'\W+', '-', place_name.lower())[:30]
    listing_id = f"listing-enriched-{slug}"
    
    # Check if this ID already exists
    existing_by_id = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if existing_by_id:
        return existing_by_id
    
    # Extract city/country from address if available
    address = retreat_data.get("address", "")
    city, country = "", ""
    if address:
        parts = [p.strip() for p in address.split(",")]
        if len(parts) >= 2:
            city = parts[-2] if len(parts) >= 2 else ""
            country = parts[-1] if parts else ""
        elif len(parts) == 1:
            country = parts[0]
    
    new_listing = models.Listing(
        id=listing_id,
        owner_id="user-1",
        name=place_name,
        description=retreat_data.get("description_long", retreat_data.get("page_summary", ""))[:500],
        property_type="Wellness Retreat",
        city=city,
        country=country,
        price_usd=0.0,
        features=[],
        images=parse_list_field(retreat_data.get("image_urls", ""))[:5],
        guest_capacity=2,
        bedrooms=1,
        bathrooms=1,
    )
    db.add(new_listing)
    return new_listing


def enrich_listing(listing: models.Listing, retreat_data: Dict) -> None:
    """Apply enrichment data to a listing."""
    # Booking URL (prioritize first booking link, skip mailto)
    booking_links = parse_list_field(retreat_data.get("booking_links", ""))
    http_links = [l for l in booking_links if l.startswith("http")]
    if http_links:
        listing.booking_url = http_links[0]
    elif booking_links:
        listing.booking_url = booking_links[0]
    elif not listing.booking_url:
        source_url = retreat_data.get("source_url", "")
        if source_url:
            listing.booking_url = source_url
    
    # Scraped amenities
    amenities = parse_list_field(retreat_data.get("amenities", ""))
    if amenities:
        listing.scraped_amenities = amenities
    
    # Price range (first price found)
    prices = parse_list_field(retreat_data.get("program_prices", ""))
    if prices:
        listing.price_range = prices[0]
    
    # Program names
    programs = parse_list_field(retreat_data.get("program_names", ""))
    if programs:
        listing.program_names = programs[:5]
    
    # Upcoming dates
    dates = parse_list_field(retreat_data.get("upcoming_dates", ""))
    if dates:
        listing.upcoming_dates = dates[:10]
    
    # Social links
    social = parse_json_field(retreat_data.get("social_links", ""))
    if social:
        listing.social_links = social
    
    # Update images — only if listing has NO images; preserve existing Unsplash images
    images = parse_list_field(retreat_data.get("image_urls", ""))
    # Filter to only valid image URLs
    valid_images = [img for img in images if img.startswith("http") and not any(x in img.lower() for x in ["pixel", "spacer", ".svg", "1x1", "blank"])]
    current_images = listing.images or []
    # Only add scraped images if listing has NO existing images at all
    if valid_images and not current_images:
        listing.images = valid_images[:6]
    
    # Update description if richer
    description = retreat_data.get("description_long", "")
    if description and (not listing.description or len(description) > len(listing.description or "")):
        listing.description = description[:1000]
    
    # Extract city/country from address if not set
    address = retreat_data.get("address", "")
    if address and not listing.city:
        parts = [p.strip() for p in address.split(",")]
        if len(parts) >= 2:
            listing.city = parts[-2]
            listing.country = parts[-1]
    
    # Mark as enriched
    listing.last_enriched_at = datetime.datetime.now(datetime.timezone.utc)


def sync_enriched_data(csv_path: str = None) -> Dict:
    """
    Main enrichment function: Load CSV and update database listings.
    Returns stats on what was updated.
    """
    db = get_db()
    stats = {"loaded": 0, "updated": 0, "created": 0, "failed": 0}
    
    try:
        retreats = load_enriched_csv(csv_path)
        stats["loaded"] = len(retreats)
        
        for retreat_data in retreats:
            try:
                listing = find_or_create_listing(db, retreat_data)
                if listing:
                    was_new = listing.last_enriched_at is None and listing.booking_url is None
                    enrich_listing(listing, retreat_data)
                    
                    if was_new:
                        stats["created"] += 1
                    else:
                        stats["updated"] += 1
                else:
                    stats["failed"] += 1
            except Exception as e:
                logger.warning("enrichment_item_error", place=retreat_data.get('place_name', 'unknown'), error=str(e))
                stats["failed"] += 1
        
        db.commit()
        logger.info("enrichment_complete", **stats)
        
    except Exception as e:
        logger.error("enrichment_failed", error=str(e), exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()
    
    return stats


def get_enriched_listings(db: Session = None) -> List[Dict]:
    """Get all listings that have enrichment data (booking_url populated)."""
    should_close = False
    if db is None:
        db = get_db()
        should_close = True
    
    try:
        listings = db.query(models.Listing).filter(
            models.Listing.booking_url.isnot(None)
        ).all()
        
        return [
            {
                "id": l.id,
                "name": l.name,
                "booking_url": l.booking_url,
                "amenities": l.scraped_amenities or [],
                "programs": l.program_names or [],
                "dates": l.upcoming_dates or [],
                "price_range": l.price_range,
            }
            for l in listings
        ]
    finally:
        if should_close:
            db.close()


if __name__ == "__main__":
    import sys
    csv_path = sys.argv[1] if len(sys.argv) > 1 else None
    sync_enriched_data(csv_path)
