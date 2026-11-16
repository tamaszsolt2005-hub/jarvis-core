"""Decision-quality guidance for JARVIS business recommendations.

This module only selects response guidance; it never changes business data.
"""
from __future__ import annotations

_DECISION_TERMS = (
    "érdemes", "erdemes", "döntés", "dontes", "válasszak", "valasszak",
    "melyiket", "melyik legyen", "hasonlítsd össze", "hasonlitsd ossze",
    "stratégia", "strategia", "befekt", "terjeszked", "árajánlat",
    "árazás", "arazas", "üzleti ötlet", "uzleti otlet", "megéri", "megeri",
    "javasolj", "ajánlj", "ajanlj", "prioritás", "prioritas",
)


def decision_support_instructions(question: str) -> str:
    """Return a compact, evidence-led decision review when the user asks for advice."""
    normalized = (question or "").casefold()
    if not any(term in normalized for term in _DECISION_TERMS):
        return ""
    return (
        "DÖNTÉSTÁMOGATÁSI MÓD: ha a kérdés döntést, választást vagy üzleti javaslatot kér, "
        "ne csak megerősítsd a felhasználó ötletét. Először fogalmazd meg a döntést és a kívánt "
        "eredményt. Válaszd szét a rendelkezésre álló bizonyítékot, a feltételezéseket és az "
        "ismeretlen tényezőket. Vizsgáld meg legalább a javasolt irányt és egy érdemi alternatívát; "
        "ha nincs elég adat, ne találj ki alternatívákhoz számokat. Mutasd be a várható előnyt, "
        "költséget/erőforrásigényt, fő kockázatot, visszafordíthatóságot és azt, milyen bizonyíték "
        "változtatná meg a javaslatodat. Keress ellenérvet és cáfold vagy fogadd el az adatok alapján. "
        "Adj biztonságos, kis költségű validációs lépést, mérhető sikerkritériummal és leállítási "
        "feltétellel. A végén adj egyértelmű ajánlást és bizonyossági szintet (alacsony/közepes/magas), "
        "a bizonyosság indoklásával. Ne adj hamis pontosságú ROI-, bevétel- vagy konverzióbecslést; "
        "ha számolni nem lehet, nevezd meg a hiányzó adatokat."
    )
