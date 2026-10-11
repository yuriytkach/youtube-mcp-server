"""Merging translated titles/descriptions (the ``localizations`` part).

videos.update and playlists.update replace the WHOLE ``localizations`` part:
any language that is not sent again is deleted. So the current localizations
are always read first and the new ones merged in, language by language and
field by field.

YouTube only accepts localizations when ``snippet.defaultLanguage`` is set
(the language of the main title/description). We never guess it: if the
resource has none, the caller must pass ``default_language``.
"""


def merge_localizations(
    snippet: dict,
    current: dict | None,
    updates: dict | None,
    default_language: str | None,
    title_limit: int,
    description_limit: int = 5000,
) -> tuple[dict | None, str | None]:
    """Return ``(merged_localizations, error)``.

    Changes ``snippet["defaultLanguage"]`` in place when ``default_language``
    is given. ``merged_localizations`` is None when the localizations part
    does not need to be sent (no ``updates``).
    """
    if default_language is not None:
        snippet["defaultLanguage"] = default_language

    if not updates:
        return None, None

    default = snippet.get("defaultLanguage")
    if not default:
        return None, (
            "The resource has no defaultLanguage (language of the main title/description). "
            "Pass default_language (e.g. 'ru') so translations can be added."
        )

    merged = {lang: dict(fields) for lang, fields in (current or {}).items()}
    for lang, fields in updates.items():
        if lang == default:
            return None, (
                f"'{lang}' is the default language; change the main title/description "
                "instead of adding a translation for it."
            )
        if not isinstance(fields, dict):
            return None, f"localizations['{lang}'] must be a dict with title/description"
        unknown = set(fields) - {"title", "description"}
        if unknown:
            return None, f"localizations['{lang}']: unknown fields {sorted(unknown)}"
        entry = merged.setdefault(lang, {})
        if fields.get("title") is not None:
            if len(fields["title"]) > title_limit:
                return None, f"localizations['{lang}'].title longer than {title_limit} chars"
            entry["title"] = fields["title"]
        if fields.get("description") is not None:
            if len(fields["description"]) > description_limit:
                return None, (
                    f"localizations['{lang}'].description longer than {description_limit} chars"
                )
            entry["description"] = fields["description"]
        if not entry.get("title"):
            return None, f"localizations['{lang}'] is new and needs a title"
    return merged, None
