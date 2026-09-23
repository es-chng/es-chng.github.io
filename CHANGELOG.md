# Changelog

Everything here was built and checked in small steps, each one verified
before the next began. This file is the history of that process — what
changed, what broke, and how each fix was actually confirmed rather than
just asserted. See `README.md` for the current state only.

Entries are newest first.

## Optimization pass: workflow, process, rendering, frontend

A full review pass across four areas, each change actually verified (built,
rendered, and in most cases converted into a permanent regression check),
not just read and assumed correct.

**Two real bugs, fixed and verified:**
- The Zenodo-ledger DOI lookup in `_layouts/article.html` used Liquid
  dot-notation on a hyphenated key (`site.data.zenodo-ledger`), which Liquid
  cannot parse as a property access. Fixed with bracket syntax
  (`site.data['zenodo-ledger']`) and confirmed with a real ledger entry: the
  page now genuinely shows the deposited DOI instead of the front-matter
  placeholder, not just "the syntax looks right."
- The schema-lock system could lock a schema but never unlock one. An
  article moved from `published` back to `draft` left its schema permanently
  locked, because `--update-locks` only ever added or refreshed entries,
  never pruned one no longer backed by any published article. Fixed in
  `validate_schema.py`, and confirmed: mark an article published (locks),
  revert it to draft and re-run `--update-locks` (unlocks), then genuinely
  edit the previously-locked schema file and watch validation pass.

**A documented-but-never-built gap, closed:** the schema field vocabulary has
listed `shape: text | list | table | boolean | date` from the very first
schema file written, but no renderer ever had a branch for `date` — it would
have silently fallen through to "unrecognised shape." Implemented in the
webpage renderer, the PDF renderer, and the validator (which now also
rejects a genuinely malformed date, not just accepts anything with that
shape declared). `schema-toy-example`'s `reviewed_on` field is now a real,
permanent, working example of it, not a throwaway test fixture.

**Frontend: the whole site never had dark-mode support.** Every colour was a
fixed light-mode hex value in `:root`, with no
`@media (prefers-color-scheme: dark)` override anywhere — confirmed by
checking for hardcoded hex values outside the variable block (found exactly
one, the error-message colour, also fixed). Added a dark palette following
the same monochrome-plus-one-accent philosophy as the light mode, and
verified visually at mobile width in both modes, on both the homepage and an
article page.

**Workflow: the two GitHub Actions workflows had identical setup steps
duplicated between them** (Python, `pip install -r requirements.txt`, the
font package) — exactly the kind of duplication that let the font package
name drift out of sync between the two files in an earlier round. Extracted
into one composite action, `.github/actions/setup-toolchain`, that both
workflows now reference; a future fix like that one only needs to happen
once.

Every fix above that has a testable behaviour was turned into a permanent
`scripts/selftest.py` check (checks 11 through 15), not left as something
verified once by hand and then trusted forever. The suite ran 32 checks by
the end of this pass.

## Repositioned as a single-author, non-peer-reviewed newsletter

The schema and content were adapted for a different model than originally
designed around: one author, no editorial board, no peer review, publishing
their own reading of the literature under their own name and dated.

- **`is_trainee_led` and `supervisor` were removed from the schema
  entirely**, not just left unused — that framing (supervised,
  reviewed-before-sign-off) does not fit a model with no reviewer at all.
  Removing them, rather than leaving them optional and unused, keeps the
  schema honest about what this actually is.
- **`declarations` changed from `visibility: editor` to `visibility:
  public`**, relabelled "Conflicts of interest." With no editor to disclose
  to privately, keeping it hidden from readers served no purpose; a reader
  can now see it directly on every entry.
- **The four substantive demo articles were standardised to one author**
  ("Example Author," consistently), since a single-author newsletter's mock
  content should actually look single-authored. The MMR article was
  substantively rewritten, not just stripped of two fields: its personal
  perspective was originally written around being supervised by someone
  else, which no longer describes anything real once that relationship is
  removed from the model. It was renamed `mmr-ihc.md`.
- **A new `/about/` page states the model in plain terms**: single-author,
  not peer-reviewed, corrections are dated and public, conflicts of interest
  are disclosed on every entry.

Removing two schema fields required no renderer code changes — confirmed by
searching the whole codebase for `is_trainee_led`/`supervisor` before
removing them, which turned up only the schema file and article content,
nothing in `scripts/` or `_includes/`. That is the schema-driven design
doing its job: a field that no longer belongs to the model can be deleted
from exactly one file, and every article and every renderer follows without
being told to.

## Homepage rewrite

The homepage was a bare placeholder until this point. Rebuilt as an actual
front page:

- A one-line positioning statement under the title.
- Links to `/about/` and a new `/issues/` archive page (added alongside
  this, since without it "browse everything" had nowhere real to point).
- The 5 most recent articles **across every issue**, not just the latest
  issue's own list — for a rolling newsletter, recency matters more than
  which batch an entry was filed under. Each shows its title, date, and its
  schema's nominated teaser field, using the exact same generic lookup
  `_layouts/issue.html` already used within one issue.

Checked properly, not just "does it build": a scratch copy with four
articles given distinct dates confirmed the five shown are ordered newest
first, and that an article backdated outside the top-5 window is correctly
excluded, not just correctly ordered. Both checks became permanent
regression tests.

## Phase A: closing the gaps (after the first live deployment)

After the first live deployment (confirmed working on `es-chng.github.io`),
two gaps were closed:

- **Validation now blocks publishing**, not just reports a problem. This
  required switching Pages source to GitHub Actions, because the previous
  branch-based deploy has no way to be stopped by a separate check — it
  publishes regardless of what any other workflow says.
- **Every article now gets a PDF automatically**, built fresh at deploy time
  and published alongside the HTML, with a working "Download PDF" link on
  each article page. No file is ever committed back to the repository for
  this.

Two real bugs were found and fixed while building this:

- `mock-one-field.md` had been left deliberately incomplete since early in
  development, to demonstrate the validator's missing-field message. With
  validation now blocking every deploy, that same deliberate gap would have
  permanently blocked the site from ever updating again. Fixed by
  completing the article; the validator's missing-field message is now
  demonstrated only by the fixtures in `tests/broken-articles/`, which don't
  affect real deployment.
- The "Download PDF" button initially rendered with **invisible text** —
  dark green text on a dark green background. The cause was a CSS
  specificity bug: `.base-footer a { color: #0F5C4D; }` (one class + one
  element) is more specific than `.pdf-link { color: #fff; }` (one class
  alone), so the dark colour silently won regardless of source order. Fixed
  by writing the button's rule as `.base-footer a.pdf-link { ... }`.

## Writing register, and the anchor "type" column

The mock articles' prose was rewritten toward a more precise, attributive
academic register: naming study designs and sample sizes, giving effect
sizes with confidence intervals where the (illustrative) source states them,
distinguishing a defined convention from an established fact, and writing
the personal-perspective sections in a measured first-person voice rather
than casual advice.

One schema field was added to support this: every anchor now carries a
`type` (`guideline`, `RCT`, `cohort study`, `audit`, `expert consensus`,
etc.) alongside its citation and note, so a reader can weigh a claim without
parsing the citation string closely. Deliberately kept to a single
classification field — no evidence grading, no limitations column, no
scoring — since that fuller apparatus is the CAT-style machinery this format
intentionally avoids in favour of staying fast to write.

Adding the column required **no renderer code changes** — both
`_includes/schema-field.html` and `render_pdf.py` already read a table
field's columns generically from the schema. It did, correctly, require
every existing article's anchors to be updated: `validate_schema.py` caught
all five articles missing the new column on the first run after the schema
changed, before anything was rebuilt.

**A second table-rendering bug was found and fixed while doing this**: the
PDF's anchor table had hardcoded column widths sized for exactly two
columns. Adding the third (`type`) column caused the "Note" column to
overflow past the page's right margin instead of wrapping — the same
category of bug as an earlier cell-wrapping issue, now recurring because
that fix was still tied to a fixed column count. Fixed by extracting the
width calculation into `compute_col_widths()`, which sizes columns from
however many a schema actually declares, with a permanent regression check
confirming table columns fit the page width for two, three, four, and even
a single-column table — not just the one case that broke.

## Section labels: "Practice recommendations" / "Unresolved questions"

The two `solvable_now` / `not_solved` fields were originally labelled
"Solvable now" and "Not solved" — read as too casual for a scholarly format.
Relabelled to "Practice recommendations" and "Unresolved questions." The
field *keys* were deliberately left unchanged, since keys are internal
identifiers an article's front matter refers to, not displayed text — only
the schema's `label` for each changed. This meant the fix was two lines, in
one file, and updated every article's displayed heading at once, on both
outputs, with no article file needing to change and no renderer code
touched.

## Visual register: academic, not casual

The webpage and PDF were rebuilt toward a formal, print-journal register:
one serif type family throughout (no separate sans-serif for labels), a
near-monochrome palette (a single muted colour, used only for links), thin
horizontal rules in place of coloured boxes, small-caps-style section labels
instead of coloured badges, and the "personal perspective" field set as a
traditional italic block quotation rather than a highlighted callout.

Styling-only change — touched nothing about the schema model, the
field-rendering logic, or which fields exist. The generic "style" values a
schema can declare (`plain`, `boxed`, `opinion`, `badge`, `table`) are
unchanged in meaning; only how each one is drawn changed.

## Original build, in order

Every step below was built, then checked, before the next one started:

1. An empty site builds.
2. The ten base fields render alone, with the schema section left visibly
   empty.
3. The schema is written down as its own file, self-checked to have exactly
   one teaser field.
4. One field, then each remaining shape (list, table, boolean) and style
   (badge, boxed, opinion), added and checked one at a time.
5. A complete, realistic article (a HER2-ultralow example) renders correctly
   end to end.
6. Two more complete articles render correctly.
7. The issue-listing page correctly shows every article with its teaser,
   and correctly shows a plain fallback for an article with no schema at
   all.
8. Three deliberately broken articles were fed through the validator and
   the renderer. The validator caught all three cleanly. But the renderer,
   on its own, **silently** produced a broken-looking empty table row for
   the shape-mismatch case — a real bug, fixed so the renderer fails
   **loudly** instead (a visible, specific message) as a second line of
   defence behind validation.
9. A PDF renderer was built, deliberately reusing the same frame-then-schema
   logic as the webpage. Its first version had a second real bug: table
   cells didn't wrap, so long citation and note text overlapped illegibly.
   Fixed by wrapping each cell in its own paragraph rather than a plain
   string.
10. A second, genuinely different toy schema (different fields entirely)
    was written and given one mock article. It rendered correctly through
    the **exact same, unmodified** templates — the actual proof that the
    design is schema-agnostic, not just well-tuned to the one schema it was
    developed against.

`scripts/selftest.py` automates steps 8, 9, and 10's checks, so a future
template change can be re-verified in seconds rather than by repeating the
whole manual process by hand.
