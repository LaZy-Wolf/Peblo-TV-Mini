import json
from dataclasses import dataclass
from functools import lru_cache

from app.config import settings


@dataclass(frozen=True)
class ArtworkSpec:
    kind: str
    aspect_w: int
    aspect_h: int
    target_w: int
    target_h: int
    max_kb: int

    @property
    def aspect(self) -> float:
        return self.aspect_w / self.aspect_h


@dataclass(frozen=True)
class Reference:
    sections: list[str]
    categories: list[str]
    languages: list[str]
    artwork_specs: dict[str, ArtworkSpec]

    def section_order(self, section: str | None) -> int:
        return self.sections.index(section) if section in self.sections else len(self.sections)

    def language_order(self, language: str) -> int:
        if language in self.languages:
            return self.languages.index(language)
        return len(self.languages)

    def sort_languages(self, languages: list[str]) -> list[str]:
        return sorted(set(languages), key=self.language_order)


@lru_cache
def reference() -> Reference:
    raw = json.loads((settings.data_dir / "reference.json").read_text(encoding="utf-8"))
    specs = {}
    for kind, spec in raw["artwork_specs"].items():
        aw, ah = (int(p) for p in spec["aspect"].split(":"))
        specs[kind] = ArtworkSpec(
            kind=kind,
            aspect_w=aw,
            aspect_h=ah,
            target_w=spec["target_px"][0],
            target_h=spec["target_px"][1],
            max_kb=spec["max_kb"],
        )
    return Reference(
        sections=list(raw["sections"]),
        categories=list(raw["categories"]),
        languages=list(raw["languages"]),
        artwork_specs=specs,
    )
