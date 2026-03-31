from sqlalchemy.orm import Session, joinedload
from typing import List
from backend import models, schemas, database
from backend.utils import get_current_user
from fastapi import APIRouter, Depends, HTTPException, status
from uuid import uuid4
from backend.utils.cache import cached, invalidate_cache
import anyio

router = APIRouter()


def get_db():
    yield from database.get_db()


@router.get(
    "/",
    response_model=schemas.PaginatedResponse[schemas.Listing],
    summary="List all listings",
    description="Returns a paginated list of all available co-living spaces with eager-loaded owners. Cached for 5 minutes.",
)
@cached(ttl=300, prefix="listings")
async def read_listings(page: int = 1, size: int = 20, db: Session = Depends(get_db)):
    offset = (page - 1) * size
    
    # We define a sync function to handle the DB part
    def get_listings_sync():
        # Simple query without eager loading to avoid null relationship issues
        query = db.query(models.Listing)
        total = query.count()
        items = query.offset(offset).limit(size).all()
        # We need to manually convert items to serializable dicts if needed,
        # but schemas.PaginatedResponse and Pydantic will handle it for the response.
        # However, our @cached decorator uses json.dumps which needs serializable data.
        # So we should convert to Pydantic objects or dicts here.
        return {
            "items": [schemas.Listing.model_validate(i) for i in items],
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size,
        }

    # Run sync DB call in a thread pool
    return await anyio.to_thread.run_sync(get_listings_sync)


@router.post(
    "/",
    response_model=schemas.Listing,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new listing",
    description="Creates a new co-living property entry. Requires host privileges.",
    responses={
        400: {"description": "Invalid input data"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions (Host required)"},
    },
)
async def create_listing(
    listing: schemas.ListingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not current_user.is_host:
         raise HTTPException(status_code=403, detail="Host privileges required")

    db_listing = models.Listing(
        id=str(uuid4()), owner_id=current_user.id, **listing.model_dump()
    )
    db.add(db_listing)
    db.commit()
    db.refresh(db_listing)

    # Audit Log
    from backend.services.audit_logging import log_user_action, AuditAction
    log_user_action(
        action=AuditAction.LISTING_CREATE,
        actor_id=current_user.id,
        resource_id=db_listing.id,
        metadata={"name": db_listing.name, "city": db_listing.city},
        db=db
    )

    # Invalidate listings cache so new listing appears immediately
    await invalidate_cache("listings")
    
    return db_listing


from backend.errors import ResourceNotFoundError


@router.get(
    "/{listing_id}",
    response_model=schemas.Listing,
    summary="Get listing details",
    description="Returns detailed information for a specific listing with eager-loaded related data. Cached for 10 minutes.",
    responses={
        404: {"description": "Listing not found"},
    },
)
@cached(ttl=600, prefix="listing")
async def read_listing(listing_id: str, db: Session = Depends(get_db)):
    def get_listing_sync():
        listing = (
            db.query(models.Listing)
            .options(
                joinedload(models.Listing.owner),
                joinedload(models.Listing.reviews)
            )
            .filter(models.Listing.id == listing_id)
            .first()
        )
        if listing is None:
            raise ResourceNotFoundError(resource="Listing", identifier=listing_id)
        return schemas.Listing.model_validate(listing)

    return await anyio.to_thread.run_sync(get_listing_sync)
