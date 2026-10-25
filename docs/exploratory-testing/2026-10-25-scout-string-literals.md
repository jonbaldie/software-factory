# Exploratory pass: scout and JavaScript string literals (2026-10-25)

A focused live check of the fix for [#78](https://github.com/jonbaldie/software-factory/issues/78): the scout must ignore `TODO(factory):` markers inside JavaScript strings and still file real comments next to them.

## Setup and evidence

- Factory: the #78 candidate `factory-scout.yml`, copied from this branch's `template/` onto sandbox branch `scout-78-check` at [`2816251`](https://github.com/jonbaldie/software-factory-sandbox/commit/28162517230a2c28dbf3d4db790400a1c065c8f5). The scout ran on that branch through `workflow_dispatch --ref`, so the sandbox's `main` and settings were not changed.
- Fixtures: [a literal-only test](2026-10-25-evidence/fixtures/scout78-literal.test.js) with the issue's string assignment, its `includes("TODO(factory):")` assertion, and single-quoted, escaped-quote and template-literal markers. [A mixed source line](2026-10-25-evidence/fixtures/scout78-mixed.js) puts a marker in a string containing an apostrophe and `//`, then a real `//` comment after it. Locally, `npm test` passed 130/130, including the fixture test.
- Sandbox state: no open PRs and no running jobs before dispatch.

## Observations

- [Scout run 40173301736](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/40173301736) succeeded. [Log](2026-10-25-evidence/04-scout.log).
- It filed exactly one issue, #136 `Scout check 78, real comment after a string (sandbox test, close me)`, linking `src/scout78-mixed.js#L1`. The title has no string text or trailing code. [Issue snapshot](2026-10-25-evidence/01-issue-136.json).
- None of the six string markers became an issue. Only #136 was created after dispatch. [Issues since dispatch](2026-10-25-evidence/02-issues-since-dispatch.json).
- The scout dispatched exactly one triage run, [40173310395](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/40173310395), for #136. It succeeded and closed #136 as `wontfix`. [Runs since dispatch](2026-10-25-evidence/03-runs.json).

Before the fix, the [2026-10-19 pass](2026-10-19-install-scout-pause.md) recorded the same literal fixtures filing tickets such as `Render a documentation preview 20261019";` and `"));`.

## Limitations

- The scout reads each line on its own. A template literal opened on an earlier line isn't recognised, so a marker on a later line of it is still filed.
- Only `.js`, `.jsx`, `.ts`, `.tsx` and their `c`/`m` variants are checked for strings. Markers in strings in other languages are filed as before.

## Cleanup

#136 was closed by triage. Sandbox branch `scout-78-check` was deleted and the local clone removed. All runs finished. No sandbox settings changed and no Docker resources were created.
