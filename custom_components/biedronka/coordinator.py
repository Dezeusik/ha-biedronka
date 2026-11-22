from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import parser as P
from .api import BiedronkaAuthError, BiedronkaClient
from .const import DOMAIN, EVENT_RECEIPT, KEEP_RECEIPTS

_LOGGER = logging.getLogger(__name__)
MAX_PAGES_FIRST = 5   # przy pierwszym uruchomieniu: ok. 2–3 miesiące historii
MAX_PAGES = 2


class BiedronkaCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, client: BiedronkaClient, entry_id: str, minutes: int) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(minutes=minutes))
        self.client = client
        self._store = Store(hass, 1, f"{DOMAIN}_{entry_id}")
        self._db: dict | None = None

    async def _async_update_data(self):
        if self._db is None:
            self._db = await self._store.async_load() or {"receipts": {}}
        db = self._db["receipts"]
        first = not self._db.get("init")
        new = []
        try:
            for page in range(1, (MAX_PAGES_FIRST if first else MAX_PAGES) + 1):
                lst = await self.client.transactions(page)
                rows = lst.get("transactions") or []
                fresh = [t for t in rows if str(t.get("id")) not in db]
                for t in fresh:
                    try:
                        r = P.receipt(await self.client.transaction(str(t["id"])))
                    except BiedronkaAuthError:
                        raise
                    except Exception as e:  # noqa: BLE001
                        _LOGGER.warning("Biedronka: nie udało się pobrać paragonu %s: %s", t.get("id"), e)
                        continue
                    db[r["id"]] = r
                    new.append(r)
                if not fresh or not lst.get("next_page"):
                    break
        except BiedronkaAuthError as e:
            raise ConfigEntryAuthFailed(f"Sesja Biedronki wygasła: {e}") from e
        except Exception as e:  # noqa: BLE001
            raise UpdateFailed(str(e)) from e

        if len(db) > KEEP_RECEIPTS:
            for rid in sorted(db, key=lambda x: db[x]["data"] or "")[: len(db) - KEEP_RECEIPTS]:
                db.pop(rid)
        if not first:
            for r in sorted(new, key=lambda x: x["data"] or ""):
                self.hass.bus.async_fire(EVENT_RECEIPT, {**r, "podsumowanie": P.summary_line(r)})
        self._db["init"] = True
        await self._store.async_save(self._db)
        return self._build(db)

    @staticmethod
    def _build(db: dict) -> dict:
        receipts = sorted(db.values(), key=lambda r: r["data"] or "", reverse=True)
        now = dt_util.now()
        ym = f"{now.year:04d}-{now.month:02d}"
        prev = (now.replace(day=1) - timedelta(days=1))
        pym = f"{prev.year:04d}-{prev.month:02d}"

        def month(key):
            rs = [r for r in receipts if (r["data"] or "").startswith(key)]
            groups, cats = {}, {}
            for r in rs:
                for g, v in r["grupy"].items():
                    groups[g] = round(groups.get(g, 0) + v, 2)
                for c, v in r["kategorie"].items():
                    cats[c] = round(cats.get(c, 0) + v, 2)
            return {"suma": round(sum(r["suma"] for r in rs), 2), "liczba": len(rs),
                    "grupy": dict(sorted(groups.items(), key=lambda x: -x[1])),
                    "kategorie": dict(sorted(cats.items(), key=lambda x: -x[1]))}

        return {"paragony": receipts, "ten_miesiac": month(ym), "poprzedni_miesiac": month(pym)}
