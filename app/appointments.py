import json
import os
from datetime import date, datetime, timedelta

DATA_DIR = "data"
APPT_FILE = os.path.join(DATA_DIR, "appointments.json")

os.makedirs(DATA_DIR, exist_ok=True)


def _read():
    if not os.path.exists(APPT_FILE):
        return []
    with open(APPT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _write(data):
    with open(APPT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def book_appointment(student_name, email, when, advisor="Advisor", notes="", **extra):
    """Create a simple appointment entry and return a confirmation id."""
    data = _read()
    appt = {
        "id": len(data) + 1,
        "student_name": student_name,
        "email": email,
        "advisor": advisor,
        "when": when,
        "notes": notes,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    for key, value in extra.items():
        if value not in (None, "", [], {}):
            appt[key] = value
    data.append(appt)
    _write(data)
    return appt


def list_working_hours(start_hour=10, end_hour=18, step_minutes=30):
    slots = []
    current_minutes = start_hour * 60
    end_minutes = end_hour * 60
    while current_minutes <= end_minutes:
        hours, minutes = divmod(current_minutes, 60)
        slots.append(f"{hours:02d}:{minutes:02d}")
        current_minutes += step_minutes
    return slots


def _parse_when(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def suggest_appointment_slots(preferred_date=None, start_hour=16, end_hour=19, step_minutes=30, count=5):
    if preferred_date is None:
        preferred_date = date.today() + timedelta(days=1)
    if isinstance(preferred_date, str):
        try:
            preferred_date = datetime.fromisoformat(preferred_date).date()
        except Exception:
            preferred_date = date.today() + timedelta(days=1)

    booked = {_parse_when(item.get("when")) for item in list_appointments()}
    booked = {item for item in booked if item is not None}

    suggestions = []
    current_date = preferred_date
    horizon = preferred_date + timedelta(days=14)

    while current_date <= horizon and len(suggestions) < count:
        for slot in list_working_hours(start_hour=start_hour, end_hour=end_hour, step_minutes=step_minutes):
            when_dt = datetime.combine(current_date, datetime.strptime(slot, "%H:%M").time())
            if when_dt not in booked:
                suggestions.append({"date": current_date.isoformat(), "time": slot, "when": when_dt.isoformat(timespec="minutes")})
                if len(suggestions) >= count:
                    return suggestions
        current_date += timedelta(days=1)

    return suggestions


def auto_schedule_appointment(student_name, email, topic, profile=None, preferred_date=None, advisor="Basic Maths Prep Coach", notes=""):
    profile = profile or {}
    slots = suggest_appointment_slots(preferred_date=preferred_date, count=10)
    if not slots:
        slots = [{"when": (datetime.utcnow() + timedelta(days=1)).isoformat(timespec="minutes"), "date": (date.today() + timedelta(days=1)).isoformat(), "time": "10:00"}]

    chosen = slots[0]
    profile_bits = []
    for label, key in [("Grade", "grade"), ("Board", "board"), ("Goal", "goal"), ("City", "city")]:
        value = profile.get(key)
        if value:
            profile_bits.append(f"{label}: {value}")

    combined_notes = notes.strip()
    if topic:
        combined_notes = f"{combined_notes} Topic: {topic}.".strip()
    if profile_bits:
        combined_notes = f"{combined_notes} Profile: {' | '.join(profile_bits)}.".strip()

    appointment = book_appointment(
        student_name or profile.get("student_name") or "Math Student",
        email or profile.get("email") or "",
        chosen["when"],
        advisor=advisor,
        notes=combined_notes,
        topic=topic,
        profile=profile,
        auto_scheduled=True,
        suggested_slots=slots[:3],
    )
    appointment["scheduled_for"] = chosen
    return appointment


def list_upcoming_appointments(limit=10):
    items = list_appointments()
    upcoming = []
    now = datetime.utcnow()
    for item in items:
        when_dt = _parse_when(item.get("when"))
        if when_dt is None or when_dt >= now:
            upcoming.append(item)
    upcoming.sort(key=lambda row: row.get("when", ""))
    return upcoming[:limit]


def list_appointments():
    return _read()

if __name__ == "__main__":
    print(book_appointment("Test Student", "s@example.com", "2026-06-01T10:00:00", "Dr. Rao", "Discuss electives"))
