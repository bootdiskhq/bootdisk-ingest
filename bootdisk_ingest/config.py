"""Version contract and compatibility exports for pre-1.0 integrations."""
from . import __version__
from .adapters.kcd.config import KNOWN_ASSETS, KNOWN_NON_CATEGORY_FIELDS, SOURCE_FORMAT

SCHEMA_VERSION = "0.9"
PARSER_VERSION = __version__
