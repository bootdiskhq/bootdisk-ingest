# Supplementary Tools.dtx catalogue

The DTX adapter now reads root K.DTX and optional Tools.dtx (case-insensitive
resolution, with actual spelling retained). Previously, Tools.dtx appeared only
in the file inventory. Its entries were silently absent from the catalogue.

K.DTX entries and ordering remain unchanged. Tools sections matching I followed
by digits append their original I IDs in metadata order. CPU-Z K23 and I2 both
survive: two source entries can share a folder without establishing program
identity or authorizing deduplication. On K-CD 15/2001 this produces **68 source
entries**, not a claim of 68 distinct programs. The previous approximate 67 count
was a presentation estimate counting the known CPU-Z overlap once.

## Projection and evidence

- Navn supplies normalized.title; InstruksNo supplies normalized.description.
- raw remains the actual Tools fields, never fabricated Titel/Global keys.
- evidence.metadata_source binds filename, SHA-256 and section.
- evidence.description_tools binds the parsed InstruksNo text, section, field,
  filename, SHA-256 and explicit nb-NO field language. ConfigParser's existing
  whitespace/duplicate handling applies to the parsed view; raw_base64 preserves
  the exact source bytes. No prose is rewritten or translated.
- If InstruksNo is absent, description stays absent. No Danish/Swedish/Finnish
  substitution and no unrelated RTF fallback is made. Other languages stay raw.
- Existing folder/start-file, screenshot (JPG/BMP) and icon lookup rules apply.
- Tools Ja flags and numeric Kategori fields remain raw; normalized.categories
  is empty. AdAware has Spil=Ja, so K.DTX category semantics would be misleading.
- Missing startfiles are reported by normal reference validation. Malformed Tools
  metadata, missing Navn/Folder, unsafe paths or changed metadata abort the read.

source.supplemental_metadata retains the exact bytes, hash, encoding, actual
filename, parsed sections/defaults, parse warnings and projected/unprojected IDs.
The existing source.dtx_file and source.sections still describe K.DTX.

source.coverage enumerates processed metadata and unprojected sections, unknown
DTX files anywhere in the inventory, and shared entry folders. complete_disc is
always false: processing known metadata is not proof that all menus, bonus
content, unlisted tools or cover-advertised items are represented. The CLI reports
this boundary and unprocessed metadata. validation.valid still checks explicit
file references, not overall CD completeness. --strict retains that meaning.

## Verification and downstream boundary

Synthetic tests cover Tools absent/present, casing, retained bytes, unchanged K
entries, overlap, misleading flags, language absence, unknown sections/files,
duplicates, unsafe paths, changed bytes and extraction metadata.

K-CD 15/2001: parser read both metadata files from the mounted CD against the
previously hashed 887-file inventory: 39 old entries exactly unchanged, 29 Tools
entries, all with Norwegian text and existing installer/screenshot references.
All 58 Tools installer/screenshot files were independently read and hash-checked.
Repeated parsing was identical. Audit artifacts are local under
local-results/kcd15-2001-tools-ingest/.

A complete fresh filesystem ingest was attempted but macOS denied
FirstPage/DATA1.CAB, including outside the sandbox. This is not counted as a passed
full-media re-ingest. The frozen reference test still checks all original K
entries, identities, statistics and validation; the optional media test also now
requires the 29 Tools entries instead of incorrectly requiring a 39-entry disc.

This change does not republish the website or migrate Catalog review workspaces.
A new manifest has a new hash: old human decisions must be reconciled deliberately,
not rebound silently. Catalog's source-context projection needs explicit support
for description_tools before original descriptions are exposed in the curator or
public projection. No Tools semantic claims are automatically approved here.
