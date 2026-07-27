import json
import os
from config import SUPPORTED_LANGUAGES

LOCALES_DIR = os.path.join(os.path.dirname(__file__), "locales")

_cache = {}


def _load(lang_code):
    if lang_code in _cache:
        return _cache[lang_code]
    path = os.path.join(LOCALES_DIR, f"{lang_code}.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    _cache[lang_code] = data
    return data


def t(key, lang="en", **kwargs):
    """Translate `key` into `lang`. Falls back to English, then to the key itself."""
    data = _load(lang)
    text = data.get(key)
    if text is None:
        text = _load("en").get(key, key)
    try:
        return text.format(**kwargs)
    except (KeyError, IndexError):
        return text


def available_languages():
    """Only list languages that actually have a locale file present."""
    result = {}
    for code, name in SUPPORTED_LANGUAGES.items():
        if os.path.exists(os.path.join(LOCALES_DIR, f"{code}.json")):
            result[code] = name
    return result
