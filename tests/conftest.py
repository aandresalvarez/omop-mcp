"""Pytest configuration and fixtures."""

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Setup test environment variables."""
    # Set test environment variables if not already set
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = "sk-test-key"

    if not os.getenv("ATHENA_BASE_URL"):
        os.environ["ATHENA_BASE_URL"] = "https://athena.ohdsi.org/api/v1"
