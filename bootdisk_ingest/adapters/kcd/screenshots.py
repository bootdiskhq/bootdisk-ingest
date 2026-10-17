"""Select known Norwegian/neutral screenshot names within the entry folder."""
from .paths import relative_disc_path

# Norwegian artwork precedes neutral artwork; never borrow another language.
# Keep the established JPG/BMP order for discs without localized artwork.
NAMES = ('ShotNo.jpg', 'ShotNo.bmp', 'ShotNo.png', 'Shot.jpg', 'Shot.bmp', 'Shot.png')


def screenshot_path(inventory, folder):
    for name in NAMES:
        path = relative_disc_path(folder, name)
        if path is None:
            continue
        matches = [r for r in inventory['files'] if r['path'].casefold() == path.casefold()]
        if len(matches) > 1:
            raise ValueError(f'Ambiguous screenshot filename: {path}')
        if matches:
            return path
    return relative_disc_path(folder, 'Shot.jpg')
