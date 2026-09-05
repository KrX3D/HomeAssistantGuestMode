---
name: steward
description: Repo-specific conventions for driving PRs on this repository to green.
---

# Guest Mode integration — PR steward notes

This repository is a Home Assistant custom integration (HACS), not an
application with its own test suite. Treat these as the local equivalent of
"the checks a contributor runs before pushing":

- `ruff check custom_components` — lint. Keep the default rule set; do not
  add suppressions to get around a real finding.
- `python -m compileall -q custom_components` — syntax check for every
  module.
- `python -m json.tool <file>` — validate any `.json` file you touch
  (`manifest.json`, `hacs.json`, `strings.json`, `translations/*.json`).
- CI also runs `home-assistant/actions/hassfest` and `hacs/action` — these
  validate `manifest.json` / `hacs.json` against the current Home Assistant
  and HACS schemas. A failure there usually means a manifest field is
  missing, misnamed, or the wrong type; fix the manifest rather than the
  workflow.

There is intentionally no `ruff format` check: the existing code aligns `=`
signs and dict values by hand in several places, and reformatting the whole
tree is not something to do as a side effect of an unrelated PR. Don't add
a formatter gate or reformat existing files unless the user explicitly asks
for it.

Every `strings.json` step whose flow can show a form error (e.g.
`errors[...] = "some_key"`) needs a matching `"error": {"some_key": "..."}`
block in `strings.json` **and** in every file under `translations/`. A
missing translation surfaces as a raw, untranslated key in the config flow
UI — treat it as a real bug, not a nit.

There is no automated Home Assistant test harness in this repo (no
`pytest-homeassistant-custom-component` setup). Don't add one as a side
effect of a PR that isn't about testing; if a PR would benefit from a
regression test and none of the above tooling can express it, say so in
the PR description rather than inventing a test framework on the spot.
