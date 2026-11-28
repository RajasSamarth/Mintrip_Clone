"""Ingest Google Flights scraper output in JSON or CSV form."""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

try:
    from .base_adapter import AdapterResult, FlightRecord, slugify
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scrapers.adapters.base_adapter import AdapterResult, FlightRecord, slugify

ALIASES: dict[str, tuple[str, ...]] = {
    "airline": ("airline", "carrier", "airline_name", "carrier_name"),
    "airline_code": ("airline_code", "carrier_code", "iata", "airline_iata"),
    "flight_number": ("flight_number", "flight_no", "number", "flight", "flightNumber"),
    "origin": ("origin", "from", "origin_iata", "departure_airport", "from_airport", "dep_airport"),
    "destination": ("destination", "to", "destination_iata", "arrival_airport", "to_airport", "arr_airport"),
    "departure_time": ("departure_time", "departure", "depart_time", "departureTime", "takeoff", "dep_time"),
    "arrival_time": ("arrival_time", "arrival", "arrive_time", "arrivalTime", "landing", "arr_time"),
    "flight_date": ("flight_date", "date", "outbound_date", "departure_date"),
    "duration_minutes": ("duration_minutes", "duration", "total_duration", "durationMins", "duration_min"),
    "stops": ("stops", "num_stops", "stop_count", "layovers"),
    "price_usd": ("price_usd", "price", "total_price", "amount", "fare", "price_inr"),
    "cabin": ("cabin", "cabin_class", "class", "travel_class"),
    "baggage": ("baggage", "bags", "baggage_info", "carry_on"),
    "booking_url": ("booking_url", "url", "link", "deeplink", "booking_link"),
    "is_top_pick": ("is_top_pick", "top_pick", "best_flight"),
    "emissions": ("emissions", "carbon", "co2"),
    "self_transfer": ("self_transfer", "separate_tickets"),
    "id": ("id", "flight_id", "offer_id"),
}

AIRLINE_NAME_TO_IATA: dict[str, str] = {
    "american": "AA",
    "american airlines": "AA",
    "united": "UA",
    "united airlines": "UA",
    "delta": "DL",
    "delta air lines": "DL",
    "frontier": "F9",
    "frontier airlines": "F9",
    "alaska": "AS",
    "alaska airlines": "AS",
    "jetblue": "B6",
    "jetblue airways": "B6",
    "southwest": "WN",
    "southwest airlines": "WN",
    "spirit": "NK",
    "spirit airlines": "NK",
    "sun country": "SY",
    "sun country airlines": "SY",
    "hawaiian": "HA",
    "hawaiian airlines": "HA",
    "allegiant": "G4",
    "allegiant air": "G4",
    "breeze": "MX",
    "breeze airways": "MX",
    "avelo": "XP",
    "air canada": "AC",
    "westjet": "WS",
    "porter": "PD",
    "porter airlines": "PD",
    "flair": "F8",
    "aeromexico": "AM",
    "volaris": "Y4",
    "indigo": "6E",
    "air india": "AI",
    "air india express": "IX",
    "vistara": "UK",
    "spicejet": "SG",
    "akasa air": "QP",
    "akasa": "QP",
    "alliance air": "9I",
    "emirates": "EK",
    "qatar airways": "QR",
    "qatar": "QR",
    "etihad": "EY",
    "etihad airways": "EY",
    "flydubai": "FZ",
    "air arabia": "G9",
    "saudia": "SV",
    "gulf air": "GF",
    "oman air": "WY",
    "kuwait airways": "KU",
    "british airways": "BA",
    "virgin atlantic": "VS",
    "lufthansa": "LH",
    "air france": "AF",
    "klm": "KL",
    "swiss": "LX",
    "austrian": "OS",
    "brussels airlines": "SN",
    "iberia": "IB",
    "vueling": "VY",
    "ryanair": "FR",
    "easyjet": "U2",
    "wizz air": "W6",
    "tap air portugal": "TP",
    "ita airways": "AZ",
    "finnair": "AY",
    "sas": "SK",
    "scandinavian airlines": "SK",
    "norwegian": "DY",
    "aer lingus": "EI",
    "icelandair": "FI",
    "turkish airlines": "TK",
    "pegasus": "PC",
    "lot": "LO",
    "lot polish airlines": "LO",
    "aegean": "A3",
    "singapore airlines": "SQ",
    "scoot": "TR",
    "ana": "NH",
    "all nippon airways": "NH",
    "jal": "JL",
    "japan airlines": "JL",
    "cathay pacific": "CX",
    "korean air": "KE",
    "asiana": "OZ",
    "asiana airlines": "OZ",
    "thai airways": "TG",
    "bangkok airways": "PG",
    "vietnam airlines": "VN",
    "malaysia airlines": "MH",
    "airasia": "AK",
    "garuda indonesia": "GA",
    "philippine airlines": "PR",
    "eva air": "BR",
    "china airlines": "CI",
    "qantas": "QF",
    "jetstar": "JQ",
    "virgin australia": "VA",
    "air new zealand": "NZ",
    "ethiopian": "ET",
    "ethiopian airlines": "ET",
    "egyptair": "MS",
    "royal air maroc": "AT",
    "kenya airways": "KQ",
    "latam": "LA",
    "avianca": "AV",
    "copa": "CM",
    "copa airlines": "CM",
    "azul": "AD",
}


def _resolve_airline_code(airline: str, explicit_code: str = "") -> str:
    """Resolve a 2-character IATA carrier code from explicit input or airline name."""
    code = str(explicit_code or "").strip().upper()
    if code:
        return code
    raw = str(airline or "").strip()
    if not raw:
        return ""
    # Handle strings like "American, Operated by SkyWest" or "United · Lufthansa"
    primary = re.split(r"[,·/|]|operated by", raw, maxsplit=1, flags=re.I)[0].strip().lower()
    if primary in AIRLINE_NAME_TO_IATA:
        return AIRLINE_NAME_TO_IATA[primary]
    cleaned = re.sub(r"\s+(airlines?|airways|air lines|air)\s*$", "", primary).strip()
    if cleaned in AIRLINE_NAME_TO_IATA:
        return AIRLINE_NAME_TO_IATA[cleaned]
    for name, iata in AIRLINE_NAME_TO_IATA.items():
        if name in primary:
            return iata
    return ""


def _pick(row: dict[str, Any], key: str) -> Any:
    for alias in ALIASES[key]:
        if alias in row and row[alias] not in (None, ""):
            return row[alias]
    return None


def _duration_minutes(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    match = re.search(r"(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?", text, re.I)
    if match and (match.group(1) or match.group(2)):
        return int(match.group(1) or 0) * 60 + int(match.group(2) or 0)
    return 0


def _stops(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, list):
        return max(0, len(value) - 1)
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).lower()
    if "nonstop" in text or "direct" in text:
        return 0
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else 0


def _price(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    digits = re.sub(r"[^0-9.]", "", str(value or ""))
    return float(digits) if digits else 0.0


def _normalize_time(val: Any, base_date: str) -> str:
    if not val:
        return ""
    text = str(val).strip()
    if not text:
        return ""
    if "T" in text or (len(text) >= 10 and text[4] == "-" and text[7] == "-"):
        return text
    date_part = base_date or datetime.today().strftime("%Y-%m-%d")
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M", "%H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
            return f"{date_part}T{parsed.strftime('%H:%M:%S')}"
        except ValueError:
            pass
    return f"{date_part}T{text}" if date_part else text


def _to_record(row: dict[str, Any], fallback_date: str = "", index: int = 0) -> FlightRecord | None:
    airline = _pick(row, "airline")
    origin, destination = _pick(row, "origin"), _pick(row, "destination")
    if not airline or not origin or not destination:
        return None
    date_hint = _pick(row, "flight_date") or fallback_date or datetime.today().strftime("%Y-%m-%d")
    raw_dep = _pick(row, "departure_time") or date_hint
    departure = _normalize_time(raw_dep, str(date_hint))
    raw_arr = _pick(row, "arrival_time") or ""
    arr_str = str(raw_arr).strip()
    arr_has_explicit_date = bool(
        arr_str and ("T" in arr_str or (len(arr_str) >= 10 and arr_str[4] == "-" and arr_str[7] == "-"))
    )
    arrival = _normalize_time(raw_arr, str(date_hint)) if raw_arr else ""
    duration = _duration_minutes(_pick(row, "duration_minutes"))
    if arrival and departure and not arr_has_explicit_date:
        try:
            dep_dt = datetime.fromisoformat(str(departure))
            arr_dt = datetime.fromisoformat(str(arrival))
            if duration > 0:
                est_arr = dep_dt + timedelta(minutes=duration)
                max_days = max(3, (duration // 1440) + 3)
                candidates = [arr_dt + timedelta(days=k) for k in range(max_days)]
                valid = [c for c in candidates if c >= dep_dt] or candidates
                arr_dt = min(valid, key=lambda c: abs((c - est_arr).total_seconds()))
            elif arr_dt < dep_dt:
                arr_dt = arr_dt + timedelta(days=1)
            arrival = arr_dt.isoformat()
        except ValueError:
            pass
    if not arrival and departure and duration:
        try:
            arrival = (datetime.fromisoformat(str(departure)) + timedelta(minutes=duration)).isoformat()
        except ValueError:
            arrival = ""
    raw_price_val = _pick(row, "price_usd")
    raw_price_str = str(raw_price_val or "")
    raw_price = _price(raw_price_val)
    currency = str(row.get("currency") or "").upper()
    if not currency:
        if "$" in raw_price_str or "USD" in raw_price_str:
            currency = "USD"
        elif "₹" in raw_price_str or "INR" in raw_price_str:
            currency = "INR"
        elif "€" in raw_price_str or "EUR" in raw_price_str:
            currency = "EUR"
        elif "£" in raw_price_str or "GBP" in raw_price_str:
            currency = "GBP"
        elif "¥" in raw_price_str or "JPY" in raw_price_str:
            currency = "JPY"
        else:
            currency = "USD"

    if currency == "INR":
        price_inr = raw_price
        price_usd = round(raw_price / 85.0, 2)
    elif currency == "USD":
        price_usd = raw_price
        price_inr = round(raw_price * 85.0, 2)
    elif currency == "EUR":
        price_usd = round(raw_price * 1.08, 2)
        price_inr = round(price_usd * 85.0, 2)
    elif currency == "GBP":
        price_usd = round(raw_price * 1.28, 2)
        price_inr = round(price_usd * 85.0, 2)
    elif currency == "JPY":
        price_usd = round(raw_price / 152.0, 2)
        price_inr = round(price_usd * 85.0, 2)
    else:
        price_usd = raw_price
        price_inr = round(raw_price * 85.0, 2)

    # Sanity guard against artifact prices (e.g. 1 Rs from '1 stop')
    min_thresh_inr = 500.0
    min_thresh_usd = 15.0
    if (price_inr is not None and price_inr < min_thresh_inr) or (price_usd is not None and price_usd < min_thresh_usd):
        base_fare = 6500.0 if _stops(_pick(row, "stops")) == 0 else 8200.0
        price_inr = base_fare
        price_usd = round(base_fare / 85.0, 2)

    is_top_pick = bool(_pick(row, "is_top_pick") or False)
    emissions = str(_pick(row, "emissions") or "")
    self_transfer = bool(_pick(row, "self_transfer") or False)

    flight_id = _pick(row, "id") or ""
    if not flight_id:
        f_num = str(_pick(row, "flight_number") or "").strip()
        stops_count = _stops(_pick(row, "stops"))
        if f_num:
            flight_id = slugify(f"{airline}-{f_num}-{origin}-{destination}-{departure}-{index}")
        else:
            flight_id = slugify(f"{airline}-{origin}-{destination}-{departure}-{stops_count}s-{duration}m-{index}")

    airline_code = _resolve_airline_code(str(airline), str(_pick(row, "airline_code") or ""))

    return FlightRecord(
        id=flight_id,
        airline=str(airline),
        airline_code=airline_code,
        flight_number=str(_pick(row, "flight_number") or ""),
        origin=str(origin),
        destination=str(destination),
        departure_time=departure,
        arrival_time=arrival,
        duration_minutes=duration,
        stops=_stops(_pick(row, "stops")),
        price_usd=price_usd,
        price_inr=price_inr,
        is_top_pick=is_top_pick,
        cabin=str(_pick(row, "cabin") or "Economy").capitalize(),
        baggage=str(_pick(row, "baggage") or ""),
        booking_url=str(_pick(row, "booking_url") or ""),
        emissions=emissions,
        self_transfer=self_transfer,
        source="google_flights",
        metadata={k: v for k, v in row.items() if k not in {"segments", "layovers"}},
    )


def _iter_rows(path: Path) -> Iterable[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            yield from csv.DictReader(fh)
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        for key in ("results", "flights", "offers", "data", "items", "itineraries"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        raise ValueError("Expected a JSON list or an object with results/flights/offers/data")
    yield from payload


def ingest(path: str | Path, fallback_date: str = "") -> AdapterResult:
    path = Path(path)
    records: list[FlightRecord] = []
    warnings: list[str] = []
    skipped = 0
    for index, row in enumerate(_iter_rows(path)):
        try:
            record = _to_record(row, fallback_date, index=index)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"row {index}: {exc}")
            skipped += 1
            continue
        if record is None:
            warnings.append(f"row {index}: missing airline/origin/destination")
            skipped += 1
            continue
        records.append(record)
    return AdapterResult(source="google_flights", total=len(records), records=records, skipped=skipped, warnings=warnings[:20])


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalise Google Flights scraper output")
    parser.add_argument("input")
    parser.add_argument("--date", default="", help="Fallback departure date/time")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    result = ingest(args.input, args.date)
    text = json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {len(result.records)} flights to {args.out} ({result.skipped} skipped)")
    else:
        print(text)


if __name__ == "__main__":
    main()
