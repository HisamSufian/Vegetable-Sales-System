"""Rules and database access for the five profile types:
farm owners, customers, drivers, vehicles, vegetables.
One configuration table (KINDS) drives all the pages, so the five types
behave the same way."""
import psycopg
from fastapi import HTTPException

from app.db import execute, query


def _f(name, label, type="text", required=False, upper=False):
    return {"name": name, "label": label, "type": type, "required": required, "upper": upper}


# Table and column names below come from this file only (never from the user),
# so they are safe to place inside SQL text. User values always use %s.
KINDS = {
    "farm-owners": {
        "table": "farm_owners", "title": "Farm owners", "singular": "farm owner",
        "name_field": "name",
        "fields": [_f("name", "Name", required=True), _f("phone", "Phone", "tel"),
                   _f("email", "Email", "email"), _f("farm_location", "Farm location"),
                   _f("notes", "Notes", "textarea")],
        "search": ["name", "phone", "farm_location"], "subtitle": ["phone", "farm_location"],
        "order": "lower(name)",
    },
    "customers": {
        "table": "customers", "title": "Customers", "singular": "customer",
        "name_field": "name",
        "fields": [_f("name", "Name", required=True), _f("phone", "Phone", "tel"),
                   _f("shop_no", "Shop no."), _f("shop_location", "Shop location"),
                   _f("notes", "Notes", "textarea")],
        "search": ["name", "phone", "shop_no", "shop_location"], "subtitle": ["phone", "shop_no"],
        "order": "is_walk_in DESC, lower(name)",
    },
    "drivers": {
        "table": "drivers", "title": "Drivers", "singular": "driver",
        "name_field": "name",
        "fields": [_f("name", "Name", required=True), _f("phone", "Phone", "tel")],
        "search": ["name", "phone"], "subtitle": ["phone"],
        "order": "lower(name)",
    },
    "vehicles": {
        "table": "vehicles", "title": "Vehicles", "singular": "vehicle",
        "name_field": "plate_number",
        "fields": [_f("plate_number", "Plate number", required=True, upper=True)],
        "search": ["plate_number"], "subtitle": [],
        "order": "plate_number",
    },
    "vegetables": {
        "table": "vegetables", "title": "Vegetables", "singular": "vegetable",
        "name_field": "name",
        "fields": [_f("name", "Name", required=True)],
        "search": ["name"], "subtitle": [],
        "order": "lower(name)",
    },
}
for _key, _cfg in KINDS.items():
    _cfg["key"] = _key


def get_kind(kind: str) -> dict:
    cfg = KINDS.get(kind)
    if cfg is None:
        raise HTTPException(status_code=404, detail="Unknown profile type")
    return cfg


def _decorate(cfg: dict, row: dict) -> dict:
    """Adds 'label' (main text) and 'sub' (small grey text) for lists."""
    row["label"] = row[cfg["name_field"]]
    row["sub"] = " | ".join(str(row[c]) for c in cfg["subtitle"] if row.get(c))
    return row


def clean_values(cfg: dict, form: dict) -> tuple[dict, list[str]]:
    """Trims the submitted text and checks required fields."""
    values, errors = {}, []
    for f in cfg["fields"]:
        value = (form.get(f["name"]) or "").strip()
        if f["upper"]:
            value = value.upper()
        if f["required"] and not value:
            errors.append(f"{f['label']} is required.")
        values[f["name"]] = value or None
    return values, errors


def list_profiles(cfg: dict, q: str = "", show_hidden: bool = False) -> list[dict]:
    where, params = ["(is_deleted = false OR %s)"], [show_hidden]
    if q:
        where.append("(" + " OR ".join(
            f"lower(coalesce({col}, '')) LIKE %s" for col in cfg["search"]) + ")")
        params += [f"%{q.lower()}%"] * len(cfg["search"])
    sql = (f"SELECT * FROM {cfg['table']} WHERE {' AND '.join(where)} "
           f"ORDER BY {cfg['order']}")
    return [_decorate(cfg, r) for r in query(sql, params)]


def search_options(cfg: dict, q: str, limit: int = 8) -> list[dict]:
    """Visible (not hidden) profiles for the search-as-you-type dropdown."""
    where, params = ["is_deleted = false"], []
    if q:
        where.append("(" + " OR ".join(
            f"lower(coalesce({col}, '')) LIKE %s" for col in cfg["search"]) + ")")
        params += [f"%{q.lower()}%"] * len(cfg["search"])
    sql = (f"SELECT * FROM {cfg['table']} WHERE {' AND '.join(where)} "
           f"ORDER BY {cfg['order']} LIMIT %s")
    return [_decorate(cfg, r) for r in query(sql, params + [limit])]


def exact_match_exists(cfg: dict, text: str) -> bool:
    sql = (f"SELECT 1 AS found FROM {cfg['table']} "
           f"WHERE is_deleted = false AND lower({cfg['name_field']}) = lower(%s) LIMIT 1")
    return bool(query(sql, [text]))


def get_profile(cfg: dict, profile_id: int) -> dict | None:
    rows = query(f"SELECT * FROM {cfg['table']} WHERE id = %s", [profile_id])
    return _decorate(cfg, rows[0]) if rows else None


def create_profile(cfg: dict, values: dict) -> int:
    cols = list(values)
    sql = (f"INSERT INTO {cfg['table']} ({', '.join(cols)}) "
           f"VALUES ({', '.join(['%s'] * len(cols))}) RETURNING id")
    return execute(sql, list(values.values()))[0]["id"]


def update_profile(cfg: dict, profile_id: int, values: dict) -> None:
    sets = ", ".join(f"{col} = %s" for col in values)
    execute(f"UPDATE {cfg['table']} SET {sets} WHERE id = %s",
            list(values.values()) + [profile_id])


def set_hidden(cfg: dict, profile_id: int, hidden: bool) -> None:
    execute(f"UPDATE {cfg['table']} SET is_deleted = %s WHERE id = %s", [hidden, profile_id])


def duplicate_message(cfg: dict, value: str) -> str:
    """Friendly text when a unique value (plate, vegetable name) is already used."""
    rows = query(f"SELECT is_deleted FROM {cfg['table']} "
                 f"WHERE lower({cfg['name_field']}) = lower(%s) LIMIT 1", [value])
    if rows and rows[0]["is_deleted"]:
        return (f'"{value}" already exists but is hidden. Open Profiles > {cfg["title"]} '
                f'> Show hidden to restore it.')
    return f'"{value}" already exists.'


def usage_blockers(cfg: dict, profile_id: int) -> list[str]:
    """Reasons a profile cannot be hidden because other records use it,
    for example 'This farm owner is used by 3 trips'.
    Nothing uses profiles yet; later phases (trips, sales, payments)
    will add their checks here."""
    return []


UniqueViolation = psycopg.errors.UniqueViolation
