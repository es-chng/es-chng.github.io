# Schema Lab — schema-driven publishing for a single-author microjournal

## What this is

Schema Lab is a standalone, **schema-driven publishing engine** for a single-author,  
non-peer-reviewed microjournal (or "practice-update" newsletter). It is a prototype  
and a reusable building block — not a real journal, and not a CMS.

It exists to prove one design idea: an article can be defined as a *schema* — a  
named, ordered list of fields, each with a shape, a display style, and a  
visibility — and one small set of templates can turn **any** schema, and any  
article using it, into a correct webpage, a matching PDF, and a correct entry in  
an issue's table of contents, **without the templates ever hard-coding a field's  
name**.

Built with **Jekyll** (HTML), **ReportLab** (PDF), validated and deployed via  
**GitHub Actions**, with optional **Zenodo** integration for per-article DOIs.  
Two demo schemas ship: `schema-practice-update` (fully built out) and  
`schema-toy-example` (minimal, proving the templates are schema-agnostic).

> Every file in `_articles/` and `_data/` is **mock content** for testing only.  
> The authors, DOIs, and citations are invented. `schema-toy-example.yml` and  
> its one article exist solely to prove a second, unrelated schema renders  
> through the same templates — delete both before real use.

## What it does

Given Markdown articles with YAML front matter, Schema Lab produces:

- **HTML article pages** — academic serif register, near-monochrome palette,  
  responsive, with a "Download PDF" link and DOI in the footer.
- **PDFs** — one per article, the same frame-then-schema structure as the  
  webpage, with the DOI embedded in the footer.
- **Issue listing pages** — a table of contents showing each article's  
  nominated teaser field.
- A **homepage** — the 5 most recent entries across all issues, newest first.
- An **/about/** page and an **/issues/** archive.

It also enforces:

- **Pre-build validation** — every article is checked against its declared  
  schema (required fields, shape match, teaser length, schema-version pinning,  
  schema content-lock). Any failure **blocks deployment**.
- **Published = immutable** — published articles pin their schema version;  
  schemas used by published articles are content-hashed and locked; editing a  
  locked schema fails validation (format evolution = a new schema file).
- **Incremental PDF builds** — a manifest-based cache rebuilds only articles  
  whose own file or schema changed; deleted articles' stale PDFs are pruned;  
  the cache self-heals on a miss.

Optional Zenodo DOI minting (per article): reserve DOI → embed in PDF → upload →  
publish → record in a ledger. No write-back into article `.md` files, so no  
workflow re-trigger loops.

## The two-layer schema model (in short)

**Layer 1 — the base (fixed, 10 fields, the same for every article):**  
`title`, `authors[]`, `corresponding_email`, `volume`, `issue`, `order`,  
`pages`, `published_date`, `doi`, `licence`. The article/PDF header and footer  
read only these and never consult any schema.

**Layer 2 — the schema (fully open).** A schema is a list of fields; each  
declares:

| Property     | Meaning                                                        |
| ------------ | -------------------------------------------------------------- |
| `key`        | the front-matter key                                           |
| `label`      | the reader-facing heading                                      |
| `shape`      | `text` | `list` | `table` | `boolean`                          |
| `style`      | `plain` | `boxed` | `opinion` | `badge` | `table`              |
| `visibility` | `public` | `reviewer` | `editor` | `private`                   |
| `teaser`     | `true` on exactly one field (shown on issue/homepage listings) |
| `max_chars`  | hard cap, enforced on teaser fields                            |
| `optional`   | `true` where a field may be empty                              |

- A **new schema** needs **no code changes** — just a new `_data/schema-*.yml`  
  file plus articles that declare it.
- A **new field shape** needs handling added to exactly three places:  
  `_includes/schema-field.html` (webpage), `scripts/render_pdf.py` (PDF), and  
  `scripts/validate_schema.py` (validation rule).

## Repository layout

| Path                             | What it is                                                                            |
| -------------------------------- | ------------------------------------------------------------------------------------- |
| `_data/schema-*.yml`             | Schema definitions (one file per schema).                                             |
| `_articles/*.md`                 | Articles: base fields + whatever the declared schema requires.                        |
| `_issues/*.md`                   | Issue identity (volume/issue/date/theme), not contents.                               |
| `_layouts/article.html`          | Fixed base frame, then schema-driven fields via `schema-slot.html`.                   |
| `_layouts/issue.html`            | Lists an issue's articles with each one's teaser.                                     |
| `_includes/schema-slot.html`     | Walks a schema's fields in order (webpage).                                           |
| `_includes/schema-field.html`    | Renders one field generically by shape/style — no field names.                        |
| `scripts/validate_schema.py`     | Pre-build validator (required fields, shapes, teaser length, schema pin + lock).      |
| `scripts/render_pdf.py`          | Builds one article's PDF, walking the same schema as the webpage.                     |
| `scripts/render_all_pdfs.py`     | Batch-builds every article's PDF (local use).                                         |
| `scripts/render_changed_pdfs.py` | Incremental PDF build with a persistent manifest cache (used in CI).                  |
| `scripts/zenodo_articles.py`     | Zenodo DOI → embed in PDF → upload → publish → ledger. `--dry-run` supported.         |
| `scripts/selftest.py`            | 22-check self-test reproducing every build checkpoint. Run after any template change. |
| `tests/broken-articles/*.md`     | Three deliberately malformed fixtures for the validator/selftest.                     |
| `_data/schema-locks.yml`         | Content hashes of schemas used by published articles (immutability).                  |
| `_data/zenodo-ledger.yml`        | Article → DOI map written by the Zenodo deposit workflow.                             |
| `CITATION.cff`, `.zenodo.json`   | Package-level citation/Zenodo metadata (for the package DOI).                         |
| `requirements.txt`, `Gemfile`    | Python and Ruby dependencies.                                                         |

## How to deploy (GitHub Pages, automated)

The repository builds, validates, and publishes itself via  
`.github/workflows/pages.yml` on every push to `main`.

### One-time setup

1. **Push to a GitHub repository.** If it is a user/org root site, leave  
   `baseurl` empty in `_config.yml`; if it is a project site, set `baseurl` to  
   the subpath.
2. **Switch the Pages source.** Settings → Pages → change **Source** from  
   "Deploy from a branch" to **GitHub Actions**. Until you do this, GitHub  
   serves the old branch-based deploy, which bypasses validation and PDF  
   building — the new workflow will look green in the Actions tab without  
   actually serving the site.
3. **Fonts (no action needed).** The PDF renderer prefers the DejaVu serif  
   family (matching the webpage) but now **falls back to ReportLab's built-in  
   Times/Helvetica faces if any DejaVu face is missing** — so a PDF build  
   never crashes on a font, even on a bare system. The workflow installs the  
   full `fonts-dejavu` set (the meta-package that also pulls  
   `fonts-dejavu-extra`, which contains the italic serif), so the intended  
   typeface is used on GitHub-hosted runners. If you run locally and lack the  
   italic, you still get a valid PDF in Times. (Earlier versions installed only  
   `fonts-dejavu-core`, which omits `DejaVuSerif-Italic.ttf`; the code-level  
   fallback now makes this safe regardless of which package is present.)
4. **Build files are excluded from the published site (no action needed).**  
   `_config.yml` excludes `tests/`, `scripts/`, `requirements.txt`,  
   `CITATION.cff`, `.zenodo.json`, `Gemfile`, and `Gemfile.lock`, so only the  
   journal content is served. (Earlier versions excluded only `README.md`,  
   which published the deliberately-broken test articles as reachable HTML.)

### What every push to `main` does

1. Runs `scripts/validate_schema.py`. **If any article fails, the job stops  
   here** — the site keeps serving whatever was last published successfully.  
   This is a hard gate, not a warning.
2. Builds the Jekyll site.
3. Restores the previous run's PDF cache (GitHub Actions cache, keyed by run  
   ID, restored via a shared prefix), then runs `render_changed_pdfs.py`,  
   rebuilding only articles that are new or whose own file or schema changed.  
   Every current article's PDF ends up at `/files/<slug>.pdf`.
4. Publishes the result via `actions/deploy-pages`. Nothing is committed back  
   to the repository (PDFs live in the Actions cache between runs), which  
   deliberately avoids a workflow-triggers-itself loop.

### Optional: per-article Zenodo DOIs

For DOIs embedded **inside** the published PDF (the record must cite a real  
DOI, so the order matters: reserve → render → upload → publish):

1. Create a Zenodo personal access token with `deposit:write` and  
   `deposit:actions` scopes. Start on  
   [sandbox.zenodo.org](https://sandbox.zenodo.org).
2. Add the repository secret `ZENODO_TOKEN`.
3. Optional variables: `SITE_URL` (article page link on the Zenodo record);  
   `ZENODO_LIVE=1` only when targeting production `zenodo.org`.

With the token set, the build step reserves a DOI → renders the PDF with that  
DOI in the footer → uploads and publishes the deposition → records the DOI in  
`_data/zenodo-ledger.yml` (committed with `[skip ci]`). Without the token,  
PDFs still build with placeholder front-matter DOIs only. The HTML layout  
prefers a real ledger DOI over a placeholder front-matter DOI.

The separate `.github/workflows/zenodo-articles.yml` can deposit on demand  
(`workflow_dispatch`, with optional `live` and `force` inputs) and is also  
wired to run after a successful Pages build.

### Package DOI (the tool itself)

Use Zenodo's native GitHub integration (no Action required):

1. Make the repository public.
2. On [zenodo.org](https://zenodo.org), link your GitHub account and toggle  
   this repo **On**.
3. Create a GitHub Release (e.g. `v0.1.0`).
4. Zenodo archives the release and mints a DOI automatically.

`CITATION.cff` and `.zenodo.json` are already present. After the first  
release, paste the concept DOI into `CITATION.cff` and add a badge here.

## Running locally

```bash
bundle install                                          # once — installs Jekyll
pip install -r requirements.txt                         # once — pyyaml, reportlab, requests
python scripts/validate_schema.py                      # check content before building
bundle exec jekyll serve                                # preview at http://localhost:4000
python scripts/render_pdf.py _articles/her2-ultralow.md out.pdf   # one PDF
python scripts/render_all_pdfs.py /tmp/pdfs             # all PDFs
python scripts/selftest.py                              # 22-check self-test (requires jekyll)
python scripts/zenodo_articles.py /tmp/pdfs --dry-run   # DOI dry-run (embeds a fake DOI)
```

> The PDF renderer prefers the DejaVu serif family and **falls back to  
> ReportLab's built-in Times/Helvetica if any face is missing**, so PDFs  
> render even with no DejaVu installed. For the intended serif typeface,  
> install `fonts-dejavu` on Ubuntu (`sudo apt-get install fonts-dejavu`) or  
> the DejaVu family via Homebrew on macOS.

## Published = immutable

Once an article is published, neither the article nor the schema it used may  
change in place.

- A published article pins `schema_version: N` matching its schema file's  
  top-level `version`. The validator fails if the pin does not match.
- Schemas used by published articles are content-locked in  
  `_data/schema-locks.yml`. Editing a locked schema fails validation with a  
  message naming the lock holders and the remedy: create a **new** schema  
  file (e.g. `schema-practice-update-v2.yml` with `version: 2`). Old  
  published articles stay pinned to v1 and its locked content.
- An article is treated as published if any of: `status: published`, a  
  non-placeholder `doi`, or an entry in the Zenodo ledger.

Refresh/create locks after marking articles published:

```bash
python scripts/validate_schema.py --update-locks
```

## What was tested

`scripts/selftest.py` reproduces every build checkpoint in 22 checks:

- The validator passes on all real articles and rejects each broken fixture  
  with a specific, relevant message.
- The site builds even with broken articles present; a shape-mismatch fails  
  **loudly** (a visible message), not silently; a known-good article stays  
  clean alongside broken siblings.
- Both schemas build together cleanly (cross-schema isolation).
- The batch PDF step produces one PDF per article, and each article's  
  "Download PDF" link resolves to a file that was actually built.
- The homepage shows exactly 5 entries, newest first, and correctly excludes  
  an article beyond the cutoff.
- Table column widths fit the page for 1, 2, 3, and 4 columns (regression  
  check for a past overflow bug).
- The incremental PDF cache: an empty cache builds everything; an unchanged  
  run reuses everything; a single changed article rebuilds only itself; a  
  changed schema rebuilds every article using it (and no article that does  
  not); a deleted article's cached PDF and manifest entry are both removed.

All 22 checks also pass with **zero font files present** (the renderer's  
built-in Times/Helvetica fallback), so a missing font can never block a build.

## What is explicitly out of scope

- **Figures/images** — the `shape` vocabulary has a slot for an image shape,  
  but no upload, storage, or display pipeline has been built or tested.
- **PDF pagination with very long content** — the fixed frame and  
  table-wrapping were checked against realistic articles, not intentionally  
  long ones.
- **A real submission/review workflow** — every article here was hand-written  
  into `_articles/`. How an accepted, schema-shaped record is produced by an  
  external editorial system is a separate integration step.

## Notes on fonts and published files

1. **Font handling is self-healing.** `scripts/render_pdf.py` searches the  
   standard font directories for the DejaVu faces and registers whichever it  
   finds; any missing role falls back to ReportLab's built-in standard fonts  
   (Times-Roman / Times-Bold / Times-Italic for the serif body, Helvetica for  
   sans). The gap that motivated this — `DejaVuSerif-Italic.ttf` being absent  
   from `fonts-dejavu-core` — is therefore no longer fatal: a clean system  
   with only the core package, or no DejaVu at all, still produces valid PDFs  
   (in Times rather than DejaVu). Verified: 22/22 self-test checks pass with  
   zero font files present, and a Zenodo `--dry-run` embeds its DRYRUN DOI in  
   Times. The CI workflows install the full `fonts-dejavu` set so the  
   intended typeface is used when available.
2. **Build files are excluded from the published site.** `_config.yml`  
   excludes `tests/`, `scripts/`, `requirements.txt`, `CITATION.cff`,  
   `.zenodo.json`, `Gemfile`, and `Gemfile.lock`, so the three  
   deliberately-broken test articles and the Python scripts are not served at  
   the live URL.

## If you extend this

- A **new schema** needs no code changes — just a new `_data/schema-*.yml`  
  file and articles that declare it.
- A **new field shape** needs handling added to exactly three places, and no  
  more: `_includes/schema-field.html`, `scripts/render_pdf.py`, and  
  `scripts/validate_schema.py`. The issue-listing page only needs a change if  
  the new shape could plausibly be nominated as a teaser.
- Before folding this into a real journal repository, decide how an article  
  records *which version* of a schema it used — the version-pin +  
  content-lock mechanism here is one working answer.
