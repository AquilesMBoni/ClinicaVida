"""Motor do assistente virtual da Clínica Vida.

Funciona 100% offline com regras + busca no FAQ, usando o próprio banco SQLite como base de
conhecimento. Se um LLM compatível com a API da OpenAI estiver configurado (ex.: Ollama local),
ele é usado apenas como último recurso para perguntas que as regras não cobrem.

Guardrails: nunca faz diagnóstico nem indica medicamentos, e trata sinais de emergência
antes de qualquer outra coisa.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models
from ..schemas import ChatAction, ChatResponse, ChatTurn
from ..seed_data import CLINIC_INFO
from . import llm
from .text import contains_any, contains_prefix, normalize, tokens

PROTOCOL_RE = re.compile(r"\bCV-?([A-Z0-9]{6})\b", re.IGNORECASE)
TITLES = {"dr", "dra", "psi", "nutri", "doutor", "doutora"}

EMERGENCY_TERMS = [
    "dor no peito", "dor forte no peito", "aperto no peito", "falta de ar", "nao consigo respirar",
    "dificuldade para respirar", "desmaio", "desmaiou", "desmaiei", "convulsao", "convulsionando", "avc",
    "derrame", "infarto", "infartando", "sangramento forte", "sangrando muito", "hemorragia",
    "envenenamento", "intoxicacao", "overdose", "emergencia", "urgencia", "acidente", "boca torta",
    "perdi os movimentos", "inconsciente", "engasgado", "engasgou",
]
SELF_HARM_TERMS = [
    "suicidio", "suicida", "me matar", "quero morrer", "tirar minha vida", "tirar a minha vida",
    "nao quero mais viver", "acabar com tudo", "me machucar", "autolesao", "me cortar",
]
SYMPTOM_TERMS = [
    "estou com", "to com", "tou com", "sinto", "sentindo", "sintoma", "sintomas", "dor de", "doendo",
    "febre", "tosse", "remedio", "remedios", "medicamento", "medicacao", "posso tomar", "devo tomar",
    "diagnostico", "o que pode ser", "o que eu tenho", "e grave", "receita de",
]
SYMPTOM_TO_SPECIALTY = [
    (["pele", "mancha", "pinta", "acne", "espinha", "coceira", "alergia na pele", "cabelo", "unha", "caspa"], "dermatologia"),
    (["crianca", "bebe", "meu filho", "minha filha", "filho", "filha", "neto", "neta"], "pediatria"),
    (["ansiedade", "ansioso", "ansiosa", "estresse", "estressado", "tristeza", "triste", "depressao",
      "insonia", "panico", "angustia", "burnout"], "psicologia"),
    (["coracao", "pressao alta", "pressao", "palpitacao", "arritmia", "colesterol"], "cardiologia"),
    (["emagrecer", "dieta", "peso", "engordar", "alimentacao", "comer"], "nutricao"),
]

ONLINE_TERMS = ["online", "teleconsulta", "video", "videochamada", "remoto", "a distancia", "telemedicina", "presencial"]
INSURANCE_TERMS = ["convenio", "convenios", "plano", "planos", "plano de saude", "cobertura", "cobre",
                   "credenciado", "credenciada", "aceita", "aceitam", "atende plano", "operadora"]
HOURS_TERMS = ["horario", "horarios", "funciona", "funcionamento", "abre", "abrem", "fecha", "fecham",
               "aberto", "aberta", "expediente", "que horas", "sabado", "domingo", "feriado", "dias"]
LOCATION_TERMS = ["endereco", "onde fica", "onde e", "localizacao", "localiza", "como chegar", "rota",
                  "mapa", "bairro", "cambui", "chegar"]
CONTACT_TERMS = ["telefone", "whatsapp", "whats", "zap", "contato", "ligar", "email", "e-mail", "atendente",
                 "humano", "recepcao", "pessoa", "falar com alguem"]
PRICE_TERMS = ["valor", "valores", "preco", "precos", "quanto custa", "custa", "custo", "pagar", "pagamento",
               "pix", "cartao", "parcelar"]
DOCTOR_LIST_TERMS = ["medico", "medicos", "medica", "medicas", "profissional", "profissionais", "doutor",
                     "doutora", "especialista", "especialistas", "quem atende", "corpo clinico", "equipe",
                     "quem e", "quem sao", "nome do", "nome da", "pediatra", "cardiologista", "dermatologista",
                     "psicologo", "psicologa", "nutricionista", "clinico geral"]
SPECIALTY_LIST_TERMS = ["especialidade", "especialidades", "areas", "area", "o que voces atendem",
                        "quais atendimentos", "servicos", "atendem o que"]
EXAM_TERMS = ["exame", "exames", "coleta", "laboratorio", "ultrassom", "raio x", "eletrocardiograma", "resultado"]
PRIVACY_TERMS = ["lgpd", "privacidade", "meus dados", "dados pessoais", "sigilo", "seguranca dos dados"]
ABOUT_TERMS = ["sobre a clinica", "quem sao", "clinica vida", "historia", "proposito"]
GREETING_TERMS = ["oi", "ola", "bom dia", "boa tarde", "boa noite", "e ai", "hello", "hey", "opa", "salve"]
THANKS_TERMS = ["obrigado", "obrigada", "valeu", "agradeco", "brigado", "brigada", "obg", "show", "perfeito"]
BYE_TERMS = ["tchau", "ate logo", "ate mais", "ate breve", "falou", "adeus"]

# Palavras do FAQ que, sozinhas, já indicam a pergunta (evita confundir com agendamento).
FAQ_STRONG = ["remarcar", "cancelar", "cancelamento", "desmarcar", "reagendar", "documento", "documentos",
              "levar", "carteirinha", "nota fiscal", "reembolso", "recibo", "estacionamento", "estacionar",
              "acessibilidade", "cadeirante", "elevador", "garante", "garantido", "teleconsulta",
              "telemedicina", "videochamada"]

# Palavras genéricas em perguntas sobre convênio (não indicam o nome de um plano específico).
INSURANCE_GENERIC = {normalize(w) for w in INSURANCE_TERMS} | {
    "atende", "atendem", "atendimento", "trabalham", "trabalha", "lista", "todos", "algum", "alguns", "usar",
    "usa", "tipo", "tipos", "clinica", "consulta", "consultas", "saude", "medico", "aceito", "tambem", "nao",
    "sim", "ok", "pelo", "pela", "meu", "plano", "convenio", "convenios", "quais", "vida", "voces",
}

DEFAULT_SUGGESTIONS = ["Quais convênios vocês aceitam?", "Horário de funcionamento", "Quero agendar uma consulta"]


@dataclass
class Knowledge:
    specialties: list[models.Specialty]
    doctors: list[models.Doctor]
    insurances: list[models.Insurance]
    faqs: list[models.Faq]
    clinic: dict = field(default_factory=lambda: CLINIC_INFO)

    @classmethod
    def load(cls, db: Session) -> Knowledge:
        return cls(
            specialties=list(db.scalars(select(models.Specialty)
                                        .options(selectinload(models.Specialty.doctors))
                                        .order_by(models.Specialty.position))),
            doctors=list(db.scalars(select(models.Doctor)
                                    .options(selectinload(models.Doctor.specialty))
                                    .order_by(models.Doctor.position))),
            insurances=list(db.scalars(select(models.Insurance).order_by(models.Insurance.position))),
            faqs=list(db.scalars(select(models.Faq).order_by(models.Faq.position))),
        )

    def specialty(self, slug: str) -> models.Specialty | None:
        return next((s for s in self.specialties if s.slug == slug), None)

    def as_context(self) -> str:
        """Resumo textual da clínica para o LLM opcional (RAG simples)."""
        c = self.clinic
        lines = [
            f"Clínica: {c['name']} — {c['address']}. Telefone {c['phone']}. E-mail {c['email']}.",
            "Horários: " + "; ".join(c["hours"].values()) + ".",
            "Estrutura: " + ", ".join(c["amenities"]) + ".",
            "Especialidades:",
        ]
        for s in self.specialties:
            docs = ", ".join(d.name for d in s.doctors)
            lines.append(f"- {s.name} ({' e '.join(s.modalities)}): {s.description} Profissionais: {docs}.")
        lines.append("Convênios: " + ", ".join(i.name for i in self.insurances) + ".")
        lines.append("Perguntas frequentes:")
        lines += [f"- {f.question} {f.answer}" for f in self.faqs]
        return "\n".join(lines)


def _modalities_text(modalities: list[str]) -> str:
    if set(modalities) == {"Presencial", "Teleconsulta"}:
        return "presencial e por teleconsulta"
    return "apenas presencial" if modalities == ["Presencial"] else "apenas por teleconsulta"


class Assistant:
    def __init__(self, knowledge: Knowledge, db: Session | None = None) -> None:
        self.k = knowledge
        self.db = db

    # ------------------------------------------------------------------ entidades
    def _find_specialty(self, norm: str) -> models.Specialty | None:
        for spec in self.k.specialties:
            terms = [spec.slug.replace("-", " "), spec.name, spec.short_name, *spec.keywords]
            if contains_any(norm, terms):
                return spec
        return None

    def _find_doctor(self, norm: str) -> models.Doctor | None:
        words = set(norm.split())
        for doc in self.k.doctors:
            name_parts = {p for p in normalize(doc.name).split() if p not in TITLES}
            if words & name_parts:
                return doc
        return None

    def _find_insurance(self, norm: str) -> models.Insurance | None:
        for ins in self.k.insurances:
            if contains_any(norm, [ins.name, *ins.keywords]):
                return ins
        return None

    # ------------------------------------------------------------------ ações
    @staticmethod
    def _book(spec: models.Specialty | None = None, doctor: models.Doctor | None = None) -> ChatAction:
        if doctor:
            return ChatAction(type="book", label=f"Agendar com {doctor.first_name}",
                              specialty=doctor.specialty.slug, doctor=doctor.slug)
        if spec:
            return ChatAction(type="book", label=f"Agendar {spec.short_name}", specialty=spec.slug)
        return ChatAction(type="scroll", label="Ir para o agendamento", target="#agendamento")

    @staticmethod
    def _profile(doctor: models.Doctor) -> ChatAction:
        return ChatAction(type="open_doctor", label=f"Ver perfil — {doctor.first_name}", doctor=doctor.slug)

    def _whatsapp(self) -> ChatAction:
        return ChatAction(type="link", label="Falar no WhatsApp", href=f"https://wa.me/{self.k.clinic['whatsapp']}")

    # ------------------------------------------------------------------ pipeline
    def reply(self, message: str, history: list[ChatTurn] | None = None) -> ChatResponse:
        norm = normalize(message)
        if not norm:
            return self._greeting()

        if contains_any(norm, SELF_HARM_TERMS):
            return self._self_harm()
        if contains_any(norm, EMERGENCY_TERMS):
            return self._emergency()

        if match := PROTOCOL_RE.search(message):
            return self._protocol(f"CV-{match.group(1).upper()}")

        spec = self._find_specialty(norm)
        doctor = self._find_doctor(norm)
        insurance = self._find_insurance(norm)

        if contains_any(norm, SYMPTOM_TERMS):
            return self._symptoms(norm)

        wants_booking = contains_prefix(norm, ("agend", "marcar", "marcacao")) or (
            contains_any(norm, ["consulta", "quero consultar", "horario disponivel", "vaga"])
            and not contains_any(norm, FAQ_STRONG)
        )

        if (spec or doctor) and contains_any(norm, ONLINE_TERMS) and not wants_booking:
            return self._modality(doctor, spec or (doctor.specialty if doctor else None))

        if insurance or contains_any(norm, INSURANCE_TERMS):
            return self._insurance(insurance, spec, norm)

        if contains_any(norm, PRICE_TERMS):
            return self._price()

        if not wants_booking or contains_any(norm, FAQ_STRONG):
            if faq := self._faq_match(norm, strong_only=True):
                return faq

        if wants_booking:
            return self._booking(spec, doctor)

        if (doctor or spec) and contains_any(norm, HOURS_TERMS):
            return self._schedule(doctor, spec)

        if doctor:
            return self._doctor(doctor)

        if contains_any(norm, EXAM_TERMS):
            return self._exams()

        if contains_any(norm, LOCATION_TERMS):
            return self._location()
        if contains_any(norm, HOURS_TERMS):
            return self._hours()
        if contains_any(norm, CONTACT_TERMS):
            return self._contact()

        if contains_any(norm, DOCTOR_LIST_TERMS):
            return self._doctor_list(spec)
        if spec:
            return self._specialty(spec)
        if contains_any(norm, SPECIALTY_LIST_TERMS):
            return self._specialty_list()

        if contains_any(norm, PRIVACY_TERMS):
            return self._privacy()
        if contains_any(norm, ABOUT_TERMS):
            return self._about()

        short = len(norm.split()) <= 5
        if short and contains_any(norm, THANKS_TERMS):
            return ChatResponse(reply="Imagina! Fico feliz em ajudar. Precisa de mais alguma coisa? 😊",
                                intent="agradecimento", source="regras", suggestions=DEFAULT_SUGGESTIONS)
        if short and contains_any(norm, BYE_TERMS):
            return ChatResponse(reply="Até logo! Cuide-se bem. Se precisar, é só abrir o assistente de novo.",
                                intent="despedida", source="regras")
        if short and contains_any(norm, GREETING_TERMS):
            return self._greeting()

        if faq := self._faq_match(norm):
            return faq

        if answer := llm.ask(message, history or [], self.k.as_context()):
            return ChatResponse(reply=answer, intent="llm", source="llm", suggestions=DEFAULT_SUGGESTIONS)

        return self._fallback()

    # ------------------------------------------------------------------ respostas
    def _greeting(self) -> ChatResponse:
        return ChatResponse(
            reply=("Olá! Eu sou a **Vida**, assistente virtual da Clínica Vida. Posso ajudar com "
                   "especialidades, profissionais, convênios, horários e com o seu pré-agendamento.\n"
                   "Como posso ajudar?"),
            intent="saudacao", source="regras",
            suggestions=["Quais especialidades vocês têm?", "Aceitam Unimed?", "Quero agendar uma consulta"],
        )

    def _emergency(self) -> ChatResponse:
        return ChatResponse(
            reply=("⚠️ **Isso pode ser uma emergência.** Ligue agora para o **SAMU — 192** ou procure o "
                   "pronto-socorro mais próximo.\n"
                   "A Clínica Vida não realiza atendimento de urgência e o assistente não substitui "
                   "avaliação médica."),
            intent="emergencia", source="regras",
            actions=[ChatAction(type="link", label="Ligar para o SAMU (192)", href="tel:192")],
        )

    def _self_harm(self) -> ChatResponse:
        return ChatResponse(
            reply=("Sinto muito que você esteja passando por isso. Você não precisa enfrentar esse momento "
                   "sozinho(a).\n"
                   "• **CVV — 188**: ligação gratuita, 24 horas, ou chat em cvv.org.br\n"
                   "• Se houver risco imediato, ligue para o **SAMU — 192** ou vá ao pronto-socorro.\n"
                   "Quando se sentir pronto(a), nossa equipe de Psicologia também pode acompanhar você."),
            intent="apoio_emocional", source="regras",
            actions=[ChatAction(type="link", label="Ligar para o CVV (188)", href="tel:188"),
                     ChatAction(type="link", label="Ligar para o SAMU (192)", href="tel:192")],
        )

    def _protocol(self, code: str) -> ChatResponse:
        appt = None
        if self.db is not None:
            appt = self.db.scalar(select(models.Appointment).where(models.Appointment.protocol == code))
        if not appt:
            return ChatResponse(
                reply=(f"Não encontrei o protocolo **{code}**. Confira se digitou corretamente — ele aparece "
                       "no resumo exibido após o pré-agendamento."),
                intent="protocolo", source="regras", actions=[self._whatsapp()],
            )
        date_br = appt.preferred_date.strftime("%d/%m/%Y")
        return ChatResponse(
            reply=(f"Encontrei o protocolo **{appt.protocol}**:\n"
                   f"• Especialidade: {appt.specialty.name}\n"
                   f"• Preferência: {date_br} — {appt.period}\n"
                   f"• Status: **{appt.status}**\n"
                   "A recepção entra em contato para confirmar o horário exato."),
            intent="protocolo", source="regras",
        )

    def _symptoms(self, norm: str) -> ChatResponse:
        slug = next((s for terms, s in SYMPTOM_TO_SPECIALTY if contains_any(norm, terms)), "clinica-geral")
        spec = self.k.specialty(slug)
        assert spec is not None
        return ChatResponse(
            reply=("Não consigo avaliar sintomas, indicar remédios ou dar diagnósticos — isso precisa de uma "
                   "consulta com um profissional. 💙\n"
                   f"Pelo que você contou, a especialidade de **{spec.name}** pode ser um bom ponto de partida "
                   "(atendimento " + _modalities_text(spec.modalities) + ").\n"
                   "Se os sintomas forem intensos ou começaram de repente, procure um pronto-socorro ou ligue 192.\n"
                   "_Por privacidade, evite compartilhar detalhes de saúde aqui no chat._"),
            intent="sintomas", source="regras",
            actions=[self._book(spec)],
            suggestions=["Quais convênios vocês aceitam?", "Como funciona a teleconsulta?"],
        )

    def _modality(self, doctor: models.Doctor | None, spec: models.Specialty | None) -> ChatResponse:
        if doctor:
            text = f"{doctor.name} atende **{_modalities_text(doctor.modalities)}**."
            actions = [self._book(doctor=doctor), self._profile(doctor)]
        else:
            assert spec is not None
            text = f"**{spec.name}** é atendida **{_modalities_text(spec.modalities)}**."
            actions = [self._book(spec)]
        if (doctor or spec).modalities == ["Presencial"]:
            text += "\nAs especialidades com teleconsulta são: " + ", ".join(
                s.short_name for s in self.k.specialties if "Teleconsulta" in s.modalities) + "."
        return ChatResponse(reply=text, intent="modalidade", source="regras", actions=actions,
                            suggestions=["Como funciona a teleconsulta?", "Quais convênios vocês aceitam?"])

    def _insurance(self, ins: models.Insurance | None, spec: models.Specialty | None, norm: str) -> ChatResponse:
        names = ", ".join(i.name for i in self.k.insurances if not i.is_private)
        if ins and ins.is_private:
            reply = ("Sim! Fazemos **atendimento particular** e emitimos nota fiscal detalhada para você "
                     "solicitar reembolso à sua operadora, conforme o seu contrato.")
        elif ins:
            reply = f"Sim, atendemos **{ins.name}** ({ins.note.lower()})."
            if spec:
                reply += f" Isso inclui consultas de **{spec.name}**, de acordo com a categoria do seu plano."
            reply += "\nA cobertura pode variar conforme a categoria do plano — a recepção confirma a elegibilidade antes da consulta."
        else:
            asked_specific = any(t not in INSURANCE_GENERIC for t in tokens(norm))
            if asked_specific and not spec:
                reply = ("Não encontrei esse plano na nossa lista de convênios. Trabalhamos com: "
                         f"{names}.\nVocê também pode fazer **atendimento particular** com nota fiscal para reembolso, "
                         "ou falar com a recepção para confirmar.")
            else:
                reply = f"Atendemos os convênios: **{names}**.\nTambém oferecemos atendimento particular com nota fiscal para reembolso."
        return ChatResponse(
            reply=reply, intent="convenio", source="regras",
            actions=[self._book(spec) if spec else ChatAction(type="scroll", label="Ver convênios", target="#convenios")],
            suggestions=["Vocês emitem nota fiscal para reembolso?", "Quero agendar uma consulta"],
        )

    def _booking(self, spec: models.Specialty | None, doctor: models.Doctor | None) -> ChatResponse:
        if doctor:
            return ChatResponse(
                reply=(f"Ótimo! Vou abrir o pré-agendamento com **{doctor.name}** ({doctor.specialty_label}), "
                       f"que atende {_modalities_text(doctor.modalities)}.\nÉ só escolher data, período e convênio. "
                       "A recepção confirma o horário pelo WhatsApp."),
                intent="agendamento", source="regras", actions=[self._book(doctor=doctor), self._profile(doctor)],
            )
        if spec:
            names = ", ".join(d.name for d in spec.doctors)
            return ChatResponse(
                reply=(f"Perfeito! Vou preencher o formulário com **{spec.name}** "
                       f"(atendimento {_modalities_text(spec.modalities)}). Profissional: {names}.\n"
                       "Depois é só escolher data, período e convênio."),
                intent="agendamento", source="regras", actions=[self._book(spec)],
            )
        return ChatResponse(
            reply="Claro! Para qual especialidade você quer agendar?",
            intent="agendamento", source="regras",
            suggestions=[f"Agendar {s.short_name}" for s in self.k.specialties],
        )

    def _schedule(self, doctor: models.Doctor | None, spec: models.Specialty | None) -> ChatResponse:
        docs = [doctor] if doctor else (spec.doctors if spec else [])
        lines = [f"• **{d.name}**: {'; '.join(d.schedule)}" for d in docs]
        return ChatResponse(
            reply="Agenda de atendimento:\n" + "\n".join(lines) + "\nA recepção confirma o horário exato após o pré-agendamento.",
            intent="agenda_profissional", source="regras",
            actions=[self._book(doctor=d) for d in docs][:2],
        )

    def _exams(self) -> ChatResponse:
        return ChatResponse(
            reply=("Nossos profissionais solicitam e avaliam exames durante a consulta. Para saber se um exame "
                   "específico é realizado na unidade, fale com a recepção. Os resultados devem ser interpretados "
                   "pelo profissional que acompanha você."),
            intent="exames", source="regras", actions=[self._whatsapp()],
        )

    def _doctor(self, doctor: models.Doctor) -> ChatResponse:
        return ChatResponse(
            reply=(f"**{doctor.name}** — {doctor.specialty_label}\n{doctor.bio}\n"
                   f"• Atendimento: {_modalities_text(doctor.modalities)}\n"
                   f"• Agenda: {'; '.join(doctor.schedule)}"),
            intent="profissional", source="regras",
            actions=[self._profile(doctor), self._book(doctor=doctor)],
        )

    def _doctor_list(self, spec: models.Specialty | None) -> ChatResponse:
        if spec:
            docs = spec.doctors
            reply = f"Em **{spec.name}** atende:\n" + "\n".join(f"• {d.name} — {d.credential}" for d in docs)
            actions = [self._profile(d) for d in docs] + [self._book(spec)]
        else:
            reply = "Nosso corpo clínico:\n" + "\n".join(f"• {d.name} — {d.specialty_label}" for d in self.k.doctors)
            actions = [ChatAction(type="scroll", label="Ver corpo clínico", target="#equipe")]
        return ChatResponse(reply=reply, intent="profissionais", source="regras", actions=actions)

    def _specialty(self, spec: models.Specialty) -> ChatResponse:
        names = ", ".join(d.name for d in spec.doctors)
        return ChatResponse(
            reply=(f"**{spec.name}** — {spec.description}\n"
                   f"• Atendimento {_modalities_text(spec.modalities)}\n• Profissional: {names}"),
            intent="especialidade", source="regras",
            actions=[self._book(spec), ChatAction(type="filter_team", label="Ver especialistas", specialty=spec.slug)],
        )

    def _specialty_list(self) -> ChatResponse:
        lines = [f"• **{s.name}** — {_modalities_text(s.modalities)}" for s in self.k.specialties]
        return ChatResponse(
            reply="Estas são as nossas especialidades:\n" + "\n".join(lines),
            intent="especialidades", source="regras",
            suggestions=[f"Agendar {s.short_name}" for s in self.k.specialties[:3]],
            actions=[ChatAction(type="scroll", label="Ver especialidades", target="#especialidades")],
        )

    def _hours(self) -> ChatResponse:
        h = self.k.clinic["hours"]
        return ChatResponse(
            reply=f"Nosso horário de funcionamento:\n• {h['weekdays']}\n• {h['saturday']}\n• {h['sunday']}",
            intent="horario", source="regras", suggestions=["Onde fica a clínica?", "Quero agendar uma consulta"],
        )

    def _location(self) -> ChatResponse:
        c = self.k.clinic
        return ChatResponse(
            reply=f"Estamos na **{c['address']}**.\n" + " • ".join(c["amenities"]) + ".",
            intent="localizacao", source="regras",
            actions=[ChatAction(type="link", label="Abrir rota no mapa",
                                href="https://maps.google.com/?q=Campinas+SP")],
        )

    def _contact(self) -> ChatResponse:
        c = self.k.clinic
        return ChatResponse(
            reply=(f"Você pode falar com a nossa recepção:\n• Telefone: **{c['phone']}**\n• E-mail: {c['email']}\n"
                   f"• WhatsApp no botão abaixo\n{c['hours']['weekdays']} • {c['hours']['saturday']}"),
            intent="contato", source="regras", actions=[self._whatsapp()],
        )

    def _price(self) -> ChatResponse:
        return ChatResponse(
            reply=("Os valores variam conforme a especialidade e a forma de atendimento (convênio ou particular), "
                   "por isso a recepção informa o valor atualizado na confirmação. Aceitamos Pix e cartões, e "
                   "emitimos nota fiscal para reembolso."),
            intent="valores", source="regras", actions=[self._whatsapp()],
        )

    def _privacy(self) -> ChatResponse:
        return ChatResponse(
            reply=("Levamos a LGPD a sério: o pré-agendamento coleta apenas dados de contato, e as conversas com "
                   "este assistente **não são armazenadas**. Por isso, não compartilhe sintomas, exames ou "
                   "histórico médico aqui."),
            intent="privacidade", source="regras",
        )

    def _about(self) -> ChatResponse:
        return ChatResponse(
            reply=("A Clínica Vida reúne diferentes especialidades em um ambiente acolhedor, com escuta atenta, "
                   "diagnósticos claros e agendamento descomplicado — de check-ups preventivos a cuidados contínuos."),
            intent="sobre", source="regras",
            actions=[ChatAction(type="scroll", label="Conhecer a clínica", target="#sobre")],
        )

    def _faq_match(self, norm: str, strong_only: bool = False) -> ChatResponse | None:
        best, best_score = None, 0.0
        query = set(tokens(norm))
        for faq in self.k.faqs:
            kw_hits = sum(1 for kw in faq.keywords if contains_any(norm, [kw]))
            if strong_only:
                strong_hits = [kw for kw in faq.keywords if kw in FAQ_STRONG and contains_any(norm, [kw])]
                score = float(len(strong_hits))
            else:
                overlap = len(query & set(tokens(faq.question + " " + " ".join(faq.keywords))))
                score = kw_hits * 2 + overlap
            if score > best_score:
                best, best_score = faq, score
        threshold = 1 if strong_only else 2
        if not best or best_score < threshold:
            return None
        return ChatResponse(reply=best.answer, intent="faq", source="faq",
                            suggestions=[f.question for f in self.k.faqs if f.id != best.id][:2])

    def _fallback(self) -> ChatResponse:
        return ChatResponse(
            reply=("Hmm, não tenho certeza se entendi. 🤔 Posso ajudar com especialidades, profissionais, "
                   "convênios, horários, localização e pré-agendamento. Se preferir, fale com a recepção."),
            intent="desconhecido", source="regras",
            suggestions=DEFAULT_SUGGESTIONS, actions=[self._whatsapp()],
        )
