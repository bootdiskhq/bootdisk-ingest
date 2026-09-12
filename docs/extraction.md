# First file extraction

From the project root, with Python 3.10+:

```sh
python3 -m bootdisk_ingest "/run/media/stian/K-CD 9-2000" \
  --output "$HOME/kcd-resultat-ny.json" \
  --extract-to "$HOME/kcd-9-2000-uttrekk"
```

The extraction directory must be new and outside the source tree. `--force`
only applies to the observation JSON, never an existing extraction directory.
The output JSON must also be outside the extraction directory.

Each numbered entry directory contains `entry.json` (title, description, source
references, all observed branches and issues) and `files/` with original relative
paths. Root `extraction.json` lists the copied files, identities and provenance.
It is written last to indicate completion. Files are copied without execution,
unpacking or changing source bytes. Every copied file is checked against its
inventory SHA-256 and size. A failed copy removes the newly created extraction.

This first extraction copies **explicit inventory references**. For Director
entries these are existing primary launch files, not inferred complete program
folders or installer contents. Dependencies, neighboring data files and shared
runtimes are not automatically gathered. For DTX entries, the existing adapter's
folder inventory references are used. Empty entries still retain their metadata.
Conflicting branches retain all existing referenced files; missing references
and unresolved branches remain in the entry metadata, not silently corrected.

`--strict` still writes the extraction and manifest, then returns 1 for metadata
validation issues. Without it, completed observation and extraction return 0.
Input/copy failures return 2. If later manifest publication fails, a completed
extraction can remain; inspect extraction.json before retrying with a new path.

The Director adapter now also links an available `Norsk.cxt` when the movie
explicitly declares Norsk.cst or Norsk.cxt. This is a narrowly specified protected
cast filename substitution, not arbitrary authoring-path traversal. Missing Norsk
remains unresolved. A supplied corrupt or incompatible cast fails parsing.
On 9/2000 this exposes NeoTrace's stale Publisher direct path while retaining
its separate NeoTrace warning-continue path.

Optional 9/2000 regression: set `BOOTDISK_DIRECTOR_KCD9_FIXTURES` to a directory
containing the three original files, then run the standard unittest discovery.
