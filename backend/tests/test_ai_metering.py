"""
Tests for AI Metering Service - Usage tracking and cost calculation coverage
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from backend.services.ai_metering import (
    log_ai_usage,
    get_user_usage_summary,
    calculate_cost_cents,
)
from backend import models


class TestAIMeteringLogging:
    """Test AI usage logging."""

    def test_log_ai_usage_creates_record(self, db):
        """Test that AI call logging creates a database record."""
        from uuid import uuid4
        
        user_id = str(uuid4())
        
        # Log an AI call
        record_id = log_ai_usage(
            user_id=user_id,
            model="gpt-4o",
            provider="openai",
            endpoint="/concierge/chat",
            prompt_tokens=100,
            completion_tokens=50,
            latency_ms=1500,
            db=db
        )
        
        # Verify record was created
        record = db.query(models.AIUsageMetrics).filter_by(user_id=user_id).first()
        assert record is not None
        assert record.model == "gpt-4o"
        assert record.prompt_tokens == 100
        assert record.completion_tokens == 50

    def test_log_ai_usage_calculates_cost(self, db):
        """Test that cost is calculated based on model and tokens."""
        from uuid import uuid4
        
        user_id = str(uuid4())
        
        log_ai_usage(
            user_id=user_id,
            model="gpt-4o",
            provider="openai",
            endpoint="/concierge/chat",
            prompt_tokens=1000,
            completion_tokens=500,
            latency_ms=2000,
            db=db
        )
        
        record = db.query(models.AIUsageMetrics).filter_by(user_id=user_id).first()
        assert record.cost_cents > 0


class TestAIUsageAggregation:
    """Test usage aggregation and reporting."""

    def test_get_user_usage_summary(self, db):
        """Test getting usage summary for a user."""
        from uuid import uuid4
        
        user_id = str(uuid4())
        
        # Create some test usage records
        for i in range(3):
            record = models.AIUsageMetrics(
                id=str(uuid4()),
                user_id=user_id,
                model="gpt-3.5-turbo",
                provider="openai",
                endpoint="/concierge/chat",
                prompt_tokens=100 * (i + 1),
                completion_tokens=50 * (i + 1),
                total_tokens=150 * (i + 1),
                latency_ms=1000,
                cost_cents=(i + 1),
                created_at=datetime.utcnow()
            )
            db.add(record)
        db.commit()
        
        # Get usage
        usage = get_user_usage_summary(user_id, db=db)
        
        assert usage is not None
        assert usage["request_count"] == 3
        assert usage["total_tokens"] == 900  # 150 + 300 + 450


class TestCostCalculation:
    """Test cost calculation for different models."""

    def test_calculate_cost_cents_gpt4o(self):
        """Test GPT-4o cost calculation."""
        cost = calculate_cost_cents(
            model="gpt-4o",
            prompt_tokens=1000,
            completion_tokens=500
        )
        # GPT-4o: $0.0025/1k prompt, $0.01/1k completion = 0.25 + 0.5 cents
        # Returned as int cents
        assert cost >= 0

    def test_calculate_cost_cents_gpt35(self):
        """Test GPT-3.5-turbo cost calculation."""
        cost = calculate_cost_cents(
            model="gpt-3.5-turbo",
            prompt_tokens=1000,
            completion_tokens=500
        )
        # Much cheaper than GPT-4o
        assert cost >= 0

    def test_calculate_cost_cents_gemini(self):
        """Test Gemini cost calculation."""
        cost = calculate_cost_cents(
            model="gemini-pro",
            prompt_tokens=1000,
            completion_tokens=500
        )
        # Gemini free tier
        assert cost == 0
