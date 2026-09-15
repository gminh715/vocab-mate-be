"""Administrative analytics service providing system-wide operational, content, and cohort retention metrics."""

import uuid
from typing import Any

from sqlalchemy import and_, case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.articles import Article
from app.models.categories import Category
from app.models.enums import ArticleStatus
from app.models.reading import UserArticleProgress
from app.models.users import User
from app.models.vocabularies import UserVocabulary
from app.modules.analytics.helpers import (
    fill_missing_buckets,
    resolve_analytics_date_range,
    resolve_analytics_group_by,
    round_ratio,
)
from app.modules.analytics.schemas import (
    AdminAnalyticsOverviewDataDto,
    AdminArticleCompletionDto,
    AdminContentAnalyticsDataDto,
    AdminContentAnalyticsQueryDto,
    AdminTermSaveDto,
    AdminTopArticleDto,
    AdminUserAnalyticsDataDto,
    AdminUserAnalyticsQueryDto,
    AnalyticsDateRangeQueryDto,
    LearningDistributionDto,
    RegistrationTrendBucketDto,
    RetentionProxyDto,
)

TOP_LIMIT: int = 20


class AdminAnalyticsService:
    """Calculates platform-level operational KPIs, bounded content engagement rankings, and cohort retention."""

    @classmethod
    async def get_admin_overview(
        cls,
        db: AsyncSession,
        query: AnalyticsDateRangeQueryDto,
    ) -> AdminAnalyticsOverviewDataDto:
        """Retrieves system-wide user counts, active users, articles, and saved vocabulary flow.

        Args:
            db (AsyncSession): Active database session.
            query (AnalyticsDateRangeQueryDto): Date range filter.

        Returns:
            AdminAnalyticsOverviewDataDto: Aggregate system numbers.

        Example:
            >>> # overview = await AdminAnalyticsService.get_admin_overview(db, query)
        """
        range_ = resolve_analytics_date_range(query)

        # 1. Total users
        q_users = select(func.count()).select_from(User)
        users = (await db.execute(q_users)).scalar() or 0

        # 2. Total articles
        q_articles = select(func.count()).select_from(Article)
        articles = (await db.execute(q_articles)).scalar() or 0

        # 3. Published articles
        q_pub_articles = select(func.count()).select_from(Article).where(Article.status == ArticleStatus.PUBLISHED)
        published_articles = (await db.execute(q_pub_articles)).scalar() or 0

        # 4. Active users in [from, to)
        active_stmt = text(
            """
            SELECT count(DISTINCT user_id)::int FROM (
                SELECT user_id FROM user_article_progress WHERE last_read_at >= :from_date AND last_read_at < :to_date
                UNION
                SELECT user_id FROM user_vocabularies WHERE saved_at >= :from_date AND saved_at < :to_date
            ) active_u
            """
        )
        active_res = await db.execute(
            active_stmt,
            {"from_date": range_.from_date, "to_date": range_.to_date},
        )
        active_users = active_res.scalar() or 0

        # 5. Saved vocabulary period flow
        q_saved = (
            select(func.count())
            .select_from(UserVocabulary)
            .where(
                UserVocabulary.saved_at >= range_.from_date,
                UserVocabulary.saved_at < range_.to_date,
            )
        )
        saved_vocabulary = (await db.execute(q_saved)).scalar() or 0

        return AdminAnalyticsOverviewDataDto(
            users=users,
            activeUsers=active_users,
            articles=articles,
            publishedArticles=published_articles,
            savedVocabulary=saved_vocabulary,
        )

    @classmethod
    async def get_admin_content_analytics(
        cls,
        db: AsyncSession,
        query: AdminContentAnalyticsQueryDto,
    ) -> AdminContentAnalyticsDataDto:
        """Retrieves bounded top articles by reading volume, completion ratios, and top saved terms.

        Args:
            db (AsyncSession): Active database session.
            query (AdminContentAnalyticsQueryDto): Date range and optional category filter.

        Returns:
            AdminContentAnalyticsDataDto: Ranked lists of top content.

        Example:
            >>> # content = await AdminAnalyticsService.get_admin_content_analytics(db, query)
        """
        range_ = resolve_analytics_date_range(query)

        # 1. Top articles by opens
        top_articles_stmt = (
            select(
                Article.id.label("article_id"),
                Article.title.label("title"),
                Article.slug.label("slug"),
                Article.status.label("status"),
                Category.name.label("category_name"),
                func.count(UserArticleProgress.id).label("opened_count"),
                func.count(case((UserArticleProgress.completed_at.is_not(None), 1))).label("completed_count"),
            )
            .join(Category, Category.id == Article.category_id)
            .join(
                UserArticleProgress,
                and_(
                    UserArticleProgress.article_id == Article.id,
                    UserArticleProgress.first_opened_at >= range_.from_date,
                    UserArticleProgress.first_opened_at < range_.to_date,
                ),
            )
        )
        if query.categoryId:
            top_articles_stmt = top_articles_stmt.where(Article.category_id == query.categoryId)

        top_articles_stmt = (
            top_articles_stmt.group_by(Article.id, Article.title, Article.slug, Article.status, Category.name)
            .order_by(func.count(UserArticleProgress.id).desc())
            .limit(TOP_LIMIT)
        )
        top_res = await db.execute(top_articles_stmt)
        top_rows = top_res.all()

        article_ids = [r.article_id for r in top_rows]
        saved_counts_map: dict[uuid.UUID, int] = {}
        if article_ids:
            # Fetch saved count per article
            s_stmt = text(
                """
                SELECT ase.article_id, count(uv.id)::int
                FROM user_vocabularies uv
                JOIN article_sentence_terms ast ON ast.id = uv.article_sentence_term_id
                JOIN article_sentences ase ON ase.id = ast.sentence_id
                WHERE ase.article_id = ANY(:article_ids)
                  AND uv.saved_at >= :from_date AND uv.saved_at < :to_date
                GROUP BY ase.article_id
                """
            )
            s_res = await db.execute(
                s_stmt,
                {
                    "article_ids": article_ids,
                    "from_date": range_.from_date,
                    "to_date": range_.to_date,
                },
            )
            saved_counts_map = {row[0]: row[1] for row in s_res.all()}

        top_articles = [
            AdminTopArticleDto(
                articleId=r.article_id,
                title=r.title,
                slug=r.slug,
                status=r.status,
                category=r.category_name,
                openedCount=r.opened_count,
                completedCount=r.completed_count,
                savedVocabularyCount=saved_counts_map.get(r.article_id, 0),
            )
            for r in top_rows
        ]

        # 2. Completion rates
        q_comp = (
            select(
                Article.id.label("article_id"),
                Article.title.label("title"),
                func.count(UserArticleProgress.id).label("opened"),
                func.count(case((UserArticleProgress.completed_at.is_not(None), 1))).label("completed"),
            )
            .join(Article, Article.id == UserArticleProgress.article_id)
            .where(
                UserArticleProgress.first_opened_at >= range_.from_date,
                UserArticleProgress.first_opened_at < range_.to_date,
            )
        )
        if query.categoryId:
            q_comp = q_comp.where(Article.category_id == query.categoryId)

        q_comp = (
            q_comp.group_by(Article.id, Article.title)
            .order_by(
                (
                    func.count(case((UserArticleProgress.completed_at.is_not(None), 1)))
                    * 1.0
                    / func.count(UserArticleProgress.id)
                ).desc(),
                func.count(UserArticleProgress.id).desc(),
                Article.id.asc(),
            )
            .limit(TOP_LIMIT)
        )
        comp_res = await db.execute(q_comp)
        completion_rates = [
            AdminArticleCompletionDto(
                articleId=row.article_id,
                title=row.title,
                opened=row.opened,
                completed=row.completed,
                completionRate=round_ratio(row.completed, row.opened),
            )
            for row in comp_res.all()
        ]

        # 3. Top saved terms
        terms_sql = """
            SELECT ast.id AS term_id,
                   ast.value AS value,
                   ast.lemma AS lemma,
                   ast.cefr_level AS cefr_level,
                   a.id AS article_id,
                   a.title AS article_title,
                   count(uv.id)::int AS save_count
            FROM user_vocabularies uv
            JOIN article_sentence_terms ast ON ast.id = uv.article_sentence_term_id
            JOIN article_sentences ase ON ase.id = ast.sentence_id
            JOIN articles a ON a.id = ase.article_id
            WHERE uv.saved_at >= :from_date AND uv.saved_at < :to_date
        """
        params: dict[str, Any] = {
            "from_date": range_.from_date,
            "to_date": range_.to_date,
            "limit": TOP_LIMIT,
        }
        if query.categoryId:
            terms_sql += " AND a.category_id = :category_id"
            params["category_id"] = query.categoryId

        terms_sql += """
            GROUP BY ast.id, ast.value, ast.lemma, ast.cefr_level, a.id, a.title
            ORDER BY save_count DESC, a.id ASC, ast.id ASC
            LIMIT :limit
        """
        terms_res = await db.execute(text(terms_sql), params)
        term_save_counts = [
            AdminTermSaveDto(
                articleSentenceTermId=row[0],
                value=row[1],
                lemma=row[2],
                cefrLevel=row[3],
                articleId=row[4],
                articleTitle=row[5],
                saveCount=row[6],
            )
            for row in terms_res.all()
        ]

        return AdminContentAnalyticsDataDto(
            topArticles=top_articles,
            completionRates=completion_rates,
            termSaveCounts=term_save_counts,
        )

    @classmethod
    async def get_admin_user_analytics(
        cls,
        db: AsyncSession,
        query: AdminUserAnalyticsQueryDto,
    ) -> AdminUserAnalyticsDataDto:
        """Retrieves registration trends, active learner counts, retention proxy, and learning distribution.

        Args:
            db (AsyncSession): Active database session.
            query (AdminUserAnalyticsQueryDto): Date range and optional account status filter.

        Returns:
            AdminUserAnalyticsDataDto: User activity and retention analytics.

        Example:
            >>> # user_analytics = await AdminAnalyticsService.get_admin_user_analytics(db, query)
        """
        range_ = resolve_analytics_date_range(query)
        group_by = resolve_analytics_group_by(range_)
        unit = {"DAY": "day", "WEEK": "week", "MONTH": "month"}[group_by.value]
        tz_str = settings.ANALYTICS_TIMEZONE

        # 1. Registration trend
        status_filter_sql = "AND status = :status" if query.status else ""
        params: dict[str, Any] = {
            "tz": tz_str,
            "from_date": range_.from_date,
            "to_date": range_.to_date,
        }
        if query.status:
            params["status"] = query.status.value

        reg_stmt = text(
            f"""
            SELECT to_char(date_trunc('{unit}', created_at AT TIME ZONE :tz), 'YYYY-MM-DD') AS bucket,
                   count(*)::int AS registrations
            FROM users
            WHERE created_at >= :from_date AND created_at < :to_date {status_filter_sql}
            GROUP BY bucket
            ORDER BY bucket ASC
            """
        )
        reg_res = await db.execute(reg_stmt, params)
        raw_reg = [{"bucket": row[0], "registrations": row[1]} for row in reg_res.all()]

        registrations_trend = fill_missing_buckets(
            raw_reg,
            range_.from_date,
            range_.to_date,
            group_by,
            map_fn=lambda r: RegistrationTrendBucketDto(bucket=r["bucket"], registrations=r["registrations"]),
            empty_fn=lambda b: RegistrationTrendBucketDto(bucket=b, registrations=0),
        )

        # 2. Distinct active learners in range
        user_status_clause = "JOIN users u ON u.id = active_u.user_id WHERE 1=1 "
        if query.status:
            user_status_clause += "AND u.status = :status "

        active_learners_stmt = text(
            f"""
            SELECT count(DISTINCT active_u.user_id)::int FROM (
                SELECT user_id FROM user_article_progress WHERE last_read_at >= :from_date AND last_read_at < :to_date
                UNION
                SELECT user_id FROM user_vocabularies WHERE saved_at >= :from_date AND saved_at < :to_date
            ) active_u
            {user_status_clause}
            """
        )
        active_res = await db.execute(active_learners_stmt, params)
        active_learners = active_res.scalar() or 0

        # 3. Retention Proxy (Split-window)
        total_duration = range_.to_date - range_.from_date
        midpoint = range_.from_date + total_duration / 2

        window1_params = {
            "from_date": range_.from_date,
            "to_date": midpoint,
            **({"status": query.status.value} if query.status else {}),
        }
        window2_params = {
            "from_date": midpoint,
            "to_date": range_.to_date,
            **({"status": query.status.value} if query.status else {}),
        }

        w1_stmt = text(
            f"""
            SELECT DISTINCT active_u.user_id FROM (
                SELECT user_id FROM user_article_progress WHERE last_read_at >= :from_date AND last_read_at < :to_date
                UNION
                SELECT user_id FROM user_vocabularies WHERE saved_at >= :from_date AND saved_at < :to_date
            ) active_u
            {user_status_clause}
            """
        )
        w1_ids = {row[0] for row in (await db.execute(w1_stmt, window1_params)).all()}
        w2_ids = {row[0] for row in (await db.execute(w1_stmt, window2_params)).all()}

        first_window_active = len(w1_ids)
        second_window_active = len(w2_ids)
        retained_users = len(w1_ids.intersection(w2_ids))
        retention_rate = round_ratio(retained_users, first_window_active)

        retention_proxy = RetentionProxyDto(
            firstWindowActive=first_window_active,
            secondWindowActive=second_window_active,
            retainedUsers=retained_users,
            rate=retention_rate,
        )

        # 4. Learning distribution (readingOnly, vocabularyOnly, multiActivity, inactive)
        q_all_users = select(User.id)
        if query.status:
            q_all_users = q_all_users.where(User.status == query.status)
        all_user_ids = {row[0] for row in (await db.execute(q_all_users)).all()}

        q_reading_users = text(
            """
            SELECT DISTINCT user_id FROM user_article_progress
            WHERE first_opened_at >= :from_date AND first_opened_at < :to_date
            """
        )
        reading_uids = {
            row[0]
            for row in (
                await db.execute(
                    q_reading_users,
                    {"from_date": range_.from_date, "to_date": range_.to_date},
                )
            ).all()
        }

        q_vocab_users = text(
            """
            SELECT DISTINCT user_id FROM user_vocabularies
            WHERE saved_at >= :from_date AND saved_at < :to_date
            """
        )
        vocab_uids = {
            row[0]
            for row in (
                await db.execute(
                    q_vocab_users,
                    {"from_date": range_.from_date, "to_date": range_.to_date},
                )
            ).all()
        }

        # Restrict to all_user_ids
        active_in_scope = reading_uids.union(vocab_uids).intersection(all_user_ids)
        reading_in_scope = reading_uids.intersection(all_user_ids)
        vocab_in_scope = vocab_uids.intersection(all_user_ids)

        multi_activity = len(reading_in_scope.intersection(vocab_in_scope))
        reading_only = len(reading_in_scope - vocab_in_scope)
        vocabulary_only = len(vocab_in_scope - reading_in_scope)
        inactive = len(all_user_ids - active_in_scope)

        learning_distribution = LearningDistributionDto(
            inactive=inactive,
            readingOnly=reading_only,
            vocabularyOnly=vocabulary_only,
            multiActivity=multi_activity,
        )

        return AdminUserAnalyticsDataDto(
            registrationsTrend=registrations_trend,
            activeLearners=active_learners,
            retentionProxy=retention_proxy,
            learningDistribution=learning_distribution,
        )
