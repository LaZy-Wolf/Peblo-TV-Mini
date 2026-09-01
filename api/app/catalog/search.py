"""Search over the published catalogue.

Deliberately a linear scan over the same artifact the viewer renders. That
makes it impossible for search to return something the browse pages cannot
show, and impossible for it to leak an unpublished row.

Scale ceiling, stated honestly: fine to roughly 10k entries and a few MB,
which is far beyond this catalogue. Past that, build a catalog_entries
projection table at publish time and query it with a Postgres tsvector index,
which also buys stemming and ranking. Past roughly a million entries, or as
soon as typo tolerance matters, move to a dedicated engine fed by the same
publish job.
"""


def _show_summary(show: dict, section: str) -> dict:
    return {
        "slug": show["slug"],
        "title": show["title"],
        "synopsis": show["synopsis"],
        "section": section,
        "categories": show["categories"],
        "languages": show["languages"],
        "artwork": show["artwork"],
    }


def search_catalog(
    catalog: dict,
    q: str | None = None,
    category: str | None = None,
    language: str | None = None,
    section: str | None = None,
) -> dict:
    needle = (q or "").strip().lower()
    results: list[dict] = []

    for block in catalog["sections"]:
        if section and block["key"] != section:
            continue

        for show in block["shows"]:
            if category and category not in show["categories"]:
                continue
            if language and language not in show["languages"]:
                continue

            summary = _show_summary(show, block["key"])

            if not needle:
                results.append({"match": "show", "show": summary, "episode": None})
                continue

            if needle in show["title"].lower():
                results.append({"match": "show", "show": summary, "episode": None})
                continue

            if any(needle in c.lower() for c in show["categories"]):
                results.append({"match": "category", "show": summary, "episode": None})
                continue

            for season in show["seasons"]:
                for episode in season["episodes"]:
                    if needle not in episode["title"].lower():
                        continue
                    if language and language not in episode["languages"]:
                        continue
                    results.append(
                        {
                            "match": "episode",
                            "show": summary,
                            # Episode titles repeat across shows, so a result
                            # without its show and position is not actionable.
                            "episode": {
                                "content_group": episode["content_group"],
                                "season_number": season["season_number"],
                                "episode_number": episode["episode_number"],
                                "title": episode["title"],
                                "duration_seconds": episode["duration_seconds"],
                                "languages": episode["languages"],
                                "artwork": episode["artwork"],
                            },
                        }
                    )

    return {"total": len(results), "results": results}
