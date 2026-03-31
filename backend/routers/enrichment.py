"""
Enrichment & Data Pipeline Router.
Provides endpoints to trigger CSV enrichment sync, check status, and run crawlers.
Requires admin authentication for all operations.
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from typing import Optional
from sqlalchemy.orm import Session
from backend.services.enrichment_service import sync_enriched_data, get_enriched_listings, load_enriched_csv
from backend.services.crawler import crawler_service, crawl_and_store
from backend.database import SessionLocal, get_db
from backend.utils import get_current_user
from backend import models

router = APIRouter()
logger = structlog.get_logger("nomadnest.enrichment")


def get_current_admin(current_user: models.User = Depends(get_current_user)):
    """Require admin privileges for enrichment operations."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


@router.get("/status")
def enrichment_status(admin: models.User = Depends(get_current_admin)):
    """Get enrichment statistics — how many listings are enriched."""
    db = SessionLocal()
    try:
        total = db.query(models.Listing).count()
        enriched = db.query(models.Listing).filter(
            models.Listing.booking_url.isnot(None)
        ).count()
        with_amenities = db.query(models.Listing).filter(
            models.Listing.scraped_amenities.isnot(None)
        ).count()
        csv_rows = len(load_enriched_csv())

        return {
            "total_listings": total,
            "enriched_count": enriched,
            "with_amenities": with_amenities,
            "csv_available": csv_rows,
            "enrichment_coverage": f"{(enriched / total * 100):.1f}%" if total > 0 else "0%",
        }
    finally:
        db.close()


@router.post("/sync")
async def trigger_enrichment_sync(
    csv_path: Optional[str] = None,
    admin: models.User = Depends(get_current_admin),
):
    """
    Re-run enrichment: load enriched_retreats.csv and sync into DB.
    Updates booking_url, amenities, prices, dates, images, social links.
    """
    try:
        logger.info("enrichment_sync_triggered", admin_id=admin.id, csv_path=csv_path)
        stats = sync_enriched_data(csv_path)
        return {
            "status": "completed",
            "stats": stats,
        }
    except Exception as e:
        logger.error("enrichment_sync_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Enrichment failed: {str(e)}")


@router.get("/listings")
async def get_bookable_listings(admin: models.User = Depends(get_current_admin)):
    """Get all enriched listings that have booking URLs."""
    db = SessionLocal()
    try:
        listings = get_enriched_listings(db)
        return {
            "count": len(listings),
            "listings": listings,
        }
    finally:
        db.close()


@router.post("/crawl/{location}")
async def crawl_location(
    location: str,
    background_tasks: BackgroundTasks,
    admin: models.User = Depends(get_current_admin),
):
    """
    Trigger a crawl for a specific location across all platform crawlers.
    Returns results from NomadList and Colivid sources.
    """
    try:
        logger.info("crawl_triggered", admin_id=admin.id, location=location)
        results = await crawler_service.search_combined(location)
        return {
            "location": location,
            "results_count": len(results),
            "results": [r.to_dict() for r in results],
        }
    except Exception as e:
        logger.error("crawl_failed", location=location, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Crawl failed: {str(e)}")


@router.post("/seed-visa")
def seed_visa_data(admin: models.User = Depends(get_current_admin)):
    """Seed expanded visa requirements (10 passports × 17 destinations)."""
    import uuid
    db = SessionLocal()
    try:
        VISA = [
            ("United States","US","Italy","IT","visa_free",90,1,1,1,12,2800,116,"Italy DNV launched 2024."),
            ("United States","US","Greece","GR","visa_free",90,1,1,1,12,3500,75,"Greece DNV."),
            ("United States","US","Croatia","HR","visa_free",90,1,1,1,12,2540,55,"Croatia DNV."),
            ("United States","US","Estonia","EE","visa_free",90,1,1,1,12,4500,100,"Estonia e-Residency + DNV."),
            ("United States","US","Czech Republic","CZ","visa_free",90,1,1,1,12,3000,100,"Czech DNV launched 2024."),
            ("United States","US","Costa Rica","CR","visa_free",90,0,0,1,12,3000,100,"Rentista Digital Nomad visa."),
            ("United States","US","Malaysia","MY","visa_free",90,0,0,1,12,2000,218,"DE Rantau Pass."),
            ("United States","US","New Zealand","NZ","visa_free",90,0,0,0,None,None,None,"NZeTA required."),
            ("United Kingdom","GB","Italy","IT","visa_free",90,1,1,1,12,2800,116,None),
            ("United Kingdom","GB","Greece","GR","visa_free",90,1,1,1,12,3500,75,None),
            ("United Kingdom","GB","Croatia","HR","visa_free",90,1,1,1,12,2540,55,None),
            ("United Kingdom","GB","Colombia","CO","visa_free",90,0,0,1,24,3000,200,None),
            ("United Kingdom","GB","Malaysia","MY","visa_free",90,0,0,1,12,2000,218,None),
            ("India","IN","Spain","ES","visa_required",None,1,0,1,12,2646,80,None),
            ("India","IN","Malaysia","MY","e_visa",30,0,0,1,12,2000,218,None),
            ("India","IN","Colombia","CO","visa_free",90,0,0,1,24,3000,200,None),
            ("India","IN","Mexico","MX","visa_required",None,0,0,0,None,None,None,"Visa required."),
            ("Canada","CA","Spain","ES","visa_free",90,1,0,1,12,2646,80,None),
            ("Canada","CA","Colombia","CO","visa_free",180,0,0,1,24,3000,200,None),
            ("Canada","CA","Costa Rica","CR","visa_free",90,0,0,1,12,3000,100,None),
            ("Canada","CA","Croatia","HR","visa_free",90,1,0,1,12,2540,55,None),
            ("Australia","AU","Spain","ES","visa_free",90,1,0,1,12,2646,80,None),
            ("Australia","AU","Colombia","CO","visa_free",90,0,0,1,24,3000,200,None),
            ("Australia","AU","New Zealand","NZ","visa_free",90,0,0,0,None,None,None,"Unlimited NZ rights."),
            ("Germany","DE","Portugal","PT","visa_free",90,1,1,1,12,3280,75,"EU freedom of movement."),
            ("Germany","DE","Spain","ES","visa_free",90,1,1,1,12,2646,80,None),
            ("Germany","DE","Thailand","TH","visa_free",60,0,0,1,12,2500,50,None),
            ("Germany","DE","Indonesia","ID","visa_on_arrival",30,0,0,1,12,2000,200,None),
            ("Germany","DE","Mexico","MX","visa_free",180,0,0,0,None,None,None,None),
            ("Germany","DE","Colombia","CO","visa_free",90,0,0,1,24,3000,200,None),
            ("Germany","DE","Georgia","GE","visa_free",365,0,0,1,12,0,0,None),
            ("Germany","DE","UAE","AE","visa_on_arrival",90,0,0,1,12,5000,611,None),
            ("France","FR","Portugal","PT","visa_free",90,1,1,1,12,3280,75,None),
            ("France","FR","Thailand","TH","visa_free",60,0,0,1,12,2500,50,None),
            ("France","FR","Indonesia","ID","visa_on_arrival",30,0,0,1,12,2000,200,None),
            ("France","FR","Mexico","MX","visa_free",180,0,0,0,None,None,None,None),
            ("France","FR","Colombia","CO","visa_free",90,0,0,1,24,3000,200,None),
            ("France","FR","Georgia","GE","visa_free",365,0,0,1,12,0,0,None),
            ("Brazil","BR","Portugal","PT","visa_free",90,1,0,1,12,3280,75,"CPLP pact."),
            ("Brazil","BR","Spain","ES","visa_free",90,1,0,1,12,2646,80,None),
            ("Brazil","BR","Mexico","MX","visa_free",180,0,0,0,None,None,None,None),
            ("Brazil","BR","Colombia","CO","visa_free",90,0,0,1,24,3000,200,None),
            ("Brazil","BR","Georgia","GE","visa_free",365,0,0,1,12,0,0,None),
            ("Brazil","BR","Thailand","TH","visa_free",60,0,0,1,12,2500,50,None),
            ("Brazil","BR","UAE","AE","visa_on_arrival",30,0,0,1,12,5000,611,None),
            ("Japan","JP","Portugal","PT","visa_free",90,1,0,1,12,3280,75,None),
            ("Japan","JP","Spain","ES","visa_free",90,1,0,1,12,2646,80,None),
            ("Japan","JP","Thailand","TH","visa_free",60,0,0,1,12,2500,50,None),
            ("Japan","JP","Indonesia","ID","visa_on_arrival",30,0,0,1,12,2000,200,None),
            ("Japan","JP","Mexico","MX","visa_free",180,0,0,0,None,None,None,None),
            ("Japan","JP","Georgia","GE","visa_free",365,0,0,1,12,0,0,None),
            ("Japan","JP","UAE","AE","visa_on_arrival",30,0,0,1,12,5000,611,None),
            ("Nigeria","NG","Portugal","PT","visa_required",None,1,0,1,12,3280,75,"Schengen visa req. DNV available."),
            ("Nigeria","NG","Spain","ES","visa_required",None,1,0,1,12,2646,80,None),
            ("Nigeria","NG","Thailand","TH","visa_required",None,0,0,1,12,2500,50,None),
            ("Nigeria","NG","Indonesia","ID","visa_on_arrival",30,0,0,1,12,2000,200,None),
            ("Nigeria","NG","Georgia","GE","e_visa",30,0,0,1,12,0,0,None),
            ("Nigeria","NG","Colombia","CO","visa_free",90,0,0,1,24,3000,200,None),
            ("Nigeria","NG","Mexico","MX","visa_required",None,0,0,0,None,None,None,None),
            ("Nigeria","NG","UAE","AE","e_visa",30,0,0,1,12,5000,611,None),
        ]
        created = updated = 0
        for r in VISA:
            pp, pc, d, dc, vt, dur, s, eu, dnv, dm, di, dcst, n = r
            existing = db.query(models.VisaRequirement).filter(
                models.VisaRequirement.passport_country_code == pc,
                models.VisaRequirement.destination_country_code == dc,
            ).first()
            if existing:
                existing.visa_type = vt
                existing.duration_days = dur
                existing.is_schengen = bool(s)
                existing.is_eu = bool(eu)
                existing.dnv_available = bool(dnv)
                existing.dnv_duration_months = dm
                existing.dnv_min_income_usd = di
                existing.dnv_cost_usd = dcst
                existing.notes = n
                updated += 1
            else:
                db.add(models.VisaRequirement(
                    id=str(uuid.uuid4()), passport_country=pp, passport_country_code=pc,
                    destination_country=d, destination_country_code=dc,
                    visa_type=vt, duration_days=dur, is_schengen=bool(s), is_eu=bool(eu),
                    dnv_available=bool(dnv), dnv_duration_months=dm,
                    dnv_min_income_usd=di, dnv_cost_usd=dcst, notes=n,
                ))
                created += 1
        db.commit()
        total = db.query(models.VisaRequirement).count()
        passports = db.query(models.VisaRequirement.passport_country_code).distinct().count()
        destinations = db.query(models.VisaRequirement.destination_country_code).distinct().count()
        return {
            "status": "completed",
            "created": created, "updated": updated, "total": total,
            "passport_countries": passports, "destination_countries": destinations,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Visa seed failed: {str(e)}")
    finally:
        db.close()

