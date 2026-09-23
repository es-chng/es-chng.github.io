# Schema Lab: schema-driven publishing for a single-author microjournal

A **standalone engine** for a single-author microjournal or practice-update
newsletter. Not a peer-reviewed journal, not a full CMS. It proves one design
idea: an article can be defined as a *schema* (a named, ordered list of
fields, each with a shape, a display style, and a visibility), and one small
set of templates can turn *any* schema, and any article using it, into a
correct webpage, a correct PDF, and a correct entry in an issue's table of
contents — without the templates ever hardcoding a field's name.

See `CHANGELOG.md` for how this was built, what broke along the way, and how
each fix was verified. This file only covers the current state.

## What's real and what's a stand-in

- **Real, meant to carry over into an actual journal:** the two-layer schema
  model, the generic field renderer (`_includes/schema-field.html`,
  `_includes/schema-slot.html`), the article and issue layouts, the PDF
  renderer, and the validator.
- **A stand-in, for testing only:** every file in `_articles/` is either mock
  content or a deliberately minimal test fixture. `schema-toy-example.yml`
  and its one article exist purely to prove a second, unrelated schema works
  through the same templates unmodified — delete both before this is ever
  used for real content.

## Layout of this repository

| Path | What it is |
| --- | --- |
| `_data/schema-*.yml` | Schema definitions. One file per schema. Each field declares `shape`, `style`, `visibility`, and optionally `teaser: true` / `max_chars` / `optional: true`. |
| `_articles/*.md` | Articles. Front matter holds the ten base fields (title, authors, corresponding_email, volume, issue, order, pages, published_date, doi, licence) plus whatever the named `schema:` requires. |
| `_issues/*.md` | One file per issue (volume/issue/date/theme) — the issue's own identity, not its contents. |
| `_layouts/article.html` | Renders the fixed base frame, then hands off to `schema-slot.html` for everything else. |
| `_layouts/issue.html` | Lists every article in an issue, showing base fields plus each article's one nominated teaser field. |
| `_layouts/page.html` | Plain static pages (About, etc.). |
| `_includes/schema-slot.html` | Walks a schema's field list in order, for the webpage. |
| `_includes/schema-field.html` | Renders one field, generically, by its declared shape and style (`text`, `list`, `table`, `boolean`, `date`). Has no knowledge of any specific field's name. |
| `_includes/site-header.html` | The shared masthead (title, About/Issues links) included on every page. |
| `index.html` | Homepage: positioning statement, 5 most recent articles across every issue. |
| `issues/index.html` | Archive of all issues. |
| `assets/css/style.css` | The visual register — serif, monochrome, small-caps labels, thin rules — with light and dark mode. |
| `scripts/validate_schema.py` | Checks every article against its schema **before** anything builds — required fields, shape mismatches, teaser length, and the publish-lock policy. Run before every build. |
| `scripts/render_pdf.py` | Builds one article's PDF, walking the same schema the webpage does. |
| `scripts/render_all_pdfs.py` | Builds every article's PDF unconditionally. Local use only — CI does not run this. |
| `scripts/render_changed_pdfs.py` | Builds a PDF only for a new or changed article, reusing the rest from a cache. What CI actually runs. |
| `scripts/zenodo_articles.py` | Reserves a DOI from Zenodo, embeds it in the PDF, uploads, publishes, records it in the ledger. |
| `scripts/selftest.py` | Automated regression checks. Run after any template or logic change. |
| `tests/broken-articles/*.md` | Three deliberately malformed articles — fixtures for the validator and the self-test, not real content. |
| `requirements.txt` | Python dependencies (`pyyaml`, `reportlab`, `requests`). |
| `Gemfile` / `Gemfile.lock` | Ruby dependencies (Jekyll), pinned. |
| `CITATION.cff` / `.zenodo.json` | Metadata for citing the *package itself* — separate from per-article DOIs. |
| `_data/schema-locks.yml` | Content-hash locks for schemas used by published articles. |
| `_data/zenodo-ledger.yml` | slug → DOI map, written automatically by the Zenodo deposit workflow. |
| `.github/workflows/pages.yml` | Validate → build → incrementally render PDFs → publish, on every push. |
| `.github/workflows/zenodo-articles.yml` | Deposits new/changed article PDFs to Zenodo, after a successful publish or on demand. |
| `.github/actions/setup-toolchain/` | The setup steps (Python, dependencies, fonts) shared by both workflows above. |

## The two-layer schema model, in short

**Layer 1, the base** — ten fields, fixed, the same for every article
regardless of schema: `title, authors[], corresponding_email, volume, issue,
order, pages, published_date, doi, licence`. The base frame (header and
footer of the article page, and of the PDF) is drawn from these alone and
never consults any schema.

**Layer 2, the schema** — fully open. A schema is a list of fields; each one
says how it should be shown (`shape`: text/list/table/boolean/date; `style`:
plain/boxed/opinion/badge/table; `visibility`: public/editor/reviewer/private).
Exactly one field per schema must be marked `teaser: true`, with a `max_chars`
limit, because the issue-listing page and the homepage show that one field
next to every article's title as a one-line summary.

The schema built out fully here, `schema-practice-update.yml`, matches a
"Practice Update" article: issue type, the issue, anchor papers (citation,
evidence type, note), practice recommendations, unresolved questions, sample
report wording, personal perspective, bottom line (the teaser), keywords, and
conflicts of interest — public, since this is a single-author,
non-peer-reviewed model with no editor to disclose to privately.

## Published = immutable

Once an article is published, you do not amend it in place, and a later
change to its format definition does not silently alter what readers see.

1. **Published articles pin their schema.** Front matter carries
   `status: published` and `schema_version: N`, matching the schema file's
   top-level `version`. Validation fails if a published article's pin does
   not match the live schema version.
2. **Schemas used by published articles are content-locked.**
   `_data/schema-locks.yml` stores a hash of each such schema. Editing that
   schema file fails validation with a clear message: create a *new* schema
   file for format changes, don't amend the locked one.
3. **A lock is removable once nothing published needs it any longer.**
   Revert every article using a schema back to `status: draft`, re-run
   `--update-locks`, and the lock is dropped — the schema becomes editable
   again.
4. **Format evolution = a new schema file.** Copy `schema-practice-update.yml`
   to `schema-practice-update-v2.yml` with `version: 2`. New articles declare
   the new schema; old published articles stay on v1 and its locked content.

An article counts as published if any of: `status: published`, a
non-placeholder `doi`, or an entry in the Zenodo ledger. `status: draft`
always overrides the others — it exempts an article from every publish-lock
check regardless of what its DOI or ledger entry might otherwise suggest.

> **Known limitation:** `status` only affects the lock system above. It does
> not hide an article from the homepage, an issue listing, or its own URL —
> a `draft` article that is pushed is fully live and listed, exactly like a
> published one. There is currently no mechanism to keep a draft private.

To create or refresh locks after marking articles published (or after
reverting one to draft):

```
python scripts/validate_schema.py --update-locks
```

## Two DOI tracks

**1. The package itself.** Zenodo's native GitHub integration, no custom
code: make the repository public, link your GitHub account on zenodo.org,
toggle this repository on, then cut a GitHub Release. Zenodo archives it and
mints a DOI automatically. `CITATION.cff` and `.zenodo.json` are already
present — paste the resulting concept DOI into `CITATION.cff` afterward.

**2. Individual articles**, with the DOI embedded in the PDF itself, not just
shown on the webpage. The pipeline, in order:

1. Reserve a DOI on Zenodo (a draft deposition).
2. Render the PDF with that DOI in the footer (`doi_override`).
3. Upload that PDF and publish the deposition.
4. Record the DOI in `_data/zenodo-ledger.yml`. The article layout prefers
   this over any placeholder DOI in front matter.

No file is ever written back into an article's `.md` — this avoids a
workflow re-triggering itself. Ledger commits use `[skip ci]`.

**One-time setup:**

1. Create a Zenodo personal access token (`deposit:write` + `deposit:actions`
   scopes). Start on [sandbox.zenodo.org](https://sandbox.zenodo.org).
2. Add it as the repository secret `ZENODO_TOKEN`.
3. Optional: repository variable `SITE_URL` (links each Zenodo record back to
   the live article page); variable `ZENODO_LIVE=1` only when you want
   production `zenodo.org` instead of the sandbox.

Local dry-run (embeds a fake DOI in the PDF so you can inspect the footer):

```
python scripts/zenodo_articles.py /tmp/pdfs --dry-run
# footer contains https://doi.org/10.5281/zenodo.DRYRUN-...
```

## Deploying

**One manual step required.** Go to **Settings > Pages** and change
**Source** to **GitHub Actions**. Until you do, GitHub keeps using the old
branch-based deploy, which skips validation and PDF generation entirely.

Once switched, every push:
1. Validates every article. **If anything fails, the job stops here** —
   nothing below it runs, and the site keeps serving whatever last published
   successfully. A hard gate, not a warning.
2. Builds the Jekyll site.
3. Builds a PDF only for a new or changed article, reusing the rest from a
   persistent cache (see below).
4. Publishes.

Nothing is committed back to the repository by this workflow — PDFs live in
GitHub's Actions cache between runs, not in git.

### Why PDFs build incrementally

Rebuilding every PDF on every push is fine at a handful of articles, but
stops being free as the count grows. `scripts/render_changed_pdfs.py` keeps a
`manifest.json` recording, per article, a hash of that article's file
**plus** the file of whichever schema it declares — so a schema edit
correctly forces a rebuild of everything using it, and nothing else. An
article removed from `_articles/` has its cached PDF and manifest entry
removed too.

The cache step saves under a key that includes the run ID (so every run
creates a new entry rather than conflicting on save) and restores via a
shared key prefix, which resolves to the most recently created matching
entry — last run's cache.

**Self-healing edge case:** GitHub evicts a cache entry unused for about a
week, and caps total cache size per repository. If a restore ever misses, the
next run just rebuilds everything from an empty manifest — slower once,
self-correcting from there, not a bug.

## Running it yourself, locally

```
bundle install                                   # once, installs Jekyll
pip install -r requirements.txt                  # once, installs Python deps
python scripts/validate_schema.py                # check content before building
bundle exec jekyll serve                         # preview at http://localhost:4000
python scripts/render_pdf.py _articles/her2-ultralow.md out.pdf
python scripts/selftest.py                       # run every regression check
```

Deliberately broken articles live only under `tests/broken-articles/` and are
used by the self-test; they never affect a normal validate or build.

## Known limitations, as of now

- **`status: draft` does not hide an article from the live site** — see the
  callout above.
- **No real submission or review workflow feeds into this.** Every article
  is hand-written directly into `_articles/`.
- **Only two schemas exist**, one fully built and one deliberately minimal.
  A schema needing a genuinely different visual arrangement, not just
  different fields, might expose gaps in the current toolbox of styles.
- **Figures/images are out of scope.** The `shape` vocabulary has room for an
  image shape later, but nothing about uploading, storing, or displaying one
  has been built.
- **PDF pagination with much longer content** hasn't been stress-tested —
  checked against realistic articles, not intentionally long ones.
- **Mixed real content and test fixtures.** `mock-*` and `toy-*` files sit in
  the same folders as real content, distinguished only by naming convention.

## If you extend this

- **A new field shape** (e.g. `figure`) needs handling added in exactly three
  places: `_includes/schema-field.html` (webpage), `scripts/render_pdf.py`
  (PDF), and `scripts/validate_schema.py` (its validation rule). The
  issue-listing and homepage only need a change if the new shape could
  plausibly be nominated as a teaser.
- **A new schema** needs none of the above — just a new `_data/schema-*.yml`
  file and articles that declare it, exactly like `schema-toy-example.yml`.
- **A new schema version** for an existing format: copy the schema file,
  bump `version`, and only new articles adopt it — published articles stay
  pinned to what they were published under (see "Published = immutable").
