# J.DTX calendar metadata

The normal K-CD pipeline now appends explicitly named J-numbered source posts
from J.DTX. The original file bytes, hash, section fields and entry binding are
preserved as supplemental metadata. Folder/Setup/Run use existing inventory and
path checks. Numeric Type values are kept raw, not guessed into content kinds.
Existing RTF observation and artwork discovery also apply to calendar posts.

Unknown sections remain in the coverage report. Duplicate fields/sections,
undefined encoding, inherited defaults and unsafe paths fail explicitly. An
absent J.DTX does not change existing entry projections. This is source metadata
coverage, not proof of runtime menu reachability or installed-product identity.

K-CD 16/2001 acceptance: 45 K.DTX + 29 Tools.dtx + 25 J.DTX = 99 entries.
All 74 preexisting parser entries are identical. The 25 include 24 calendar
slots and a bonus entry. No referenced installer or Run file is missing.
All 99 have source screenshots; 69 have Norwegian RTF files. The source ISO
has a 6144-byte tail beyond its ISO volume; the complete ISO hash is retained.
The mounted FirstPage/DATA1.CAB could not be read through macOS, so a read-only
archive reader materialized an isolated working copy from the ISO. Its three
metadata files match the mounted files byte for byte. No original media changed.
