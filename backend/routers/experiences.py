from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from backend import models, schemas, database
from uuid import uuid4

router = APIRouter()


def get_db():
    yield from database.get_db()


@router.get("/", response_model=schemas.PaginatedResponse[schemas.Experience])
def read_experiences(
    page: int = 1,
    size: int = 20,
    category: str = None,
    type: str = None,
    db: Session = Depends(get_db)
):
    """
    List experiences with optional category/type filter.
    
    - **category**: Filter by category (adventure, cultural, wellness, social)
    - **type**: Filter by type (Residency, Retreat)
    """
    query = db.query(models.Experience)
    
    # Filter by category (maps to type internally)
    if category:
        category_map = {
            "adventure": "Retreat",
            "cultural": "Residency",
            "wellness": "Wellness",
            "social": "Social"
        }
        mapped_type = category_map.get(category.lower())
        if mapped_type:
            query = query.filter(models.Experience.type == mapped_type)
    
    # Direct type filter
    if type:
        query = query.filter(models.Experience.type == type)
    
    total = query.count()
    offset = (page - 1) * size
    items = query.offset(offset).limit(size).all()
    pages = (total + size - 1) // size
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }


@router.post("/", response_model=schemas.Experience, status_code=201)
def create_experience(
    experience: schemas.ExperienceCreate, db: Session = Depends(get_db)
):
    db_experience = models.Experience(
        id=str(uuid4()),
        type=experience.type,
        name=experience.name,
        theme=experience.theme,
        mission=experience.mission,
        curator_id=experience.curator_id,
        start_date=experience.start_date,
        end_date=experience.end_date,
        image=experience.image,
        price_usd=experience.price_usd,
        website=experience.website,
        membership_link=experience.membership_link,
        city=experience.city,
        country=experience.country,
        price_label=experience.price_label,
        duration_label=experience.duration_label,
        listing_ids=experience.listing_ids,
        amenities=experience.amenities,
        activities=experience.activities,
    )
    db.add(db_experience)
    db.commit()
    db.refresh(db_experience)
    return db_experience


@router.get("/{experience_id}", response_model=schemas.Experience)
def read_experience(experience_id: str, db: Session = Depends(get_db)):
    experience = (
        db.query(models.Experience)
        .filter(models.Experience.id == experience_id)
        .first()
    )
    if experience is None:
        from backend.errors import ResourceNotFoundError
        raise ResourceNotFoundError(resource="Experience", identifier=experience_id)
    return experience


@router.put("/{experience_id}", response_model=schemas.Experience)
def update_experience(
    experience_id: str,
    experience: schemas.ExperienceCreate,
    db: Session = Depends(get_db),
):
    db_experience = (
        db.query(models.Experience)
        .filter(models.Experience.id == experience_id)
        .first()
    )
    if db_experience is None:
        raise HTTPException(status_code=404, detail="Experience not found")

    db_experience.type = experience.type
    db_experience.name = experience.name
    db_experience.theme = experience.theme
    db_experience.mission = experience.mission
    db_experience.curator_id = experience.curator_id
    db_experience.start_date = experience.start_date
    db_experience.end_date = experience.end_date
    db_experience.image = experience.image
    db_experience.price_usd = experience.price_usd
    db_experience.website = experience.website
    db_experience.membership_link = experience.membership_link
    db_experience.city = experience.city
    db_experience.country = experience.country
    db_experience.price_label = experience.price_label
    db_experience.duration_label = experience.duration_label
    db_experience.listing_ids = experience.listing_ids
    db_experience.amenities = experience.amenities
    db_experience.activities = experience.activities

    db.commit()
    db.refresh(db_experience)
    return db_experience
