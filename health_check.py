"""Read-only JARVIS runtime diagnostics; never mutates business data."""
from __future__ import annotations

from typing import Any

from jarvis_common import get_secret, get_supabase, get_gemini_client, get_model_name
from jarvis_errors import report_error


def _report_diagnostic_error(error: Exception, operation: str) -> None:
    # Diagnostics are read-only; keep failures local and never write to business tables.
    report_error(error, module="health_check", operation=operation, severity="warning")


REQUIRED_TABLES = (
    "leads",
    "tasks",
    "settings",
    "logs",
    "jarvis_memory",
    "jarvis_proactive_state",
    "email_drafts",
    "audit_chain_state",
)


def _check(label: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"label": label, "ok": bool(ok), "detail": str(detail)[:240]}


def run_self_diagnostics() -> str:
    """Probe configured integrations with bounded read-only checks and one tiny Gemini request."""
    checks: list[dict[str, Any]] = []

    supabase_url = get_secret("SUPABASE_URL")
    supabase_key = get_secret("SUPABASE_SERVICE_ROLE_KEY") or get_secret("SUPABASE_KEY")
    gemini_key = get_secret("GEMINI_API_KEY")
    dashboard_password = get_secret("JARVIS_DASHBOARD_PASSWORD")

    checks.append(_check("Supabase URL konfiguráció", bool(supabase_url), "Beállítva." if supabase_url else "Hiányzik a SUPABASE_URL."))
    checks.append(_check("Supabase API-kulcs konfiguráció", bool(supabase_key), "Beállítva; a tényleges jogosultságot a táblalekérdezések igazolják." if supabase_key else "Hiányzik a SUPABASE_SERVICE_ROLE_KEY vagy SUPABASE_KEY."))
    checks.append(_check("Gemini API-kulcs", bool(gemini_key), "Beállítva." if gemini_key else "Hiányzik a GEMINI_API_KEY."))
    checks.append(_check("Dashboard jelszó", bool(dashboard_password), "Beállítva." if dashboard_password else "Hiányzik a JARVIS_DASHBOARD_PASSWORD."))

    db = None
    if supabase_url and supabase_key:
        try:
            db = get_supabase()
            checks.append(_check("Supabase kapcsolat", True, "A kliens létrehozása sikerült."))
        except Exception as exc:
            _report_diagnostic_error(exc, "initialize_supabase")
            checks.append(_check("Supabase kapcsolat", False, f"Kapcsolat inicializálása sikertelen ({type(exc).__name__})."))
    else:
        checks.append(_check("Supabase kapcsolat", False, "A hiányzó konfiguráció miatt nem futott le."))

    if db is not None:
        for table in REQUIRED_TABLES:
            try:
                db.table(table).select("*").limit(1).execute()
                checks.append(_check(f"Supabase tábla: {table}", True, "Lekérdezhető (üres tábla is megfelelő)."))
            except Exception as exc:
                _report_diagnostic_error(exc, "probe_table")
                checks.append(_check(f"Supabase tábla: {table}", False, f"Nem kérdezhető le ({type(exc).__name__}); ellenőrizd a sémát és az RLS-hozzáférést."))
    else:
        for table in REQUIRED_TABLES:
            checks.append(_check(f"Supabase tábla: {table}", False, "A Supabase-kapcsolat hiánya miatt nem ellenőrizhető."))

    if db is not None:
        try:
            db.table("leads").select("website").limit(1).execute()
            checks.append(_check("Supabase oszlop: leads.website", True, "Az oszlop lekérdezhető."))
        except Exception as exc:
            _report_diagnostic_error(exc, "probe_leads_website")
            checks.append(_check("Supabase oszlop: leads.website", False, f"Hiányzó vagy nem lekérdezhető oszlop ({type(exc).__name__}); futtasd a website migrációt."))
    else:
        checks.append(_check("Supabase oszlop: leads.website", False, "A Supabase-kapcsolat hiánya miatt nem ellenőrizhető."))

    if db is not None:
        try:
            db.table("logs").select("level").limit(1).execute()
            checks.append(_check("Supabase oszlop: logs.level", True, "Az oszlop lekérdezhető."))
        except Exception as exc:
            _report_diagnostic_error(exc, "probe_logs_level")
            checks.append(_check("Supabase oszlop: logs.level", False, f"Hiányzó vagy nem lekérdezhető oszlop ({type(exc).__name__}); ellenőrizd a logs migrációt."))
    else:
        checks.append(_check("Supabase oszlop: logs.level", False, "A Supabase-kapcsolat hiánya miatt nem ellenőrizhető."))

    if db is not None:
        try:
            db.table("logs").select("operation_id").limit(1).execute()
            checks.append(_check("Supabase auditmezők: logs.operation_id", True, "A strukturált auditmező lekérdezhető."))
        except Exception as exc:
            _report_diagnostic_error(exc, "probe_logs_audit_fields")
            checks.append(_check("Supabase auditmezők: logs.operation_id", False, f"A strukturált auditmigráció hiányzik vagy nem érhető el ({type(exc).__name__})."))
    else:
        checks.append(_check("Supabase auditmezők: logs.operation_id", False, "A Supabase-kapcsolat hiánya miatt nem ellenőrizhető."))

    if gemini_key:
        try:
            client = get_gemini_client()
            response = client.models.generate_content(
                model=get_model_name(),
                contents="Válaszolj kizárólag ezzel: OK",
            )
            response_text = (getattr(response, "text", None) or "").strip()
            if response_text:
                checks.append(_check("Gemini API próbakérés", True, f"A(z) {get_model_name()} modell választ adott."))
            else:
                checks.append(_check("Gemini API próbakérés", False, "A modell üres választ adott."))
        except Exception as exc:
            _report_diagnostic_error(exc, "probe_gemini")
            checks.append(_check("Gemini API próbakérés", False, f"A próbakérés sikertelen ({type(exc).__name__})."))
    else:
        checks.append(_check("Gemini API próbakérés", False, "A hiányzó API-kulcs miatt nem futott le."))

    try:
        from email_utils import EMAIL_DELIVERY_ENABLED
        email_disabled = EMAIL_DELIVERY_ENABLED is False
        checks.append(_check("E-mail-küldési biztonsági zár", email_disabled,
                             "A küldés kódszinten letiltva." if email_disabled else "Figyelem: a küldési zár nincs tiltott állapotban."))
    except Exception as exc:
        _report_diagnostic_error(exc, "check_email_safety_lock")
        checks.append(_check("E-mail-küldési biztonsági zár", False, f"Nem ellenőrizhető ({type(exc).__name__})."))

    passed = sum(1 for item in checks if item["ok"])
    total = len(checks)
    lines = [
        "# JARVIS rendszerdiagnosztika",
        "",
        f"**Eredmény: {passed}/{total} ellenőrzés sikeres.**",
        "",
        "| Ellenőrzés | Állapot | Részlet |",
        "|---|---|---|",
    ]
    for item in checks:
        status = "OK" if item["ok"] else "FIGYELMET IGÉNYEL"
        detail = item["detail"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {item['label']} | {status} | {detail} |")
    lines += [
        "",
        "## Mit jelent az eredmény?",
        "- A táblák ellenőrzése csak egy korlátozott, olvasási lekérdezést végez; adatot nem módosít.",
        "- A Gemini-próbakérés egy rövid tesztkérést küldhet, amely API-használatot és költséget jelenthet.",
        "- A sikeres ellenőrzés az adott pillanatban elérhető integrációt jelzi, nem garantálja a folyamatos rendelkezésre állást.",
        "- A GitHub Actions ütemezéseket és a teljes éles üzleti folyamatokat ez a chatből indított vizsgálat nem futtatja le.",
        "- E-mailt nem küld, leadet és feladatot nem módosít.",
    ]
    return "\n".join(lines) + "\n"
