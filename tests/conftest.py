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


@pytest.fixture
def search_kjfk_live_html():
    return (FIXTURES / "search_kjfk_live.html").read_text()


@pytest.fixture
def topfeeds_live_html():
    return (FIXTURES / "topfeeds_live.html").read_text()


@pytest.fixture
def archive_kjfk_gnd_live_html():
    return (FIXTURES / "archive_kjfk_gnd_live.html").read_text()


@pytest.fixture
def hlisten_kjfk_gnd_live_html():
    return (FIXTURES / "hlisten_kjfk_gnd_live.html").read_text()
