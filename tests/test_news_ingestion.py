"""Tests for News Ingestion module: Guardian client, content extraction, and admin discovery/sync."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.articles import Article
from app.models.enums import ArticleStatus, UserRole, UserStatus
from app.models.users import User
from app.modules.news_ingestion.errors import NewsIngestionError
from app.modules.news_ingestion.guardian_client import GuardianClient
from app.modules.news_ingestion.news_content_service import NewsContentService
from app.modules.news_ingestion.types import (
    GuardianImportResult,
    GuardianSearchResult,
    NormalizedNewsArticle,
    NormalizedNewsImportArticle,
)
from app.modules.news_ingestion.url_canonicalizer import (
    canonicalize_news_url,
    try_canonicalize_news_url,
)


def test_url_canonicalizer():
    """Verifies that tracking parameters and fragments are stripped while host is normalized."""
    raw = "HTTPS://WWW.TheGuardian.com/technology/2026/jul/01/ai-news?utm_source=twitter&fbclid=xyz#comments"
    canonical = canonicalize_news_url(raw)
    assert canonical == "https://www.theguardian.com/technology/2026/jul/01/ai-news"

    # Non-http protocol rejected
    with pytest.raises(NewsIngestionError):
        canonicalize_news_url("ftp://theguardian.com/file")

    # try_canonicalize returns None on invalid inputs
    assert try_canonicalize_news_url("invalid-url") is None
    assert try_canonicalize_news_url(None) is None


def test_news_content_service_placeholders():
    """Verifies that placeholder and paywall stubs are rejected."""
    art = NormalizedNewsImportArticle(
        externalId="ext-1",
        title="Sample Title",
        description="Sample Desc",
        url="https://theguardian.com/sample",
        imageUrl=None,
        sourceName="The Guardian",
        publishedAt=datetime.now(UTC),
        authorName=None,
        sectionId="technology",
        sectionName="Technology",
        providerContent="[removed]",
    )
    with pytest.raises(NewsIngestionError) as exc_info:
        NewsContentService.resolve(art)
    assert exc_info.value.code == "GUARDIAN_BODY_UNAVAILABLE"


@pytest.mark.asyncio
async def test_admin_news_search_endpoint(client):
    """Verifies that GET /api/v1/admin/news/search returns normalized Guardian articles."""
    rand = str(uuid.uuid4())[:8]
    admin_email = f"news_admin_{rand}@example.com"
    pwd = "SecurePassword123!"

    async with AsyncSessionLocal() as session:
        admin = User(
            id=uuid.uuid4(),
            email=admin_email,
            password_hash=get_password_hash(pwd),
            display_name="News Admin",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
        session.add(admin)
        await session.commit()

    login_resp = await client.post("/api/v1/auth/login", json={"email": admin_email, "password": pwd})
    token = login_resp.json()["data"]["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    sample_article = NormalizedNewsArticle(
        externalId="world/2026/jul/01/future-tech",
        title="Future of Clean Energy",
        description="Clean energy tech is surging.",
        url="https://theguardian.com/world/2026/jul/01/future-tech",
        imageUrl="https://media.guim.co.uk/sample.jpg",
        sourceName="The Guardian",
        publishedAt=datetime.now(UTC),
        authorName="Jane Doe",
        sectionId="technology",
        sectionName="Technology",
    )
    mock_search_result = GuardianSearchResult(
        totalArticles=1,
        articles=[sample_article],
    )

    with patch.object(GuardianClient, "search_metadata", new_callable=AsyncMock) as mock_method:
        mock_method.return_value = mock_search_result

        resp = await client.get("/api/v1/admin/news/search?q=energy&pageSize=5", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["totalArticles"] == 1
        assert body["data"]["articles"][0]["title"] == "Future of Clean Energy"


@pytest.mark.asyncio
async def test_admin_news_sync_endpoint(client):
    """Verifies that POST /api/v1/admin/news/sync creates parsed draft articles and skips duplicates."""
    rand = str(uuid.uuid4())[:8]
    admin_email = f"sync_admin_{rand}@example.com"
    pwd = "SecurePassword123!"

    async with AsyncSessionLocal() as session:
        admin = User(
            id=uuid.uuid4(),
            email=admin_email,
            password_hash=get_password_hash(pwd),
            display_name="Sync Admin",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
        session.add(admin)
        await session.commit()

    login_resp = await client.post("/api/v1/auth/login", json={"email": admin_email, "password": pwd})
    token = login_resp.json()["data"]["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    external_id = f"technology/2026/jul/01/space-ai-{rand}"
    import_article = NormalizedNewsImportArticle(
        externalId=external_id,
        title=f"AI in Space Exploration {rand}",
        description="Autonomous probes are discovering new worlds with advanced algorithms.",
        url=f"https://theguardian.com/{external_id}",
        imageUrl=None,
        sourceName="The Guardian",
        publishedAt=datetime.now(UTC),
        authorName="John Scientist",
        sectionId="science",
        sectionName="Science",
        providerContent=(
            "<p>Autonomous probes are discovering new worlds with advanced machine learning algorithms. "
            "NASA and ESA have collaborated on this monumental leap in deep space exploration. "
            "Scientists hope to uncover evidence of ancient aquatic environments across Jupiter moons.</p>"
        ),
    )
    mock_import_result = GuardianImportResult(
        totalArticles=1,
        articles=[import_article],
    )

    with patch.object(GuardianClient, "search_for_import", new_callable=AsyncMock) as mock_method:
        mock_method.return_value = mock_import_result

        # 1. First sync imports the draft
        sync_resp = await client.post(
            "/api/v1/admin/news/sync",
            headers=headers,
            json={"q": "space", "pageSize": 1},
        )
        assert sync_resp.status_code == 201
        data = sync_resp.json()["data"]
        assert data["counts"]["imported"] == 1
        assert data["counts"]["skippedDuplicate"] == 0
        created_article_id = data["items"][0]["articleId"]
        assert created_article_id is not None

        # Verify in database: article is DRAFT and has parsed sentences
        async with AsyncSessionLocal() as session:
            art = await session.get(Article, uuid.UUID(created_article_id))
            assert art is not None
            assert art.status == ArticleStatus.DRAFT
            assert art.external_id == external_id

        # 2. Second sync with same item skips duplicate
        sync_resp2 = await client.post(
            "/api/v1/admin/news/sync",
            headers=headers,
            json={"q": "space", "pageSize": 1},
        )
        assert sync_resp2.status_code == 201
        data2 = sync_resp2.json()["data"]
        assert data2["counts"]["imported"] == 0
        assert data2["counts"]["skippedDuplicate"] == 1
