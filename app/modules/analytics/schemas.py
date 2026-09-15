"""Pydantic schemas and DTOs for the Analytics module managing learner and admin performance metrics."""

import uuid
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ArticleStatus, CefrLevel, UserStatus

# ---------------------------------------------------------------------------
# Enums & Query DTOs
# ---------------------------------------------------------------------------


class AnalyticsGroupBy(StrEnum):
    """Granularity options for aggregating analytics metrics into time series buckets."""

    DAY = "DAY"
    WEEK = "WEEK"
    MONTH = "MONTH"


class AnalyticsDateRangeQueryDto(BaseModel):
    """Base query parameters establishing a half-open interval [from, to) for reporting metrics.

    Attributes:
        from_time (str | None): Range start ISO timestamp.
        to_time (str | None): Range end ISO timestamp.
    """

    from_time: str | None = Field(default=None, alias="from", description="Range start ISO timestamp")
    to_time: str | None = Field(default=None, alias="to", description="Range end ISO timestamp")

    model_config = ConfigDict(populate_by_name=True)


class VocabularyAnalyticsQueryDto(AnalyticsDateRangeQueryDto):
    """Query parameters for learner vocabulary growth metrics and time series aggregation.

    Attributes:
        groupBy (AnalyticsGroupBy | None): Trend bucket size (DAY, WEEK, MONTH).
    """

    groupBy: AnalyticsGroupBy | None = Field(default=None, description="Aggregation granularity")


class AdminContentAnalyticsQueryDto(AnalyticsDateRangeQueryDto):
    """Query parameters filtering administrative content analytics by article category.

    Attributes:
        categoryId (uuid.UUID | None): Category filter identifier.
    """

    categoryId: uuid.UUID | None = Field(default=None, description="Filter content metrics to this category")


class AdminUserAnalyticsQueryDto(AnalyticsDateRangeQueryDto):
    """Query parameters filtering administrative user activity and cohort analytics by account status.

    Attributes:
        status (UserStatus | None): Account status filter.
    """

    status: UserStatus | None = Field(default=None, description="Applies account-status filter")


# ---------------------------------------------------------------------------
# Learner Overview & Vocabulary DTOs
# ---------------------------------------------------------------------------


class AnalyticsOverviewDataDto(BaseModel):
    """High-level summary metrics for the authenticated learner.

    Attributes:
        savedVocabulary (int): Current saved vocabulary stock count.
        articlesCompleted (int): Count of articles completed in the interval.
    """

    savedVocabulary: int = Field(ge=0, description="Current saved vocabulary stock")
    articlesCompleted: int = Field(ge=0, description="Reading progress records completed in interval")


class VocabularyAnalyticsTotalsDto(BaseModel):
    """Aggregated total count for saved vocabulary items.

    Attributes:
        total (int): Total saved vocabulary items.
    """

    total: int = Field(ge=0)


class VocabularyCefrCountDto(BaseModel):
    """Saved vocabulary count grouped by CEFR difficulty level.

    Attributes:
        cefrLevel (CefrLevel): CEFR proficiency level (A1-C2).
        count (int): Number of words saved at this level.
    """

    cefrLevel: CefrLevel
    count: int = Field(ge=0)


class VocabularyTrendBucketDto(BaseModel):
    """Time series data point representing vocabulary saves within an aggregated bucket.

    Attributes:
        bucket (str): Date label string (YYYY-MM-DD).
        count (int): Number of words saved in bucket.
    """

    bucket: str
    count: int = Field(ge=0)


class VocabularyAnalyticsDataDto(BaseModel):
    """Composite vocabulary analytics payload including current totals, CEFR breakdown, and growth trend.

    Attributes:
        totals (VocabularyAnalyticsTotalsDto): Total vocabulary count.
        byCefr (list[VocabularyCefrCountDto]): Distribution across CEFR levels.
        savedTrend (list[VocabularyTrendBucketDto]): Time series trend.
    """

    totals: VocabularyAnalyticsTotalsDto
    byCefr: list[VocabularyCefrCountDto]
    savedTrend: list[VocabularyTrendBucketDto]


# ---------------------------------------------------------------------------
# Learner Reading DTOs
# ---------------------------------------------------------------------------


class ReadingCategoryAnalyticsDto(BaseModel):
    """Reading activity and completion metrics broken down by article category.

    Attributes:
        categoryId (uuid.UUID): Category identifier.
        categoryName (str): Category display title.
        opened (int): Count of articles opened in this category.
        completed (int): Count of articles completed in this category.
        completionRate (float): Decimal completion ratio [0, 1].
    """

    categoryId: uuid.UUID
    categoryName: str
    opened: int = Field(ge=0)
    completed: int = Field(ge=0)
    completionRate: float = Field(ge=0.0, le=1.0)


class ReadingTrendBucketDto(BaseModel):
    """Time series bucket tracking articles opened and finished within a time interval.

    Attributes:
        bucket (str): Date label string (YYYY-MM-DD).
        opened (int): Number of articles opened.
        completed (int): Number of articles completed.
    """

    bucket: str
    opened: int = Field(ge=0)
    completed: int = Field(ge=0)


class ReadingAnalyticsDataDto(BaseModel):
    """Reading analytics payload containing aggregate completion rate, category breakdown, and trend.

    Attributes:
        opened (int): Total articles opened.
        completed (int): Total articles completed.
        completionRate (float): Overall completion ratio [0, 1].
        byCategory (list[ReadingCategoryAnalyticsDto]): Breakdown per category.
        trend (list[ReadingTrendBucketDto]): Time series trend.
    """

    opened: int = Field(ge=0)
    completed: int = Field(ge=0)
    completionRate: float = Field(ge=0.0, le=1.0)
    byCategory: list[ReadingCategoryAnalyticsDto]
    trend: list[ReadingTrendBucketDto]


# ---------------------------------------------------------------------------
# Learner Review & Streak DTOs
# ---------------------------------------------------------------------------


class RecentDayItemDto(BaseModel):
    """Individual day representation in the 7-day trailing activity tracker.

    Attributes:
        date (str): Calendar date string (YYYY-MM-DD).
        isCompleted (bool): True if study session was completed on this date.
        isToday (bool): True if this represents current study date.
    """

    date: str
    isCompleted: bool
    isToday: bool


class StreakAnalyticsDto(BaseModel):
    """Learning streak metrics tracking consecutive daily tutor session completions.

    Attributes:
        currentStreak (int): Current consecutive study streak in days.
        longestStreak (int): Longest consecutive study streak recorded.
        isTodayCompleted (bool): Whether today's tutor session is completed.
        recentDays (list[RecentDayItemDto]): 7-day activity tracking checklist.
        completedDates (list[str]): List of all completed study dates.
    """

    currentStreak: int = Field(ge=0)
    longestStreak: int = Field(ge=0)
    isTodayCompleted: bool
    recentDays: list[RecentDayItemDto]
    completedDates: list[str]


class FsrsMasteryAnalyticsDto(BaseModel):
    """FSRS spaced-repetition memory state breakdown and overall mastery rate.

    Attributes:
        total (int): Total saved vocabulary items.
        newCount (int): Number of words in NEW state.
        learningCount (int): Number of words in LEARNING state.
        reviewCount (int): Number of words in REVIEW (mastered) state.
        relearningCount (int): Number of words in RELEARNING state.
        masteryRate (float): Mastery ratio reviewCount / total [0, 1].
    """

    total: int = Field(ge=0)
    newCount: int = Field(ge=0)
    learningCount: int = Field(ge=0)
    reviewCount: int = Field(ge=0)
    relearningCount: int = Field(ge=0)
    masteryRate: float = Field(ge=0.0, le=1.0)


class ReviewAnalyticsDataDto(BaseModel):
    """Composite review analytics payload combining study streak calculations and FSRS memory distribution.

    Attributes:
        streak (StreakAnalyticsDto): Streak metrics.
        mastery (FsrsMasteryAnalyticsDto): FSRS memory state distribution.
    """

    streak: StreakAnalyticsDto
    mastery: FsrsMasteryAnalyticsDto


# ---------------------------------------------------------------------------
# Admin Overview & Content DTOs
# ---------------------------------------------------------------------------


class AdminAnalyticsOverviewDataDto(BaseModel):
    """Platform-wide operational overview reporting total users, active users, articles, and saved words.

    Attributes:
        users (int): Total registered users count.
        activeUsers (int): Users active during interval.
        articles (int): Total articles count.
        publishedArticles (int): Total published articles.
        savedVocabulary (int): Total vocabulary items saved in interval.
    """

    users: int = Field(ge=0)
    activeUsers: int = Field(ge=0)
    articles: int = Field(ge=0)
    publishedArticles: int = Field(ge=0)
    savedVocabulary: int = Field(ge=0)


class AdminTopArticleDto(BaseModel):
    """Ranked article summary metrics highlighting reading volume and vocabulary engagement.

    Attributes:
        articleId (uuid.UUID): Article identifier.
        title (str): Article title headline.
        slug (str): Article URL slug.
        status (ArticleStatus): Editorial status.
        category (str): Category name.
        openedCount (int): Reading session count.
        completedCount (int): Finished reading count.
        savedVocabularyCount (int): Number of times words were saved from this article.
    """

    articleId: uuid.UUID
    title: str
    slug: str
    status: ArticleStatus
    category: str
    openedCount: int = Field(ge=0)
    completedCount: int = Field(ge=0)
    savedVocabularyCount: int = Field(ge=0)


class AdminArticleCompletionDto(BaseModel):
    """Article reading completion metrics used to identify top-finishing content.

    Attributes:
        articleId (uuid.UUID): Article identifier.
        title (str): Article title headline.
        opened (int): Number of times opened.
        completed (int): Number of times finished.
        completionRate (float): Decimal completion ratio [0, 1].
    """

    articleId: uuid.UUID
    title: str
    opened: int = Field(ge=0)
    completed: int = Field(ge=0)
    completionRate: float = Field(ge=0.0, le=1.0)


class AdminTermSaveDto(BaseModel):
    """Frequency metrics for specific vocabulary term occurrences saved by learners.

    Attributes:
        articleSentenceTermId (uuid.UUID): Term occurrence identifier.
        value (str): Term text.
        lemma (str): Dictionary base lemma.
        cefrLevel (CefrLevel): Complexity grade.
        articleId (uuid.UUID): Source article ID.
        articleTitle (str): Source article title.
        saveCount (int): Times saved across all learners.
    """

    articleSentenceTermId: uuid.UUID
    value: str
    lemma: str
    cefrLevel: CefrLevel
    articleId: uuid.UUID
    articleTitle: str
    saveCount: int = Field(ge=0)


class AdminContentAnalyticsDataDto(BaseModel):
    """Bounded administrative content analytics payload containing top articles, completion rates, and term saves.

    Attributes:
        topArticles (list[AdminTopArticleDto]): Top opened articles.
        completionRates (list[AdminArticleCompletionDto]): Top completed articles.
        termSaveCounts (list[AdminTermSaveDto]): Top saved vocabulary terms.
    """

    topArticles: list[AdminTopArticleDto]
    completionRates: list[AdminArticleCompletionDto]
    termSaveCounts: list[AdminTermSaveDto]


# ---------------------------------------------------------------------------
# Admin User Activity & Cohort DTOs
# ---------------------------------------------------------------------------


class RegistrationTrendBucketDto(BaseModel):
    """Time series bucket tracking new learner registrations.

    Attributes:
        bucket (str): Date label string (YYYY-MM-DD).
        registrations (int): Number of accounts registered in bucket.
    """

    bucket: str
    registrations: int = Field(ge=0)


class RetentionProxyDto(BaseModel):
    """Split-window retention metric comparing user activity between first and second halves of range.

    Attributes:
        firstWindowActive (int): Active users in first half.
        secondWindowActive (int): Active users in second half.
        retainedUsers (int): Users active in both halves.
        rate (float): Retention ratio [0, 1].
    """

    firstWindowActive: int = Field(ge=0)
    secondWindowActive: int = Field(ge=0)
    retainedUsers: int = Field(ge=0)
    rate: float = Field(ge=0.0, le=1.0)


class LearningDistributionDto(BaseModel):
    """Mutually exclusive breakdown of users across distinct study engagement categories.

    Attributes:
        inactive (int): Registered users with no activity in interval.
        readingOnly (int): Users who opened/completed articles but saved no words.
        vocabularyOnly (int): Users who saved words but opened no articles.
        multiActivity (int): Users who engaged in both reading and vocabulary saving.
    """

    inactive: int = Field(ge=0)
    readingOnly: int = Field(ge=0)
    vocabularyOnly: int = Field(ge=0)
    multiActivity: int = Field(ge=0)


class AdminUserAnalyticsDataDto(BaseModel):
    """Administrative user analytics payload containing registration trend, active count, retention, and distribution.

    Attributes:
        registrationsTrend (list[RegistrationTrendBucketDto]): User registration time series.
        activeLearners (int): Distinct active learners in range.
        retentionProxy (RetentionProxyDto): Cohort retention proxy metrics.
        learningDistribution (LearningDistributionDto): Engagement category distribution.
    """

    registrationsTrend: list[RegistrationTrendBucketDto]
    activeLearners: int = Field(ge=0)
    retentionProxy: RetentionProxyDto
    learningDistribution: LearningDistributionDto
