"""Rotas de leitura: especialidades, profissionais, convênios, FAQ e dados da clínica."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models, schemas
from ..database import get_db
from ..seed_data import CLINIC_INFO

router = APIRouter(prefix="/api", tags=["catálogo"])


@router.get("/clinic", response_model=schemas.ClinicInfoOut)
def clinic_info():
    return CLINIC_INFO


@router.get("/specialties", response_model=list[schemas.SpecialtyOut])
def list_specialties(db: Session = Depends(get_db)):
    stmt = select(models.Specialty).options(selectinload(models.Specialty.doctors)).order_by(models.Specialty.position)
    return db.scalars(stmt).all()


@router.get("/doctors", response_model=list[schemas.DoctorOut])
def list_doctors(specialty: str | None = None, db: Session = Depends(get_db)):
    stmt = select(models.Doctor).options(selectinload(models.Doctor.specialty)).order_by(models.Doctor.position)
    if specialty:
        stmt = stmt.join(models.Specialty).where(models.Specialty.slug == specialty)
    return db.scalars(stmt).all()


@router.get("/doctors/{slug}", response_model=schemas.DoctorOut)
def get_doctor(slug: str, db: Session = Depends(get_db)):
    doctor = db.scalar(select(models.Doctor).where(models.Doctor.slug == slug))
    if not doctor:
        raise HTTPException(status_code=404, detail="Profissional não encontrado.")
    return doctor


@router.get("/insurances", response_model=list[schemas.InsuranceOut])
def list_insurances(db: Session = Depends(get_db)):
    return db.scalars(select(models.Insurance).order_by(models.Insurance.position)).all()


@router.get("/faqs", response_model=list[schemas.FaqOut])
def list_faqs(db: Session = Depends(get_db)):
    return db.scalars(select(models.Faq).order_by(models.Faq.position)).all()
