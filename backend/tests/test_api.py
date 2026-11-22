from datetime import timedelta

import pytest

from app.routers.appointments import today_brt


def next_weekday(target: int):
    """Próxima data (a partir de amanhã) com o dia da semana pedido (0=segunda ... 6=domingo)."""
    day = today_brt() + timedelta(days=1)
    while day.weekday() != target:
        day += timedelta(days=1)
    return day


def payload(**overrides):
    data = {
        "patient_name": "Maria da Silva",
        "phone": "(19) 99999-1234",
        "specialty": "cardiologia",
        "doctor": "mariana-albuquerque",
        "modality": "Presencial",
        "insurance": "unimed",
        "preferred_date": next_weekday(1).isoformat(),
        "period": "manha",
        "consent": True,
    }
    data.update(overrides)
    return data


def test_health_and_site(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    site = client.get("/")
    assert site.status_code == 200 and "Clínica" in site.text


def test_catalog(client):
    specs = client.get("/api/specialties").json()
    assert len(specs) == 6
    cardio = next(s for s in specs if s["slug"] == "cardiologia")
    assert cardio["modalities"] == ["Presencial"]
    assert cardio["doctors"][0]["slug"] == "mariana-albuquerque"

    doctors = client.get("/api/doctors").json()
    assert len(doctors) == 6 and doctors[0]["specialty_slug"] == "clinica-geral"
    assert client.get("/api/doctors?specialty=pediatria").json()[0]["name"] == "Dra. Camila Nogueira"
    assert client.get("/api/doctors/sofia-monteiro").json()["education"]
    assert client.get("/api/doctors/nao-existe").status_code == 404

    assert len(client.get("/api/insurances").json()) == 8
    assert len(client.get("/api/faqs").json()) >= 4


def test_create_and_lookup_appointment(client):
    res = client.post("/api/appointments", json=payload())
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["protocol"].startswith("CV-") and body["status"] == "pendente"
    assert body["patient_first_name"] == "Maria" and "phone" not in body

    status = client.get(f"/api/appointments/{body['protocol']}").json()
    assert status["specialty"] == "Cardiologia" and "patient_name" not in status

    assert client.get("/api/appointments").status_code == 401
    admin = client.get("/api/appointments", headers={"X-Admin-Token": "token-de-teste"})
    assert admin.status_code == 200 and admin.json()[0]["phone"] == "(19) 99999-1234"


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"phone": "19999991234"}, "phone"),
        ({"patient_name": "Jo"}, "patient_name"),
        ({"consent": False}, "consent"),
        ({"specialty": "ortopedia"}, "specialty"),
        ({"doctor": "camila-nogueira"}, "doctor"),                 # pediatra em cardiologia
        ({"modality": "Teleconsulta"}, "modality"),                # cardiologia é só presencial
        ({"insurance": "plano-x"}, "insurance"),
        ({"preferred_date": next_weekday(6).isoformat()}, "preferred_date"),   # domingo
        ({"preferred_date": next_weekday(5).isoformat(), "period": "tarde"}, "period"),  # sábado à tarde
        ({"preferred_date": (today_brt() - timedelta(days=1)).isoformat()}, "preferred_date"),
    ],
)
def test_appointment_rules(client, overrides, field):
    res = client.post("/api/appointments", json=payload(**overrides))
    assert res.status_code == 422, res.text
    assert res.json()["detail"][0]["field"] == field


def test_no_doctor_preference_and_other_insurance(client):
    res = client.post("/api/appointments", json=payload(
        specialty="psicologia", doctor="", modality="Teleconsulta", insurance="outro"))
    assert res.status_code == 201, res.text
    assert res.json()["doctor"].startswith("Sem preferência")
    assert res.json()["insurance"] == "Outro convênio (reembolso)"
