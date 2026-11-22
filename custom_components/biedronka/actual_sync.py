"""Dzielenie płatności z Biedronki w Actual Budget na kategorie z e-paragonu.

Korzysta z biblioteki actualpy i z danych logowania zapisanych już przez integrację
„actualbudget” (jlvcm/ha-actualbudget), więc nie trzeba drugi raz podawać hasła.
"""
from __future__ import annotations

import datetime as dt
import logging
import pathlib

_LOGGER = logging.getLogger(__name__)

PAYEE_HINTS = ("BIEDRONKA", "JERONIMO", "JMP ")
WINDOW_DAYS = 3
RETRY_DAYS = 10


def actual_config(hass) -> dict | None:
    for e in hass.config_entries.async_entries("actualbudget"):
        d = e.data
        if d.get("endpoint") and d.get("password") and d.get("file"):
            return {"endpoint": d["endpoint"], "password": d["password"], "file": d["file"],
                    "encrypt_password": d.get("encrypt_password"),
                    "cert": False if d.get("skip_validate_cert") else (d.get("cert") or True)}
    return None


def _cents(v: float) -> int:
    return int(round(v * 100))


def _split_amounts(cats: dict[str, float], total_cents: int) -> list[tuple[str, int]]:
    """Rozkłada kwotę płatności (grosze, ujemna) na kategorie proporcjonalnie do paragonu."""
    s = sum(cats.values()) or 1
    parts = [(c, int(round(total_cents * v / s))) for c, v in cats.items() if v]
    diff = total_cents - sum(p for _, p in parts)
    if parts and diff:
        c0, p0 = parts[0]
        parts[0] = (c0, p0 + diff)
    return [p for p in parts if p[1]]


def _payee_text(t) -> str:
    parts = [t.imported_description or "", t.notes or ""]
    try:
        if t.payee is not None:
            parts.append(t.payee.name or "")
    except Exception:  # noqa: BLE001
        pass
    return " ".join(parts).upper()


def sync_receipts(cfg: dict, data_dir: str, receipts: list[dict], done: dict) -> dict:
    """Uruchamiane w wątku (executor). Zwraca {id_paragonu: wynik} dla przetworzonych paragonów."""
    from actual import Actual
    from actual.queries import create_split, get_category, get_transactions

    today = dt.date.today()
    todo = []
    for r in receipts:
        if r["id"] in done and done[r["id"]].get("status") in ("ok", "pominięty"):
            continue
        d = dt.date.fromisoformat((r["data"] or "")[:10])
        if (today - d).days > RETRY_DAYS and r["id"] in done:
            continue
        if len(r.get("kategorie") or {}) < 2:
            done[r["id"]] = {"status": "pominięty", "powod": "jedna kategoria"}
            continue
        todo.append((r, d))
    if not todo:
        return {}

    results = {}
    pathlib.Path(data_dir).mkdir(parents=True, exist_ok=True)
    with Actual(base_url=cfg["endpoint"], password=cfg["password"], file=cfg["file"],
                encryption_password=cfg.get("encrypt_password"), data_dir=data_dir, cert=cfg["cert"]) as actual:
        s = actual.session
        changed = False
        for r, d in todo:
            wanted = {_cents(r["suma"])} | {_cents(p["kwota"]) for p in r.get("platnosci") or [] if p.get("kwota")}
            txs = get_transactions(s, start_date=d - dt.timedelta(days=WINDOW_DAYS),
                                   end_date=d + dt.timedelta(days=WINDOW_DAYS + 1))
            cands = [t for t in txs if not t.parent_id and not t.is_child and not t.is_parent
                     and t.amount is not None and -t.amount in wanted]
            named = [t for t in cands if any(h in _payee_text(t) for h in PAYEE_HINTS)]
            pool = named or (cands if len(cands) == 1 else [])
            if not pool:
                results[r["id"]] = {"status": "brak", "powod": "nie znaleziono płatności (jeszcze nie zsynchronizowana?)"}
                continue
            t = min(pool, key=lambda x: abs((x.get_date() - d).days))
            parts = _split_amounts(r["kategorie"], t.amount)
            fallback = t.category
            lines = []
            for cat_name, cents in parts:
                cat = get_category(s, cat_name) or fallback
                child = create_split(s, t, cents / 100)
                child.category_id = cat.id if cat else None
                items = [i["nazwa"] for i in r["pozycje"] if i["kategoria"] == cat_name]
                child.notes = ("Biedronka: " + ", ".join(items))[:250]
                lines.append(f"{cat_name} {abs(cents) / 100:.2f}")
            t.is_parent, t.category_id = 1, None
            old = t.notes or ""
            t.notes = (f"e-paragon {r.get('numer') or r['id']}: " + "; ".join(lines) + (f" | {old}" if old else ""))[:500]
            changed = True
            results[r["id"]] = {"status": "ok", "transakcja": t.id, "podzial": lines}
        if changed:
            actual.commit()
    return results
