from app.models import (
    Artwork,
    ArtworkKind,
    ContentStatus,
    Episode,
    ImportAction,
    ImportIssue,
    Season,
    Show,
)


def _art(db, kind, width, height, *, show_id=None, episode_id=None):
    db.add(
        Artwork(
            show_id=show_id,
            episode_id=episode_id,
            kind=kind,
            storage_key=f"{kind}-{show_id}-{episode_id}",
            width=width,
            height=height,
            bytes=10,
            checksum="c",
        )
    )
    db.flush()


def _publishable_show(db, slug="ok", section="series"):
    show = Show(
        slug=slug,
        title=slug.upper(),
        synopsis="",
        section=section,
        categories=["music"],
        status=ContentStatus.published,
    )
    db.add(show)
    db.flush()
    season = Season(show_id=show.id, season_number=1)
    db.add(season)
    db.flush()
    episode = Episode(
        season_id=season.id,
        episode_number=1,
        title="E1",
        duration_seconds=300,
        language="en",
        content_group=f"{slug}-s01e01",
        status=ContentStatus.published,
    )
    db.add(episode)
    db.flush()
    _art(db, ArtworkKind.thumbnail, 640, 360, episode_id=episode.id)
    _art(db, ArtworkKind.poster, 600, 900, show_id=show.id)
    _art(db, ArtworkKind.banner, 1280, 720, show_id=show.id)
    return show, season, episode


def _report(api, headers):
    response = api.get("/admin/validation-report", headers=headers)
    assert response.status_code == 200
    return response.json()


def _codes(report, key):
    return {issue["code"] for group in report["groups"] for issue in group[key]}


def test_clean_data_can_publish(api, db, editor_headers):
    _publishable_show(db)
    report = _report(api, editor_headers)
    assert report["can_publish"] is True
    assert report["blocking_count"] == 0


def test_published_show_without_section_blocks(api, db, editor_headers):
    show, _, _ = _publishable_show(db)
    show.section = None
    db.flush()
    report = _report(api, editor_headers)
    assert report["can_publish"] is False
    assert "show_missing_section" in _codes(report, "blocking")


def test_published_episode_without_artwork_blocks(api, db, editor_headers):
    _, _, episode = _publishable_show(db)
    for record in list(episode.artwork):
        db.delete(record)
    db.flush()
    report = _report(api, editor_headers)
    assert "episode_missing_artwork" in _codes(report, "blocking")


def test_published_episode_without_duration_blocks(api, db, editor_headers):
    _, _, episode = _publishable_show(db)
    episode.duration_seconds = None
    db.flush()
    report = _report(api, editor_headers)
    assert "episode_missing_duration" in _codes(report, "blocking")


def test_trailer_without_poster_warns_and_does_not_block(api, db, editor_headers):
    """Decision D4: a trailer needs a thumbnail only."""
    show, _, _ = _publishable_show(db)
    season_zero = Season(show_id=show.id, season_number=0)
    db.add(season_zero)
    db.flush()
    trailer = Episode(
        season_id=season_zero.id,
        episode_number=1,
        title="Trailer",
        duration_seconds=75,
        language="en",
        content_group=f"{show.slug}-s00e01",
        status=ContentStatus.published,
    )
    db.add(trailer)
    db.flush()
    _art(db, ArtworkKind.thumbnail, 640, 360, episode_id=trailer.id)

    report = _report(api, editor_headers)
    assert report["can_publish"] is True
    assert "trailer_thumbnail_only" in _codes(report, "warnings")


def test_trailer_without_a_thumbnail_blocks(api, db, editor_headers):
    show, _, _ = _publishable_show(db)
    season_zero = Season(show_id=show.id, season_number=0)
    db.add(season_zero)
    db.flush()
    db.add(
        Episode(
            season_id=season_zero.id,
            episode_number=1,
            title="Trailer",
            duration_seconds=75,
            language="en",
            content_group=f"{show.slug}-s00e01",
            status=ContentStatus.published,
        )
    )
    db.flush()
    report = _report(api, editor_headers)
    assert report["can_publish"] is False
    assert "trailer_missing_thumbnail" in _codes(report, "blocking")


def test_divergent_variant_durations_warn(api, db, editor_headers):
    show, season, episode = _publishable_show(db)
    hindi = Episode(
        season_id=season.id,
        episode_number=1,
        title="E1",
        duration_seconds=900,
        language="hi",
        content_group=episode.content_group,
        status=ContentStatus.published,
    )
    db.add(hindi)
    db.flush()
    _art(db, ArtworkKind.thumbnail, 640, 360, episode_id=hindi.id)

    report = _report(api, editor_headers)
    assert "variant_duration_mismatch" in _codes(report, "warnings")
    assert report["can_publish"] is True


def test_small_duration_difference_does_not_warn(api, db, editor_headers):
    show, season, episode = _publishable_show(db)
    hindi = Episode(
        season_id=season.id,
        episode_number=1,
        title="E1",
        duration_seconds=330,
        language="hi",
        content_group=episode.content_group,
        status=ContentStatus.published,
    )
    db.add(hindi)
    db.flush()
    _art(db, ArtworkKind.thumbnail, 640, 360, episode_id=hindi.id)

    report = _report(api, editor_headers)
    assert "variant_duration_mismatch" not in _codes(report, "warnings")


def test_import_problems_are_surfaced(api, db, editor_headers):
    db.add_all(
        [
            ImportIssue(
                source_row={"episode_id": "ep_9001"},
                reason="Duplicate Hindi version of motis-many-lives-s01e02.",
                action=ImportAction.rejected,
            ),
            ImportIssue(
                source_row={"episode_id": "ep_0036"},
                reason="Marked published but has no artwork.",
                action=ImportAction.downgraded_to_draft,
            ),
        ]
    )
    db.flush()
    report = _report(api, editor_headers)
    assert len(report["import_problems"]) == 2
    assert {p["action"] for p in report["import_problems"]} == {
        "rejected",
        "downgraded_to_draft",
    }


def test_report_requires_authentication(api):
    assert api.get("/admin/validation-report").status_code == 401


def test_draft_show_with_no_section_does_not_block(api, db, editor_headers):
    """rhyme-rangers in the seed is entirely draft.

    A draft show missing a section is a future problem, not a current blocker.
    """
    db.add(Show(slug="draft-one", title="Draft One", synopsis="", section=None, categories=[]))
    db.flush()
    report = _report(api, editor_headers)
    assert report["can_publish"] is True


def test_every_issue_carries_a_label_and_fix_hint(api, db, editor_headers):
    """An editor needs to know what to open, not just that something is wrong."""
    show, _, _ = _publishable_show(db)
    show.section = None
    db.flush()
    report = _report(api, editor_headers)
    for group in report["groups"]:
        for issue in group["blocking"] + group["warnings"]:
            assert issue["entity_label"]
            assert issue["fix_hint"]
            assert "—" not in issue["message"]
