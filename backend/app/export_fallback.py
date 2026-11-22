"""Gera frontend/js/fallback-data.js a partir de seed_data.py.

Assim o site continua funcionando (modo offline / GitHub Pages) com os mesmos dados do banco.
Uso:  python -m app.export_fallback
"""
from __future__ import annotations

import json

from .config import FRONTEND_DIR
from .seed_data import CLINIC_INFO, DOCTORS, FAQS, INSURANCES, SPECIALTIES, UNSPLASH


def build() -> dict:
    doctors = []
    for d in DOCTORS:
        item = {k: v for k, v in d.items() if k not in {"photo", "specialty"}}
        item.update(specialty_slug=d["specialty"], photo_url=UNSPLASH.format(id=d["photo"]))
        doctors.append(item)

    specialties = []
    for s in SPECIALTIES:
        specialties.append({
            **{k: s[k] for k in ("slug", "name", "short_name", "summary", "description", "modalities", "keywords")},
            "doctors": [{"slug": d["slug"], "name": d["name"], "first_name": d["first_name"],
                         "modalities": d["modalities"]} for d in DOCTORS if d["specialty"] == s["slug"]],
        })

    return {
        "clinic": CLINIC_INFO,
        "specialties": specialties,
        "doctors": doctors,
        "insurances": [{"is_private": False, **i} for i in INSURANCES],
        "faqs": [{"id": n + 1, **f} for n, f in enumerate(FAQS)],
    }


def main() -> None:
    target = FRONTEND_DIR / "js" / "fallback-data.js"
    payload = json.dumps(build(), ensure_ascii=False, indent=2)
    target.write_text(
        "/* Gerado por backend/app/export_fallback.py — não edite à mão.\n"
        "   Usado quando a API FastAPI não está disponível (ex.: abrir o index.html direto). */\n"
        f"window.CLINIC_FALLBACK = {payload};\n",
        encoding="utf-8",
    )
    print(f"Arquivo gerado: {target}")


if __name__ == "__main__":
    main()
