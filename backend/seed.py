import sys
import os
import csv
import random
import datetime
import structlog

logger = structlog.get_logger("nomadnest.seed")

# Adjust path to find backend module
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.orm import Session
from backend.database import SessionLocal, engine, Base
from backend import models, seed_data
from backend.utils import get_password_hash

# Ensure all tables exist (safe for PostgreSQL and SQLite)
Base.metadata.create_all(bind=engine)

# --- CSV PARSING LOGIC ---

RETREAT_COLUMN_KEYS = [
    "name",
    "website",
    "location",
    "whatIsIt",
    "types",
    "columnFallback",
    "accommodation",
    "diagnostics",
    "focus",
    "duration",
    "price",
    "membershipLink",
]


def clean_retreat_cell(value):
    if not value:
        return ""
    return value.strip().replace('"', "")


def ensure_http_url(value):
    if not value:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if trimmed.lower().startswith("http"):
        return trimmed
    return f"https://{trimmed.strip('/')}"


def parse_retreat_location(value):
    if not value:
        return {"city": "Global", "country": "Various"}
    cleaned = clean_retreat_cell(value)
    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    if not parts:
        return {"city": "Global", "country": "Various"}
    # Heuristic: last part is country, first is city
    country = parts[-1]
    city = parts[0]
    return {"city": city, "country": country}


def parse_retreats_csv():
    csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "retreats.csv")
    if not os.path.exists(csv_path):
        logger.warning("csv_not_found", path=csv_path)
        return []

    retreats = []
    with open(csv_path, "r", encoding="utf-8") as f:
        # The frontend code implies a custom parser for tab-separated values,
        # but let's try standard csv with tab delimiter first.
        # Looking at the file content, it seems to use tabs.
        reader = csv.reader(f, delimiter="\t")

        # Skip header? Frontend logic is complex, it loops and checks line validity.
        # We will try a simpler approach: iterate and map valid rows.

        # Determine strict index mapping based on RETREAT_COLUMN_KEYS length
        expected_cols = len(RETREAT_COLUMN_KEYS)

        for i, row in enumerate(reader):
            if i == 0:
                continue  # Skip header if present (heuristic)
            if not row or not row[0].strip():
                continue

            # Map row to dictionary
            record = {}
            for idx, key in enumerate(RETREAT_COLUMN_KEYS):
                val = row[idx] if idx < len(row) else ""
                record[key] = clean_retreat_cell(val)

            loc = parse_retreat_location(record["location"])

            theme = record["types"] or record["columnFallback"] or "Wellness Retreat"
            mission_parts = [
                p
                for p in [record["whatIsIt"], record["duration"], record["price"]]
                if p
            ]

            retreat = {
                "name": record["name"],
                "theme": theme,
                "mission": " ".join(mission_parts) or "Curated retreat experience.",
                "website": ensure_http_url(record["website"]),
                "amenities": [
                    a
                    for a in [
                        record["accommodation"],
                        record["price"],
                        record["diagnostics"],
                    ]
                    if a
                ],
                "activities": [
                    f.strip() for f in record["focus"].split(",") if f.strip()
                ],
                "city": loc["city"],
                "country": loc["country"],
                "membership_link": ensure_http_url(record["membershipLink"]),
                "duration_label": record["duration"],
                "price_label": record["price"],
                # Mock fields for DB
                "image": "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?q=80&w=2720&auto=format&fit=crop",
                "price_usd": 1500.0 + (len(record["name"]) * 10),  # Pseudo-random
            }
            retreats.append(retreat)

    return retreats


def seed_data_script():
    db = SessionLocal()
    try:
        # Clear existing data - use DELETE for SQLite compatibility
        logger.info("clearing_existing_data")
        from sqlalchemy import text
        
        # Check if using SQLite (no TRUNCATE support)
        is_sqlite = 'sqlite' in str(engine.url)
        
        if is_sqlite:
            # SQLite-compatible deletion 
            tables_to_clear = [
                'chat_messages', 'chat_threads', 'host_applications', 'ota_bookings',
                'external_listings', 'ota_providers', 'hub_investments', 'agent_memory', 
                'agent_jobs', 'votes', 'proposals', 'host_earnings', 'experience_bookings',
                'spending_records', 'negotiations', 'journey_legs', 'journeys',
                'skill_requests', 'skills', 'subscriptions', 'notifications', 'community_tasks',
                'experiences', 'reviews', 'bookings', 'listings', 'hubs', 'neighborhoods', 
                'community_events', 'services', 'users'
            ]
            for table in tables_to_clear:
                try:
                    db.execute(text(f"DELETE FROM {table}"))
                except Exception as e:
                    # Table may not exist yet
                    pass
            db.commit()
        else:
            # PostgreSQL with TRUNCATE CASCADE
            try:
                db.execute(
                    text(
                        """
                    TRUNCATE users, listings, bookings, reviews, neighborhoods, hubs, experiences, 
                    community_tasks, notifications, subscriptions, skills, skill_requests, 
                    journeys, journey_legs, negotiations, spending_records, experience_bookings, 
                    host_earnings, proposals, votes, agent_jobs, agent_memory, hub_investments, 
                    ota_providers, external_listings, ota_bookings, services, community_events,
                    chat_threads, chat_messages, host_applications CASCADE
                """
                    )
                )
                db.commit()
            except Exception as e:
                # Tables may not exist yet on fresh database, just rollback and continue
                db.rollback()
                logger.debug("truncate_skipped", error=str(e))

        # 1. Users
        logger.info("seeding", entity="users")
        for u_data in seed_data.USERS:
            if not db.query(models.User).filter(models.User.id == u_data["id"]).first():
                user = models.User(
                    id=u_data["id"],
                    name=u_data["name"],
                    email=u_data["email"],
                    hashed_password=get_password_hash(u_data["password"]),
                    avatar=u_data["avatar"],
                    bio=u_data["bio"],
                    is_host=u_data["is_host"],
                    is_admin=u_data.get("is_admin", False),
                    reputation_score=u_data["reputation_score"],
                    wallet_address=u_data["wallet_address"],
                )
                db.add(user)
        db.commit()

        # 2. Neighborhoods
        logger.info("seeding", entity="neighborhoods")
        for n_data in seed_data.NEIGHBORHOODS:
            if (
                not db.query(models.Neighborhood)
                .filter(models.Neighborhood.id == n_data["id"])
                .first()
            ):
                n = models.Neighborhood(**n_data)
                db.add(n)
        db.commit()

        # 3. Hubs (Static)
        logger.info("seeding", entity="static_hubs")
        for h_data in seed_data.HUBS:
            if not db.query(models.Hub).filter(models.Hub.id == h_data["id"]).first():
                hub = models.Hub(**h_data)
                db.add(hub)
        db.commit()

        # 4. Listings
        logger.info("seeding", entity="listings")
        for l_data in seed_data.LISTINGS:
            if (
                not db.query(models.Listing)
                .filter(models.Listing.id == l_data["id"])
                .first()
            ):
                listing = models.Listing(**l_data)
                db.add(listing)
        db.commit()

        # 5. Reviews
        logger.info("seeding", entity="reviews")
        for r_data in seed_data.REVIEWS:
            if (
                not db.query(models.Review)
                .filter(models.Review.id == r_data["id"])
                .first()
            ):
                review = models.Review(**r_data)
                db.add(review)
        db.commit()

        # 6. Experiences (Static)
        logger.info("seeding", entity="static_experiences")
        for e_data in seed_data.EXPERIENCES:
            if (
                not db.query(models.Experience)
                .filter(models.Experience.id == e_data["id"])
                .first()
            ):
                exp = models.Experience(**e_data)
                db.add(exp)
        db.commit()

        # 7. Tasks
        logger.info("seeding", entity="tasks")
        for t_data in seed_data.TASKS:
            if (
                not db.query(models.CommunityTask)
                .filter(models.CommunityTask.id == t_data["id"])
                .first()
            ):
                task = models.CommunityTask(**t_data)
                db.add(task)
        db.commit()

        # 8. Dynamic CSV Data (Retreats & Virtual Hubs)
        logger.info("seeding", entity="dynamic_csv_data")
        csv_retreats = parse_retreats_csv()

        virtual_hub_images = [
            "https://images.unsplash.com/photo-1575052814086-f385e2e2ad1b?q=80&w=2670&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1540541338287-417002075841?q=80&w=2640&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1599351372544-93a522288a8f?q=80&w=2670&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1475924156734-496f6cac6ec1?q=80&w=2670&auto=format&fit=crop",
        ]

        for idx, retreat in enumerate(csv_retreats):
            exp_id = f"retreat-csv-{idx}"
            virtual_hub_id = f"v-hub-{exp_id}"

            # Create Experience
            if (
                not db.query(models.Experience)
                .filter(models.Experience.id == exp_id)
                .first()
            ):
                # Randomize dates
                start_days = random.randint(1, 60)
                start_date = datetime.datetime.utcnow() + datetime.timedelta(
                    days=start_days
                )
                end_date = start_date + datetime.timedelta(days=7)

                exp = models.Experience(
                    id=exp_id,
                    type="retreat",
                    name=retreat["name"],
                    theme=retreat["theme"],
                    mission=retreat["mission"][:400]
                    if retreat["mission"]
                    else "Wellness retreat.",  # truncate just in case
                    curator_id="user-5",
                    start_date=start_date.date().isoformat(),
                    end_date=end_date.date().isoformat(),
                    image=retreat["image"],
                    city=retreat["city"],
                    country=retreat["country"],
                    price_usd=retreat["price_usd"],
                    website=retreat["website"],
                    membership_link=retreat["membership_link"],
                    price_label=retreat["price_label"],
                    duration_label=retreat["duration_label"],
                    activities=retreat["activities"],
                    amenities=retreat["amenities"],
                    listing_ids=[f"listing-{exp_id}"],
                )
                db.add(exp)

            # Create Virtual Wellness Hub wrapping the experience
            if not db.query(models.Hub).filter(models.Hub.id == virtual_hub_id).first():
                v_hub = models.Hub(
                    id=virtual_hub_id,
                    name=retreat["name"],
                    mission=retreat["mission"][:400]
                    if retreat["mission"]
                    else "Wellness retreat hub.",
                    type="wellness-hub",
                    logo=virtual_hub_images[idx % len(virtual_hub_images)],
                    charter="Virtual hub representing a partner retreat.",
                    lat=20.0 + (random.random() * 20),  # Rough random placement for now
                    lng=-20.0 + (random.random() * 40),
                    sustainability_score=90,
                    listing_ids=[f"listing-{exp_id}"],
                )
                db.add(v_hub)

            # Create Listing for the retreat to make it show up in "Stay" searches
            listing_id = f"listing-{exp_id}"
            if (
                not db.query(models.Listing)
                .filter(models.Listing.id == listing_id)
                .first()
            ):
                listing = models.Listing(
                    id=listing_id,
                    owner_id="user-5",  # Kenji Tanaka
                    name=f"Exclusive Stay at {retreat['name']}",
                    description=retreat["mission"],
                    property_type="Wellness Retreat",
                    city=retreat["city"],
                    country=retreat["country"],
                    price_usd=retreat["price_usd"],
                    features=retreat["activities"] + retreat["amenities"],
                    images=[retreat["image"]],
                    guest_capacity=2,
                    bedrooms=1,
                    bathrooms=1,
                    hub_id=virtual_hub_id,
                )
                db.add(listing)

        db.commit()

        # 9. Bookings
        logger.info("seeding", entity="bookings")
        for b_data in seed_data.BOOKINGS:
            if (
                not db.query(models.Booking)
                .filter(models.Booking.id == b_data["id"])
                .first()
            ):
                booking = models.Booking(
                    id=b_data["id"],
                    user_id=b_data["user_id"],
                    listing_id=b_data["listing_id"],
                    start_date=datetime.datetime.fromisoformat(b_data["check_in"]),
                    end_date=datetime.datetime.fromisoformat(b_data["check_out"]),
                    total_price_usd=b_data["total_price"],
                )
                db.add(booking)
        db.commit()

        # 10. Message Threads and Messages
        logger.info("seeding", entity="message_threads")
        for t_data in seed_data.MESSAGE_THREADS:
            if (
                not db.query(models.ChatThread)
                .filter(models.ChatThread.id == t_data["id"])
                .first()
            ):
                # Create thread with participant array
                thread = models.ChatThread(
                    id=t_data["id"],
                    participant_ids=t_data["participant_ids"],
                    listing_id=t_data.get("listing_id"),
                    created_at=datetime.datetime.fromisoformat(t_data["created_at"]),
                )
                db.add(thread)
                db.commit()
                
                # Add messages to the thread
                for idx, msg in enumerate(t_data.get("messages", [])):
                    message = models.ChatMessage(
                        id=f"{t_data['id']}-msg-{idx}",
                        thread_id=t_data["id"],
                        sender_id=msg["sender_id"],
                        content=msg["content"],
                        created_at=datetime.datetime.fromisoformat(msg["sent_at"]),
                    )
                    db.add(message)
        db.commit()

        # 11. Applications
        logger.info("seeding", entity="applications")
        for a_data in seed_data.APPLICATIONS:
            if (
                not db.query(models.HostApplication)
                .filter(models.HostApplication.id == a_data["id"])
                .first()
            ):
                app = models.HostApplication(
                    id=a_data["id"],
                    user_id=a_data["user_id"],
                    hub_id=a_data["hub_id"],
                    status=a_data["status"],
                    answers={"message": a_data["message"]},
                    created_at=datetime.datetime.fromisoformat(a_data["created_at"]),
                )
                db.add(app)
        db.commit()

        # 12. Services
        logger.info("seeding", entity="services")
        for s_data in seed_data.SERVICES:
            if (
                not db.query(models.Service)
                .filter(models.Service.id == s_data["id"])
                .first()
            ):
                service = models.Service(
                    id=s_data["id"],
                    hub_id=s_data["hub_id"],
                    name=s_data["name"],
                    description=s_data["description"],
                    price=s_data["price"],
                    category=s_data["category"],
                )
                db.add(service)
        db.commit()

        # 13. Community Events
        logger.info("seeding", entity="community_events")
        for e_data in seed_data.EVENTS:
            if (
                not db.query(models.CommunityEvent)
                .filter(models.CommunityEvent.id == e_data["id"])
                .first()
            ):
                event = models.CommunityEvent(
                    id=e_data["id"],
                    hub_id=e_data["hub_id"],
                    name=e_data["name"],
                    description=e_data["description"],
                    date=datetime.datetime.fromisoformat(e_data["date"]),
                    location=e_data.get("location"),
                    capacity=e_data.get("capacity"),
                )
                db.add(event)
        db.commit()

        # 14. Culture Keepers & Cultural Experiences (Quantum Temple Inspired)
        logger.info("seeding", entity="culture_keepers")
        CULTURE_KEEPERS = [
            {
                "id": "keeper-1",
                "user_id": "user-5",
                "name": "Made Wirawan",
                "bio": "Third-generation Balinese water priest dedicated to preserving the ancient subak irrigation traditions and water temple ceremonies.",
                "culture": "Balinese",
                "region": "Ubud, Bali",
                "traditions": ["Water Ceremonies", "Subak Rituals", "Temple Offerings"],
                "photo_url": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=400",
                "verified": True,
                "impact_total_usd": 2450.0,
            },
            {
                "id": "keeper-2",
                "user_id": "user-4",
                "name": "Yuki Sato",
                "bio": "Master of traditional Japanese craftsmanship, specializing in washi paper making and ikebana flower arrangement.",
                "culture": "Japanese",
                "region": "Kyoto, Japan",
                "traditions": ["Washi Making", "Ikebana", "Tea Ceremony"],
                "photo_url": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400",
                "verified": True,
                "impact_total_usd": 1820.0,
            },
            {
                "id": "keeper-3",
                "user_id": "user-1",
                "name": "Kofi Asante",
                "bio": "Elder storyteller and kente weaving master from the Ashanti region, keeping oral traditions alive through immersive workshops.",
                "culture": "Ghanaian",
                "region": "Kumasi, Ghana",
                "traditions": ["Kente Weaving", "Oral Storytelling", "Drum Ceremonies"],
                "photo_url": "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=400",
                "verified": True,
                "impact_total_usd": 980.0,
            },
        ]

        for k_data in CULTURE_KEEPERS:
            if (
                not db.query(models.CultureKeeper)
                .filter(models.CultureKeeper.id == k_data["id"])
                .first()
            ):
                keeper = models.CultureKeeper(**k_data)
                db.add(keeper)
        db.commit()

        logger.info("seeding", entity="cultural_experiences")
        CULTURAL_EXPERIENCES = [
            {
                "id": "exp-culture-1",
                "keeper_id": "keeper-1",
                "listing_id": None,
                "title": "Sacred Water Temple Blessing",
                "description": "Join a traditional Balinese water purification ceremony at a 1000-year-old temple. Learn about the subak irrigation system, a UNESCO-recognized cultural heritage.",
                "experience_type": "ceremony",
                "duration_hours": 3.0,
                "max_participants": 8,
                "price_usd": 75.0,
                "community_impact_percent": 0.5,
                "image_url": "https://images.unsplash.com/photo-1537996194471-e657df975ab4?w=800",
                "is_active": True,
            },
            {
                "id": "exp-culture-2",
                "keeper_id": "keeper-1",
                "listing_id": None,
                "title": "Traditional Offering Making Workshop",
                "description": "Create authentic Canang Sari offerings using fresh flowers and palm leaves. A meditative practice passed down through generations.",
                "experience_type": "workshop",
                "duration_hours": 2.0,
                "max_participants": 12,
                "price_usd": 45.0,
                "community_impact_percent": 0.4,
                "image_url": "https://images.unsplash.com/photo-1555400038-63f5ba517a47?w=800",
                "is_active": True,
            },
            {
                "id": "exp-culture-3",
                "keeper_id": "keeper-2",
                "listing_id": None,
                "title": "Washi Paper Making Masterclass",
                "description": "Learn the 1,300-year-old art of Japanese paper making. Create your own handmade washi using traditional techniques and natural fibers.",
                "experience_type": "craft",
                "duration_hours": 4.0,
                "max_participants": 6,
                "price_usd": 120.0,
                "community_impact_percent": 0.45,
                "image_url": "https://images.unsplash.com/photo-1528360983277-13d401cdc186?w=800",
                "is_active": True,
            },
            {
                "id": "exp-culture-4",
                "keeper_id": "keeper-2",
                "listing_id": None,
                "title": "Chado: Way of Tea Ceremony",
                "description": "Experience an authentic Japanese tea ceremony in a 400-year-old tea house. Learn the philosophy of ichi-go ichi-e (one time, one meeting).",
                "experience_type": "ceremony",
                "duration_hours": 2.0,
                "max_participants": 4,
                "price_usd": 80.0,
                "community_impact_percent": 0.4,
                "image_url": "https://images.unsplash.com/photo-1545048702-79362596cdc9?w=800",
                "is_active": True,
            },
            {
                "id": "exp-culture-5",
                "keeper_id": "keeper-3",
                "listing_id": None,
                "title": "Kente Weaving Apprenticeship",
                "description": "Learn to weave the sacred cloth of Ghanaian royalty. Each pattern tells a story; create your own meaningful design.",
                "experience_type": "craft",
                "duration_hours": 5.0,
                "max_participants": 6,
                "price_usd": 95.0,
                "community_impact_percent": 0.5,
                "image_url": "https://images.unsplash.com/photo-1590735213920-68192a487bc2?w=800",
                "is_active": True,
            },
            {
                "id": "exp-culture-6",
                "keeper_id": "keeper-3",
                "listing_id": None,
                "title": "Moonlight Stories: Elder Tales",
                "description": "Gather under the stars as Kofi shares ancient Ashanti myths and wisdom stories. Includes traditional drumming and fire ceremony.",
                "experience_type": "tradition",
                "duration_hours": 3.0,
                "max_participants": 20,
                "price_usd": 35.0,
                "community_impact_percent": 0.6,
                "image_url": "https://images.unsplash.com/photo-1528495612343-9ca9f4a4de28?w=800",
                "is_active": True,
            },
        ]

        for e_data in CULTURAL_EXPERIENCES:
            if (
                not db.query(models.CulturalExperience)
                .filter(models.CulturalExperience.id == e_data["id"])
                .first()
            ):
                exp = models.CulturalExperience(**e_data)
                db.add(exp)
        db.commit()

        logger.info("seeding", entity="nomad_passports")
        NOMAD_PASSPORTS = [
            {
                "id": "passport-1",
                "user_id": "user-1",
                "experiences_completed": 5,
                "badges": ["water_ceremony", "craft_apprentice", "story_listener"],
                "impact_contributed_usd": 275.0,
                "passport_level": "pilgrim",
                "cultures_visited": ["Balinese", "Japanese"],
                "regions_explored": ["Ubud, Bali", "Kyoto, Japan"],
            },
            {
                "id": "passport-2",
                "user_id": "user-2",
                "experiences_completed": 2,
                "badges": ["craft_apprentice"],
                "impact_contributed_usd": 95.0,
                "passport_level": "explorer",
                "cultures_visited": ["Ghanaian"],
                "regions_explored": ["Kumasi, Ghana"],
            },
        ]

        for p_data in NOMAD_PASSPORTS:
            if (
                not db.query(models.NomadPassport)
                .filter(models.NomadPassport.id == p_data["id"])
                .first()
            ):
                passport = models.NomadPassport(**p_data)
                db.add(passport)
        db.commit()

        logger.info("seeding_complete")

    except Exception as e:
        logger.error("seeding_failed", error=str(e))
        db.rollback()
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_data_script()
