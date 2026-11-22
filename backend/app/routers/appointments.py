"""Rotas de pré-agendamento, com as mesmas regras de negócio exibidas no formulário."""
from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..security import rate_limit, require_admin

router = APIRouter(prefix="/api/appointments", tags=["pré-agendamento"])

BRT = timezone(timedelta(hours=-3))          # Brasil sem horário de verão desde 2019
MAX_DAYS_AHEAD = 120
PROTOCOL_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # sem 0/O e 1/I para evitar confusão
OTHER_INSURANCE = ("outro", "Outro convênio (reembolso)")


class FieldError(HTTPException):
    """Erro de regra de negócio no mesmo formato dos erros de validação (campo + mensagem)."""

    def __init__(self, field: str, msg: str) -> None:
        super().__init__(status_code=422, detail=[{"field": field, "msg": msg}])


def today_brt() -> date:
    return datetime.now(BRT).date()


def _new_protocol(db: Session) -> str:
    while True:
        code = "CV-" + "".join(secrets.choice(PROTOCOL_ALPHABET) for _ in range(6))
        if not db.scalar(select(models.Appointment.id).where(models.Appointment.protocol == code)):
            return code


def _to_out(appt: models.Appointment) -> dict:
    return {
        "protocol": appt.protocol,
        "status": appt.status,
        "patient_first_name": appt.patient_name.split(" ")[0],
        "specialty": appt.specialty.name,
        "doctor": appt.doctor.name if appt.doctor else "Sem preferência (primeiro horário)",
        "modality": appt.modality,
        "insurance": appt.insurance,
        "preferred_date": appt.preferred_date,
        "period": appt.period,
        "created_at": appt.created_at,
        "patient_name": appt.patient_name,
        "phone": appt.phone,
    }


@router.post("", response_model=schemas.AppointmentOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit)])
def create_appointment(payload: schemas.AppointmentCreate, db: Session = Depends(get_db)):
    specialty = db.scalar(select(models.Specialty).where(models.Specialty.slug == payload.specialty))
    if not specialty:
        raise FieldError("specialty", "Especialidade não encontrada.")

    doctor = None
    if payload.doctor:
        doctor = db.scalar(select(models.Doctor).where(models.Doctor.slug == payload.doctor))
        if not doctor or doctor.specialty_id != specialty.id:
            raise FieldError("doctor", "Profissional não atende a especialidade escolhida.")

    allowed = doctor.modalities if doctor else specialty.modalities
    if payload.modality not in allowed:
        raise FieldError("modality", f"{specialty.name} é atendida apenas na modalidade: {', '.join(allowed)}.")

    if payload.insurance == OTHER_INSURANCE[0]:
        insurance_name = OTHER_INSURANCE[1]
    else:
        insurance = db.scalar(select(models.Insurance).where(models.Insurance.slug == payload.insurance))
        if not insurance:
            raise FieldError("insurance", "Convênio não reconhecido.")
        insurance_name = insurance.name

    today = today_brt()
    if payload.preferred_date < today:
        raise FieldError("preferred_date", "Não é possível escolher datas que já passaram.")
    if payload.preferred_date > today + timedelta(days=MAX_DAYS_AHEAD):
        raise FieldError("preferred_date", f"Escolha uma data em até {MAX_DAYS_AHEAD} dias.")
    weekday = payload.preferred_date.weekday()      # 0 = segunda ... 6 = domingo
    if weekday == 6:
        raise FieldError("preferred_date", "A clínica não funciona aos domingos.")
    if weekday == 5 and payload.period == "tarde":
        raise FieldError("period", "Aos sábados atendemos apenas no período da manhã.")

    appt = models.Appointment(
        protocol=_new_protocol(db),
        patient_name=payload.patient_name,
        phone=payload.phone,
        specialty_id=specialty.id,
        doctor_id=doctor.id if doctor else None,
        modality=payload.modality,
        insurance=insurance_name,
        preferred_date=payload.preferred_date,
        period=schemas.PERIOD_LABELS[payload.period],
        consent=payload.consent,
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)
    return _to_out(appt)


@router.get("/{protocol}", response_model=schemas.AppointmentStatusOut)
def appointment_status(protocol: str, db: Session = Depends(get_db)):
    """Consulta pública de status: devolve só o essencial, sem nome nem telefone."""
    appt = db.scalar(select(models.Appointment).where(models.Appointment.protocol == protocol.upper().strip()))
    if not appt:
        raise HTTPException(status_code=404, detail="Protocolo não encontrado.")
    return {
        "protocol": appt.protocol,
        "status": appt.status,
        "specialty": appt.specialty.name,
        "preferred_date": appt.preferred_date,
        "period": appt.period,
    }


@router.get("", response_model=list[schemas.AppointmentAdminOut], dependencies=[Depends(require_admin)])
def list_appointments(db: Session = Depends(get_db)):
    """Lista para a recepção (exige cabeçalho X-Admin-Token)."""
    rows = db.scalars(select(models.Appointment).order_by(models.Appointment.created_at.desc())).all()
    return [_to_out(a) for a in rows]
