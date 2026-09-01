from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ShowCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=255)
    synopsis: str = ""
    section: str | None = None
    categories: list[str] = Field(default_factory=list)


class ShowUpdate(BaseModel):
    title: str | None = None
    synopsis: str | None = None
    section: str | None = None
    categories: list[str] | None = None
    status: str | None = None


class ShowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    synopsis: str
    section: str | None
    categories: list[str]
    status: str
    updated_at: datetime


class SeasonCreate(BaseModel):
    season_number: int = Field(ge=0)


class EpisodeCreate(BaseModel):
    season_id: int
    episode_number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=255)
    duration_seconds: int | None = Field(default=None, ge=1)
    language: str
    content_group: str = Field(min_length=1, max_length=160)


class EpisodeUpdate(BaseModel):
    episode_number: int | None = Field(default=None, ge=1)
    title: str | None = None
    duration_seconds: int | None = Field(default=None, ge=1)
    language: str | None = None
    content_group: str | None = None
    status: str | None = None


class EpisodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season_id: int
    episode_number: int
    title: str
    duration_seconds: int | None
    language: str
    content_group: str
    status: str


class Page(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
