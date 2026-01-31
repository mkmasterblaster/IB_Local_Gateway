"""
Sanity check test - verifies test infrastructure is working.

This test serves as a CI canary and ensures pytest is configured correctly.
"""
import pytest


def test_sanity():
    """Basic sanity check - ensures testing framework works."""
    assert 1 + 1 == 2


def test_imports():
    """Verify core dependencies can be imported."""
    try:
        import fastapi
        import pydantic
        import sqlalchemy
        import redis
        import structlog
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import required dependency: {e}")


def test_python_version():
    """Verify Python 3.12+ is being used."""
    import sys
    assert sys.version_info >= (3, 12), f"Python 3.12+ required, got {sys.version_info}"


@pytest.mark.unit
def test_basic_math():
    """Test basic assertions work as expected."""
    assert 2 * 2 == 4
    assert 10 / 2 == 5.0
    assert 3 ** 2 == 9


@pytest.mark.unit
def test_string_operations():
    """Test string operations for sanity."""
    test_str = "hello world"
    assert test_str.upper() == "HELLO WORLD"
    assert "world" in test_str
    assert test_str.split() == ["hello", "world"]


@pytest.mark.unit
def test_list_operations():
    """Test list operations for sanity."""
    test_list = [1, 2, 3, 4, 5]
    assert len(test_list) == 5
    assert sum(test_list) == 15
    assert max(test_list) == 5


@pytest.mark.unit
def test_dict_operations():
    """Test dictionary operations for sanity."""
    test_dict = {"a": 1, "b": 2, "c": 3}
    assert len(test_dict) == 3
    assert test_dict["a"] == 1
    assert "b" in test_dict
    assert list(test_dict.keys()) == ["a", "b", "c"]
