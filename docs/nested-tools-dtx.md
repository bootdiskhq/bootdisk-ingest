# Nested Tools catalogue

K-CD 8/2002 and 16/2002 place the tools menu at Tools/Tools.dtx. Folder values
are relative to that menu directory. The adapter accepts exactly one of root
Tools.dtx and Tools/Tools.dtx (case-insensitive inventory resolution), and refuses
ambiguous media containing both. It never searches arbitrary directories.

The preserved raw fields and bytes remain unchanged. File observations join the
metadata parent with the validated relative Folder; evidence points to the actual
metadata path. Existing root-layout behavior remains compatible. Both layouts
retain unsafe-path rejection and post-inventory hash/size verification.

Nested Data*.DTX files on 16/2002 describe tutorials, not additional Tools menu
rows. They remain explicitly unprocessed in metadata coverage until a course
adapter is qualified. Reading the program menu does not certify complete media.

Validation includes nested installer resolution, original bytes, metadata coverage,
ambiguous layout rejection and traversal rejection, plus the existing root suite.
