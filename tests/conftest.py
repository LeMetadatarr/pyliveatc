from pathlib import Path
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def search_kjfk_html():
    return (FIXTURES / "search_kjfk.html").read_text()


@pytest.fixture
def topfeeds_html():
    return (FIXTURES / "topfeeds.html").read_text()


@pytest.fixture
def archive_html():
    return (FIXTURES / "archive_kjfk_app.html").read_text()
