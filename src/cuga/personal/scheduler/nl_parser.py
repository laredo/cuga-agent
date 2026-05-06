"""Natural language → cron expression parser for scheduling requests."""

import re
from typing import Optional

_DAYS: dict[str, int] = {
    "sunday": 0,
    "monday": 1,
    "tuesday": 2,
    "wednesday": 3,
    "thursday": 4,
    "friday": 5,
    "saturday": 6,
}

_DAY_NUM_TO_NAME: dict[int, str] = {v: k.capitalize() for k, v in _DAYS.items()}

_KNOWN_SKILLS = ["bulletin", "timesheet", "calculator", "knowledge-store"]

_SCHEDULE_KEYWORDS = {"every ", "daily", "weekly", "schedule", "remind me", "each "}


def is_schedule_request(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in _SCHEDULE_KEYWORDS)


def parse_schedule(text: str, default_skill: str = "bulletin") -> Optional[dict]:
    """
    Parse a natural language scheduling request.

    Returns a dict with keys: name, cron, skill_name, prompt, human_schedule
    or None if the text can't be parsed into a schedule.
    """
    t = text.lower()

    skill_name = default_skill
    for s in _KNOWN_SKILLS:
        if s in t:
            skill_name = s
            break

    day_num: Optional[int] = None
    for day, num in _DAYS.items():
        if day in t:
            day_num = num
            break

    hour: Optional[int] = None
    minute = 0
    m = re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", t)
    if m:
        hour = int(m.group(1))
        if m.group(2):
            minute = int(m.group(2))
        meridiem = m.group(3)
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0

    if hour is None:
        if "morning" in t:
            hour = 9
        elif "afternoon" in t:
            hour = 14
        elif "evening" in t:
            hour = 18

    if hour is None:
        return None

    if day_num is not None:
        cron = f"{minute} {hour} * * {day_num}"
        day_label = _DAY_NUM_TO_NAME[day_num]
        human = f"every {day_label} at {_fmt_hour(hour, minute)}"
    elif "daily" in t or "every day" in t or "each day" in t:
        cron = f"{minute} {hour} * * *"
        human = f"daily at {_fmt_hour(hour, minute)}"
    elif "weekday" in t or "weekdays" in t:
        cron = f"{minute} {hour} * * 1-5"
        human = f"every weekday at {_fmt_hour(hour, minute)}"
    else:
        # default: daily
        cron = f"{minute} {hour} * * *"
        human = f"daily at {_fmt_hour(hour, minute)}"

    slug = human.lower().replace(" ", "-").replace(":", "")
    name = f"{skill_name}-{slug}"

    prompt = _build_prompt(skill_name)

    return {
        "name": name,
        "cron": cron,
        "skill_name": skill_name,
        "prompt": prompt,
        "human_schedule": human,
    }


def _fmt_hour(hour: int, minute: int = 0) -> str:
    h12 = hour % 12 or 12
    suffix = "am" if hour < 12 else "pm"
    if minute:
        return f"{h12}:{minute:02d}{suffix}"
    return f"{h12}{suffix}"


def _build_prompt(skill_name: str) -> str:
    prompts = {
        "bulletin": "Draft a customer bulletin from what we shipped this week.",
        "timesheet": "Fill my timesheet for this week.",
    }
    return prompts.get(skill_name, f"Run the {skill_name} skill.")
