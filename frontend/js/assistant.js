"use strict";

/* =====================================================================
   Assistente virtual "Vida"
   - Conversa com POST /api/assistant/chat (FastAPI).
   - Sem servidor, responde o básico localmente com os dados do site.
   - As mensagens ficam só na memória da aba (nada é salvo).
   ===================================================================== */
(function () {
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const motionOK = window.matchMedia("(prefers-reduced-motion: no-preference)").matches;
  const mobileQuery = window.matchMedia("(max-width: 991.98px)");

  const panel = $("#assistantPanel");
  const log = $("#assistantLog");
  const form = $("#assistantForm");
  const input = $("#assistantInput");
  const suggestionsBox = $("#assistantSuggestions");
  const statusText = $("#assistantStatus .status-text");
  const statusRoot = $("#assistantStatus");
  const fabs = $$('[data-assistant-open="toggle"]');

  const history = [];
  let started = false;
  let online = null;          // null = ainda não verificado
  let busy = false;
  let lastOpener = null;

  const GREETING = {
    reply: "Olá! Eu sou a **Vida**, assistente virtual da Clínica Vida. 👋\nPosso ajudar com especialidades, profissionais, convênios, horários e com o seu pré-agendamento.",
    suggestions: ["Quais especialidades vocês têm?", "Aceitam Unimed?", "Quero agendar uma consulta", "Qual o horário de funcionamento?"],
    actions: [],
  };

  // ------------------------------------------------------------ renderização
  /** Converte **negrito**, _itálico_ e quebras de linha depois de escapar o HTML. */
  function formatMessage(text) {
    const escaped = text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    return escaped
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|\s)_(.+?)_(?=\s|$|[.,!?])/g, "$1<em>$2</em>")
      .replace(/\n/g, "<br>");
  }

  function scrollToEnd() {
    log.scrollTo({ top: log.scrollHeight, behavior: motionOK ? "smooth" : "auto" });
  }

  function addMessage(role, text, actions = []) {
    const bubble = document.createElement("div");
    bubble.className = `msg msg-${role}`;
    const content = document.createElement("div");
    content.className = "msg-bubble";
    if (role === "bot") content.innerHTML = formatMessage(text);
    else content.textContent = text;

    const sr = document.createElement("span");
    sr.className = "visually-hidden";
    sr.textContent = role === "bot" ? "Vida disse: " : "Você disse: ";
    content.prepend(sr);
    bubble.append(content);

    if (actions.length) {
      const row = document.createElement("div");
      row.className = "msg-actions";
      actions.forEach((action) => row.append(actionButton(action)));
      bubble.append(row);
    }
    log.append(bubble);
    scrollToEnd();
  }

  function actionButton(action) {
    if (action.type === "link") {
      const a = document.createElement("a");
      a.className = "msg-action";
      a.href = action.href;
      a.textContent = action.label;
      if (!action.href.startsWith("tel:")) {
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.textContent += " ↗";
      }
      return a;
    }
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `msg-action${action.type === "book" ? " is-primary" : ""}`;
    btn.textContent = action.label;
    btn.addEventListener("click", () => runAction(action));
    return btn;
  }

  function runAction(action) {
    const ui = window.ClinicUI;
    if (!ui) return;
    // No celular o painel ocupa a tela inteira: fecha antes de levar o usuário ao conteúdo
    if (mobileQuery.matches || action.type === "book") close({ restoreFocus: false });
    if (action.type === "book") ui.book(action.specialty, action.doctor || "");
    else if (action.type === "open_doctor") ui.openDoctor(action.doctor);
    else if (action.type === "filter_team") ui.filterTeam(action.specialty);
    else if (action.type === "scroll") ui.scrollTo(action.target);
  }

  function setSuggestions(list = []) {
    suggestionsBox.replaceChildren(...list.slice(0, 4).map((text) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip";
      chip.textContent = text;
      chip.addEventListener("click", () => send(text));
      return chip;
    }));
    suggestionsBox.hidden = list.length === 0;
  }

  function showTyping() {
    const typing = document.createElement("div");
    typing.className = "msg msg-bot msg-typing";
    typing.setAttribute("aria-label", "Vida está digitando");
    typing.innerHTML = '<div class="msg-bubble"><span></span><span></span><span></span></div>';
    log.append(typing);
    scrollToEnd();
    return typing;
  }

  function setStatus(isOnline) {
    online = isOnline;
    statusRoot.classList.toggle("is-offline", !isOnline);
    statusText.textContent = isOnline ? "Online agora" : "Modo offline · respostas básicas";
  }

  // ------------------------------------------------------------ respostas locais (sem servidor)
  function norm(text) {
    return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9\s-]/g, " ").replace(/\s+/g, " ").trim();
  }
  const has = (text, terms) => terms.some((t) => ` ${text} `.includes(` ${norm(t)} `));

  function localReply(message) {
    const data = window.ClinicUI?.data || window.CLINIC_FALLBACK;
    const t = norm(message);
    const clinic = data.clinic;
    const wa = { type: "link", label: "Falar no WhatsApp", href: `https://wa.me/${clinic.whatsapp}` };

    if (has(t, ["suicidio", "me matar", "quero morrer", "nao quero mais viver", "tirar minha vida", "me machucar"])) {
      return { reply: "Você não precisa passar por isso sozinho(a). Ligue para o **CVV — 188** (gratuito, 24h) ou, em risco imediato, para o **SAMU — 192**.", actions: [{ type: "link", label: "Ligar para o CVV (188)", href: "tel:188" }] };
    }
    if (has(t, ["dor no peito", "falta de ar", "desmaio", "desmaiou", "convulsao", "avc", "infarto", "emergencia", "urgencia", "sangramento"])) {
      return { reply: "⚠️ **Isso pode ser uma emergência.** Ligue para o **SAMU — 192** ou procure o pronto-socorro mais próximo.", actions: [{ type: "link", label: "Ligar para o SAMU (192)", href: "tel:192" }] };
    }

    const spec = data.specialties.find((s) => has(t, [s.name, s.short_name, ...(s.keywords || [])]));
    const insurance = data.insurances.find((i) => has(t, [i.name, ...(i.keywords || [])]));

    if (has(t, ["sintoma", "estou com", "remedio", "medicamento", "diagnostico", "febre", "dor de"])) {
      return { reply: "Não consigo avaliar sintomas nem indicar remédios — isso precisa de uma consulta. Um bom ponto de partida é a **Clínica Geral**.", actions: [{ type: "book", label: "Agendar Clínica Geral", specialty: "clinica-geral" }] };
    }
    if (insurance) {
      return { reply: insurance.is_private ? "Sim! Fazemos atendimento **particular** com nota fiscal para reembolso." : `Sim, atendemos **${insurance.name}** (${insurance.note.toLowerCase()}). A recepção confirma a cobertura do seu plano.` };
    }
    if (has(t, ["convenio", "convenios", "plano", "planos", "aceita", "aceitam"])) {
      return { reply: `Atendemos: **${data.insurances.filter((i) => !i.is_private).map((i) => i.name).join(", ")}**, além de atendimento particular.` };
    }
    if (/\b(agend|marc)/.test(t) || has(t, ["consulta"])) {
      return spec
        ? { reply: `Perfeito! Vou preencher o formulário com **${spec.name}**.`, actions: [{ type: "book", label: `Agendar ${spec.short_name}`, specialty: spec.slug }] }
        : { reply: "Claro! Para qual especialidade?", suggestions: data.specialties.map((s) => `Agendar ${s.short_name}`) };
    }
    if (spec) {
      const mods = spec.modalities.includes("Teleconsulta") ? "presencial e por teleconsulta" : "apenas presencial";
      return { reply: `**${spec.name}** — ${spec.description}\nAtendimento ${mods}.`, actions: [{ type: "book", label: `Agendar ${spec.short_name}`, specialty: spec.slug }] };
    }
    if (has(t, ["horario", "funciona", "abre", "fecha", "sabado", "domingo"])) {
      return { reply: `• ${clinic.hours.weekdays}\n• ${clinic.hours.saturday}\n• ${clinic.hours.sunday}` };
    }
    if (has(t, ["endereco", "onde fica", "localizacao", "como chegar", "mapa"])) {
      return { reply: `Estamos na **${clinic.address}**.` };
    }
    if (has(t, ["telefone", "whatsapp", "contato", "email", "atendente", "recepcao"])) {
      return { reply: `Telefone **${clinic.phone}** • ${clinic.email}`, actions: [wa] };
    }
    if (has(t, ["especialidade", "especialidades", "areas", "medicos", "profissionais"])) {
      return { reply: "Nossas especialidades:\n" + data.specialties.map((s) => `• ${s.name}`).join("\n") };
    }

    const words = new Set(t.split(" ").filter((w) => w.length > 3));
    const scored = data.faqs.map((f) => ({ f, score: norm(`${f.question} ${(f.keywords || []).join(" ")}`).split(" ").filter((w) => words.has(w)).length }))
      .sort((a, b) => b.score - a.score)[0];
    if (scored?.score >= 1) return { reply: scored.f.answer };

    return { reply: "Ainda não sei responder isso no modo offline. A recepção pode ajudar!", actions: [wa], suggestions: GREETING.suggestions.slice(0, 3) };
  }

  // ------------------------------------------------------------ envio
  async function send(text) {
    const message = text.trim();
    if (!message || busy) return;
    busy = true;
    form.classList.add("is-busy");
    setSuggestions([]);
    addMessage("user", message);
    input.value = "";

    const typing = showTyping();
    const minDelay = new Promise((r) => setTimeout(r, motionOK ? 550 : 0));
    let result;
    try {
      if (online === false) throw new Error("offline");
      result = await window.ClinicApi.post("/api/assistant/chat", { message, history: history.slice(-8) }, { timeout: 15000 });
      if (online !== true) setStatus(true);
    } catch (err) {
      if (err?.status === 429) result = { reply: err.message, actions: [], suggestions: [] };
      else {
        if (online !== false) setStatus(false);
        result = { actions: [], suggestions: [], ...localReply(message) };
      }
    }
    await minDelay;
    typing.remove();

    addMessage("bot", result.reply, result.actions || []);
    setSuggestions(result.suggestions || []);
    history.push({ role: "user", content: message.slice(0, 1200) }, { role: "assistant", content: result.reply.slice(0, 1200) });
    busy = false;
    form.classList.remove("is-busy");
    if (!mobileQuery.matches) input.focus();
  }

  form.addEventListener("submit", (e) => { e.preventDefault(); send(input.value); });

  // ------------------------------------------------------------ abrir / fechar
  async function checkStatus() {
    try {
      await window.ClinicApi.get("/api/assistant/status", { timeout: 2500 });
      setStatus(true);
    } catch {
      setStatus(false);
    }
  }

  function open(prefill) {
    lastOpener = document.activeElement;
    if (panel.hidden) {
      panel.hidden = false;
      requestAnimationFrame(() => panel.classList.add("is-open"));
      fabs.forEach((b) => b.setAttribute("aria-expanded", "true"));
      document.documentElement.classList.add("assistant-open");
    }
    if (!started) {
      started = true;
      checkStatus();
      addMessage("bot", GREETING.reply);
      setSuggestions(GREETING.suggestions);
    }
    if (typeof prefill === "string" && prefill) send(prefill);
    else setTimeout(() => input.focus(), motionOK ? 220 : 0);
  }

  function close({ restoreFocus = true } = {}) {
    if (panel.hidden) return;
    panel.classList.remove("is-open");
    fabs.forEach((b) => b.setAttribute("aria-expanded", "false"));
    document.documentElement.classList.remove("assistant-open");
    setTimeout(() => { panel.hidden = true; }, motionOK ? 220 : 0);
    if (restoreFocus && lastOpener?.focus) lastOpener.focus();
  }

  function reset() {
    history.length = 0;
    log.replaceChildren();
    addMessage("bot", GREETING.reply);
    setSuggestions(GREETING.suggestions);
    input.focus();
  }

  $$("[data-assistant-open]").forEach((btn) => btn.addEventListener("click", () => {
    if (btn.dataset.assistantOpen === "toggle" && !panel.hidden) close();
    else open();
  }));
  $$("[data-assistant-ask]").forEach((btn) => btn.addEventListener("click", () => open(btn.dataset.assistantAsk)));
  $("#assistantClose").addEventListener("click", () => close());
  $("#assistantReset").addEventListener("click", reset);
  panel.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.stopPropagation(); close(); } });

  // Mostra o rótulo do botão flutuante por alguns segundos para facilitar a descoberta
  const desktopFab = $(".assistant-fab");
  if (desktopFab) {
    setTimeout(() => desktopFab.classList.add("is-hinting"), 2500);
    setTimeout(() => desktopFab.classList.remove("is-hinting"), 8000);
  }

  window.ClinicAssistant = { open, close, send };
})();
