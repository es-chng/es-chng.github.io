# Schema Lab: schema-driven publishing for a single-author microjournal

This is a **standalone prototype** for a single-author microjournal (or practice-update
newsletter). It is not a peer-reviewed journal and not a full CMS. It exists to prove
one design idea: an article can be defined as a *schema* (a named, ordered list of
fields, each with a shape, a display style, and a visibility), and one small set of
templates can turn *any* schema, and any article using it, into a correct webpage, a
correct PDF, and a correct entry in an issue's table of contents — without the templates
ever hardcoding a field's name.

Everything here was built and checked in small steps, each one verified before the next
began. That history is worth knowing before you change anything, because two real bugs
were found and fixed along the way (see the development notes later in this file) —
the design held up, but not on the first attempt.

### Full Zenodo automation

Schema Lab supports **two independent DOI tracks**. Both can be fully automated.

#### 1. Package DOI (the tool itself)

Use Zenodo’s **native GitHub integration** (no Action required):

1. Make the repository public.
2. On [zenodo.org](https://zenodo.org) → link your GitHub account → toggle this repo **On**.
3. Create a GitHub Release (e.g. `v0.1.0`).
4. Zenodo archives the release and mints a DOI automatically.

`CITATION.cff` and `.zenodo.json` are already present. After the first release,
paste the concept DOI into `CITATION.cff` and add a badge here.

#### 2. Article DOIs (embedded in the final PDF)

The DOI must appear **inside the published PDF**, not only on the webpage. The
pipeline therefore does this in order:

1. **Prereserve** a DOI on Zenodo (draft deposition).
2. **Render** the PDF with that DOI in the footer (`doi_override`).
3. **Upload** that PDF and **publish** the deposition.
4. Record the DOI in `_data/zenodo-ledger.yml` (HTML prefers this over placeholders).

Wired into `.github/workflows/pages.yml` when `ZENODO_TOKEN` is set. Without the
token, PDFs still build with placeholder front-matter DOIs only.

**No write-back into article `.md` files** → no re-trigger loops. Ledger commits
use `[skip ci]`.

**One-time setup (you only):**

1. Create a Zenodo personal access token (`deposit:write` + `deposit:actions`).
   Start on [sandbox.zenodo.org](https://sandbox.zenodo.org).
2. Add repository secret `ZENODO_TOKEN`.
3. Optional: variable `SITE_URL` (article page link on the Zenodo record);
   variable `ZENODO_LIVE=1` only when you want production zenodo.org.

Local dry-run (embeds a fake DOI in the PDF so you can inspect the footer):

```
python scripts/zenodo_articles.py /tmp/pdfs --dry-run
# footer contains https://doi.org/10.5281/zenodo.DRYRUN-...
```

## What's real and what's a stand-in

- **Real, and meant to carry over into an actual journal:** the two-layer schema model,
  the generic field renderer (`_includes/schema-field.html`, `_includes/schema-slot.html`),
  the article and issue layouts, the PDF renderer, and the validator.
- **A stand-in, for testing only:** every file in `_articles/` and `_data/` here is a mock.
  The "authors," DOIs, and citations are invented. `schema-toy-example.yml` and its one
  article exist purely to prove a second, unrelated schema works — delete both before this
  is ever used for real content.

## Layout of this repository

| Path | What it is |
| --- | --- |
| `_data/schema-*.yml` | Schema definitions. One file per schema. Each field declares `shape`, `style`, `visibility`, and optionally `teaser: true` / `max_chars` / `optional: true`. |
| `_articles/*.md` | Articles. Front matter holds the ten base fields (title, authors, corresponding_email, volume, issue, order, pages, published_date, doi, licence) plus whatever the named `schema:` requires. |
| `_issues/*.md` | One file per issue (volume/issue/date/theme) — the issue's own identity, not its contents. |
| `_layouts/article.html` | Renders the fixed base frame, then hands off to `schema-slot.html` for everything else. |
| `_layouts/issue.html` | Lists every article in an issue, showing base fields plus each article's one nominated teaser field. |
| `_includes/schema-slot.html` | Walks a schema's field list in order, for the *webpage*. |
| `_includes/schema-field.html` | Renders one field, generically, by its declared shape and style. Has no knowledge of any specific field's name. |
| `scripts/validate_schema.py` | Checks every article against the schema it declares, **before** anything is built — required fields, shape mismatches, teaser length. Run this before every build. |
| `scripts/render_pdf.py` | Builds one article's PDF, walking the same schema the same way the webpage does. |
| `scripts/selftest.py` | Reproduces every checkpoint from the build process, including the two bugs that were caught and fixed. Run this after any template change. |
| `tests/broken-articles/*.md` | Three deliberately malformed articles (missing field, over-length teaser, wrong shape) — fixtures for the validator and the selftest, not real content. |
| `requirements.txt` | Python dependencies (`pyyaml`, `reportlab`, `requests`). |
| `CITATION.cff` / `.zenodo.json` | Citation and Zenodo metadata for the package DOI. |
| `_data/schema-locks.yml` | Content hashes of schemas used by published articles (immutability). |
| `_data/zenodo-ledger.yml` | Article → DOI map written by the Zenodo deposit workflow. |

## The two-layer schema model, in short

**Layer 1, the base — ten fields, fixed, the same for every article regardless of schema:**
`title, authors[], corresponding_email, volume, issue, order, pages, published_date, doi, licence`.
The base frame (header and footer of the article page, and of the PDF) is drawn from
these alone and never consults any schema.

**Layer 2, the schema — fully open.** A schema is just a list of fields; each one says how
it should be shown (`shape`: text/list/table/boolean; `style`: plain/boxed/opinion/badge/table;
`visibility`: public/reviewer/editor/private). Exactly one field per schema must be marked
`teaser: true`, with a `max_chars` limit, because the issue-listing page shows that one field
next to every article's title as a one-line summary.

The one schema built out fully here, `schema-practice-update.yml`, matches the "Practice
Update" article format discussed for the journal: issue type, the issue, anchor papers,
solvable-now / not-solved, sample wording, personal perspective, bottom line (the teaser),
keywords, and the trainee/supervisor/declarations fields (editor-only, never public).

## Published = immutable

In a real journal, once an article is published you do not amend it in place, and you do
not let a later change to its format definition silently alter what readers see.

Schema Lab enforces that policy:

1. **Published articles pin their schema.** Front matter carries `status: published` and
   `schema_version: N`, matching the schema file’s top-level `version`. The validator
   fails if a published article’s pin does not match the live schema version.
2. **Schemas used by published articles are content-locked.** `_data/schema-locks.yml`
   stores a hash of each such schema. If the schema file is edited, `validate_schema.py`
   fails with a clear message: create a *new* schema file for format changes; do not
   amend the locked one.
3. **Format evolution = new schema file.** e.g. copy `schema-practice-update.yml` to
   `schema-practice-update-v2.yml` with `version: 2`. New articles declare the new
   schema; old published articles stay on v1 and its locked content.

An article is treated as published if any of: `status: published`, a non-placeholder
`doi`, or an entry in the Zenodo ledger.

To create or refresh locks after marking articles published:

```
python scripts/validate_schema.py --update-locks
```

## Deploying (one manual step required)

This repository now builds, validates, and publishes itself automatically via
`.github/workflows/pages.yml` on every push to `main`. **Before this works, you
must switch this repository's Pages source once:** go to **Settings > Pages**
and change **Source** from "Deploy from a branch" to **GitHub Actions**. Until
you do, GitHub keeps using the old branch-based deploy, which does not run
validation or build PDFs, and this new workflow will show green in the
Actions tab without actually being what serves the live site.

Once switched, every push:
1. Runs `scripts/validate_schema.py`. **If any article fails, the job stops
   here** -- nothing below it runs, and the site keeps serving whatever was
   last published successfully. This is a hard gate, not just a warning.
2. Builds the Jekyll site.
3. Restores the PDFs built by the *previous* run from GitHub's Actions cache,
   then runs `scripts/render_changed_pdfs.py`, which builds a PDF **only for
   an article that is new, or whose content (or whose schema) has changed**
   since the last run -- everything else is reused unchanged. Every current
   article's PDF, built or reused, ends up at `/files/<slug>.pdf`.
4. Publishes the result.

Nothing is committed back to the repository by this workflow (the PDFs live
in GitHub's Actions cache between runs, not in git) -- this deliberately
avoids a workflow-triggers-itself loop that a commit-back step on every push
would risk.

### Why PDFs build incrementally, not from scratch every time

At a handful of articles, rebuilding every PDF on every push costs seconds and
is not worth worrying about. It stops being free as the article count grows,
since the batch script (`scripts/render_all_pdfs.py`, still present for local
use) rebuilds *everything* regardless of what changed -- a one-word typo fix
would otherwise cost the same build time as adding fifty new articles.

`scripts/render_changed_pdfs.py` fixes this with a small persistent cache:

- A `manifest.json` inside the cache directory records, per article, a hash of
  that article's own file **plus** the file of whichever schema it declares.
  Combining the two matters: editing a schema can change how every article
  using it displays, even though those articles' own files never changed, so
  a schema edit correctly forces a rebuild of everything that uses it -- and
  nothing that uses a *different* schema.
- If an article's current hash matches the manifest and its cached PDF still
  exists, it's copied through unchanged. Otherwise it's rebuilt, and the
  manifest is updated.
- An article removed from `_articles/` has its cached PDF and manifest entry
  deleted too, so nothing stale lingers.
- The workflow's cache step (`actions/cache@v4`) saves under a key that
  includes the run ID, so every run's cache is a new entry rather than an
  overwrite, while restoring via a shared key *prefix* -- which GitHub
  resolves to the most recently created matching entry, i.e. last run's
  cache.

**A self-healing edge case worth knowing:** GitHub evicts an Actions cache
entry it hasn't been touched in about a week, and imposes a total cache size
cap per repository. If a restore ever misses -- because of eviction, the very
first run ever, or anything else -- `render_changed_pdfs.py` starts from an
empty manifest and just rebuilds everything, exactly like the very first
deployment did. That's correct behaviour, not a bug: slower for one run,
self-correcting from there.

`scripts/selftest.py` checks five scenarios for this: an empty cache building
everything, an unchanged run rebuilding nothing, a single changed article
rebuilding only itself, a changed schema rebuilding every article that uses
it (and no article that doesn't), and a deleted article's cache entry being
cleaned up.

## Running it yourself, locally

```
bundle install                                   # once, installs Jekyll
pip install -r requirements.txt                  # once, installs pyyaml + reportlab
python scripts/validate_schema.py                # check content before building
bundle exec jekyll serve                         # preview at http://localhost:4000
python scripts/render_pdf.py _articles/her2-ultralow.md out.pdf
python scripts/selftest.py                       # run every checkpoint from development
```

Deliberately broken articles live only under `tests/broken-articles/` and are used by
the self-test; they do not affect a normal validate + build run.

## What was tested, and how

Every step below was built, then checked, before the next one started:

1. An empty site builds.
2. The ten base fields render alone, with the schema section left visibly empty.
3. The schema is written down as its own file, self-checked to have exactly one teaser field.
4. One field, then each remaining shape (list, table, boolean) and style (badge, boxed,
   opinion), added and checked one at a time.
5. A complete, realistic article (a HER2-ultralow example) renders correctly end to end.
6. Two more complete articles, one trainee-led, render correctly — the trainee's
   supervisor field, marked editor-only, correctly never appears on the public page.
7. The issue-listing page correctly shows every article with its teaser, and correctly
   shows a plain fallback for the one article that has no schema at all.
8. Three deliberately broken articles were fed through the validator and the renderer.
   The validator caught all three cleanly. But the renderer, on its own, **silently**
   produced a broken-looking empty table row for the shape-mismatch case — a real bug,
   now fixed so the renderer fails **loudly** instead (a visible, specific message) as a
   second line of defence behind validation.
9. A PDF renderer was built, deliberately reusing the same frame-then-schema logic as
   the webpage. Its first version had a second real bug: table cells didn't wrap, so long
   citation and note text overlapped illegibly. Fixed by wrapping each cell in its own
   paragraph rather than a plain string.
10. A second, genuinely different toy schema (different fields entirely) was written and
    given one mock article. It rendered correctly through the **exact same, unmodified**
    templates — the actual proof that the design is schema-agnostic, not just well-tuned
    to the one schema it was developed against.

`scripts/selftest.py` automates steps 8, 9 and 10's checks, so a future change to the
templates can be re-verified in seconds rather than by re-running the whole manual process.

## Visual register: academic, not casual

The webpage and PDF were rebuilt toward a formal, print-journal register:
one serif type family throughout (no separate sans-serif for labels), a
near-monochrome palette (a single muted colour, used only for links), thin
horizontal rules in place of coloured boxes, small-caps-style section labels
instead of coloured badges, and the "personal perspective" field set as a
traditional italic block quotation rather than a highlighted callout.

This was a styling-only change -- `assets/css/style.css` and the style
dictionary in `scripts/render_pdf.py` -- and touched nothing about the schema
model, the field-rendering logic, or which fields exist. The generic
"style" values a schema can declare (`plain`, `boxed`, `opinion`, `badge`,
`table`) are unchanged in meaning; only how each one is drawn changed. A
schema author does not need to do anything differently because of this.

## Writing register, and the anchor "type" column

Beyond the visual redesign above, the mock articles' prose was rewritten toward a
more precise, attributive academic register: naming study designs and sample
sizes, giving effect sizes with confidence intervals where the (illustrative)
source states them, distinguishing a defined convention from an established
fact, and writing the personal-perspective sections in a measured first-person
voice rather than casual advice.

One schema field was added to support this: every anchor now carries a `type`
(`guideline`, `RCT`, `cohort study`, `audit`, `expert consensus`, etc.)
alongside its citation and note, so a reader can weigh a claim without parsing
the citation string closely. This was deliberately kept to a single
classification field -- no evidence grading, no limitations column, no
scoring -- since that fuller apparatus is the CAT-style machinery this format
intentionally avoids in favour of staying fast to write.

Adding the column required **no renderer code changes** -- both
`_includes/schema-field.html` and `render_pdf.py` already read a table
field's columns generically from the schema, which is exactly the point of
the schema-driven design. It did, correctly, require every existing
article's anchors to be updated: `validate_schema.py` caught all five
articles missing the new column on the first run after the schema changed,
before anything was rebuilt.

**A second table-rendering bug was found and fixed while doing this**: the
PDF's anchor table had hardcoded column widths sized for exactly two columns.
Adding the third (`type`) column caused the "Note" column to overflow past
the page's right margin instead of wrapping -- the same category of bug as
the Step 9 cell-wrapping issue during original development, now recurring
because the fix at the time was still tied to a fixed column count. This was
fixed by extracting the width calculation into `compute_col_widths()`, which
sizes columns from however many a schema actually declares, and by adding a
permanent regression check in `scripts/selftest.py` that confirms table
columns fit the page width for two, three, four, and even a single-column
table -- not just the one case that broke.

## Section labels: "Practice recommendations" / "Unresolved questions"

The two `solvable_now` / `not_solved` fields were originally labelled "Solvable
now" and "Not solved" -- read as too casual for a scholarly format. Relabelled
to "Practice recommendations" and "Unresolved questions". The field *keys*
(`solvable_now`, `not_solved`) were deliberately left unchanged, since keys are
internal identifiers an article's front matter refers to, not displayed text --
only the schema's `label` for each changed. This meant the fix was two lines,
in one file (`_data/schema-practice-update.yml`), and updated every article's
displayed heading at once, on both the webpage and the PDF, with no article
file needing to change and no renderer code touched -- exactly the leverage
the schema design is meant to provide for a wording change like this.

## Repositioned as a single-author, non-peer-reviewed newsletter

The schema and content were adapted for a different model than originally
designed around: one author, no editorial board, no peer review, publishing
their own reading of the literature under their own name and dated.

What changed:

- **`is_trainee_led` and `supervisor` were removed from the schema entirely**,
  not just left unused -- that framing (supervised, reviewed-before-sign-off)
  does not fit a model with no reviewer at all. Removing them, rather than
  leaving them optional and unused, keeps the schema honest about what this
  actually is.
- **`declarations` changed from `visibility: editor` to `visibility: public`**,
  relabelled "Conflicts of interest". With no editor to disclose to privately,
  keeping it hidden from readers served no purpose; a reader can now see it
  directly on every entry.
- **The four substantive demo articles were standardised to one author**
  ("Example Author," consistently), since a single-author newsletter's mock
  content should actually look single-authored. The MMR article was
  substantively rewritten, not just stripped of two fields: its personal
  perspective was originally written around being supervised by someone else,
  which no longer describes anything real once that relationship is removed
  from the model. It was renamed `mmr-ihc.md`.
- **A new `/about/` page states the model in plain terms**: single-author, not
  peer-reviewed, corrections are dated and public, conflicts of interest are
  disclosed on every entry. This is a disclosure obligation, not a design
  choice, and it needed to be readable by a visitor, not just implied by the
  absence of review machinery.

Removing two schema fields required no renderer code changes -- confirmed by
searching the whole codebase for `is_trainee_led`/`supervisor` before removing
them, which turned up only the schema file and article content, nothing in
`scripts/` or `_includes/`. That is the schema-driven design doing its job:
a field that no longer belongs to the model can be deleted from exactly one
file, and every article and every renderer follows without being told to.

## Homepage rewrite

The homepage was a bare placeholder until now. It is rebuilt as an actual front
page:

- A one-line positioning statement under the title.
- Links to `/about/` and a new `/issues/` archive page (added alongside this,
  since without it "browse everything" had nowhere real to point).
- The 5 most recent articles **across every issue**, not just the latest
  issue's own list -- for a rolling newsletter, recency matters more than
  which batch an entry was filed under. Each shows its title, date, and its
  schema's nominated teaser field, using the exact same generic lookup
  `_layouts/issue.html` already used within one issue -- the homepage has no
  special-case knowledge of any schema either.

This was checked properly, not just "does it build": a scratch copy with four
articles given distinct dates confirmed the five shown are ordered newest
first, and that an article backdated outside the top-5 window is correctly
excluded, not just correctly ordered. Both checks are now permanent regression
tests in `scripts/selftest.py`.

## Phase A: closing the gaps (what changed after the first live deployment)

After the first live deployment (confirmed working on `es-chng.github.io`), two
gaps were closed:

- **Validation now blocks publishing**, not just reports a problem. This
  required switching Pages source to GitHub Actions (see "Deploying" above),
  because the previous branch-based deploy has no way to be stopped by a
  separate check -- it publishes regardless of what any other workflow says.
- **Every article now gets a PDF automatically**, built fresh at deploy time
  and published alongside the HTML, with a working "Download PDF" link on
  each article page. No file is ever committed back to the repository for this.

Two real bugs were found and fixed while building this:

- `mock-one-field.md` had been left deliberately incomplete since Step 3 (to
  demonstrate the validator's missing-field message). With validation now
  blocking every deploy, that same deliberate gap would have permanently
  blocked the site from ever updating again. Fixed by completing the article;
  the validator's missing-field message is now demonstrated only by the
  fixtures in `tests/broken-articles/` and `scripts/selftest.py`, which don't
  affect real deployment.
- The "Download PDF" button initially rendered with **invisible text** --
  dark green text on a dark green background. The cause was a CSS
  specificity bug: `.base-footer a { color: #0F5C4D; }` (one class + one
  element) is more specific than `.pdf-link { color: #fff; }` (one class
  alone), so the dark colour silently won regardless of source order. Fixed
  by writing the button's rule as `.base-footer a.pdf-link { ... }`, which
  is more specific than the rule it needed to override.

`scripts/selftest.py` was extended to check both the batch PDF step (one PDF
per article) and that each article's Download PDF link actually resolves to
a file that was built -- not just that the link exists.

## What was not tested

- **Nothing has been deployed to real GitHub Pages.** This has only been built and viewed
  locally (Jekyll build output, opened in a headless browser for screenshots).
- **No real submission or review workflow feeds into this.** Every article here was
  hand-written directly into `_articles/`. How an accepted, schema-shaped record gets
  produced by the editorial system (and whether its fields match what a schema expects)
  is a separate integration step, not covered here.
- **Only two schemas exist**, one fully fleshed out and one deliberately minimal. A
  schema with very different layout needs (e.g. a genuinely different visual arrangement,
  not just different fields) might expose gaps in the small toolbox of styles.
- **Figures/images are explicitly out of scope.** The `shape` vocabulary has a slot where
  an image shape could go later, but nothing about uploading, storing, or displaying an
  image has been built or tested.
- **PDF pagination with much longer content** (many anchors, long lists) hasn't been
  stress-tested — the fixed frame and table-wrapping fix were checked against one
  realistic article, not an intentionally long one.

## If you extend this

- **A new field shape** (e.g. "figure") needs handling added to *three* places, and no
  more: `_includes/schema-field.html` (webpage), `scripts/render_pdf.py` (PDF), and
  `scripts/validate_schema.py` (validation rule for that shape). The issue-listing page
  only needs a change if the new shape could plausibly be nominated as a teaser.
- **A new schema** needs none of the above — just a new `_data/schema-*.yml` file and
  articles that declare it, exactly like `schema-toy-example.yml` here.
- Before folding this into a real journal repository, decide how an article records
  *which version* of a schema it used (schemas will change over time; published articles
  shouldn't silently reinterpret under a newer version of their schema).
