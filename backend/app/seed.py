"""Cria as tabelas e popula o SQLite com os dados demonstrativos (idempotente).

Uso:  python -m app.seed          (popula se estiver vazio)
      python -m app.seed --reset  (apaga e recria tudo)
"""
from __future__ import annotations

import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .database import Base, SessionLocal, engine
from .seed_data import DOCTORS, FAQS, INSURANCES, SPECIALTIES, UNSPLASH


def seed(db: Session) -> bool:
    """Popula o banco caso ainda não existam especialidades. Retorna True se inseriu dados."""
    if db.scalar(select(models.Specialty.id).limit(1)) is not None:
        return False

    by_slug: dict[str, models.Specialty] = {}
    for position, data in enumerate(SPECIALTIES):
        spec = models.Specialty(position=position, **data)
        db.add(spec)
        by_slug[spec.slug] = spec
    db.flush()

    for position, data in enumerate(DOCTORS):
        payload = dict(data)
        specialty = by_slug[payload.pop("specialty")]
        photo = payload.pop("photo")
        db.add(models.Doctor(position=position, specialty_id=specialty.id,
                             photo_url=UNSPLASH.format(id=photo), **payload))

    for position, data in enumerate(INSURANCES):
        db.add(models.Insurance(position=position, **data))

    for position, data in enumerate(FAQS):
        db.add(models.Faq(position=position, **data))

    db.commit()
    return True


def init_db(reset: bool = False) -> None:
    if reset:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed(db)


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    init_db(reset=reset)
    print("Banco de dados pronto" + (" (recriado)." if reset else "."))
