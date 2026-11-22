import pytest


def ask(client, message):
    res = client.post("/api/assistant/chat", json={"message": message})
    assert res.status_code == 200, res.text
    return res.json()


@pytest.mark.parametrize(
    ("message", "intent"),
    [
        ("Oi", "saudacao"),
        ("bom dia!", "saudacao"),
        ("Estou com dor no peito e falta de ar", "emergencia"),
        ("não quero mais viver", "apoio_emocional"),
        ("estou com dor de cabeça, que remédio tomo?", "sintomas"),
        ("Vocês aceitam Unimed?", "convenio"),
        ("quais convênios vocês atendem?", "convenio"),
        ("aceita hapvida?", "convenio"),
        ("vocês aceitam Golden Cross?", "convenio"),
        ("Qual o horário de funcionamento?", "horario"),
        ("abre sábado?", "horario"),
        ("onde fica a clínica?", "localizacao"),
        ("quero agendar", "agendamento"),
        ("Agendar Cardiologia", "agendamento"),
        ("quero marcar consulta com a Dra. Sofia", "agendamento"),
        ("Quais especialidades vocês têm?", "especialidades"),
        ("dermatologia atende online?", "modalidade"),
        ("quem é o pediatra?", "profissionais"),
        ("me fala da Beatriz", "profissional"),
        ("quanto custa a consulta?", "valores"),
        ("quais documentos preciso levar?", "faq"),
        ("posso remarcar minha consulta?", "faq"),
        ("tem estacionamento?", "faq"),
        ("como funciona a teleconsulta?", "faq"),
        ("telefone da recepção", "contato"),
        ("obrigado!", "agradecimento"),
        ("tem pediatra que atende sábado?", "agenda_profissional"),
        ("vocês fazem exame de sangue?", "exames"),
        ("qual a capital da França?", "desconhecido"),
    ],
)
def test_intents(client, message, intent):
    assert ask(client, message)["intent"] == intent


def test_booking_action_prefills_form(client):
    data = ask(client, "quero agendar pediatria")
    action = data["actions"][0]
    assert action["type"] == "book" and action["specialty"] == "pediatria"


def test_doctor_booking_action(client):
    data = ask(client, "agendar com o Lucas")
    assert data["actions"][0] == {**data["actions"][0], "type": "book", "doctor": "lucas-ferraz", "specialty": "nutricao"}


def test_symptom_routes_to_specialty_without_diagnosis(client):
    data = ask(client, "estou com uma mancha na pele")
    assert "Dermatologia" in data["reply"] and "diagnóstico" in data["reply"]
    assert data["actions"][0]["specialty"] == "dermatologia"


def test_cardiology_presential_only(client):
    data = ask(client, "cardiologia tem teleconsulta?")
    assert "apenas presencial" in data["reply"]


def test_protocol_lookup(client):
    from tests.test_api import payload

    protocol = client.post("/api/appointments", json=payload()).json()["protocol"]
    data = ask(client, f"qual o status do protocolo {protocol}?")
    assert data["intent"] == "protocolo" and "pendente" in data["reply"]
    assert "não encontrei" in ask(client, "protocolo CV-ZZZZZZ")["reply"].lower()


def test_status_endpoint(client):
    assert client.get("/api/assistant/status").json()["llm"] is False


def test_unknown_insurance_is_not_confirmed(client):
    reply = ask(client, "aceita hapvida?")["reply"]
    assert "Não encontrei esse plano" in reply
