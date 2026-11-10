# Webkit-GN optimisation audit (0.25)

The active GTK4/WebKit/ProseMirror editor was audited without changing its feature
set. The abandoned WordCraft implementation was moved to the local sibling
`/workspace/gnome-wordprocessor-legacy-wordcraft` before cleanup; it is not part of
this repository. A complete pre-optimisation editor snapshot is also retained
locally outside this repository.

## Changes

- Minify the shipped JavaScript bundle, keeping readable sources and dependency
  licences. Bundle size: **620,082 → 288,965 bytes (53.4% smaller)**. Gzipped:
  **140,665 → 90,423 bytes (35.7% smaller)**.
- Cache normalized style maps by immutable ProseMirror attribute identity, rather
  than rebuilding them on cursor/formatting notifications.
- Cache dirty comparisons until the document or saved snapshot actually changes.
  Undo and asynchronous-save semantics remain covered by regression tests.
- Reuse unchanged search results and decorations. Searches/replacements pass their
  already-computed results to the search plugin rather than scanning twice.
- Skip GTK toolbar resynchronisation when its formatting, styles and relevant
  selection state are unchanged. Undo availability, search, outline and status
  still update independently.
- Prevent an outline toggle from issuing two identical asynchronous requests.
- Share one immutable text/highlight palette and generate its swatch CSS once.
- Remove unused imports, a redundant handle array and image-load listener leaks.
- Remove 20 bundled SVGs superseded by themed icons; preserve the four live
  fallbacks (subscript, superscript, page break and line spacing).
- Remove unused Rust environment setup from the active launcher and replace
  accumulated obsolete README notes with current run/build/test documentation.
- Add CI for editor/Python tests and deterministic bundle generation, plus a
  native-test runner that retains per-test logs in ignored `.runtime/native/`.

## Reproducible synthetic benchmark

Run `npm run benchmark --prefix webkit`. This measures synchronous editor work
under Node/JSDOM, **not native typing latency or a promise about every document**.
The fixture contains 800 paragraphs, 100 custom styles, a dirty edit near the
end and thousands of search hits. Each operation is warmed up. The table gives
medians of three before/after paired runs on the same cloud machine:

| Operation | Iterations | Before | After |
|---|---:|---:|---:|
| Dirty-status checks | 2,000 | 12.14 ms | 0.47 ms |
| Formatting notifications | 150 | 74.66 ms | 41.85 ms |
| Formatting with active search | 150 | 1,249.46 ms | 786.99 ms |
| Repeated identical Find | 15 | 56.98 ms | 1.68 ms |

Timings vary with load and document structure. Changed searches still scan the
document, and layout remains WebKit's responsibility. Print preparation still
uses its existing measured print-only layout; this audit did not replace it.

Validation: all 30 editor tests, 10 Python tests and 32 native scenarios passed (31 existing scenarios plus branding). Two older visual assertions were updated to the already-shipped eased blur length and GTK context-menu font metrics; they passed on rerun. The production bundle is the one exercised by the native suite.
