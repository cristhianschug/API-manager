"""Token status reporter: OmniRoute free tiers only (real data)"""
import sys
import json
import urllib.request
from datetime import datetime, timedelta

OMNIROUTE_URL = "http://localhost:20128"


def fetch(path: str):
    try:
        req = urllib.request.Request(f"{OMNIROUTE_URL}{path}", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as r:
            return json.loads(r.read())
    except Exception:
        return None


def bar(pct: float, width: int = 20) -> str:
    filled = int(width * pct / 100)
    return "#" * filled + "-" * (width - filled)


def fmt(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def next_renewal(period: str) -> str:
    now = datetime.now()
    if period == "daily":
        next_r = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        delta = next_r - now
        h, m = divmod(int(delta.total_seconds() // 60), 60)
        return f"{next_r.strftime('%d/%m')} 00:00 (em {h}h{m:02d}m)"
    if period == "weekly":
        days_until_monday = (7 - now.weekday()) % 7 or 7
        next_r = (now + timedelta(days=days_until_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        delta = next_r - now
        d = delta.days
        h, m = divmod(int((delta.total_seconds() % 86400) // 60), 60)
        return f"{next_r.strftime('%d/%m')} 00:00 (em {d}d {h}h{m:02d}m)"
    return "N/A"


def report_short():
    online = fetch("/dashboard") is not None
    if not online:
        print("\n[GRATIS] OmniRoute OFFLINE - inicie com: npx omniroute\n")
        return

    data = fetch("/api/free-tiers/summary")
    if data:
        daily_rem   = data.get("daily_remaining", 0)
        daily_total = data.get("daily_total", 1)
        pct = daily_rem / daily_total * 100
        print(f"\n[GRATIS] OmniRoute online | Diario: [{bar(pct,14)}] {pct:.0f}% ({fmt(daily_rem)} restantes)\n")
    else:
        print("\n[GRATIS] OmniRoute online | dados detalhados indisponiveis\n")


def report_full():
    sep = "=" * 55
    thin = "-" * 55
    print(f"\n{sep}")
    print(f"  OMNIROUTE - TOKEN STATUS  |  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Tokens gratuitos - sua API Anexar")
    print(sep)

    online = fetch("/dashboard") is not None
    if not online:
        print("\n  STATUS: OFFLINE")
        print(f"  Inicie com: npx omniroute")
        print(f"  Dashboard : {OMNIROUTE_URL}")
        print(f"\n{sep}\n")
        return

    data = fetch("/api/free-tiers/summary")
    if data:
        daily_rem    = data.get("daily_remaining", 0)
        daily_total  = data.get("daily_total", 1)
        weekly_rem   = data.get("weekly_remaining", 0)
        weekly_total = data.get("weekly_total", 1)
        monthly_rem  = data.get("monthly_remaining", 0)
        monthly_total = data.get("monthly_total", 1_470_000_000)

        dp = daily_rem / daily_total * 100
        wp = weekly_rem / weekly_total * 100
        mp = monthly_rem / monthly_total * 100

        print(f"\n  STATUS: ONLINE\n  {thin}")
        print(f"  Diario    : {fmt(daily_rem):>8} / {fmt(daily_total):<9} [{bar(dp,16)}] {dp:5.1f}%")
        print(f"  Semanal   : {fmt(weekly_rem):>8} / {fmt(weekly_total):<9} [{bar(wp,16)}] {wp:5.1f}%")
        print(f"  Mensal    : {fmt(monthly_rem):>8} / {fmt(monthly_total):<9} [{bar(mp,16)}] {mp:5.1f}%")
        print(f"\n  {thin}")
        print(f"  Prox. renovacao diaria  : {next_renewal('daily')}")
        print(f"  Prox. renovacao semanal : {next_renewal('weekly')}")
    else:
        print("\n  STATUS: ONLINE (sem dados detalhados neste endpoint)")

    print(f"\n  Dashboard  : {OMNIROUTE_URL}")
    print(f"  Free tiers : {OMNIROUTE_URL}/dashboard/free-tiers")
    print(f"\n{sep}\n")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "short"
    if mode == "full":
        report_full()
    else:
        report_short()
