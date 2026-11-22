"""Schemas Pydantic (contratos de entrada e saída da API)."""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PHONE_RE = re.compile(r"^\(\d{2}\) \d{4,5}-\d{4}$")
NAME_RE = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ' .-]+$")

PERIOD_LABELS = {"manha": "Manhã (08h às 12h)", "tarde": "Tarde (13h às 19h)"}


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Catálogo ----------
class DoctorBrief(ORMModel):
    slug: str
    name: str
    first_name: str
    modalities: list[str]


class SpecialtyOut(ORMModel):
    slug: str
    name: str
    short_name: str
    summary: str
    description: str
    modalities: list[str]
    doctors: list[DoctorBrief]


class DoctorOut(ORMModel):
    slug: str
    name: str
    first_name: str
    specialty_slug: str
    specialty_label: str
    credential: str
    modalities: list[str]
    photo_url: str
    bio: str
    about: str
    education: list[str]
    focus_areas: list[str]
    languages: list[str]
    schedule: list[str]
    years_experience: int


class InsuranceOut(ORMModel):
    slug: str
    name: str
    note: str
    monogram: str
    keywords: list[str]
    is_private: bool


class FaqOut(ORMModel):
    id: int
    question: str
    answer: str


class ClinicInfoOut(BaseModel):
    name: str
    address: str
    phone: str
    whatsapp: str
    email: str
    hours: dict[str, str]
    amenities: list[str]


# ---------- Pré-agendamento ----------
class AppointmentCreate(BaseModel):
    patient_name: str = Field(min_length=3, max_length=120)
    phone: str
    specialty: str = Field(max_length=40, description="slug da especialidade")
    doctor: str | None = Field(default=None, max_length=60, description="slug do profissional ou vazio")
    modality: Literal["Presencial", "Teleconsulta"]
    insurance: str = Field(max_length=40, description="slug do convênio ou 'outro'")
    preferred_date: date
    period: Literal["manha", "tarde"]
    consent: bool

    @field_validator("patient_name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 3 or not NAME_RE.match(value):
            raise ValueError("Informe um nome válido (apenas letras e espaços).")
        return value

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str) -> str:
        value = value.strip()
        if not PHONE_RE.match(value):
            raise ValueError("Telefone deve estar no formato (19) 99999-9999.")
        return value

    @field_validator("doctor")
    @classmethod
    def _doctor(cls, value: str | None) -> str | None:
        return value or None

    @field_validator("consent")
    @classmethod
    def _consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("É necessário concordar com o uso dos dados de contato.")
        return value


class AppointmentOut(BaseModel):
    protocol: str
    status: str
    patient_first_name: str
    specialty: str
    doctor: str
    modality: str
    insurance: str
    preferred_date: date
    period: str
    created_at: datetime


class AppointmentAdminOut(AppointmentOut):
    patient_name: str
    phone: str


class AppointmentStatusOut(BaseModel):
    protocol: str
    status: str
    specialty: str
    preferred_date: date
    period: str


# ---------- Assistente ----------
class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=1200)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=600)
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)


class ChatAction(BaseModel):
    type: Literal["book", "open_doctor", "filter_team", "scroll", "link"]
    label: str
    specialty: str | None = None
    doctor: str | None = None
    target: str | None = None
    href: str | None = None


class ChatResponse(BaseModel):
    reply: str
    intent: str
    source: Literal["regras", "faq", "llm"]
    suggestions: list[str] = Field(default_factory=list)
    actions: list[ChatAction] = Field(default_factory=list)
