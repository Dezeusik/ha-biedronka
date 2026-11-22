from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN

PLN = "PLN"


async def async_setup_entry(hass, entry, async_add):
    c = hass.data[DOMAIN][entry.entry_id]
    async_add([LastReceipt(c, entry), LastReceiptTime(c, entry), MonthTotal(c, entry), MonthCount(c, entry),
               PrevMonthTotal(c, entry), MonthGroups(c, entry)])


class Base(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    key = ""

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{self.key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}, "name": entry.title,
                                  "manufacturer": "Biedronka (nieoficjalnie)", "model": "e-paragony"}

    @property
    def d(self) -> dict:
        return self.coordinator.data or {}

    @property
    def last(self) -> dict | None:
        p = self.d.get("paragony") or []
        return p[0] if p else None


class LastReceipt(Base):
    key, _attr_name, _attr_icon = "last_receipt", "Ostatni paragon", "mdi:receipt-text"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = PLN

    @property
    def native_value(self):
        return self.last["suma"] if self.last else None

    @property
    def extra_state_attributes(self):
        r = self.last
        if not r:
            return {}
        return {"data": r["data"], "sklep": r["sklep"], "rabaty": r["rabaty"], "grupy": r["grupy"],
                "kategorie": r["kategorie"], "pozycji": len(r["pozycje"]),
                "pozycje": [f"{i['nazwa']} – {i['cena']:.2f} zł ({i['grupa']})" for i in r["pozycje"]][:60]}


class LastReceiptTime(Base):
    key, _attr_name, _attr_icon = "last_receipt_time", "Ostatnie zakupy", "mdi:cart-clock"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        if not self.last or not self.last["data"]:
            return None
        t = dt_util.parse_datetime(self.last["data"])
        if t and t.tzinfo is None:
            t = t.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
        return t


class MonthTotal(Base):
    key, _attr_name, _attr_icon = "month_total", "Wydatki w tym miesiącu", "mdi:cash-multiple"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = PLN
    _attr_state_class = SensorStateClass.TOTAL

    @property
    def native_value(self):
        return self.d.get("ten_miesiac", {}).get("suma")

    @property
    def extra_state_attributes(self):
        m = self.d.get("ten_miesiac", {})
        return {"grupy": m.get("grupy"), "kategorie": m.get("kategorie"), "paragonow": m.get("liczba")}


class MonthCount(Base):
    key, _attr_name, _attr_icon = "month_count", "Zakupy w tym miesiącu", "mdi:counter"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "paragonów"

    @property
    def native_value(self):
        return self.d.get("ten_miesiac", {}).get("liczba")


class PrevMonthTotal(Base):
    key, _attr_name, _attr_icon = "prev_month_total", "Wydatki w poprzednim miesiącu", "mdi:cash-clock"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = PLN

    @property
    def native_value(self):
        return self.d.get("poprzedni_miesiac", {}).get("suma")

    @property
    def extra_state_attributes(self):
        m = self.d.get("poprzedni_miesiac", {})
        return {"grupy": m.get("grupy"), "kategorie": m.get("kategorie"), "paragonow": m.get("liczba")}


class MonthGroups(Base):
    """Stan = grupa, na którą w tym miesiącu idzie najwięcej; atrybuty = wszystkie grupy w zł."""
    key, _attr_name, _attr_icon = "month_top_group", "Najwięcej na", "mdi:chart-pie"

    @property
    def native_value(self):
        g = self.d.get("ten_miesiac", {}).get("grupy") or {}
        return next(iter(g), None)

    @property
    def extra_state_attributes(self):
        return dict(self.d.get("ten_miesiac", {}).get("grupy") or {})
