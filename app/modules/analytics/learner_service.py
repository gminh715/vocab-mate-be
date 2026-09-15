"""Learner analytics service calculating personal vocabulary acquisition, reading velocity, and FSRS streaks."""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.articles import Article
from app.models.categories import Category
from app.models.enums import CefrLevel, FsrsCardState, TutorSessionStatus
from app.models.reading import UserArticleProgress
from app.models.tutor import TutorSession
from app.models.vocabularies import UserVocabulary
from app.modules.analytics.helpers import (
    calculate_streak,
    fill_missing_buckets,
    format_date_to_study_date,
    get_analytics_timezone,
    resolve_analytics_date_range,
    resolve_analytics_group_by,
    round_ratio,
)
from app.modules.analytics.schemas import (
    AnalyticsDateRangeQueryDto,
    AnalyticsOverviewDataDto,
    FsrsMasteryAnalyticsDto,
    ReadingAnalyticsDataDto,
    ReadingCategoryAnalyticsDto,
    ReadingTrendBucketDto,
    RecentDayItemDto,
    ReviewAnalyticsDataDto,
    StreakAnalyticsDto,
    VocabularyAnalyticsDataDto,
    VocabularyAnalyticsQueryDto,
    VocabularyAnalyticsTotalsDto,
    VocabularyCefrCountDto,
    VocabularyTrendBucketDto,
)

ALL_CEFR_LEVELS = [
    CefrLevel.A1,
    CefrLevel.A2,
    CefrLevel.B1,
    CefrLevel.B2,
    CefrLevel.C1,
    CefrLevel.C2,
]


class LearnerAnalyticsService:
    """Calculates personal learning metrics, reading cohorts, and FSRS retention velocity."""

    @classmethod
    async def get_overview(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        query: AnalyticsDateRangeQueryDto,
    ) -> AnalyticsOverviewDataDto:
        """Retrieves high-level summary metrics of saved words and completed articles.

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Authenticated user identifier.
            query (AnalyticsDateRangeQueryDto): Date range filter.

        Returns:
            AnalyticsOverviewDataDto: Summary counts.

        Example:
            >>> # overview = await LearnerAnalyticsService.get_overview(db, user_id, query)
        """
        range_ = resolve_analytics_date_range(query)

        # 1. Total vocabulary stock
        q_vocab = select(func.count()).select_from(UserVocabulary).where(UserVocabulary.user_id == user_id)
        vocab_res = await db.execute(q_vocab)
        saved_vocabulary = vocab_res.scalar() or 0

        # 2. Articles completed in [from, to)
        q_articles = (
            select(func.count())
            .select_from(UserArticleProgress)
            .where(
                UserArticleProgress.user_id == user_id,
                UserArticleProgress.completed_at >= range_.from_date,
                UserArticleProgress.completed_at < range_.to_date,
            )
        )
        articles_res = await db.execute(q_articles)
        articles_completed = articles_res.scalar() or 0

        return AnalyticsOverviewDataDto(
            savedVocabulary=saved_vocabulary,
            articlesCompleted=articles_completed,
        )

    @classmethod
    async def get_vocabulary_analytics(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        query: VocabularyAnalyticsQueryDto,
    ) -> VocabularyAnalyticsDataDto:
        """Generates comprehensive vocabulary growth analytics and CEFR distribution.

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Authenticated user identifier.
            query (VocabularyAnalyticsQueryDto): Date range and grouping granularity.

        Returns:
            VocabularyAnalyticsDataDto: CEFR breakdown and interpolated time series trend.

        Example:
            >>> # vocab_analytics = await LearnerAnalyticsService.get_vocabulary_analytics(db, user_id, query)
        """
        range_ = resolve_analytics_date_range(query)
        group_by = resolve_analytics_group_by(range_, query.groupBy)

        # 1. Total count
        q_total = select(func.count()).select_from(UserVocabulary).where(UserVocabulary.user_id == user_id)
        total = (await db.execute(q_total)).scalar() or 0

        # 2. CEFR distribution
        q_cefr = (
            select(UserVocabulary.saved_cefr_level, func.count())
            .where(UserVocabulary.user_id == user_id)
            .group_by(UserVocabulary.saved_cefr_level)
        )
        cefr_res = await db.execute(q_cefr)
        cefr_counts = {level: count for level, count in cefr_res.all()}

        by_cefr = [
            VocabularyCefrCountDto(cefrLevel=level, count=cefr_counts.get(level, 0)) for level in ALL_CEFR_LEVELS
        ]

        # 3. Historical save trend
        unit = {"DAY": "day", "WEEK": "week", "MONTH": "month"}[group_by.value]
        tz_str = settings.ANALYTICS_TIMEZONE

        stmt = text(
            f"""
            SELECT to_char(date_trunc('{unit}', saved_at AT TIME ZONE :tz), 'YYYY-MM-DD') AS bucket,
                   count(*)::int AS count
            FROM user_vocabularies
            WHERE user_id = :user_id AND saved_at >= :from_date AND saved_at < :to_date
            GROUP BY bucket
            ORDER BY bucket ASC
            """
        )
        trend_res = await db.execute(
            stmt,
            {
                "tz": tz_str,
                "user_id": user_id,
                "from_date": range_.from_date,
                "to_date": range_.to_date,
            },
        )
        raw_trend = [{"bucket": row[0], "count": row[1]} for row in trend_res.all()]

        saved_trend = fill_missing_buckets(
            raw_trend,
            range_.from_date,
            range_.to_date,
            group_by,
            map_fn=lambda r: VocabularyTrendBucketDto(bucket=r["bucket"], count=r["count"]),
            empty_fn=lambda b: VocabularyTrendBucketDto(bucket=b, count=0),
        )

        return VocabularyAnalyticsDataDto(
            totals=VocabularyAnalyticsTotalsDto(total=total),
            byCefr=by_cefr,
            savedTrend=saved_trend,
        )

    @classmethod
    async def get_reading_analytics(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        query: AnalyticsDateRangeQueryDto,
    ) -> ReadingAnalyticsDataDto:
        """Retrieves reading cohort metrics, category breakdowns, and reading velocity trends.

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Authenticated user identifier.
            query (AnalyticsDateRangeQueryDto): Date range filter.

        Returns:
            ReadingAnalyticsDataDto: Reading volume, completion ratios, and trends.

        Example:
            >>> # reading_analytics = await LearnerAnalyticsService.get_reading_analytics(db, user_id, query)
        """
        range_ = resolve_analytics_date_range(query)
        group_by = resolve_analytics_group_by(range_)

        # 1. Total cohort opened and completed
        cohort_filter = [
            UserArticleProgress.user_id == user_id,
            UserArticleProgress.first_opened_at >= range_.from_date,
            UserArticleProgress.first_opened_at < range_.to_date,
        ]

        q_totals = select(
            func.count().label("opened"),
            func.count(case((UserArticleProgress.completed_at.is_not(None), 1))).label("completed"),
        ).where(*cohort_filter)

        totals_res = (await db.execute(q_totals)).one()
        opened = totals_res.opened or 0
        completed = totals_res.completed or 0
        completion_rate = round_ratio(completed, opened)

        # 2. Breakdown by category
        q_category = (
            select(
                Category.id.label("category_id"),
                Category.name.label("category_name"),
                func.count(UserArticleProgress.id).label("opened"),
                func.count(case((UserArticleProgress.completed_at.is_not(None), 1))).label("completed"),
            )
            .join(Article, Article.id == UserArticleProgress.article_id)
            .join(Category, Category.id == Article.category_id)
            .where(*cohort_filter)
            .group_by(Category.id, Category.name)
            .order_by(func.count(UserArticleProgress.id).desc())
        )
        cat_res = await db.execute(q_category)
        by_category = [
            ReadingCategoryAnalyticsDto(
                categoryId=row.category_id,
                categoryName=row.category_name,
                opened=row.opened,
                completed=row.completed,
                completionRate=round_ratio(row.completed, row.opened),
            )
            for row in cat_res.all()
        ]

        # 3. Time series trend
        unit = {"DAY": "day", "WEEK": "week", "MONTH": "month"}[group_by.value]
        tz_str = settings.ANALYTICS_TIMEZONE

        stmt = text(
            f"""
            SELECT to_char(date_trunc('{unit}', first_opened_at AT TIME ZONE :tz), 'YYYY-MM-DD') AS bucket,
                   count(*)::int AS opened,
                   count(CASE WHEN completed_at IS NOT NULL THEN 1 END)::int AS completed
            FROM user_article_progress
            WHERE user_id = :user_id AND first_opened_at >= :from_date AND first_opened_at < :to_date
            GROUP BY bucket
            ORDER BY bucket ASC
            """
        )
        trend_res = await db.execute(
            stmt,
            {
                "tz": tz_str,
                "user_id": user_id,
                "from_date": range_.from_date,
                "to_date": range_.to_date,
            },
        )
        raw_trend = [{"bucket": row[0], "opened": row[1], "completed": row[2]} for row in trend_res.all()]

        trend = fill_missing_buckets(
            raw_trend,
            range_.from_date,
            range_.to_date,
            group_by,
            map_fn=lambda r: ReadingTrendBucketDto(bucket=r["bucket"], opened=r["opened"], completed=r["completed"]),
            empty_fn=lambda b: ReadingTrendBucketDto(bucket=b, opened=0, completed=0),
        )

        return ReadingAnalyticsDataDto(
            opened=opened,
            completed=completed,
            completionRate=completion_rate,
            byCategory=by_category,
            trend=trend,
        )

    @classmethod
    async def get_review_analytics(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> ReviewAnalyticsDataDto:
        """Retrieves consecutive study streaks, 7-day activity checklist, and FSRS mastery distribution.

        Args:
            db (AsyncSession): Active database session.
            user_id (uuid.UUID): Authenticated user identifier.

        Returns:
            ReviewAnalyticsDataDto: Streak and FSRS memory state metrics.

        Example:
            >>> # review_analytics = await LearnerAnalyticsService.get_review_analytics(db, user_id)
        """
        now = datetime.now(UTC)
        tz = get_analytics_timezone()
        today_str = format_date_to_study_date(now, tz)

        # 1. FSRS state counts
        q_states = (
            select(UserVocabulary.fsrs_state, func.count())
            .where(UserVocabulary.user_id == user_id)
            .group_by(UserVocabulary.fsrs_state)
        )
        state_res = await db.execute(q_states)
        state_map = {row[0]: row[1] for row in state_res.all()}

        new_count = state_map.get(FsrsCardState.NEW, 0)
        learning_count = state_map.get(FsrsCardState.LEARNING, 0)
        review_count = state_map.get(FsrsCardState.REVIEW, 0)
        relearning_count = state_map.get(FsrsCardState.RELEARNING, 0)
        total = new_count + learning_count + review_count + relearning_count
        mastery_rate = round_ratio(review_count, total)

        mastery = FsrsMasteryAnalyticsDto(
            total=total,
            newCount=new_count,
            learningCount=learning_count,
            reviewCount=review_count,
            relearningCount=relearning_count,
            masteryRate=mastery_rate,
        )

        # 2. Completed study dates
        q_sessions = select(TutorSession.study_date).where(
            TutorSession.user_id == user_id,
            TutorSession.status == TutorSessionStatus.COMPLETED,
        )
        sess_res = await db.execute(q_sessions)
        completed_dates_set = {
            row[0].strftime("%Y-%m-%d") if isinstance(row[0], datetime | type(date(2026, 1, 1))) else str(row[0])[:10]
            for row in sess_res.all()
        }

        current_streak, longest_streak, is_today_completed, recent_days_raw = calculate_streak(
            completed_dates_set, today_str
        )

        streak = StreakAnalyticsDto(
            currentStreak=current_streak,
            longestStreak=longest_streak,
            isTodayCompleted=is_today_completed,
            recentDays=[RecentDayItemDto(**d) for d in recent_days_raw],
            completedDates=sorted(completed_dates_set),
        )

        return ReviewAnalyticsDataDto(streak=streak, mastery=mastery)
