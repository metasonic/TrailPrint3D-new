import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture
def gpx_bytes():
    """Minimal valid GPX file for upload tests."""
    return b"""<?xml version="1.0"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
  <trk><trkseg>
    <trkpt lat="46.770" lon="23.590"><ele>350</ele></trkpt>
    <trkpt lat="46.772" lon="23.592"><ele>360</ele></trkpt>
    <trkpt lat="46.774" lon="23.595"><ele>370</ele></trkpt>
  </trkseg></trk>
</gpx>"""
