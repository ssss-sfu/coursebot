import difflib

MAX_AUTOCOMPLETE_CHOICES = 25  # Discord's limit


def filter_departments(departments: list[str], current: str, limit: int = MAX_AUTOCOMPLETE_CHOICES) -> list[str]:
  """Departments matching what the user has typed so far: prefix matches first, then substring matches."""
  query = current.strip().upper()
  if not query:
    return departments[:limit]
  prefix = [d for d in departments if d.startswith(query)]
  contains = [d for d in departments if query in d and not d.startswith(query)]
  return (prefix + contains)[:limit]


def suggest_names(query: str, names: list[str], n: int = 3) -> list[str]:
  """Close spellings first (difflib), then names containing the query, e.g. a last name on its own."""
  query = query.strip().lower()
  if not query:
    return []
  by_lower: dict[str, str] = {}
  for name in names:
    by_lower.setdefault(name.strip().lower(), name.strip())
  suggestions = difflib.get_close_matches(query, list(by_lower), n=n, cutoff=0.75)
  for lowered in by_lower:
    if len(suggestions) >= n:
      break
    if query in lowered and lowered not in suggestions:
      suggestions.append(lowered)
  return [by_lower[s] for s in suggestions]
