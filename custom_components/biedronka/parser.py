"""Normalizacja paragonu z API do prostego słownika."""
from __future__ import annotations

from .categories import classify


def _scale(raw: dict) -> int:
    """API może zwracać kwoty w zł (59.99) albo w groszach (5999). Zgaduje po wartościach."""
    vals = [raw.get("total_price")] + [i.get("total_price") for i in raw.get("items") or []]
    vals = [v for v in vals if isinstance(v, (int, float))]
    if any(isinstance(v, float) and not float(v).is_integer() for v in vals):
        return 1
    total = raw.get("total_price") or 0
    return 100 if abs(total) >= 1000 else 1


def receipt(raw: dict) -> dict:
    k = _scale(raw)

    def m(v):
        return round((v or 0) / k, 2)

    items, groups, cats = [], {}, {}
    for it in raw.get("items") or []:
        name = (it.get("name") or "").strip()
        price = m(it.get("total_price"))
        group, cat = classify(name)
        items.append({"nazwa": name, "ilosc": it.get("quantity"), "cena": price,
                      "rabat": m(it.get("total_discount")), "ean": it.get("ean"), "grupa": group, "kategoria": cat})
        groups[group] = round(groups.get(group, 0) + price, 2)
        cats[cat] = round(cats.get(cat, 0) + price, 2)
    total = m(raw.get("total_price"))
    return {
        "id": str(raw.get("id")),
        "data": raw.get("date"),
        "suma": total,
        "rabaty": m(raw.get("total_discount")),
        "sklep": raw.get("store_name"),
        "sklep_id": raw.get("store_id"),
        "numer": raw.get("receipt_num"),
        "platnosci": [{"typ": p.get("payment_type"), "nazwa": p.get("name"), "kwota": m(p.get("value"))}
                      for p in raw.get("payments") or []],
        "pozycje": items,
        "grupy": dict(sorted(groups.items(), key=lambda x: -x[1])),
        "kategorie": dict(sorted(cats.items(), key=lambda x: -x[1])),
    }


def reclassify(r: dict) -> dict:
    """Ponownie przypisuje grupy (po zmianie słownika w categories.py)."""
    groups, cats = {}, {}
    for i in r.get("pozycje") or []:
        i["grupa"], i["kategoria"] = classify(i["nazwa"])
        groups[i["grupa"]] = round(groups.get(i["grupa"], 0) + i["cena"], 2)
        cats[i["kategoria"]] = round(cats.get(i["kategoria"], 0) + i["cena"], 2)
    r["grupy"] = dict(sorted(groups.items(), key=lambda x: -x[1]))
    r["kategorie"] = dict(sorted(cats.items(), key=lambda x: -x[1]))
    return r


def summary_line(r: dict, top: int = 4) -> str:
    parts = [f"{g} {v:.0f}" for g, v in list(r["grupy"].items())[:top]]
    return f"{r['suma']:.2f} zł → " + ", ".join(parts)
