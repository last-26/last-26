#!/usr/bin/env python3
import datetime as dt
import html
import json
import os
import urllib.request
from collections import OrderedDict
from pathlib import Path


USERNAME = os.environ.get("USERNAME") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "last-26"
START_DATE = dt.date.fromisoformat(os.environ.get("ACTIVITY_START", "2026-02-01"))
OUTPUT_PATH = Path(os.environ.get("ACTIVITY_OUTPUT", "profile-assets/2026-momentum.svg"))


def graphql(query, variables):
    token = os.environ["GITHUB_TOKEN"]
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "last-26-profile-readme",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.loads(response.read().decode())
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    return payload["data"]


def fmt_count(value):
    if value >= 1000:
        return f"{value / 1000:.2f}k".rstrip("0").rstrip(".")
    return f"{value:,}"


def color_for(count):
    if count <= 0:
        return "#242938"
    if count <= 5:
        return "#173B57"
    if count <= 15:
        return "#3178C6"
    if count <= 30:
        return "#70A5FD"
    if count <= 50:
        return "#BF91F3"
    return "#50FA7B"


def longest_streak(days):
    best = 0
    current = 0
    for day in days:
        if day["count"] > 0:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def current_streak(days):
    streak = 0
    for day in reversed(days):
        if day["count"] > 0:
            streak += 1
        else:
            break
    return streak


def esc(value):
    return html.escape(str(value), quote=True)


def text(x, y, content, size=14, fill="#E6EDF3", weight=500, anchor="start", opacity=1):
    return (
        f'<text x="{x}" y="{y}" fill="{fill}" fill-opacity="{opacity}" '
        f'font-family="Segoe UI, Ubuntu, sans-serif" font-size="{size}" '
        f'font-weight="{weight}" text-anchor="{anchor}">{esc(content)}</text>'
    )


def main():
    today = dt.datetime.now(dt.timezone.utc).date()
    start_dt = dt.datetime.combine(START_DATE, dt.time.min, tzinfo=dt.timezone.utc).isoformat()
    end_dt = dt.datetime.combine(today, dt.time.max, tzinfo=dt.timezone.utc).isoformat()
    query = """
      query($login: String!, $from: DateTime!, $to: DateTime!) {
        user(login: $login) {
          contributionsCollection(from: $from, to: $to) {
            contributionCalendar {
              totalContributions
              weeks {
                contributionDays {
                  date
                  contributionCount
                  weekday
                }
              }
            }
          }
        }
      }
    """
    data = graphql(query, {"login": USERNAME, "from": start_dt, "to": end_dt})
    weeks = data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = []
    for week_index, week in enumerate(weeks):
        for raw in week["contributionDays"]:
            date = dt.date.fromisoformat(raw["date"])
            if START_DATE <= date <= today:
                days.append(
                    {
                        "date": date,
                        "count": int(raw["contributionCount"]),
                        "weekday": int(raw["weekday"]),
                        "week": week_index,
                    }
                )

    total = sum(day["count"] for day in days)
    active_days = sum(1 for day in days if day["count"] > 0)
    best_day = max(days, key=lambda day: day["count"]) if days else {"date": today, "count": 0}
    current = current_streak(days)
    longest = longest_streak(days)

    month_totals = OrderedDict()
    for day in days:
        key = day["date"].strftime("%b")
        month_totals[key] = month_totals.get(key, 0) + day["count"]

    unique_weeks = []
    for day in days:
        if day["week"] not in unique_weeks:
            unique_weeks.append(day["week"])
    week_offsets = {week: i for i, week in enumerate(unique_weeks)}

    width, height = 900, 360
    cell, gap = 15, 5
    heat_x, heat_y = 42, 174
    month_labels = []
    seen_months = set()
    for day in days:
        label = day["date"].strftime("%b")
        if label not in seen_months:
            seen_months.add(label)
            x = heat_x + week_offsets[day["week"]] * (cell + gap)
            month_labels.append(text(x, heat_y - 14, label, size=12, fill="#8B949E", weight=600))

    cells = []
    for day in days:
        x = heat_x + week_offsets[day["week"]] * (cell + gap)
        y = heat_y + day["weekday"] * (cell + gap)
        cells.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="4" '
            f'fill="{color_for(day["count"])}">'
            f'<title>{day["date"].isoformat()}: {day["count"]} contributions</title>'
            f"</rect>"
        )

    stat_cards = [
        ("Focused total", fmt_count(total), "since Feb 2026"),
        ("Active days", str(active_days), f"{len(days)} day window"),
        ("Best day", str(best_day["count"]), best_day["date"].strftime("%b %d")),
        ("Current streak", str(current), f"longest {longest} days"),
    ]
    cards = []
    for i, (label, value, detail) in enumerate(stat_cards):
        x = 42 + i * 206
        cards.append(f'<rect x="{x}" y="78" width="188" height="72" rx="12" fill="#161B22" stroke="#30363D"/>')
        cards.append(text(x + 16, 103, label, size=12, fill="#8B949E", weight=600))
        cards.append(text(x + 16, 132, value, size=26, fill="#70A5FD" if i != 0 else "#50FA7B", weight=800))
        cards.append(text(x + 92, 132, detail, size=12, fill="#B7C7E6", weight=500))

    max_month = max(month_totals.values()) if month_totals else 1
    bars = []
    chart_x, chart_y = 520, 185
    chart_w, chart_h = 320, 112
    bars.append(text(chart_x, chart_y - 22, "Monthly ramp", size=14, fill="#E6EDF3", weight=700))
    bars.append(text(chart_x + chart_w, chart_y - 22, "Feb 2026 -> now", size=12, fill="#8B949E", weight=600, anchor="end"))
    bar_gap = 18
    bar_width = (chart_w - (len(month_totals) - 1) * bar_gap) / max(len(month_totals), 1)
    for i, (month, count) in enumerate(month_totals.items()):
        h = max(4, chart_h * count / max_month)
        x = chart_x + i * (bar_width + bar_gap)
        y = chart_y + chart_h - h
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{h:.1f}" rx="7" fill="url(#barGradient)"/>')
        bars.append(text(x + bar_width / 2, chart_y + chart_h + 24, month, size=12, fill="#8B949E", weight=600, anchor="middle"))
        bars.append(text(x + bar_width / 2, y - 8, fmt_count(count), size=12, fill="#E6EDF3", weight=700, anchor="middle"))

    legend_x, legend_y = 42, 325
    legend = [text(legend_x, legend_y, "Less", size=11, fill="#8B949E", weight=600)]
    for i, c in enumerate(["#242938", "#173B57", "#3178C6", "#70A5FD", "#BF91F3", "#50FA7B"]):
        legend.append(f'<rect x="{legend_x + 38 + i * 20}" y="{legend_y - 11}" width="13" height="13" rx="3" fill="{c}"/>')
    legend.append(text(legend_x + 166, legend_y, "More", size=11, fill="#8B949E", weight=600))

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">2026 GitHub build sprint for {esc(USERNAME)}</title>
  <desc id="desc">Focused contribution heatmap and monthly ramp from February 2026 to today.</desc>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="{width}" y2="{height}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#0D1117"/>
      <stop offset="0.55" stop-color="#101827"/>
      <stop offset="1" stop-color="#16213A"/>
    </linearGradient>
    <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#50FA7B"/>
      <stop offset="0.5" stop-color="#70A5FD"/>
      <stop offset="1" stop-color="#BF91F3"/>
    </linearGradient>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="10" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  <rect width="{width}" height="{height}" rx="18" fill="url(#bg)"/>
  <circle cx="778" cy="36" r="94" fill="#70A5FD" opacity="0.08" filter="url(#glow)"/>
  {text(42, 42, "2026 Build Sprint", size=26, fill="#E6EDF3", weight=800)}
  {text(42, 65, f"Focused activity window: {START_DATE.strftime('%b %d, %Y')} -> {today.strftime('%b %d, %Y')}", size=13, fill="#8B949E", weight=600)}
  {"".join(cards)}
  {"".join(month_labels)}
  {"".join(cells)}
  {"".join(bars)}
  {"".join(legend)}
  {text(858, 346, "Generated daily from GitHub Contributions API", size=11, fill="#8B949E", weight=600, anchor="end")}
</svg>
"""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    main()
