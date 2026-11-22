"""Modelos ORM (tabelas do SQLite)."""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Specialty(Base):
    __tablename__ = "specialties"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    short_name: Mapped[str] = mapped_column(String(40))
    summary: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    modalities: Mapped[list[str]] = mapped_column(JSON, default=list)   # ["Presencial", "Teleconsulta"]
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)     # usados pelo assistente
    position: Mapped[int] = mapped_column(Integer, default=0)

    doctors: Mapped[list[Doctor]] = relationship(back_populates="specialty", order_by="Doctor.position")


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    first_name: Mapped[str] = mapped_column(String(40))
    specialty_id: Mapped[int] = mapped_column(ForeignKey("specialties.id"))
    specialty_label: Mapped[str] = mapped_column(String(60))
    credential: Mapped[str] = mapped_column(String(80))   # CRM/RQE/CRP/CRN
    modalities: Mapped[list[str]] = mapped_column(JSON, default=list)
    photo_url: Mapped[str] = mapped_column(String(300))
    bio: Mapped[str] = mapped_column(String(240))
    about: Mapped[str] = mapped_column(Text)
    education: Mapped[list[str]] = mapped_column(JSON, default=list)
    focus_areas: Mapped[list[str]] = mapped_column(JSON, default=list)
    languages: Mapped[list[str]] = mapped_column(JSON, default=list)
    schedule: Mapped[list[str]] = mapped_column(JSON, default=list)
    years_experience: Mapped[int] = mapped_column(Integer, default=0)
    position: Mapped[int] = mapped_column(Integer, default=0)

    specialty: Mapped[Specialty] = relationship(back_populates="doctors")

    @property
    def specialty_slug(self) -> str:
        return self.specialty.slug


class Insurance(Base):
    __tablename__ = "insurances"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    note: Mapped[str] = mapped_column(String(80))
    monogram: Mapped[str] = mapped_column(String(4))
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)


class Faq(Base):
    __tablename__ = "faqs"

    id: Mapped[int] = mapped_column(primary_key=True)
    question: Mapped[str] = mapped_column(String(200))
    answer: Mapped[str] = mapped_column(Text)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    position: Mapped[int] = mapped_column(Integer, default=0)


class Appointment(Base):
    """Pré-agendamento. Guarda apenas dados administrativos (LGPD): nada de sintomas ou histórico."""

    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    protocol: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    patient_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20))
    specialty_id: Mapped[int] = mapped_column(ForeignKey("specialties.id"))
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"), nullable=True)
    modality: Mapped[str] = mapped_column(String(20))
    insurance: Mapped[str] = mapped_column(String(80))
    preferred_date: Mapped[date] = mapped_column(Date)
    period: Mapped[str] = mapped_column(String(40))
    consent: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="pendente")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    specialty: Mapped[Specialty] = relationship()
    doctor: Mapped[Doctor | None] = relationship()
