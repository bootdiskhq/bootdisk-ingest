# Score-bound Director image observations

Run `python -m bootdisk_ingest.director_images MANIFEST --source MEDIA --output NEW_BUNDLE`.
The source remains read-only. The supplemental `images.json` is bound to the exact
original ingest manifest; it does not replace that manifest or alter its identity.

The K-CD D6 profile rechecks the selected source frames against verified source
archives. It selects a unique 195×145 bitmap on each detail frame and a unique
16–32 pixel bitmap whose score position is inside the clickable title row on program
menus. Ambiguity is an explicit outcome, never a first-match choice. Game pages
currently have no qualified icon selector; their screenshots can be used as
presentation thumbnails, not relabelled as original icons.

The bundle preserves the complete hash-checked containers, raw BITD, CLUT and CASt
resources, byte offsets, resource/library/member IDs, frame/channel, sprite bytes,
selection rule, original palette binding and normalized raster layout. A zero
palette-library reference is resolved only when precisely one palette member with
that number exists in the explicitly supplied archives. Unknown palettes fail.
Only indexed 8-bit rasters with full 256-color palettes are currently qualified.

Format research references: [ScummVM D6 bitmap metadata](https://github.com/scummvm/scummvm/blob/master/engines/director/castmember/bitmap.cpp),
[BITD image decoding](https://github.com/scummvm/scummvm/blob/master/engines/director/images.cpp)
and [palette loading](https://github.com/scummvm/scummvm/blob/master/engines/director/cast.cpp).
The normalized codec declares raw data when the byte count equals row-stride ×
height; otherwise low controls copy n+1 literal bytes and high controls repeat
the next byte 257−n times. Publish handles bounded raster decoding, not source
resource discovery or Director archive parsing.

K-CD 1/2000: 21 detail images and 18 menu icons. Three games lack a qualified icon
association. Some source images/icons are reused: Zing editions share an image,
Laid Back uses a Winamp icon, and Excel Viewer uses the same icon as Word eksempel
on the original menu. Preserve those source observations; do not silently replace
them with more plausible modern images. Launch-target conflicts do not remove a
separate, verified menu-image association.

## Five-disc qualification (September 2026)

Selection method `kcd-d6-score-images-2` accepts cropped menu icons between
16 and 32 pixels on both axes. K-CD 4/2000, 9/2000 and 13/2000 contain
26×32, 30×31, 32×31 and 30×30 icons. The separate 38×38 menu-button
decoration remains excluded; multiple eligible icons in a title row still
produce an explicit ambiguity. Results: 4/2000 has 16 images and 13 icons;
9/2000 has 20 images and 17 icons; 13/2000 has 16 images and 13 icons.
The three game entries on each disc use image thumbnails in the frontend.
