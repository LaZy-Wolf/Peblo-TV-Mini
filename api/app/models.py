import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Role(StrEnum):
    editor = "editor"
    admin = "admin"


class ContentStatus(StrEnum):
    draft = "draft"
    published = "published"


class RunStatus(StrEnum):
    running = "running"
    success = "success"
    failed = "failed"
    no_change = "no_change"


class ArtworkKind(StrEnum):
    poster = "poster"
    banner = "banner"
    thumbnail = "thumbnail"


class ImportAction(StrEnum):
    rejected = "rejected"
    downgraded_to_draft = "downgraded_to_draft"


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _updated_at() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class Show(Base):
    __tablename__ = "shows"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    synopsis: Mapped[str] = mapped_column(Text, default="", nullable=False)
    section: Mapped[str | None] = mapped_column(String(32))
    categories: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=ContentStatus.draft.value, nullable=False
    )
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    seasons: Mapped[list["Season"]] = relationship(
        back_populates="show", cascade="all, delete-orphan"
    )
    artwork: Mapped[list["Artwork"]] = relationship(
        back_populates="show", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Serves both the publish query and the validation report, which share
        # this exact predicate.
        Index("ix_shows_status_section", "status", "section"),
        # Serves the category filter, which uses the @> containment operator.
        Index("ix_shows_categories_gin", "categories", postgresql_using="gin"),
    )


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(primary_key=True)
    show_id: Mapped[int] = mapped_column(
        ForeignKey("shows.id", ondelete="CASCADE"), nullable=False
    )
    season_number: Mapped[int] = mapped_column(Integer, nullable=False)

    show: Mapped[Show] = relationship(back_populates="seasons")
    episodes: Mapped[list["Episode"]] = relationship(
        back_populates="season", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("show_id", "season_number", name="uq_seasons_show_number"),
    )


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False
    )
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    content_group: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=ContentStatus.draft.value, nullable=False
    )
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    season: Mapped[Season] = relationship(back_populates="episodes")
    artwork: Mapped[list["Artwork"]] = relationship(
        back_populates="episode", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # The brief's constraint, enforced by the database rather than by
        # application code, so a concurrent write cannot slip past it.
        # Also the grouping key at catalogue build time.
        UniqueConstraint("content_group", "language", name="uq_episodes_group_language"),
        Index("ix_episodes_season_number", "season_id", "episode_number"),
        Index("ix_episodes_content_group", "content_group"),
    )


class Artwork(Base):
    __tablename__ = "artwork"

    id: Mapped[int] = mapped_column(primary_key=True)
    show_id: Mapped[int | None] = mapped_column(ForeignKey("shows.id", ondelete="CASCADE"))
    episode_id: Mapped[int | None] = mapped_column(ForeignKey("episodes.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _created_at()

    show: Mapped[Show | None] = relationship(back_populates="artwork")
    episode: Mapped[Episode | None] = relationship(back_populates="artwork")

    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(show_id, episode_id) = 1", name="ck_artwork_exactly_one_owner"
        ),
        Index(
            "uq_artwork_show_kind",
            "show_id",
            "kind",
            unique=True,
            postgresql_where=show_id.isnot(None),
        ),
        Index(
            "uq_artwork_episode_kind",
            "episode_id",
            "kind",
            unique=True,
            postgresql_where=episode_id.isnot(None),
        ),
    )


class PublishRun(Base):
    __tablename__ = "publish_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    started_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[datetime] = _created_at()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    catalog_key: Mapped[str | None] = mapped_column(String(512))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    counts: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (Index("ix_publish_runs_started_at", started_at.desc()),)


class CatalogPointer(Base):
    """Single row. Flipping current_run_id is the atomic commit point of a publish."""

    __tablename__ = "catalog_pointer"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    current_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("publish_runs.id", ondelete="RESTRICT")
    )
    updated_at: Mapped[datetime] = _updated_at()

    __table_args__ = (CheckConstraint("id = 1", name="ck_catalog_pointer_singleton"),)


class ImportIssue(Base):
    __tablename__ = "import_issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_row: Mapped[dict] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = _created_at()
