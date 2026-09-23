# Original DTX descriptions stored as RTF

When a DTX entry has no nonblank `raw.Global`, ingest observes its explicit
`description_rtf` file. The file must still match the inventory SHA-256 and size.
`evidence.description_rtf` retains exact base64 bytes, file identity, method
`rtf-ansi-text-1`, and a derived plain-text view. Existing Global wording always
wins; normalized descriptions are not substituted. No semantic claim is created.

The source-agnostic RTF reader is bounded to 1 MiB and 128 group levels. It
supports ANSI/CP1252 text, scoped font/Unicode fallback controls, paragraphs,
escaped characters and common punctuation. It omits formatting metadata,
ignorable destinations and hidden text. Field instructions and external
references are not evaluated. Unsupported code pages, font character sets,
binary data, surrogate escapes and malformed documents produce an explicit
warning and no text. This is a qualified plain-text profile, not a full renderer.

Qualification: all 33 referenced No.rtf files from K-CD 1/2001 decode with text
identical to macOS textutil's independent plain-text conversion, including
whitespace. Intercent's declared file is absent and is not fabricated. The full
original files remain preserved separately and embedded in these observations.

Reference: [Microsoft RTF text/code-page guidance](https://learn.microsoft.com/en-us/openspecs/exchange_server_protocols/ms-oxrtfex/1e44fa4c-3ea3-402c-8b21-fb19a617e43b).
