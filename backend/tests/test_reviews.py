"""
Test suite for Reviews router.
Tests CRUD operations, stats, and duplicate guard.
Run with: pytest backend/tests/test_reviews.py -v
"""
import pytest
from uuid import uuid4


@pytest.fixture
def review_listing(db, test_host, test_hub):
    """Create a listing for review tests."""
    from backend import models

    listing = models.Listing(
        id=str(uuid4()),
        name="Reviewable Listing",
        description="A place worth reviewing",
        property_type="Villa",
        city="Ubud",
        country="Indonesia",
        price_usd=80.0,
        features=["wifi"],
        images=["https://example.com/img.jpg"],
        hub_id=test_hub.id,
        owner_id=test_host.id,
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


class TestCreateReview:
    """Test POST /api/v1/reviews/."""

    def test_create_review(self, client, test_user, review_listing):
        """Creating a review returns 201 with review data."""
        response = client.post(
            "/api/v1/reviews/",
            json={
                "listing_id": review_listing.id,
                "author_id": test_user.id,
                "rating": 5,
                "comment": "Amazing place, highly recommend!",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["rating"] == 5
        assert data["listing_id"] == review_listing.id
        assert data["author_id"] == test_user.id

    def test_create_review_listing_not_found(self, client, test_user):
        """Reviewing a non-existent listing returns 404."""
        response = client.post(
            "/api/v1/reviews/",
            json={
                "listing_id": "nonexistent-listing",
                "author_id": test_user.id,
                "rating": 4,
                "comment": "Good place",
            },
        )
        assert response.status_code == 404

    def test_create_review_duplicate(self, client, test_user, review_listing):
        """Cannot review the same listing twice."""
        payload = {
            "listing_id": review_listing.id,
            "author_id": test_user.id,
            "rating": 4,
            "comment": "First review",
        }
        # First review
        resp1 = client.post("/api/v1/reviews/", json=payload)
        assert resp1.status_code == 201

        # Duplicate
        payload["comment"] = "Second attempt"
        resp2 = client.post("/api/v1/reviews/", json=payload)
        assert resp2.status_code == 400

    def test_create_review_invalid_rating(self, client, test_user, review_listing):
        """Rating outside 1-5 returns 422."""
        response = client.post(
            "/api/v1/reviews/",
            json={
                "listing_id": review_listing.id,
                "author_id": test_user.id,
                "rating": 10,
                "comment": "Too high",
            },
        )
        assert response.status_code == 422


class TestGetReviews:
    """Test GET endpoints for reviews."""

    def test_get_listing_reviews(self, client, review_listing):
        """Listing reviews endpoint returns paginated response."""
        response = client.get(f"/api/v1/reviews/listing/{review_listing.id}")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_get_user_reviews(self, client, test_user):
        """User reviews endpoint returns paginated response."""
        response = client.get(f"/api/v1/reviews/user/{test_user.id}")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_get_review_stats_empty(self, client):
        """Stats for a listing with no reviews."""
        response = client.get(f"/api/v1/reviews/stats/{uuid4()}")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["average"] == 0

    def test_get_review_stats_with_reviews(
        self, client, db, test_user, test_host, review_listing
    ):
        """Stats calculated correctly from multiple reviews."""
        from backend import models

        # Add two reviews from different users
        user2 = models.User(
            id=str(uuid4()),
            email=f"reviewer-{uuid4().hex[:8]}@example.com",
            name="Reviewer Two",
            hashed_password="hashed",
            is_host=False,
        )
        db.add(user2)
        db.commit()

        for user, rating in [(test_user, 4), (user2, 5)]:
            review = models.Review(
                id=str(uuid4()),
                listing_id=review_listing.id,
                author_id=user.id,
                rating=rating,
                comment=f"Rating {rating}",
            )
            db.add(review)
        db.commit()

        response = client.get(f"/api/v1/reviews/stats/{review_listing.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert data["average"] == 4.5
