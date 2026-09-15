import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.database import engine
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def reset_engine_pool():
    await engine.dispose()
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
