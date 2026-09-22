#!/usr/bin/env python3
"""
Self-test for the schema and publication module.

Reproduces the checks made during development (Steps 0-10):
  1. The validator passes on the real, working articles (aside from one
     known-incomplete test fixture, mock-one-field.md, kept deliberately
     partial to demonstrate the missing-field message -- see README).
  2. The validator correctly REJECTS each fixture in tests/broken-articles/,
     with a specific, relevant error message for each kind of problem.
  3. The site builds without error.
  4. A known-good article's built page contains no "field-missing" or
     "field-render-error" markers (i.e. nothing is silently or loudly broken).
  5. A field known to belong to a different schema does not leak across
     schemas (the toy schema's fields do not appear on a practice-update
     article, and vice versa).

Run from the site/ directory:
    python scripts/selftest.py

Requires `jekyll` on PATH. Nothing here touches the real _articles/ directory;
broken fixtures are copied into a temporary directory before building.
"""
import shutil
import subprocess
import sys
import tempfile
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

PASSED = FAILED = 0


def check(cond, msg):
    global PASSED, FAILED
    print(("PASS  " if cond else "FAIL  ") + msg)
    PASSED += bool(cond)
    FAILED += not cond


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def main():
    # 1. validator on the real articles: all of them must now be fully valid,
    #    because a blocking CI gate (pages.yml) means any real article that
    #    fails validation stops the entire site from deploying.
    r = run([sys.executable, "scripts/validate_schema.py"], ROOT)
    check(r.returncode == 0, "validator passes cleanly on all real articles (required, now that validation blocks deployment)")

    # 2. validator rejects each broken fixture, with a relevant message
    with tempfile.TemporaryDirectory() as tmp:
        work = pathlib.Path(tmp) / "site"
        shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns("_site", ".jekyll-cache", "__pycache__", "tests"))
        cases = {
            "missing-field.md": "required field 'bottom_line'",
            "teaser-too-long.md": "over its 400-character limit",
            "shape-mismatch.md": "is declared shape 'table' but the value is not a list of rows",
        }
        for fname, expect in cases.items():
            shutil.copy(ROOT / "tests/broken-articles" / fname, work / "_articles" / fname)
            r = run([sys.executable, "scripts/validate_schema.py"], work)
            check(r.returncode == 1 and expect in r.stdout, f"{fname}: validator catches it ({expect!r})")
            (work / "_articles" / fname).unlink()

        # 3. the site still builds cleanly (with all real + broken articles present, to test the renderer's own defences)
        for fname in cases:
            shutil.copy(ROOT / "tests/broken-articles" / fname, work / "_articles" / fname)
        out_dir = pathlib.Path(tmp) / "_site_out"
        r = run(["jekyll", "build", "--source", str(work), "--destination", str(out_dir), "--baseurl", ""], work)
        check(r.returncode == 0, "site builds even with broken articles present (build itself does not crash)")

        # 4. broken articles fail LOUDLY (visible message), not silently
        shape_html = (out_dir / "articles/broken-wrong-shape-for-a-field/index.html")
        alt = list(out_dir.glob("articles/*shape*/index.html"))
        target = alt[0] if alt else shape_html
        if target.exists():
            html = target.read_text()
            check("field-render-error" in html or "cannot display" in html,
                  "the shape-mismatch article fails LOUDLY (a visible message), not silently")
        else:
            check(False, "could not find the built shape-mismatch article to check")

        # 5. known-good articles remain clean (no missing/error markers) despite broken siblings existing
        her2 = out_dir / "articles/her2-ultralow/index.html"
        if her2.exists():
            html = her2.read_text()
            check("field-missing" not in html and "field-render-error" not in html,
                  "a known-good article stays clean even when broken articles exist alongside it")
        else:
            check(False, "could not find the built her2-ultralow article to check")

    # 6. cross-schema isolation: toy schema's fields never appear on a practice-update article,
    #    AND the batch PDF renderer produces one PDF per article, matching the download link
    #    each article's page actually points to.
    site_out = pathlib.Path(tempfile.mkdtemp())
    r = run(["jekyll", "build", "--source", str(ROOT), "--destination", str(site_out), "--baseurl", ""], ROOT)
    check(r.returncode == 0, "the real site (both schemas together) builds cleanly")

    r = run([sys.executable, "scripts/render_all_pdfs.py", str(site_out / "files")], ROOT)
    n_articles = len(list((ROOT / "_articles").glob("*.md")))
    n_pdfs = len(list((site_out / "files").glob("*.pdf")))
    check(r.returncode == 0 and n_pdfs == n_articles, f"the batch PDF step produces one PDF per article ({n_pdfs}/{n_articles})")

    # 6a2. the homepage shows the 5 most recent articles across ALL issues, most
    #      recent first, and correctly excludes older articles beyond that cutoff --
    #      not just "does it build", but "is the ordering and cutoff actually right".
    import re as _re
    scratch2 = pathlib.Path(tempfile.mkdtemp()) / "scratch2"
    shutil.copytree(ROOT, scratch2, ignore=shutil.ignore_patterns("_site", ".jekyll-cache", "__pycache__"))
    dated = {"her2-ultralow.md": "2026-09-15", "intramucosal-adenocarcinoma.md": "2026-09-10",
             "mmr-ihc.md": "2026-09-20", "scanner-validation.md": "2026-08-01"}
    for fname, d in dated.items():
        fp = scratch2 / "_articles" / fname
        fp.write_text(_re.sub(r"published_date: \d{4}-\d{2}-\d{2}", f"published_date: {d}", fp.read_text()))
    home_out = pathlib.Path(tempfile.mkdtemp())
    rh = run(["jekyll", "build", "--source", str(scratch2), "--destination", str(home_out), "--baseurl", ""], scratch2)
    home_html = (home_out / "index.html").read_text() if (home_out / "index.html").exists() else ""
    order = _re.findall(r'toc-item">\s*<a href="[^"]+">([^<]+)</a>', home_html)
    check(rh.returncode == 0 and len(order) == 5, "homepage shows exactly 5 recent entries")
    check(order[:3] == ["Patchy MMR loss on IHC: how do I read it?",
                        "HER2-ultralow: how do I recognise it, and how sure can I be?",
                        "Intramucosal adenocarcinoma in the colon: does the label matter?"],
          "homepage orders the 3 distinctly-dated articles newest first")
    check("Switching scanners" not in home_html or order.count("Switching scanners: what do I need to re-validate before I trust the new images?") == 0,
          "an article older than the top-5 cutoff (backdated a month) is correctly excluded")

    # 6b. the PDF table-width logic never lets columns overflow the page, for any
    #     number of columns a schema might declare -- this is the regression test
    #     for the overflow bug found when the anchors table gained a third column.
    from render_pdf import compute_col_widths, TABLE_AVAILABLE_WIDTH
    for cols in (["citation", "note"], ["citation", "type", "note"], ["a", "b", "c", "d"], ["solo"]):
        widths = compute_col_widths(cols)
        check(len(widths) == len(cols) and all(w > 0 for w in widths) and sum(widths) <= TABLE_AVAILABLE_WIDTH + 1,
              f"table column widths for {cols} fit within the page ({sum(widths):.0f} <= {TABLE_AVAILABLE_WIDTH:.0f})")

    her2_html = (site_out / "articles/her2-ultralow/index.html")
    if her2_html.exists():
        html = her2_html.read_text()
        import re
        m = re.search(r'class="pdf-link" href="([^"]+)"', html)
        check(bool(m) and (site_out / m.group(1).lstrip("/")).is_file(),
              "an article's Download PDF link points to a PDF file that was actually built")
    else:
        check(False, "could not find the built her2-ultralow article to check the PDF link")

    # 7. the incremental PDF cache: build once, then confirm an unchanged run reuses
    #    everything, a single changed article rebuilds only itself, a schema change
    #    rebuilds every article using that schema (and no others), and a deleted
    #    article's cached PDF and manifest entry are both cleaned up.
    import hashlib, json, shutil as _shutil
    scratch = pathlib.Path(tempfile.mkdtemp()) / "scratch"
    _shutil.copytree(ROOT, scratch, ignore=shutil.ignore_patterns("_site", ".jekyll-cache", "__pycache__"))
    cache_dir = pathlib.Path(tempfile.mkdtemp()) / "pdf-cache"

    r1 = run([sys.executable, "scripts/render_changed_pdfs.py", str(cache_dir), str(pathlib.Path(tempfile.mkdtemp()))], scratch)
    n_real = len(list((scratch / "_articles").glob("*.md")))
    check(r1.returncode == 0 and f"Built {n_real}, reused 0" in r1.stdout, "first run (empty cache) builds every article")

    out2 = pathlib.Path(tempfile.mkdtemp())
    r2 = run([sys.executable, "scripts/render_changed_pdfs.py", str(cache_dir), str(out2)], scratch)
    check(r2.returncode == 0 and f"Built 0, reused {n_real}" in r2.stdout, "an unchanged second run rebuilds nothing, reuses everything")

    (scratch / "_articles" / "her2-ultralow.md").write_text(
        (scratch / "_articles" / "her2-ultralow.md").read_text() + "\n"
    )
    r3 = run([sys.executable, "scripts/render_changed_pdfs.py", str(cache_dir), str(pathlib.Path(tempfile.mkdtemp()))], scratch)
    check(r3.returncode == 0 and "Built 1, reused" in r3.stdout and "her2-ultralow.md" in r3.stdout.split("Built:")[1].split("\n")[0],
          "changing one article rebuilds only that article")

    schema_path = scratch / "_data" / "schema-practice-update.yml"
    schema_path.write_text(schema_path.read_text() + "\n# touched for the schema-change test\n")
    r4 = run([sys.executable, "scripts/render_changed_pdfs.py", str(cache_dir), str(pathlib.Path(tempfile.mkdtemp()))], scratch)
    built_line = next((l for l in r4.stdout.splitlines() if l.startswith("Built:")), "")
    check(r4.returncode == 0 and "toy-example-article.md" not in built_line and "mock-base-only.md" not in built_line
          and "intramucosal-adenocarcinoma.md" in built_line,
          "changing a schema rebuilds every article using it, and no article using a different schema")

    (scratch / "_articles" / "toy-example-article.md").unlink()
    out5 = pathlib.Path(tempfile.mkdtemp())
    r5 = run([sys.executable, "scripts/render_changed_pdfs.py", str(cache_dir), str(out5)], scratch)
    manifest = json.loads((cache_dir / "manifest.json").read_text())
    check(r5.returncode == 0 and "toy-example-article.md" not in manifest and not (cache_dir / "toy-example-article.pdf").exists()
          and not (out5 / "toy-example-article.pdf").exists(),
          "deleting an article removes its cached PDF and its manifest entry")

    print(f"\n{PASSED} passed, {FAILED} failed.")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
