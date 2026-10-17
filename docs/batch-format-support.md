# K-CD batch format observations, 17 October 2026

The ten-CD trial exposed three independent format variants. This change preserves
original bytes and raw fields while extending qualified projections:

- Nonempty Norwegian `TitelNO` field variants (case-insensitive field selection)
  supply the title before the common `Titel`. Foreign-language fields are not
  fallbacks. Conflicting Norwegian variants fail rather than choosing silently.
- `Tools/Tools.dtx` resolves Folder relative to its metadata directory. Having both
  root and nested Tools.dtx remains ambiguous and is rejected. Raw Folder is unchanged.
- Unindented continuation in a bounded set of prose fields is indented only in the
  INI parsing view. Repeated lines and newline boundaries remain in the value.
  Original metadata bytes, their hash, and continuation line numbers are retained.
  Garbage after a non-prose field still fails. Catalog independently validates this
  versioned parsing view against the preserved source.

Workshop Data*.dtx documents are not another program catalogue. The qualified
Tools path pattern and lesson section structure identify lesson documents. Their
full bytes, sections, language hint and same-folder associations are retained in
supplemental metadata with role `workshop_lesson_document` and publication status
`preserved_only`. No new program identity, runnable target or published lesson is
inferred. Unknown section types still block coverage; a Data filename containing
an unknown program menu remains unprocessed. Complete-disc coverage remains false.

Real-media trial: all 73 missing-title tasks on seven 2008/2009 discs are resolved
from actual Norwegian fields, with 289 source posts/289 RTFs. No previously nonempty
title changed on these discs. 8/2002 and 16/2002 produce 67 and 71 posts. Lesson
preservation is distinct from providing an interactive course player.

4/2002 now parses its multiline Tools.dtx verbatim but remains blocked on the
previously hidden K.DTX section `Flytter`: a Danish Pixia 2.4 row beside the ordinary
Pixia row. Its menu role is unqualified. Static inspection encountered unsupported
compressed resources in the Director archive. Do not discard it, count it as a
second reachable program, or suppress the coverage gate to obtain a green run.

Validation: 213 unit tests, 153 passed and 60 private-media/optional tests skipped.
Original sources were separately exercised through the full coordinator. Synthetic
checks cover field conflicts, byte preservation, duplicate prose, non-prose errors,
nested path escapes/ambiguity and unknown lesson sections. Full deployment and
cross-repository acceptance evidence belongs in the project batch report.
