# Peblo TV Mini: Design Spec

Date: 2026-09-01
Status: approved, pending implementation plan

## 1. Goal

Build the three layers of a miniature streaming content pipeline plus the operational
scaffolding around them:

```
CMS (React) -> API (FastAPI + Postgres) -> publish job -> catalogue.json in storage
                                                               |
                                        Viewer UI (React) <----+
```

Scope agreed: Parts A through E complete, plus one stretch goal (versioned catalogue
with rollback). Publish dry-run diff and audit log are explicitly out of scope.

The grading rubric rewards judgment and operability over feature count. Every decision
below is written so it can be defended in the README, and every ambiguity resolved is
recorded in section 3 so the README can list them without re-deriving them.

## 2. Seed data audit

The supplied `seed_shows.json` (95 rows, 8 shows) is deliberately imperfect. Findings
from a full audit, each of which drives a requirement later in this spec.

| # | Defect | Evidence | Requirement it drives |
|---|---|---|---|
| 1 | Duplicate `(content_group, language)` | `ep_9001` collides with `ep_0004` on `(motis-many-lives-s01e02, hi)`. Title drift too: it reads `"The Lost Kite (v2)"` but S1E2 is `"Rain on the Roof"` | DB unique constraint + `import_issues` table + validation report group |
| 2 | Whole show with `section: null` | `rhyme-rangers`, all 8 rows, all `draft` | Blocking rule: a published show must have a section |
| 3 | Published episode with zero artwork | `ep_0036`, `artwork_available: []`, status `published` | Write-time rule: cannot set published without artwork. Seeder downgrades it (D9) |
| 4 | Trailers ship thumbnail only | `ep_0093`, `ep_0094`, Season 0, published, `["thumbnail"]` | Decision D4: trailers require thumbnail only, warn on the rest |
| 5 | Language variants disagree on duration | 16 content groups, e.g. `s01e01` en=510s hi=480s | Decision D3: canonical language wins; warn when the gap exceeds 20% |
| 6 | Collapse decoy | `peblo-songs-lyrical` is a separate slug with the same 10 episode titles as `peblo-songs`, distinct content groups, same `songs` section | Collapse keys on `content_group` only, never on title similarity |
| 7 | Episode titles repeat across all 8 shows | `"The Lost Kite"` exists in every show | Search results must carry show context or they are unusable |
| 8 | Partial publish show | `number-nest`: 6 published, 2 draft | Publish emits the show carrying only its published episodes |

Checked and cleared, so they are not defects: the file is valid UTF-8 (the `—` in
the "Peblo Songs" lyrical show title is a genuine em dash that decodes correctly, not
mojibake, despite looking corrupt in a cp1252 terminal); no episode number gaps; no
duplicate `episode_id`; no null or zero durations; no show level field drift.

### 2.1 Asset audit

```
banner_good.jpg        1280x720   16:9    14.7 KB   PASS
banner_too_big.png     2560x1440  16:9    13.8 KB   FAIL dimensions only
poster_good.jpg        600x900     2:3     9.1 KB   PASS
poster_wrong_ratio.jpg 900x600     3:2     9.1 KB   FAIL aspect (rotated)
thumb_good.jpg         640x360    16:9     4.2 KB   PASS
thumb_tiny.jpg         160x90     16:9     0.8 KB   FAIL dimensions
```

Two consequences:

1. Dimension checks and the byte ceiling are independent. `banner_too_big.png` fails on
   pixels while comfortably passing on bytes, so a validator that only weighs files
   would accept it.
2. No supplied asset exceeds 200 KB, so the ceiling rule is unreachable from the given
   fixtures. Tests must generate a synthetic oversized image, otherwise the rule ships
   as an untested claim.

`artwork_available` in the seed is a claim about what exists, not a set of files. The
seeder must materialise real artwork records from the supplied assets so the pipeline
is exercised end to end rather than trusting the flag. Concretely: every show receives
`poster_good.jpg`, `banner_good.jpg` and `thumb_good.jpg`, and every episode receives
`thumb_good.jpg`, each pushed through the same `POST /admin/artwork` validation path the
CMS uses rather than inserted directly, so a broken validator fails the seed loudly. The
one exception is `ep_0036`, which receives nothing, because erasing the planted defect
would erase the thing the validation report exists to demonstrate. The three deliberately
malformed fixtures are never seeded; they are test inputs and manual upload material for
the screen recording.

## 3. Decisions log

These are the ambiguities resolved by fiat. All of them go in the README.

- **D1. Categories stored as Postgres `text[]` with a GIN index**, not a join table. The
  vocabulary is fixed at 15 values, read constantly, written rarely. Saves a table and a
  join on the hottest query.
- **D2. Search runs server side over the published catalogue held in memory**, not over
  Postgres. The viewer must only ever see published content, and searching the same
  artifact it renders makes divergence structurally impossible. Scale ceiling documented
  in section 10.
- **D3. Canonical language for a collapsed entry is the first present in
  `reference.json` language order**, so `en` when available, otherwise `hi`. Its title
  and duration become the entry's title and duration. Divergent durations are surfaced
  as a warning, not silently averaged.
- **D4. Season 0 trailers require a thumbnail only.** A trailer never occupies a poster
  row, it appears as a chip on the detail page, so demanding a 2:3 poster makes an
  editor's life worse for no viewer benefit. Missing poster or banner on a Season 0
  episode is a warning, not a block.
- **D5. Two separate Vite applications**, not one app with two routes. The viewer's API
  client contains no admin endpoints and no auth header code, making "viewer UI calling
  admin endpoints" unrepresentable rather than merely discouraged.
- **D6. `ep_9001` is rejected at import, not silently dropped.** The unique constraint
  refuses it; the seeder records the rejection with its reason and the validation report
  surfaces it under "Data import problems".
- **D7. Duplicate episode titles across shows are left as-is.** They are plausible real
  data. Search results carry show title, season and episode number so they disambiguate.
- **D8. No self-registration.** Users are seeded. The brief needs role enforcement, not
  user management.
- **D9. The seeder downgrades rather than blocks.** A seed row that arrives already
  marked `published` but fails a publish precondition (`ep_0036`, published with no
  artwork) is imported as `draft` and recorded in `import_issues` with
  `action = downgraded_to_draft`. Rationale in the next paragraph. Rows that violate a
  database constraint outright (`ep_9001`) are recorded with `action = rejected` and not
  imported at all.
- **D10. A show's status is derived at import**: `published` if any of its episodes is
  published, otherwise `draft`. The seed carries status per episode only. Under this
  rule `rhyme-rangers` (all 8 draft) becomes a draft show, so its `section: null` is
  correctly not a blocking issue yet, and `number-nest` (6 of 8 published) becomes a
  published show carrying only its published episodes.

**Why D9 matters, and it is the one place this spec nearly contradicted itself.** The
publish job aborts on any blocking issue. `ep_0036` is published with no artwork, which
is blocking. A literal import would therefore mean the very first publish fails, and
`docker-compose up` would hand the reviewer an empty viewer, contradicting the acceptance
criterion in section 15.1. The fix is not to weaken the publish rule, which is the
valuable part, but to recognise that the rule belongs at write time: the API refuses to
set an episode `published` without artwork and a duration, so a row like `ep_0036` could
never have been created through the API in the first place. It exists only because it
came in through a bulk import that bypassed validation. The seeder therefore applies the
same write-time rule the API applies, downgrades the row, and reports it. The defect
stays visible in the validation report instead of being swallowed, the demo works out of
the box, and the blocking path is still demonstrable by flipping `rhyme-rangers` to
published, which immediately blocks publish on its missing section.

## 4. Repository layout

```
peblo-tv-mini/
  api/
    app/
      main.py
      config.py                 pydantic-settings, every env var declared
      db.py                     engine, session dependency
      models.py                 SQLAlchemy models
      schemas.py                pydantic request/response models
      auth.py                   JWT issue/verify, role dependencies
      storage/
        base.py                 Storage Protocol
        local.py                LocalDiskStorage
        r2.py                   R2Storage (boto3, S3 compatible)
      artwork.py                image validation
      catalog/
        build.py                catalogue construction
        publish.py              run orchestration, pointer flip
        serve.py                cached read path
        search.py               in-memory query
      validation.py             validation report rules
      routers/
        auth.py  shows.py  seasons.py  episodes.py  artwork.py
        admin_catalog.py  catalog.py  health.py
      seed.py                   seeder + import rejection recording
    alembic/
    tests/
    pyproject.toml
    Dockerfile
  cms/                          Vite + React + TS + TanStack Query
  viewer/                       Vite + React + TS
  data/                         supplied seed_shows.json, reference.json, assets/
  docker-compose.yml
  .github/workflows/ci.yml
  .env.example
  README.md
```

## 5. Data model

```sql
users(id, email UNIQUE, password_hash, role, created_at)
shows(id, slug UNIQUE, title, synopsis, section NULL, categories text[],
      status, created_at, updated_at)
seasons(id, show_id FK, season_number)               UNIQUE(show_id, season_number)
episodes(id, season_id FK, episode_number, title, duration_seconds NULL,
         language, content_group, status, created_at, updated_at)
                                                     UNIQUE(content_group, language)
artwork(id, show_id NULL FK, episode_id NULL FK, kind, storage_key,
        width, height, bytes, checksum, created_at)
        CHECK (num_nonnulls(show_id, episode_id) = 1)
publish_runs(id, run_id UNIQUE, started_by FK users, started_at, finished_at,
             status, catalog_key, content_hash, counts jsonb, error)
catalog_pointer(id smallint PK CHECK (id = 1), current_run_id FK publish_runs,
                updated_at)
import_issues(id, source_row jsonb, reason, action, created_at)
```

`role` is an enum of `editor | admin`. `status` on shows and episodes is an enum of
`draft | published`. `publish_runs.status` is an enum of
`running | success | failed | no_change`. `artwork.kind` is an enum of
`poster | banner | thumbnail`. `import_issues.action` is an enum of
`rejected | downgraded_to_draft`.

### 5.1 Indexes, each with the query behind it

| Index | Query it serves |
|---|---|
| `shows.slug` UNIQUE | Show lookup by slug from CMS and catalogue build |
| `episodes(content_group, language)` UNIQUE | Enforces the brief's constraint in the database rather than in application code, so a concurrent write cannot slip past it. Also the grouping key at build time |
| `episodes(season_id, episode_number)` | Ordering episodes within a season |
| `shows(status, section)` | The exact predicate shared by the publish query and the validation report |
| GIN on `shows.categories` | Category filter via the `@>` containment operator |
| `publish_runs(started_at DESC)` | Run history page, newest first |
| Partial UNIQUE `artwork(show_id, kind) WHERE show_id IS NOT NULL` | One poster per show |
| Partial UNIQUE `artwork(episode_id, kind) WHERE episode_id IS NOT NULL` | One thumbnail per episode |

### 5.2 Migrations

Alembic, two migrations: one creating the schema, one seeding the enum vocabularies and
the singleton `catalog_pointer` row. Migrations run on container start before the API
binds its port, so `docker-compose up` is ordered correctly rather than racing.

## 6. Auth and roles

- `POST /auth/login` takes email and password, returns a JWT carrying `sub` and `role`,
  expiring in 8 hours. Passwords hashed with bcrypt.
- Seeded accounts: `editor@peblo.test` and `admin@peblo.test`, passwords from
  `.env.example`.
- FastAPI dependencies: `require_editor` accepts both roles, `require_admin` accepts
  admin only. Every `/admin/*` route declares one of them. There is no route that reads
  the role and branches inside its body, because that is how enforcement rots.
- `/catalog` and `/catalog/search` are unauthenticated. The viewer never sends a token.
- 401 for missing or invalid token, 403 for valid token with insufficient role. Both
  return a body an editor can read, not a bare status.

Enforcement is proven by test, not by declaration: an editor token calling
`POST /admin/catalog/publish` must receive 403.

## 7. Storage abstraction

```python
class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> str: ...
    def get(self, key: str) -> bytes: ...
    def url(self, key: str) -> str: ...
    def exists(self, key: str) -> bool: ...
```

`LocalDiskStorage` writes under `STORAGE_LOCAL_ROOT` and serves through a static mount.
`R2Storage` uses boto3 against an S3 compatible `endpoint_url`. Selection by the
`STORAGE_BACKEND` env var. The R2 implementation ships written but is honestly labelled
as unverified against a live R2 bucket, since there is no bucket to verify against.

Moving to R2 changes: `STORAGE_BACKEND=r2`, four R2 credentials in the environment, and
the artwork URL base becomes the bucket's public domain. No call site changes, because
every caller depends on the Protocol.

## 8. Artwork validation

Independent checks, run server side, in this order so the first failure is the most
actionable:

1. **Decodable image.** Rejects non-images and corrupt files.
2. **Aspect** within 1% of the spec ratio.
3. **Dimensions** within 10% of the target for each axis.
4. **Bytes** at or under 200 KB.

Errors are written for a content editor. No jargon, no ratios expressed as decimals, and
each one names the fix:

> Your poster is 900 by 600 pixels (landscape). Posters need to be portrait, about 600
> by 900. It looks like this image is rotated. Try the tall version.

> This banner is 2560 by 1440 pixels, which is twice the size we need. Please export it
> at about 1280 by 720.

> This thumbnail is 160 by 90 pixels, which is too small to look sharp on a TV. Please
> export it at about 640 by 360.

> This file is 340 KB. Artwork needs to be under 200 KB so pages load quickly for
> children on slow connections. Try exporting as JPEG at 80% quality.

Multiple failures are returned together, not one at a time, so an editor fixes the image
once rather than three times.

`POST /admin/artwork` accepts a multipart upload plus `kind` and one owner reference
(`show_id` or `episode_id`). Validation happens before anything touches storage, so a
rejected upload leaves no orphan.

## 9. Publish

### 9.1 Algorithm

1. `require_admin`.
2. Insert a `publish_runs` row with status `running`, `started_by`, `started_at`.
3. Run the validation report. Any blocking issue aborts: the run is marked `failed` with
   the issues recorded in `error`, and 409 is returned carrying the same issues.
4. Build the catalogue in memory (section 9.3).
5. Hash the canonical serialisation. If the hash equals the current pointer's run hash,
   mark the run `no_change`, skip the write, and return. This is what makes publish
   idempotent: publishing twice with no edits produces one file, not two.
6. `storage.put("catalog/runs/{run_id}.json", body)`. Never an existing key, because
   `run_id` is a fresh UUID.
7. Read the key back and verify it parses and its hash matches. A write that reported
   success but landed corrupt must not become live.
8. In one transaction: update `catalog_pointer.current_run_id` to this run, and mark the
   run `success` with `counts` and `finished_at`.

### 9.2 Atomicity and failure semantics

The pointer update in step 8 is the atomic commit point. It is a single row update in a
single transaction. Before it, the new file exists but nothing references it, so no
reader can reach it. After it, every reader sees the complete file.

If the process dies mid-publish:

- **Before step 6:** run row stuck at `running`, nothing written, pointer untouched.
- **Between 6 and 8:** an orphan file sits in storage, unreferenced and harmless. Pointer
  untouched. Readers continue serving the previous catalogue with no interruption.
- **During step 8:** the transaction either commits or it does not. Postgres decides,
  and there is no half state.

A sweep on API startup marks any run left `running` for more than 5 minutes as `failed`,
so the CMS run history never shows a permanently spinning run. Orphan files are left in
place deliberately: storage is cheap, and deleting on a path that just crashed is how
you delete the wrong thing.

### 9.3 Catalogue construction and deterministic ordering

Only `status = published` shows and episodes are considered. A published show with zero
published episodes is a blocking validation issue, so in practice the build never sees
one; the build additionally skips it rather than emitting an empty show, as defence in
depth against a rule and a builder disagreeing.

Episodes are grouped by `content_group`. Each group collapses to one entry. The canonical
variant is the one whose language comes first in `reference.json` order. The entry takes
its title, duration and thumbnail from the canonical variant, and lists every published
variant's language in `reference.json` order. A show's `languages` is the union of its
published episodes' languages, in `reference.json` order.

Ordering, fully deterministic so two runs over identical data produce byte identical
output:

- Sections in `reference.json` order: `featured`, `series`, `minisodes`, `songs`.
- Shows within a section by `title`, then `slug` as tiebreak.
- Seasons ascending. Season 0 is emitted in a separate `trailers` array on the show, not
  in `seasons`.
- Episodes by `episode_number` ascending.
- `languages` in `reference.json` order. `categories` sorted alphabetically.
- JSON serialised with sorted keys and no insignificant whitespace, so the hash is stable.

The hero is the first show of the `featured` section under this ordering.

### 9.4 Catalogue shape

```json
{
  "version": 1,
  "run_id": "uuid",
  "generated_at": "2026-09-01T00:00:00Z",
  "hero": { "slug": "motis-many-lives" },
  "sections": [
    {
      "key": "featured",
      "shows": [
        {
          "slug": "motis-many-lives",
          "title": "Moti's Many Lives",
          "synopsis": "...",
          "categories": ["adventure", "friendship", "india"],
          "languages": ["en", "hi"],
          "artwork": { "poster": "...", "banner": "...", "thumbnail": "..." },
          "trailers": [
            { "title": "Trailer", "duration_seconds": 75,
              "languages": ["en"], "artwork": { "thumbnail": "..." } }
          ],
          "seasons": [
            {
              "season_number": 1,
              "episodes": [
                {
                  "content_group": "motis-many-lives-s01e01",
                  "episode_number": 1,
                  "title": "The Lost Kite",
                  "duration_seconds": 510,
                  "languages": ["en", "hi"],
                  "artwork": { "thumbnail": "..." }
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

### 9.5 Rollback (stretch)

`POST /admin/catalog/rollback` with a target `run_id`, admin only. Validates the target
run is `success` and its file still reads, then flips the pointer. Because publish never
overwrites, every previous catalogue is still there, which is why this endpoint is
roughly ten lines rather than a project.

## 10. Read path

`GET /catalog` resolves the pointer and serves the file. The parsed catalogue is cached
in process keyed by `run_id`; the pointer itself is cached for 5 seconds, so a publish
becomes visible within 5 seconds without a database read per request. Multiple workers
each hold their own copy, which is correct because the value is immutable per `run_id`.

`GET /catalog/search?q=&category=&language=&section=` runs against that same cached
structure. All filters compose with AND. `q` matches show title, episode title and
category, case insensitive, substring. Results carry show title, season and episode
number so the repeated titles across shows disambiguate.

**Scale ceiling, stated honestly in the README.** A linear scan over the parsed catalogue
is fine to roughly 10k entries and a few MB, which is far beyond this exercise. Past
that: build a `catalog_entries` projection table on publish and query it with a Postgres
`tsvector` index, which also buys stemming and ranking. Past roughly a million entries,
or as soon as typo tolerance and relevance tuning matter, move to a dedicated engine
such as OpenSearch or Typesense fed by the same publish job.

The reason to serve a pre-published file at all: the read path becomes a pure function of
one immutable artifact, so it cannot be broken by an in-progress edit, it caches trivially
at any layer, and viewer traffic does not touch the database that editors are writing to.
Where it bites: edits are invisible until someone publishes, so the catalogue can drift
from editor intent silently, and any bug in the build job ships to every viewer at once
with no gradual rollout. Rollback is the mitigation for the second.

## 11. Validation report

`GET /admin/validation-report`, editor or admin. Grouped by show, then by issue type.
Every issue carries the entity id, a plain sentence, and a fix hint. Blocking and warning
are separate lists because the publish button needs to know which is which.

Blocking:

- Published show with no section
- Published episode with no artwork
- Published episode with no duration
- Published show with zero publishable episodes
- Section, category or language outside `reference.json`

Warning:

- Language variants whose durations differ by more than 20%
- Season 0 trailer missing poster or banner (per D4)
- Published show with no poster or banner of its own
- Rows rejected or downgraded at import, surfaced as "Data import problems" (per D6, D9).
  On a fresh seed this group contains exactly two entries: `ep_9001` rejected as a
  duplicate language variant, and `ep_0036` downgraded to draft for having no artwork.
  Reading that group is how an editor discovers both planted defects without asking an
  engineer, which is the entire point of the endpoint.

## 12. API surface

| Method | Path | Role | Notes |
|---|---|---|---|
| POST | `/auth/login` | public | Returns JWT |
| GET | `/auth/me` | editor | Current user and role, drives CMS UI gating |
| GET/POST | `/admin/shows` | editor | List with search, filters, pagination |
| GET/PATCH/DELETE | `/admin/shows/{id}` | editor | |
| GET/POST | `/admin/shows/{id}/seasons` | editor | |
| GET/POST | `/admin/episodes` | editor | Filters: show, season, status, language |
| GET/PATCH/DELETE | `/admin/episodes/{id}` | editor | |
| POST | `/admin/artwork` | editor | Multipart, validated before storage |
| DELETE | `/admin/artwork/{id}` | editor | |
| GET | `/admin/validation-report` | editor | |
| POST | `/admin/catalog/publish` | **admin** | |
| POST | `/admin/catalog/rollback` | **admin** | Stretch |
| GET | `/admin/catalog/runs` | editor | Run history |
| GET | `/catalog` | public | |
| GET | `/catalog/search` | public | |
| GET | `/healthz` | public | Liveness, no dependencies |
| GET | `/readyz` | public | Database ping, storage ping, pointer resolvable |

Errors use a consistent envelope: a machine `code`, a human `message`, and an optional
`field`. Validation failures return every problem at once.

## 13. CMS

React, TypeScript, Vite, TanStack Query. TanStack Query is the right fit here because
almost all state is server state: the interesting problems are cache invalidation after
a mutation, keeping the validation report fresh while an editor fixes issues, and not
refetching a large list on every keystroke. Hand-rolling that is how people end up with
stale publish buttons.

Plain, dense, light, table first. Optimised for someone doing this fifty times a week:
keyboard reachable, no decorative motion, nothing that costs a second per repetition.

Screens:

1. **Login.** Email, password, error state.
2. **Shows list.** Search, filters (section, status, language), pagination. Row shows
   title, section, status, episode count, artwork completeness.
3. **Show detail / edit.** Metadata form, three labelled artwork slots, seasons and
   episodes beneath.
4. **Episode edit.** Fields plus its own thumbnail slot. Language and content group are
   shown together with an inline explanation of what a content group does, since that
   convention is the one an editor will get wrong.
5. **Publish page.** Validation report grouped by show, publish button, run history.

Artwork slots each display the required dimensions as a label before upload, a live
preview after selection, and errors as sentences beneath the slot. Validation is server
side; the client shows what the server said rather than duplicating the rules, so the two
can never disagree.

The publish button renders blocking reasons inline when disabled, not in a tooltip,
because a tooltip cannot be read and acted on at the same time. An editor logged in
without the admin role sees the button replaced by an explanation of who can publish.

Every screen handles loading, empty, error and permission denied with written copy.

## 14. Viewer

Design read: a browse surface for a child, with a parent holding the tablet. Warm and
playful but calm. Dark cinema shell. Dials: variance 4, motion 3, density 5.

Tokens:

- Shell `oklch(0.16 0.01 260)`, surface `oklch(0.21 0.015 260)`, text `oklch(0.96 0.005 260)`,
  muted text `oklch(0.72 0.01 260)`.
- One accent, a warm marigold: `oklch(0.78 0.16 65)`. Deliberately neither Netflix red
  nor the default AI purple.
- Spacing on a 4px scale. Corner radius 12px on cards, 8px on controls.
- Body 16px minimum, line height 1.5. Heading scale ratio 1.25.

Structure:

- **Home.** Featured hero using the show's **banner**, with a bottom gradient scrim,
  title, synopsis capped at 20 words, and a primary action. Below it, one horizontal row
  per section using **poster** cards.
- **Rows** use native CSS scroll snap rather than a carousel library. Arrow key
  navigable, visible focus rings, no layout shift on hover (colour and shadow only).
- **Show detail.** Synopsis, seasons and episodes using **thumbnail** artwork. Language
  options for a grouped episode render as chips. Season 0 never appears as a season; it
  surfaces as a "Watch trailer" chip.
- **Search and filters** (category, language) hitting `GET /catalog/search`.
- **Empty state** with written copy: "Nothing here yet. Try clearing the language filter."

Slow images: every image sits in an `aspect-ratio` box so space is reserved before load,
with a tinted skeleton behind it, `loading="lazy"` and `decoding="async"`. Zero layout
shift, and it is roughly six lines of CSS rather than a dependency.

Accessibility: contrast verified at 4.5:1 for body and 3:1 for large text, focus visible
on every interactive element, alt text from episode and show titles,
`prefers-reduced-motion` honoured on every transition, touch targets at 44px minimum.

No em dashes anywhere in UI copy.

## 15. Pipeline and operability

### 15.1 docker-compose

Services: `db` (postgres:16 with a healthcheck), `api` (waits for db healthy, runs
migrations, then seed, then a bootstrap publish, then uvicorn), `cms`, `viewer`. Seed is
idempotent so a restart does not duplicate rows, and the bootstrap publish is idempotent
by the hash rule in 9.1 step 5, so a restart records `no_change` rather than writing a
second identical file.

`docker-compose up` from a clean checkout must produce a browsable catalogue with no
manual steps. This is an explicit acceptance test, not an aspiration, and D9 is what
makes it hold: without the import downgrade the bootstrap publish would abort on
`ep_0036` and the viewer would open empty.

### 15.2 CI

`.github/workflows/ci.yml`, three jobs:

1. **lint**: ruff for the API, eslint plus tsc for both frontends.
2. **test**: pytest against a Postgres service container, plus a frontend typecheck.
3. **build**: docker build for all three images, tagged with the commit SHA.

The deploy job is written and gated on the default branch, with each step explained in a
comment: build and push to a registry, run migrations as a one-off task, deploy the API,
then the two static frontends. It targets no real cloud, and says so.

### 15.3 Secrets

`.env.example` lists every variable with a comment: database URL, JWT secret and expiry,
seeded account passwords, storage backend and root, R2 credentials, CORS origins, API
base URLs for both frontends.

Production paragraph for the README: secrets never live in the repository or in compose
files. They come from the platform's secret manager (AWS Secrets Manager, GCP Secret
Manager, or Cloudflare's encrypted environment variables), injected at container start,
never baked into images, because an image layer is forever and gets pushed to registries
people can read. The JWT secret and R2 credentials are rotated on a schedule, with the
API reading them at startup so rotation is a restart rather than a deploy. CI gets a
narrow deploy identity through OIDC rather than a long lived key.

### 15.4 Health and alerting

`/healthz` is liveness only, no dependencies, so a database blip does not cause the
orchestrator to kill healthy containers. `/readyz` checks the database, storage, and that
the pointer resolves to a readable catalogue.

**The one alert: a publish run stuck in `running` for more than five minutes.**

Reasoning: the loud failures here are already safe. If the API is down, the viewer shows
errors and everyone knows within seconds. If a publish fails validation, the editor sees
it immediately on screen. The dangerous failure is the silent one: a publish that died
between writing the file and flipping the pointer. Nothing is broken, no error is raised,
the viewer keeps serving the previous catalogue perfectly, and the editor believes they
published. Content that was supposed to go live simply does not, and nobody finds out
until a human notices something missing. That is the failure with the longest gap between
occurrence and detection, which is exactly what an alert is for.

Secondary, worth a lower severity: `readyz` failing on pointer resolution, meaning the
live catalogue file has become unreadable.

## 16. Testing

Tests concentrate on the parts most likely to be wrong and most expensive if they are.

1. **Publish atomicity and idempotency.** Publishing twice with no edits records
   `no_change` and writes one file. A simulated crash after the storage write leaves the
   pointer at the previous run and `GET /catalog` unchanged. A publish blocked by
   validation writes no file and records `failed`.
2. **Language grouping.** `motis-many-lives-s01e02` collapses to one entry listing
   `["en", "hi"]`. `peblo-songs` and `peblo-songs-lyrical` stay separate despite
   identical episode titles. A group with only draft variants is omitted.
3. **Artwork validation** against all six supplied fixtures with the expected pass or
   fail, plus a generated file over 200 KB, since no supplied asset reaches the ceiling.
4. **Role enforcement.** An editor token calling publish gets 403. An absent token gets
   401. An admin token succeeds.
5. **Filter composition.** `q`, `category`, `language` and `section` combined narrow
   correctly rather than one silently winning.
6. **Season 0 handling.** Trailers are absent from `seasons` and present in `trailers`.
7. **Seed import.** `ep_9001` lands in `import_issues` as `rejected` and is absent from
   `episodes`. `ep_0036` lands as `draft` with `action = downgraded_to_draft`. Both
   surface in the validation report. `rhyme-rangers` imports as a draft show per D10.
8. **Bootstrap publish succeeds on a fresh seed.** The end to end guard for D9: seed,
   publish, assert `success` and a non-empty catalogue. If someone later removes the
   downgrade, this test fails rather than `docker-compose up` failing in front of a
   reviewer.
9. **Write-time refusal.** `PATCH /admin/episodes/{id}` setting `status = published` on
   an episode with no artwork returns 422 with an editor-readable message. This is the
   rule D9 leans on, so it needs its own test rather than being implied.

## 17. Out of scope

Stated plainly so the README can repeat it: publish dry-run diff, audit log of who
changed what, video playback of any kind, image resizing or transcoding on upload
(we reject rather than fix, because silently altering an editor's artwork is worse than
telling them), user management UI, and pagination on the public catalogue endpoint
(the whole catalogue is the artifact by design).

## 18. Time budget

| Part | Estimate |
|---|---|
| A: backend | 6h |
| B: CMS | 4h |
| C: viewer | 3h |
| D: pipeline and CI | 1.5h |
| E: README and tests | 2h |
