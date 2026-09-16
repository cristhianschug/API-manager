"""Token status reporter: Anthropic session + OmniRoute free tiers"""
import sys
import json
import urllib.request
from datetime import datetime, timedelta

OMNIROUTE_URL = "http://localhost:20128"
SESSION_TOTAL = 15_000_000


def fetch_omniroute(path: str):
    try:
        req = urllib.request.Request(f"{OMNIROUTE_URL}{path}", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as r:
            return json.loads(r.read())
    except Exception:
        return None


def bar(pct: float, width: int = 20) -> str:
    filled = int(width * pct / 100)
    return "#" * filled + "-" * (width - filled)


def fmt_tokens(n: int) -> str:
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
        return f"{next_r.strftime('%d/%m %H:%M')} (em {h}h{m:02d}m)"
    if period == "weekly":
        days_until_monday = (7 - now.weekday()) % 7 or 7
        next_r = (now + timedelta(days=days_until_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        delta = next_r - now
        days_left = delta.days
        h, m = divmod(int((delta.total_seconds() % 86400) // 60), 60)
        return f"{next_r.strftime('%d/%m')} (em {days_left}d {h}h{m:02d}m)"
    return "N/A"


def report_short(session_remaining: int):
    pct = session_remaining / SESSION_TOTAL * 100
    omni_ok = fetch_omniroute("/dashboard") is not None
    omni_status = "online" if omni_ok else "offline"
    print(
        f"\n{'='*53}\n"
        f"[PAGO]   Anthropic  [{bar(pct, 16)}] {pct:.1f}%  {fmt_tokens(session_remaining)} restantes\n"
        f"[GRATIS] OmniRoute  gateway {omni_status} | use /token-status para detalhes\n"
        f"{'='*53}"
    )


def report_full(session_remaining: int):
    pct = session_remaining / SESSION_TOTAL * 100
    used = SESSION_TOTAL - session_remaining

    sep = "=" * 55
    thin = "-" * 55
    print(f"\n{sep}")
    print(f"  TOKEN STATUS REPORT  |  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(sep)

    print("\n  [PAGO] ANTHROPIC  (cobrado na sua conta Anthropic)")
    print(f"  {thin}")
    print(f"  Restantes : {fmt_tokens(session_remaining):>8}  [{bar(pct, 22)}] {pct:5.1f}%")
    print(f"  Usados    : {fmt_tokens(used):>8}  de {fmt_tokens(SESSION_TOTAL)} (sessao atual)")
    print(f"  Renovacao : automatica ao iniciar nova sessao")

    print(f"\n  [GRATIS] OMNIROUTE  (tokens gratuitos - sua API)")
    print(f"  {thin}")

    data = fetch_omniroute("/api/free-tiers/summary")
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

        print(f"  Diario    : {fmt_tokens(daily_rem):>8} / {fmt_tokens(daily_total):<9} [{bar(dp, 14)}] {dp:5.1f}%")
        print(f"  Semanal   : {fmt_tokens(weekly_rem):>8} / {fmt_tokens(weekly_total):<9} [{bar(wp, 14)}] {wp:5.1f}%")
        print(f"  Mensal    : {fmt_tokens(monthly_rem):>8} / {fmt_tokens(monthly_total):<9} [{bar(mp, 14)}] {mp:5.1f}%")
        print(f"\n  Renovacao diaria  : {next_renewal('daily')}")
        print(f"  Renovacao semanal : {next_renewal('weekly')}")
    else:
        print("  Gateway   : OFFLINE ou sem dados da API")
        print("  Estimativa: ~1.47B tokens/mes disponiveis")
        print(f"  Diario (est.)  : ~49M tokens")
        print(f"  Semanal (est.) : ~343M tokens")
        print(f"\n  Prox. renovacao diaria  : {next_renewal('daily')}")
        print(f"  Prox. renovacao semanal : {next_renewal('weekly')}")

    print(f"\n  Dashboard  : http://localhost:20128")
    print(f"  Free tiers : http://localhost:20128/dashboard/free-tiers")
    print(f"\n{sep}\n")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "short"
    remaining = int(sys.argv[2]) if len(sys.argv) > 2 else SESSION_TOTAL

    if mode == "full":
        report_full(remaining)
    else:
        report_short(remaining)
