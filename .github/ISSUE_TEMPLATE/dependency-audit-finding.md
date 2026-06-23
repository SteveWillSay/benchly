---
name: Dependency / CVE audit finding
about: A vulnerability or worthwhile update surfaced by the dependency audit
title: "[deps] "
labels: dependencies
---

<!-- Filed by the every-3-days dependency audit, or by hand. See docs/dependency-audit.md. -->

## Summary

<!-- One line: which package, and is this a CVE or just a stale pin? -->

## Details

| | |
|---|---|
| **Package** | |
| **Installed version** | |
| **Fixed / latest version** | |
| **Advisory** | <!-- CVE / GHSA id + link, if any --> |
| **Direct or transitive?** | |

## Relevance to Benchly

<!-- Does this affect a code path Benchly actually uses? (e.g. Pillow image parsing = yes;
     a server-only flaw in a transitive dep = probably not.) -->

## Recommended change

<!-- Exact requirements.txt edit, e.g. `pillow==12.2.0` -> `pillow==12.3.1` -->

## Checklist before closing

- [ ] `requirements.txt` pin bumped
- [ ] `.venv\Scripts\python -m pip_audit` clean
- [ ] `.venv\Scripts\python -c "import app"` still succeeds
- [ ] Shipped in a build (or noted for the next release)
