import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";

export type ArtworkKind = "poster" | "banner" | "thumbnail";
export type ArtworkMap = Partial<Record<ArtworkKind, string>>;

export type Show = {
  id: number;
  slug: string;
  title: string;
  synopsis: string;
  section: string | null;
  categories: string[];
  status: "draft" | "published";
  updated_at: string;
};

export type ShowDetail = Show & { artwork: ArtworkMap };

export type Episode = {
  id: number;
  season_id: number;
  episode_number: number;
  title: string;
  duration_seconds: number | null;
  language: string;
  content_group: string;
  status: "draft" | "published";
};

export type EpisodeDetail = Episode & {
  artwork: ArtworkMap;
  season_number: number;
  show_id: number;
  show_title: string;
};

export type Season = { id: number; show_id: number; season_number: number };

export type Page<T> = { items: T[]; total: number; page: number; page_size: number };

export type Issue = {
  code: string;
  message: string;
  fix_hint: string;
  entity_type: string;
  entity_id: number | null;
  entity_label: string;
};

export type ValidationReport = {
  can_publish: boolean;
  blocking_count: number;
  warning_count: number;
  groups: {
    show_id: number | null;
    show_title: string;
    show_slug: string;
    blocking: Issue[];
    warnings: Issue[];
  }[];
  import_problems: { id: number; reason: string; action: string; source_row: unknown }[];
};

export type PublishRun = {
  id: number;
  run_id: string;
  status: "running" | "success" | "failed" | "no_change";
  started_by: number | null;
  started_at: string | null;
  finished_at: string | null;
  counts: Record<string, number> | null;
  catalog_key: string | null;
  error: unknown;
};

export type ShowFilters = {
  q?: string;
  section?: string;
  status?: string;
  page: number;
  page_size: number;
};

function qs(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export function useShows(filters: ShowFilters) {
  return useQuery({
    queryKey: ["shows", filters],
    queryFn: () => api.get<Page<Show>>(`/admin/shows${qs(filters)}`),
  });
}

export function useShow(id: number) {
  return useQuery({
    queryKey: ["show", id],
    queryFn: () => api.get<ShowDetail>(`/admin/shows/${id}`),
    enabled: Number.isFinite(id),
  });
}

export function useSeasons(showId: number) {
  return useQuery({
    queryKey: ["seasons", showId],
    queryFn: () => api.get<{ items: Season[] }>(`/admin/shows/${showId}/seasons`),
    enabled: Number.isFinite(showId),
  });
}

export function useCreateShow() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Show>) => api.post<ShowDetail>("/admin/shows", body),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["shows"] });
      client.invalidateQueries({ queryKey: ["validation-report"] });
    },
  });
}

export function useUpdateShow(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Show>) => api.patch<ShowDetail>(`/admin/shows/${id}`, body),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["shows"] });
      client.invalidateQueries({ queryKey: ["show", id] });
      // Publishing eligibility may have changed, so the report is now stale.
      client.invalidateQueries({ queryKey: ["validation-report"] });
    },
  });
}

export function useEpisodes(showId: number) {
  return useQuery({
    queryKey: ["episodes", showId],
    queryFn: () =>
      api.get<Page<Episode>>(`/admin/episodes${qs({ show_id: showId, page_size: 200 })}`),
    enabled: Number.isFinite(showId),
  });
}

export function useEpisode(id: number) {
  return useQuery({
    queryKey: ["episode", id],
    queryFn: () => api.get<EpisodeDetail>(`/admin/episodes/${id}`),
    enabled: Number.isFinite(id),
  });
}

export function useCreateEpisode(showId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post<EpisodeDetail>("/admin/episodes", body),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["episodes", showId] });
      client.invalidateQueries({ queryKey: ["validation-report"] });
    },
  });
}

export function useUpdateEpisode(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.patch<EpisodeDetail>(`/admin/episodes/${id}`, body),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["episode", id] });
      client.invalidateQueries({ queryKey: ["episodes"] });
      client.invalidateQueries({ queryKey: ["validation-report"] });
    },
  });
}

export function useValidationReport() {
  return useQuery({
    queryKey: ["validation-report"],
    queryFn: () => api.get<ValidationReport>("/admin/validation-report"),
  });
}

export function useRuns() {
  return useQuery({
    queryKey: ["runs"],
    queryFn: () => api.get<{ items: PublishRun[] }>("/admin/catalog/runs"),
  });
}

export function usePublish() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<PublishRun>("/admin/catalog/publish"),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["runs"] });
      client.invalidateQueries({ queryKey: ["validation-report"] });
    },
  });
}

export function useRollback() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (runDbId: number) =>
      api.post<PublishRun>("/admin/catalog/rollback", { run_db_id: runDbId }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["runs"] }),
  });
}

export type UploadResult = {
  id: number;
  kind: string;
  url: string;
  width: number;
  height: number;
  bytes: number;
};

export function useUploadArtwork() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { kind: string; file: File; showId?: number; episodeId?: number }) => {
      const form = new FormData();
      form.set("kind", input.kind);
      form.set("file", input.file);
      if (input.showId !== undefined) form.set("show_id", String(input.showId));
      if (input.episodeId !== undefined) form.set("episode_id", String(input.episodeId));
      return api.post<UploadResult>("/admin/artwork", form);
    },
    onSuccess: (_data, input) => {
      if (input.showId !== undefined) {
        client.invalidateQueries({ queryKey: ["show", input.showId] });
      }
      if (input.episodeId !== undefined) {
        client.invalidateQueries({ queryKey: ["episode", input.episodeId] });
      }
      client.invalidateQueries({ queryKey: ["validation-report"] });
    },
  });
}
