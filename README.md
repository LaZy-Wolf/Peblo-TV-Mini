# Peblo TV Mini

CMS upload → published catalogue → Netflix-style browse.

```
CMS (React) ──► API (FastAPI + Postgres) ──► publish job ──► catalogue.json in storage
                                                                     │
                                              Viewer UI (React) ◄────┘
```

**Contents:** [Run it](#run-it) · [Seed data audit](#what-was-wrong-with-the-seed-data)
· [Decisions](#decisions-and-trade-offs) · [Design](#design) · [Data model](#data-model)
· [Part E written answers](#part-e-written) · [Operability](#pipeline-and-operability)
· [Tests](#tests)

---

## Run it

```bash
cp .env.example .env
docker compose up --build
```

| What | Where | Sign in |
|---|---|---|
| Viewer | http://localhost:5174 | none, it is public |
| CMS | http://localhost:5173 | `admin@peblo.test` / `admin-dev-password` |
| CMS as an editor | http://localhost:5173 | `editor@peblo.test` / `editor-dev-password` |
| API docs | http://localhost:8000/docs | |

The API container migrates, seeds and publishes an initial catalogue before it
starts serving, so a clean checkout gives you a browsable viewer with no manual
steps. All three are idempotent, so restarting does not duplicate anything.

**If any of those ports are busy on your machine**, every host port is a
variable. Set whichever you need in `.env` and nothing else changes, because
only the host side of the mapping moves:

```bash
POSTGRES_HOST_PORT=5433
API_HOST_PORT=8010
CMS_HOST_PORT=5173
VIEWER_HOST_PORT=5174
```

This came from developing on a machine that already had something on 5432 and
8000. It seemed worth making a property of the project rather than a thing you
have to work around.

### Running the backend without Docker

```bash
docker compose up -d db
cd api && python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/alembic upgrade head && .venv/bin/python -m app.seed
.venv/bin/pytest        # 162 tests
```

### Try the interesting paths

1. **Role enforcement.** Sign in as the editor, open Publish. The button is
   disabled with a written reason. Sign in as the admin: it is enabled. The
   editor also gets a 403 from the API directly, not just a hidden button.
2. **Artwork validation.** Open any show, drop `data/assets/poster_wrong_ratio.jpg`
   into the Poster slot. You get a sentence about the image being rotated, not a
   status code. `banner_too_big.png` is rejected on pixels while passing the
   200 KB ceiling comfortably.
3. **Idempotent publish.** Publish twice with no edits. The second run records
   `no_change` and writes no file.
4. **Rollback.** Edit a show title, publish, then use "Make this live again" on
   the previous run. The viewer serves the old catalogue immediately.
5. **The planted defects.** The Publish page has a "Data import problems"
   section listing exactly what arrived broken in `seed_shows.json`.
6. **Season 0.** Open any show in the viewer. Trailers get their own strip and
   never appear as a season, and a grouped episode shows its language options as
   chips.
7. **Slow images.** Throttle the network and reload the viewer. Every image slot
   holds its space, so the page is fully usable before a single image arrives
   and nothing moves when they do.

---

## What was wrong with the seed data

The brief said the seed is deliberately imperfect and would not say where. A
full audit found eight things. Each one drove a requirement rather than being
patched over.

| # | Defect | Evidence | How it is handled |
|---|---|---|---|
| 1 | Duplicate `(content_group, language)` | `ep_9001` collides with `ep_0004` on `(motis-many-lives-s01e02, hi)`, and its title reads "The Lost Kite (v2)" while S1E2 is "Rain on the Roof" | Database unique constraint. The seeder records the rejection in `import_issues` and the validation report shows it |
| 2 | A whole show with `section: null` | `rhyme-rangers`, all 8 rows, all draft | Imports as a draft show, so it is correctly not a blocker yet. Publishing it is refused with the allowed sections named |
| 3 | Published episode with zero artwork | `ep_0036`, `artwork_available: []`, status `published` | Imported as a draft and reported. See decision D9 below, this one shaped the design |
| 4 | Trailers ship thumbnail only | `ep_0093`, `ep_0094`, Season 0 | Warning, not a blocker. See D4 |
| 5 | Language variants disagree on duration | 16 content groups, 7 by more than 20% | The canonical language wins, and the gap is surfaced as a warning |
| 6 | A collapse decoy | `peblo-songs-lyrical` is a separate show with the *same 10 episode titles* as `peblo-songs`, distinct content groups, same section | Collapsing keys on `content_group` only, never on title similarity. A test asserts they stay separate |
| 7 | Episode titles repeat across all 8 shows | "The Lost Kite" exists in every show | Search results carry show, season and episode, or they would be unusable |
| 8 | A partially published show | `number-nest`: 6 published, 2 draft | Publishes carrying only its published episodes |

Checked and cleared, so **not** defects: the file is valid UTF-8 (the dash in
"Peblo Songs — Lyrical" is a real em dash that only looks broken in a cp1252
terminal); no episode number gaps; no duplicate `episode_id`; no null durations;
no show-level field drift.

**The assets audit mattered too.** No supplied image exceeds 200 KB, and
`banner_too_big.png` is 2560×1440 at 13.8 KB. So dimension checks and the byte
ceiling have to be independent, and the 200 KB rule needs a generated fixture in
tests or it ships having never once executed.

---

## Decisions and trade-offs

Recorded so they can be argued with, per the brief's instruction to decide and
move on.

- **D1. Categories are a Postgres `text[]` with a GIN index**, not a join table.
  Fixed 15-value vocabulary, read constantly, written rarely. Saves a table and
  a join on the hottest query. A join table would be more orthodox and would
  start paying off if categories ever needed their own attributes.
- **D2. Search runs server side over the published catalogue held in memory**,
  not over Postgres. Reasoning in Part E.
- **D3. The canonical language of a collapsed entry is the first present in
  `reference.json` order**, so `en` when available. Its title and duration
  represent the group. Divergent durations warn rather than being averaged,
  because averaging invents a number nobody can verify.
- **D4. Season 0 trailers need a thumbnail only.** A trailer never occupies a
  poster row, so demanding a 2:3 poster makes an editor's life worse for no
  viewer benefit. Missing poster or banner on a trailer warns.
- **D5. Two separate applications**, not one app with two routes. The viewer's
  API client has no token and no admin path, so "the viewer UI calling admin
  endpoints" is unrepresentable rather than discouraged. CI greps for it too.
- **D6. `ep_9001` is rejected at import, not silently dropped**, and surfaces in
  the validation report.
- **D9. The seeder downgrades rather than blocks, and this shaped the design.**
  `ep_0036` arrives `published` with no artwork, which is a blocking condition,
  so a literal import would have made the very first publish fail and handed you
  an empty viewer on `docker compose up`. The fix was not to weaken the publish
  rule, which is the valuable part, but to notice that the rule belongs at
  *write time*: the API refuses to set an episode published without artwork and
  a duration, so a row like `ep_0036` could never have been created through the
  API. It exists only because it came in through a bulk import that bypassed
  validation. The seeder therefore applies the same rule, imports it as a draft,
  and reports it. The defect stays visible, the demo works, and the blocking
  path is still demonstrable.
- **D10. A show's status is derived at import** from whether any of its episodes
  is published. The seed carries status per episode only.
- **No component library and no CSS framework.** Two small apps rendering
  tables, forms and a grid. Hand-written CSS with custom properties is smaller
  and has no upgrade risk. At ten more screens a library starts paying for
  itself.
- **TanStack Query in the CMS, not in the viewer.** The CMS is almost entirely
  server state, and its hard problem is invalidation: the validation report and
  the publish button must go stale the moment an editor fixes something. That is
  exactly what the library is for. The viewer fetches one immutable document per
  session that cannot change under it, so a fetch in a context provider is the
  whole job. Adding a cache over a value that never invalidates is complexity
  with no counterpart benefit.

---

## Design

Two surfaces, one language, deliberately different amounts of personality.

### Why the viewer looks like this

The use scene decided the ground: a child on a tablet with a parent nearby, in a
lit room. That rules out a cinema-dark shell, which causes eye strain in
daylight and, here, would have made the supplied flat placeholder artwork look
like holes punched in the page.

The palette is **measured rather than guessed**. I loaded a reference design
into a canvas and counted pixels:

| Colour | Share of frame | Role |
|---|---|---|
| `#ffffff` | 53% | the ground is white |
| blush, lavender, sky, cream | ~10% | soft tinted section panels |
| `#f0a800`, `#7860d8`, `#f04890` | ~4% | amber, violet, pink accents |

That measurement changed the design twice over: the ground got lighter, and one
accent became a family of them.

**The tinted bands earn their place twice.** They give the page rhythm, and they
solve a real problem: flat placeholder posters dissolve into plain white. Each
row now sits on its own soft ground, so the artwork has a frame.

**The doodle layer is where the personality lives.** Curls, clouds, sparkles,
stars, a sun, a zigzag, all drawn as SVG paths, so the charm costs a few hundred
bytes and no image requests. They drift on a slow loop and sit only in the outer
margins, because a doodle landing on the headline stops being charm and becomes
noise. Hidden entirely on mobile and under `prefers-reduced-motion`. This
matters more than usual here: the artwork cannot supply personality, so the
type, the colour and the drawn marks have to.

**Poster cards are cut as arches**, which reads as a storybook window and is the
one shape in the design that is not a rounded rectangle. It also does work: with
flat artwork, the silhouette carries the interest photography normally would.

Primary actions are near-black pills. Amber and pink are too light to carry
white text and too loud to carry ink at button size, so they stay accents.

### Why the CMS looks plainer

It shares the viewer's tokens, display face, pill shapes and accents, so the two
read as one product. It does not share the playfulness.

The brief asks for a tool someone uses fifty times a week, and the rubric line
is *usability*. So the working areas keep tabular numerals so durations and
counts align, a sticky table header that survives a long list, and status pills
that carry a dot as well as a colour, so the distinction survives a colour-blind
reader. A drifting doodle behind ninety-four episode rows is something to look
past, not something to enjoy.

Sign-in is the deliberate exception, because it is the one screen an editor sees
before they are working. It carries the full language: a colour panel with the
doodle layer beside the form. Its role picker is the one idea taken from
reference screens and made functional rather than decorative: two cards fill the
seeded editor and admin credentials, so the difference between the roles is
legible before signing in and nobody copies passwords out of this file. The
server still decides what each role may do.

### Two defects that only measurement caught

- **The compositor never rested.** A tiled `feTurbulence` grain and an
  *infinite* skeleton shimmer meant that with lazy images below the fold,
  placeholders animated forever and rendering never reached a stable frame. The
  grain is gone; the shimmer is bounded to eight passes. On a child's tablet
  that was a frame-rate and battery cost for a texture nobody would consciously
  notice.
- **Six colour pairs failed WCAG AA as text**, between 2.82:1 and 4.34:1,
  including episode numbers and placeholder text. Fixed by splitting text-safe
  siblings off the brand colours. Every pair across both apps is now measured;
  the lowest is 5.30:1 against a 4.5 requirement.

Both apps also pass a copy audit in CI that fails the build on an em dash or an
emoji used as an icon, and a grep that fails if the viewer ever references an
admin endpoint.

---

## Data model

```
users(id, email UNIQUE, password_hash, role)
shows(id, slug UNIQUE, title, synopsis, section NULL, categories text[], status)
seasons(id, show_id, season_number)          UNIQUE(show_id, season_number)
episodes(id, season_id, episode_number, title, duration_seconds NULL,
         language, content_group, status)    UNIQUE(content_group, language)
artwork(id, show_id NULL, episode_id NULL, kind, storage_key,
        width, height, bytes, checksum)      CHECK(exactly one owner)
publish_runs(id, run_id, started_by, started_at, finished_at, status,
             catalog_key, content_hash, counts, error)
catalog_pointer(id=1 CHECK(id=1), current_run_id, updated_at)
import_issues(id, source_row, reason, action)
```

Every index exists for a query, not for decoration:

| Index | The query behind it |
|---|---|
| `episodes(content_group, language)` UNIQUE | The brief's constraint, enforced by Postgres rather than app code so a concurrent write cannot slip past it. Also the grouping key at build time |
| `shows(status, section)` | The exact predicate the publish query and the validation report both run |
| `episodes(season_id, episode_number)` | Season ordering |
| GIN on `shows.categories` | The category filter, via `@>` |
| `publish_runs(started_at DESC)` | Run history, newest first |
| Partial UNIQUE on `artwork(show_id, kind)` and `(episode_id, kind)` | One poster per show, one thumbnail per episode |

`alembic check` runs in CI, so a model change without a migration fails there
rather than on the next deploy.

---

## Part E: written

### How publishing is atomic, and what happens if the process dies

Each publish writes `catalog/runs/<uuid>.json`. The key has never been used
before and is never written again. When the write completes and reads back with
a matching hash, one transaction flips a single row in `catalog_pointer` to that
run. **That pointer update is the atomic commit point**, and it is a single row
update, so Postgres either commits it or it does not.

Before the flip, the new file exists but nothing references it, so no reader can
reach it. After the flip, every reader sees a complete file. A half-written
catalogue is unreachable by construction rather than by timing.

If the process dies:

- **Before the write:** the run row is stuck at `running`, nothing was written,
  the pointer is untouched.
- **Between the write and the flip:** an orphan file sits in storage,
  unreferenced and harmless. Readers keep serving the previous catalogue with no
  interruption. Orphans are deliberately not cleaned up on the crash path, since
  deleting things immediately after a crash is how you delete the wrong thing.
- **During the flip:** the transaction commits or it does not. There is no half
  state.

A sweep on API startup marks any run left `running` for over five minutes as
`failed`, so run history never shows a permanently spinning publish.

`test_a_crash_before_the_pointer_flip_leaves_readers_untouched` monkeypatches
the pointer flip to raise and asserts readers stay on the previous catalogue. It
tests the claim itself rather than a proxy for it.

**Idempotence** comes from hashing the built catalogue with `run_id` and
`generated_at` excluded. Publishing twice over unchanged data produces the same
hash, records `no_change`, and writes nothing.

### The storage abstraction: what changes to move to Cloudflare R2

A five-method `Protocol` (`put`, `get`, `url`, `exists`, `delete`).
`LocalDiskStorage` and `R2Storage` both implement it, and `get_storage()` picks
one from `STORAGE_BACKEND`. Every caller depends on the Protocol, never on a
concrete class.

Moving to R2 is: set `STORAGE_BACKEND=r2`, supply four R2 credentials, and point
`STORAGE_PUBLIC_BASE_URL` at the bucket's public domain. No call site changes.

**That claim is tested rather than asserted.** MinIO speaks the same S3 API R2
does, so `R2Storage` is exercised against it over the real wire protocol:

```bash
docker compose --profile storage-test up -d minio
cd api && pytest tests/test_storage_contract.py
```

`test_storage_contract.py` runs one set of assertions against **both** backends,
so any behavioural divergence fails rather than being discovered in production.
The strongest case in there seeds the database, uploads all 117 artwork files,
publishes, and reads the catalogue back, entirely on S3, with no application
code changed. Idempotence is checked there too, because it comes from the
content hash rather than from anything filesystem-shaped. In CI MinIO runs as a
service container and a follow-up step fails the build if the R2 half *skipped*,
since a storage test that silently skips proves nothing.

**Writing that test found a real bug.** `build_catalog` was reaching for the
global `get_storage()` singleton to build artwork URLs instead of using the
storage it had been handed. The catalogue file went to S3 while the URLs inside
it were generated by whatever the environment happened to be configured with.
Storage is now a parameter, so the URLs in a catalogue always come from the same
backend the catalogue itself was written to. That is exactly the kind of hidden
global coupling that makes a "just swap one class" claim quietly untrue, and it
only surfaced because the swap was actually performed.

**Still honest about the limit:** MinIO is not Cloudflare. R2 has its own
quirks, notably around multipart uploads and conditional requests, that this
does not cover. What is proven is that the abstraction holds and the boto3 code
path works against a real S3 implementation.

### Search: how, at what size it stops working, and what next

Server side, over the published catalogue held in memory and cached by `run_id`.
Not over Postgres. Two reasons: the viewer must only ever see published content,
and searching the same artifact it renders makes divergence structurally
impossible; and it is roughly twenty lines with no new index.

`q` matches show title, episode title and category, case insensitively. All
filters compose with AND. Results carry show, season and episode number, because
the seed proves episode titles repeat across all eight shows.

**It stops working at roughly 10k entries or a few MB**, where the per-request
linear scan starts costing real CPU and the in-process copy per worker starts
costing real memory. This catalogue is 7 shows and 63 entries, so that is about
two orders of magnitude of headroom.

**Next:** build a `catalog_entries` projection table at publish time and query it
with a Postgres `tsvector` index, which also buys stemming and ranking. Past
roughly a million entries, or as soon as typo tolerance and relevance tuning
matter, move to OpenSearch or Typesense fed by the same publish job. The
projection step is where I would start, because it keeps one writer, the publish
job, as the only thing that can change what search sees.

### Why serve a pre-published file at all

The read path becomes a pure function of one immutable artifact. It cannot be
broken by an edit in progress, it caches trivially at any layer, viewer traffic
never touches the database editors are writing to, and rolling back is a pointer
move rather than a data migration.

**Where it bites.** Edits are invisible until someone publishes, so the
catalogue can drift from what editors believe is live, silently and for as long
as nobody publishes. Any bug in the build job ships to every viewer at once with
no gradual rollout. And the whole catalogue is one document, so it stops being
appropriate at the size where a viewer should not download all of it, which is
the same ceiling search hits. Rollback mitigates the second. The first is why
the alert below is the one I chose.

### What was left out, and why

- **Publish dry-run diff** and **audit log of who changed what**, the other two
  stretch goals. This was a deliberate call rather than running out of time. The
  100 rubric points contain no stretch category, so both would have added new
  surface across every write path, late, for no scored benefit, while making
  this section thinner. The one stretch goal I did build, rollback, was worth it
  for a different reason: it exists because atomicity was designed as immutable
  files plus a pointer, so it is evidence for the publish section rather than a
  bolt-on. Publish runs already record who, when, counts and outcome.
- **Automated frontend tests.** Neither app has any. CI typechecks, lints and
  runs a copy audit over both, and the backend has 162 tests, but there are no
  component or end-to-end tests for the UI. I verified both apps by driving them
  in a browser instead, including the role gate in both directions, the artwork
  rejection path and the blocked-publish state. Adding a test framework at this
  stage would have been the padding the brief warns against, so I would rather
  name the gap than pretend the typecheck covers it. If this were going further,
  Playwright over the five-step flow in "Try the interesting paths" is where
  I would start, because that is the path that would actually catch a
  regression.
- **Video playback.** There is no video in the exercise.
- **Image resizing on upload.** We reject rather than silently transform,
  because quietly altering an editor's artwork is worse than telling them.
- **User management UI.** The brief needs roles enforced, not user CRUD.
- **Pagination on `/catalog`.** The whole catalogue is the artifact by design;
  paginating it would defeat the point. It is the same ceiling as search.
- **A real deploy target.** The deploy job is written and commented but gated
  off, since there is no cloud to deploy to.

### AI tools, and where I rejected their output

I used Claude Code throughout. The brief asks where I accepted its output and
where I did not, and the rejections are the part worth reading, because they are
where the design decisions actually got made:

- **The `ui-ux-pro-max` design-system tool was wrong three times in a row for
  the viewer, in the same way.** It returned "Dark Mode OLED, cinema dark and
  play red" for every query, including one that explicitly said *not dark*. It
  was keyword-matching on "streaming" and would have produced a Netflix clone
  for a children's product. **Rejected.** It also proposed Comic Neue for body
  text (**rejected**: a Comic Sans derivative hurts readability and reads as
  unserious) and a video-background hero (**rejected**: there is no video here,
  and a video background taxes exactly the audience most likely to be on a slow
  connection). What I did take from it was Baloo 2 for display, which is
  genuinely kid-appropriate, and its accessibility checklist, which is sound.
- **For the CMS the same tool returned a "Comparison Table + CTA" landing-page
  pattern and a dark style with a light background.** Rejected wholesale: it had
  matched on the word "table" and returned a marketing page structure for an
  internal admin tool, and its own recommendation contradicted itself.
- **Where the tools were replaced by measurement.** Rather than take a palette
  on trust, I loaded a reference design into a canvas and counted pixels. That
  produced white at 53% of the frame, a family of soft tinted panels at roughly
  10%, and saturated amber, violet and pink as accents. Every one of those
  numbers contradicted what the recommendation tool had suggested, and the
  design follows the measurement.
- **Generated code needed correcting in places that were quiet rather than
  loud.** A `str`-mixin enum whose `str()` renders as `ContentStatus.published`
  rather than `published` (switched to `StrEnum`). A `pydantic` `EmailStr` that
  rejects the `.test` TLD as reserved (dropped, since the endpoint looks up a row
  rather than mailing anyone). A form-state effect causing cascading renders
  (replaced with a keyed child component). An artwork validator reporting
  "larger than we need" about a rotated image that was also too short.
- **The design spec in `docs/` was written before any code.** Its self-review
  pass is what caught D9, a genuine contradiction between the publish rule and
  the "compose works first try" requirement.

The general shape: these tools are good at checklists and bad at judgment. Every
accessibility and interaction item they raised was worth keeping. Every
aesthetic recommendation was a category reflex that had to be thrown out.


---

## Pipeline and operability

### Secrets in production

Nothing in `.env.example` is real, and none of it would be in production.
Secrets come from the platform's secret manager (AWS Secrets Manager, GCP Secret
Manager, or Cloudflare's encrypted environment variables) and are injected into
the container at start, never baked into an image, because an image layer is
permanent and gets pushed to registries other people can read. The JWT signing
key and the R2 credentials rotate on a schedule; the API reads them at startup,
so rotation is a restart rather than a code deploy. CI authenticates to the
cloud through OIDC with a role scoped to this repository and branch, so there is
no long-lived deploy key to leak. Database credentials come from the managed
database's own rotation, and the application never sees the admin role.

### Health

- `GET /healthz` is **liveness only** and touches no dependency, so a database
  blip cannot make the orchestrator kill otherwise healthy containers and turn a
  small incident into an outage.
- `GET /readyz` checks the database, storage, and that the catalogue pointer
  resolves to a file that actually reads. That last check is the one that
  matters: it is the exact condition the viewer depends on.

### The one thing I would alert on

**A publish run stuck in `running` for more than five minutes.**

The loud failures here are already safe. If the API is down the viewer errors
and everyone knows in seconds. If a publish fails validation the editor sees it
on screen immediately. The dangerous failure is the silent one: a publish that
died between writing the file and flipping the pointer. Nothing is broken, no
error is raised, the viewer keeps serving the previous catalogue perfectly, and
the editor believes they published. Content that was supposed to go live simply
does not, and nobody finds out until a human notices something missing.

That is the failure with the longest gap between occurrence and detection, which
is exactly what an alert is for. Everything else in this system fails loudly
enough to alert itself.

Second, at lower severity: `readyz` failing on the catalogue check, meaning the
live file has become unreadable. That one is viewer-facing, so it is louder, but
it is also the one a synthetic check would catch anyway.

### CI

`lint` (ruff, oxlint, `tsc`, and a copy audit that fails on em dashes and emoji
used as icons), `test` (migrations apply from empty, `alembic check` for model
drift, then 162 pytest tests against a real Postgres and a real S3), `build` (all three
images, tagged by commit SHA). A grep step fails the build if the viewer source
ever references an admin endpoint or an auth header.

The `deploy` job is written and commented step by step, and gated off because
there is no cloud behind it. The comments carry the reasoning that matters:
migrations run before the rollout and must be backward compatible with the
version still running, the API waits on `/readyz` rather than `/healthz`, the
frontends deploy after the API because they are static bundles calling it, and
images are tagged by SHA so a rollback is "deploy the previous SHA" rather than
a guess about what `latest` meant an hour ago.

---

## Tests

162, concentrated on what is risky rather than spread evenly:

- **Publish**: atomicity (a monkeypatched crash before the pointer flip),
  idempotence, that a blocked publish writes nothing, that two publishes over
  changed data leave two files with the older one intact.
- **Language grouping**: S1E2 collapses to `["en","hi"]` at the English
  duration; `peblo-songs` and `peblo-songs-lyrical` stay separate despite
  identical episode titles; drafts are excluded.
- **Artwork**: all six supplied fixtures with their expected verdicts, plus a
  generated file over 200 KB, since no supplied asset reaches the ceiling.
- **Roles**: an editor gets 403 from publish, an anonymous caller gets 401.
- **Filters**: `q`, `category`, `language` and `section` narrow together rather
  than one silently winning.
- **Storage**: one contract run against both backends, with `R2Storage`
  exercised against MinIO over the real S3 protocol, including a full
  seed-publish-read cycle on S3 with no application code changed.
- **Season 0**: absent from `seasons`, present in `trailers`.
- **Seed import**: `ep_9001` rejected, `ep_0036` downgraded, both reported, and
  a bootstrap publish succeeds on a fresh seed so that D9 cannot be removed
  without CI noticing.

---

## Time spent

| Part | Time |
|---|---|
| Audit, design spec and plan | 1.5h |
| A: backend | 6h |
| B: CMS | 3.5h |
| C: viewer | 2.5h |
| D: pipeline, CI, ops | 1.5h |
| E: README | 1h |
| Visual design pass across both UIs | 2h |

The audit came first on purpose. Finding the eight defects before writing any
schema is what turned "handle bad data" from a vague worry into eight concrete
requirements with tests attached.
