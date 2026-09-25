# Workshop sources without Tools.dtx

The tools shelves are a separate Director menu source. Reading K.dtx or only the main program menu misses them. For the qualified six discs, run this additive stage as well as the normal ingest. Existing manifests and curation keys remain unchanged.

```sh
python -m bootdisk_ingest.legacy_tools /mounted/CD inventory.json --output workshop.json --images workshop-images
```

The inventory must be a full file inventory from the same disc. Original movie, cast and resolved launch bytes are checked against it. Outputs must be new and outside source media. No historical code is executed.

The profile selects Hylde shelf sprites whose attached mouseUp behavior consumes a literal correctCommand destination. The title is the corresponding shelf text, two channels after the clickable artwork. The next frame after the named destination is the introduction. The longest non-control body text is selected unchanged as the description; this is a documented layout heuristic, not semantic approval. All introduction texts and original CP1252 bytes remain in evidence. Literal installer commands are retained, with missing targets reported. `open "Launcher Tools…"` is a source convention, not proof of execution.

Source IDs are `Tool` followed by the hex encoding of the original destination label. They do not assert software identity or version, and identical titles on different discs are not merged.

Shelf artwork is taken from the same clickable sprite. Indexed 8-bit and D6 32-bit BITD observations retain original container/resource hashes and locations. For Afterburner, provenance identifies the compressed stream and the exact expanded subrange. Separate application screenshots are not inferred from artwork.

Afterburner is opt-in: bounded little-endian D6 FGDM/FGDC, explicit stream boundaries, resource IDs and lengths. Unsupported codecs are never decoded. Omitted optional KEY references to THUM/sndH/sndS/SCRF are skipped; missing required targets fail. A missing terminal RIFF alignment byte is accepted only if every real resource fits the original bytes. The source remains unmodified.

Format facts were checked against the primary [ScummVM Director archive reader](https://github.com/scummvm/scummvm/blob/master/engines/director/archive.cpp) and [BITD decoder](https://github.com/scummvm/scummvm/blob/master/engines/director/images.cpp). These Python readers do not execute Lingo.

## Qualification, 2026-09-25

| Medium | Added source posts | Original descriptions | Shelf artworks |
| --- | ---: | ---: | ---: |
| K-CD 1/2000 | 22 | 22 | 22 |
| K-CD 4/2000 | 25 | 25 | 25 |
| K-CD 9/2000 | 25 | 25 | 25 |
| K-CD 13/2000 | 28 | 28 | 28 |
| K-CD 1/2001 | 29 | 29 | 29 |
| K-CD 8/2001 | 33 | 33 | 33 |
| Total | 162 | 162 | 162 |

Two source deviations: SuperDesk on 4/2000 points to missing `Tools/SuperDesk/Setup.exe`; Add/Remove on 1/2001 points to missing `Tools/AddRemove/adrmpro2.exe`. No replacement filename was guessed. These observations can be published as pending source posts, not approved identities.

This qualifies workshop shelves on these six discs. It is not a claim that every item on every CD, every course or every menu subsection has been captured. Future ingest acceptance must account for each menu source (main menu, Tools.dtx or workshop shelves), images, and explicit unresolved sections.
