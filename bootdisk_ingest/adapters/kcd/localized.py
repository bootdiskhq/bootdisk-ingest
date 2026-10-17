"""Select Norwegian DTX title fields without changing the preserved raw view."""

def title_field(raw):
    fields = [key for key, value in raw.items()
              if key.casefold() == 'titelno' and value.strip()]
    if fields:
        if len({raw[key].strip() for key in fields}) != 1:
            raise ValueError('Conflicting Norwegian title fields')
        return sorted(fields)[0]
    return 'Titel'
