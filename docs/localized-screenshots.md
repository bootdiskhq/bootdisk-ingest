# Norwegian and neutral screenshots

The rc22 intake recognized Shot.jpg and Shot.bmp but omitted Shot.png and
ShotNo.png. This left all seven 2008–2009 CDs without screenshots even though
icons passed the package's image gate. HTTP byte verification checked the files
in the package; it did not establish that all source images had been selected.

Screenshot discovery now selects within the same entry folder, case-insensitively:
ShotNo.jpg, ShotNo.bmp, ShotNo.png, then Shot.jpg, Shot.bmp, Shot.png.
Norwegian artwork wins over neutral artwork. Other languages are not fallbacks.
Ambiguous case-colliding filenames stop discovery. Original bytes, hashes and
observed filename casing remain recorded; no image is inferred from a title.

Regression tests cover PNG discovery, Norwegian priority, mixed-case names,
foreign-only files, another folder, ambiguity and existing JPG/BMP precedence.
The nine affected format-batch CDs are rebuilt from preserved source files;
Publish verifies selected image bytes against the previous preservation extraction.
Their per-medium screenshot minimums are raised to the verified source coverage,
so losing the selected screenshots blocks subsequent package builds.
