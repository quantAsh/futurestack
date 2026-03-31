"""
Unit Tests for Deprecation Utilities
"""
import pytest
import warnings
from datetime import date
from backend.utils.deprecation import (
    deprecated,
    deprecated_sync,
    deprecated_param,
    DeprecatedField,
)


class TestDeprecationDecorator:
    """Tests for async deprecated decorator."""
    
    @pytest.mark.asyncio
    async def test_deprecated_issues_warning(self):
        """Deprecated decorator should issue DeprecationWarning."""
        @deprecated(reason="Use new_func instead")
        async def old_func():
            return "result"
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = await old_func()
            
            assert result == "result"
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "Use new_func instead" in str(w[0].message)
    
    @pytest.mark.asyncio
    async def test_deprecated_stores_metadata(self):
        """Decorator should store deprecation metadata."""
        @deprecated(
            reason="Outdated",
            sunset_date=date(2025, 12, 31),
            replacement="/api/v2/endpoint"
        )
        async def old_endpoint():
            pass
        
        assert old_endpoint.__deprecated__ == True
        assert old_endpoint.__deprecation_reason__ == "Outdated"
        assert old_endpoint.__sunset_date__ == date(2025, 12, 31)
        assert old_endpoint.__replacement__ == "/api/v2/endpoint"


class TestDeprecatedSync:
    """Tests for sync deprecated decorator."""
    
    def test_sync_deprecated_issues_warning(self):
        """Sync decorator should also issue warnings."""
        @deprecated_sync(reason="Legacy function")
        def legacy_func():
            return 42
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = legacy_func()
            
            assert result == 42
            assert len(w) == 1
            assert "Legacy function" in str(w[0].message)


class TestDeprecatedParam:
    """Tests for parameter deprecation."""
    
    def test_deprecated_param_warning(self):
        """Should warn about deprecated parameters."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            deprecated_param(
                "old_param",
                "Use new_param instead",
                replacement="new_param"
            )
            
            assert len(w) == 1
            assert "old_param" in str(w[0].message)
            assert "new_param" in str(w[0].message)


class TestDeprecatedField:
    """Tests for Pydantic field deprecation."""
    
    def test_deprecated_field_description(self):
        """Field should have deprecation in description."""
        from pydantic import BaseModel
        
        class TestModel(BaseModel):
            old_field: str = DeprecatedField(
                None,
                reason="Use new_field",
                replacement="new_field"
            )
        
        field_info = TestModel.model_fields["old_field"]
        assert "DEPRECATED" in field_info.description
        assert "Use new_field" in field_info.description
