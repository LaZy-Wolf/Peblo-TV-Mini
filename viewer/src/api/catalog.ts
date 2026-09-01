/**
 * The viewer's entire API surface.
 *
 * This file is why the viewer cannot call an admin endpoint: there is no
 * token, no Authorization header, and no admin path anywhere in it. Calling
 * one is unrepresentable rather than merely discouraged.
 */

const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export type Artwork = Partial<Record<"poster" | "banner" | "thumbnail", string>>;

export type CatalogEpisode = {
  content_group: string;
  episode_number: number;
  title: string;
  duration_seconds: number | null;
  languages: string[];
  artwork: Artwork;
};

export type CatalogSeason = { season_number: number; episodes: CatalogEpisode[] };

export type CatalogShow = {
  slug: string;
  title: string;
  synopsis: string;
  categories: string[];
  languages: string[];
  artwork: Artwork;
  trailers: CatalogEpisode[];
  seasons: CatalogSeason[];
};

export type Catalog = {
  version: number;
  run_id: string;
  generated_at: string;
  hero: { slug: string } | null;
  sections: { key: string; shows: CatalogShow[] }[];
};

export type SearchResult = {
  match: "show" | "episode" | "category";
  show: CatalogShow & { section: string };
  episode: (CatalogEpisode & { season_number: number }) | null;
};

async function readJson<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`);
  } catch {
    throw new Error("We could not reach Peblo TV. Check your connection and try again.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      body?.errors?.[0]?.message ?? "We could not load the catalogue. Please try again.",
    );
  }
  return (await response.json()) as T;
}

export function fetchCatalog(): Promise<Catalog> {
  return readJson<Catalog>("/catalog");
}

export function searchCatalog(params: {
  q?: string;
  category?: string;
  language?: string;
  section?: string;
}): Promise<{ total: number; results: SearchResult[] }> {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) search.set(key, value);
  }
  return readJson(`/catalog/search?${search.toString()}`);
}
