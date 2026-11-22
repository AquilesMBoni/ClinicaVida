"use strict";

/* =====================================================================
   Clínica Vida — interações do site
   1. Utilidades            6. Convênios (marquee + busca)
   2. Efeito de escrita     7. FAQ
   3. Carrossel do hero     8. Pré-agendamento (API)
   4. Tabela de especialid. 9. Navegação e scroll reveal
   5. Corpo clínico + modal 10. API pública para o assistente
   ===================================================================== */

// ---------------------------------------------------------------- 1. Utilidades
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const motionOK = window.matchMedia("(prefers-reduced-motion: no-preference)").matches;
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

/** Cria elementos com segurança (texto sempre via textContent, nunca innerHTML com dados). */
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  node.append(...children.flat().filter((c) => c !== null && c !== undefined && c !== false));
  return node;
}

/** Ícones SVG estáticos (markup fixo, sem dados do usuário). */
function icon(name, size = 16) {
  const paths = {
    presencial: '<path d="M3 21h18M5 21V7l7-4 7 4v14M9 21v-5h6v5M10 9h4M12 7v4"/>',
    online: '<rect x="3" y="6" width="13" height="12" rx="2"/><path d="m16 10 5-3v10l-5-3z"/>',
    chevron: '<path d="m6 9 6 6 6-6"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    check: '<path d="m5 12 5 5 9-10"/>',
    arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    cap: '<path d="m2 9 10-5 10 5-10 5z"/><path d="M6 11v5c0 1.5 2.7 3 6 3s6-1.5 6-3v-5"/>',
  };
  const span = document.createElement("span");
  span.className = `ico ico-${name}`;
  span.setAttribute("aria-hidden", "true");
  span.innerHTML = `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${paths[name]}</svg>`;
  return span;
}

const normalizeText = (t) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
const modalityLabel = (mods) => mods.map((m) => (m === "Teleconsulta" ? "Online" : m)).join(" • ");
const initials = (name) => name.replace(/^(Dra?|Psi|Nutri)\.\s*/i, "").split(" ").map((p) => p[0]).slice(0, 2).join("");

const state = { data: null, bySpecialty: new Map(), byDoctor: new Map() };

// ---------------------------------------------------------------- 9a. Scroll reveal (usado por todas as seções)
const Reveal = (() => {
  const enabled = motionOK && "IntersectionObserver" in window;
  if (enabled) document.documentElement.classList.add("motion");
  const io = enabled
    ? new IntersectionObserver((entries) => entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("in");
        io.unobserve(entry.target);
      }), { threshold: 0.12, rootMargin: "0px 0px -6% 0px" })
    : null;

  function add(targets, variant = "up") {
    if (!enabled) return;
    const list = typeof targets === "string" ? $$(targets) : [...targets];
    list.forEach((node) => {
      if (node.classList.contains("reveal")) return;
      const unit = node.closest('[class*="col-"]') || node;
      const siblings = unit.parentElement ? [...unit.parentElement.children] : [unit];
      node.style.setProperty("--index", Math.min(siblings.indexOf(unit), 5));
      node.dataset.reveal ||= variant;
      node.classList.add("reveal");
      io.observe(node);
    });
  }
  return { add, enabled };
})();

// ---------------------------------------------------------------- 2. Efeito de escrita no título
function initTypewriter() {
  const title = $(".hero-title");
  if (!title) return;
  const lines = $$(".tw-line", title).map((line) => ({
    typed: $(".tw-typed", line),
    segments: [...$(".tw-ghost", line).childNodes].map((n) => ({ text: n.textContent, em: n.nodeName === "EM" })),
  }));

  const fillInstantly = () => {
    lines.forEach(({ typed, segments }) => {
      typed.replaceChildren(...segments.map((s) => (s.em ? el("em", { text: s.text }) : s.text)));
    });
    title.classList.add("tw-done");
  };
  if (!motionOK) return fillInstantly();

  const caret = el("span", { class: "tw-caret", "aria-hidden": "true" });
  title.classList.add("tw-active");

  (async () => {
    await wait(450);
    for (const [i, { typed, segments }] of lines.entries()) {
      typed.append(caret);
      for (const seg of segments) {
        const target = seg.em ? typed.insertBefore(el("em"), caret) : null;
        for (const char of seg.text) {
          if (target) target.textContent += char;
          else caret.before(char);
          const pause = /[.,]/.test(char) ? 260 : 38 + Math.random() * 42;
          await wait(pause);
        }
      }
      if (i < lines.length - 1) await wait(380);
    }
    title.classList.add("tw-done");
    setTimeout(() => caret.classList.add("tw-caret-off"), 2600);
  })();
}

// ---------------------------------------------------------------- 3. Carrossel automático do hero
function initHeroCarousel() {
  const root = $("#heroCarousel");
  if (!root) return;
  const dotsWrap = $(".hc-dots", root);
  const toggle = $(".hc-toggle", root);
  const bar = $(".hc-progress span", root);
  const caption = $(".hc-caption");
  const capTitle = $("#heroCaptionTitle");
  const capText = $("#heroCaptionText");
  let slides = $$(".hc-slide", root);
  let index = 0;
  let userPaused = !motionOK;          // com movimento reduzido, começa pausado
  let hoverPaused = false;

  function syncPlayState() {
    const paused = userPaused || hoverPaused || document.hidden;
    root.classList.toggle("is-paused", paused);
    toggle.setAttribute("aria-pressed", String(userPaused));
    toggle.setAttribute("aria-label", userPaused ? "Retomar carrossel" : "Pausar carrossel");
  }

  function restartProgress() {
    bar.classList.remove("run");
    void bar.offsetWidth;               // reinicia a animação CSS
    if (slides.length > 1) bar.classList.add("run");
  }

  function buildDots() {
    dotsWrap.replaceChildren(...slides.map((slide, i) => el("button", {
      type: "button", class: "hc-dot",
      "aria-label": `Slide ${i + 1}: ${slide.dataset.title}`,
      "aria-current": i === index ? "true" : "false",
      onclick: () => goTo(i, true),
    })));
    slides.forEach((s, i) => s.setAttribute("aria-label", `${i + 1} de ${slides.length}`));
    root.classList.toggle("is-single", slides.length < 2);
  }

  function goTo(next, fromUser = false) {
    if (!slides.length) return;
    index = (next + slides.length) % slides.length;
    slides.forEach((s, i) => {
      s.classList.toggle("is-active", i === index);
      s.setAttribute("aria-hidden", String(i !== index));
    });
    $$(".hc-dot", dotsWrap).forEach((d, i) => d.setAttribute("aria-current", String(i === index)));

    const { title, text } = slides[index].dataset;
    caption.classList.add("is-changing");
    setTimeout(() => {
      capTitle.textContent = title;
      capText.textContent = text;
      caption.classList.remove("is-changing");
    }, motionOK ? 220 : 0);
    caption.setAttribute("aria-live", fromUser ? "polite" : "off");
    restartProgress();
  }

  // A barra de progresso dita o ritmo: quando a animação termina, avança (e pausa junto com ela).
  bar.addEventListener("animationend", () => goTo(index + 1));

  // Remove slides cujas imagens não carregarem (ex.: bloqueio de rede), sem quebrar o layout.
  function dropSlide(slide) {
    const wasActive = slide.classList.contains("is-active");
    slide.remove();
    slides = $$(".hc-slide", root);
    if (index >= slides.length) index = 0;
    buildDots();
    if (wasActive || slides.length) goTo(index);
  }
  slides.forEach((slide) => {
    const img = $("img", slide);
    img.addEventListener("error", () => slides.length > 1 && dropSlide(slide), { once: true });
    if (img.complete && img.naturalWidth === 0 && img.getAttribute("loading") !== "lazy" && slides.length > 1) dropSlide(slide);
  });

  toggle.addEventListener("click", () => { userPaused = !userPaused; syncPlayState(); });
  root.addEventListener("mouseenter", () => { hoverPaused = true; syncPlayState(); });
  root.addEventListener("mouseleave", () => { hoverPaused = false; syncPlayState(); });
  root.addEventListener("focusin", () => { hoverPaused = true; syncPlayState(); });
  root.addEventListener("focusout", (e) => { if (!root.contains(e.relatedTarget)) { hoverPaused = false; syncPlayState(); } });
  document.addEventListener("visibilitychange", syncPlayState);
  root.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") { e.preventDefault(); goTo(index + 1, true); }
    if (e.key === "ArrowLeft") { e.preventDefault(); goTo(index - 1, true); }
  });

  // Gesto de arrastar no celular
  let startX = null;
  root.addEventListener("pointerdown", (e) => { startX = e.clientX; });
  root.addEventListener("pointerup", (e) => {
    if (startX === null) return;
    const dx = e.clientX - startX;
    if (Math.abs(dx) > 40) goTo(index + (dx < 0 ? 1 : -1), true);
    startX = null;
  });

  // Pré-carrega as próximas imagens depois do carregamento inicial
  window.addEventListener("load", () => $$("img[loading=lazy]", root).forEach((img) => { img.loading = "eager"; }));

  buildDots();
  syncPlayState();
  goTo(0);
}

// ---------------------------------------------------------------- 4. Tabela dinâmica de especialidades
function renderSpecialties(specialties) {
  const body = $("#specialtyRows");
  body.replaceChildren();

  specialties.forEach((spec, i) => {
    const triggerId = `spec-trigger-${spec.slug}`;
    const panelId = `spec-panel-${spec.slug}`;
    const doctorCount = spec.doctors.length;

    const trigger = el("button", {
      type: "button", class: "spec-trigger", id: triggerId,
      "aria-expanded": "false", "aria-controls": panelId,
    },
      el("span", { class: "spec-index", text: String(i + 1).padStart(2, "0") }),
      el("span", { class: "spec-name" },
        el("span", { class: "spec-title", text: spec.name }),
        el("span", { class: "spec-summary", text: spec.summary })),
      el("span", { class: "spec-mods" },
        spec.modalities.map((m) => el("span", { class: "spec-mod", title: m },
          icon(m === "Presencial" ? "presencial" : "online", 15),
          el("span", { class: "spec-mod-text", text: m === "Teleconsulta" ? "Online" : m })))),
      el("span", { class: "spec-team" },
        el("span", { class: "spec-avatars", "aria-hidden": "true" },
          spec.doctors.map((d) => {
            const doc = state.byDoctor.get(d.slug);
            return el("span", { class: "spec-avatar" }, doc ? el("img", { src: doc.photo_url, alt: "", loading: "lazy" }) : initials(d.name));
          })),
        el("span", { class: "spec-team-text", text: `${doctorCount} ${doctorCount === 1 ? "profissional" : "profissionais"}` })),
      el("span", { class: "spec-chevron" }, icon("chevron", 18)),
    );

    const panel = el("div", { class: "spec-panel", id: panelId, role: "region", "aria-labelledby": triggerId, inert: true },
      el("div", { class: "spec-panel-inner" },
        el("div", { class: "spec-panel-content" },
          el("div", { class: "spec-detail" },
            el("div", { class: "spec-tags" },
              spec.modalities.map((m) => el("span", { class: "modality-tag" },
                icon(m === "Presencial" ? "presencial" : "online", 14),
                m === "Teleconsulta" ? "Online (teleconsulta)" : "Presencial na clínica"))),
            el("p", { class: "spec-description", text: spec.description }),
            el("div", { class: "spec-doctors" },
              spec.doctors.map((d) => {
                const doc = state.byDoctor.get(d.slug);
                return el("button", {
                  type: "button", class: "spec-doctor", "aria-haspopup": "dialog",
                  "aria-label": `Ver perfil de ${d.name}`, onclick: () => openDoctorModal(d.slug),
                },
                  el("span", { class: "spec-avatar spec-avatar-lg", "aria-hidden": "true" },
                    doc ? el("img", { src: doc.photo_url, alt: "", loading: "lazy" }) : initials(d.name)),
                  el("span", { class: "spec-doctor-text" },
                    el("strong", { text: d.name }),
                    el("small", { text: doc ? doc.credential : modalityLabel(d.modalities) })),
                  icon("arrow", 16));
              }))),
          el("div", { class: "specialty-actions spec-actions" },
            el("button", { type: "button", class: "btn btn-link-clinic", text: "Ver especialistas →",
              onclick: () => filterTeam(spec.slug, true) }),
            el("button", { type: "button", class: "btn btn-sm btn-soft-clinic", text: `Agendar ${spec.short_name}`,
              onclick: () => prefillBooking(spec.slug) })))));

    const row = el("div", { class: "spec-row", role: "listitem", dataset: { modalities: spec.modalities.join(",") } },
      el("h3", { class: "spec-row-heading" }, trigger), panel);

    trigger.addEventListener("click", () => toggleSpecialty(row));
    body.append(row);
  });

  // Filtro por modalidade (Todas / Presencial / Online)
  $$(".segmented-btn").forEach((btn) => btn.addEventListener("click", () => {
    $$(".segmented-btn").forEach((b) => {
      b.classList.toggle("active", b === btn);
      b.setAttribute("aria-pressed", String(b === btn));
    });
    const mod = btn.dataset.modality;
    let visible = 0;
    $$(".spec-row").forEach((row) => {
      const show = mod === "todas" || row.dataset.modalities.split(",").includes(mod);
      row.hidden = !show;
      if (!show && row.classList.contains("is-open")) toggleSpecialty(row, false);
      if (show) visible += 1;
    });
    $("#specCount").textContent = `${visible} ${visible === 1 ? "especialidade" : "especialidades"}`
      + (mod === "todas" ? "" : mod === "Presencial" ? " com atendimento presencial" : " com teleconsulta");
  }));

  $("#specCount").textContent = `${specialties.length} especialidades`;
  Reveal.add($$(".spec-row"), "up");
}

function toggleSpecialty(row, force) {
  const open = force ?? !row.classList.contains("is-open");
  if (open) $$(".spec-row.is-open").forEach((other) => other !== row && toggleSpecialty(other, false));
  row.classList.toggle("is-open", open);
  $(".spec-trigger", row).setAttribute("aria-expanded", String(open));
  $(".spec-panel", row).inert = !open;
}

// ---------------------------------------------------------------- 5. Corpo clínico + modal de perfil
function renderTeam(specialties, doctors) {
  const filters = $("#teamFilters");
  filters.append(...specialties.map((s) => el("button", {
    type: "button", class: "filter-pill", "aria-pressed": "false",
    dataset: { specialtyFilter: s.slug }, text: s.short_name,
  })));
  $$(".filter-pill", filters).forEach((pill) => pill.addEventListener("click", () => filterTeam(pill.dataset.specialtyFilter)));

  const grid = $("#doctorsGrid");
  grid.replaceChildren(...doctors.map((doc) => {
    const photo = el("img", { src: doc.photo_url, alt: "", loading: "lazy" });
    const photoBtn = el("button", {
      type: "button", class: "doctor-photo-wrap", "aria-haspopup": "dialog",
      "aria-label": `Ver perfil completo de ${doc.name}`, onclick: () => openDoctorModal(doc.slug),
    },
      photo,
      el("span", { class: "doctor-initials", "aria-hidden": "true", text: initials(doc.name) }),
      el("span", { class: "doctor-modality", text: modalityLabel(doc.modalities) }),
      el("span", { class: "doctor-view" }, "Ver perfil", icon("plus", 14)));
    photo.addEventListener("error", () => photoBtn.classList.add("no-photo"), { once: true });

    return el("div", { class: "col-md-6 col-lg-4 doctor-item", dataset: { specialty: doc.specialty_slug } },
      el("article", { class: "doctor-card h-100" },
        photoBtn,
        el("div", { class: "doctor-body" },
          el("span", { class: "doctor-specialty", text: doc.specialty_label }),
          el("h3", { text: doc.name }),
          el("p", { class: "doctor-registry", text: doc.credential }),
          el("p", { class: "doctor-bio", text: doc.bio }),
          el("div", { class: "doctor-actions mt-auto" },
            el("button", { type: "button", class: "btn btn-link-clinic", text: "Ver perfil",
              "aria-haspopup": "dialog", "aria-label": `Ver perfil de ${doc.name}`, onclick: () => openDoctorModal(doc.slug) }),
            el("button", { type: "button", class: "btn btn-outline-clinic flex-grow-1", text: `Agendar com ${doc.first_name}`,
              onclick: () => prefillBooking(doc.specialty_slug, doc.slug) })))));
  }));

  Reveal.add($$(".doctor-card"), "up");
}

function filterTeam(specialtyKey, scroll = false) {
  let visible = 0;
  $$(".filter-pill").forEach((pill) => {
    const active = pill.dataset.specialtyFilter === specialtyKey;
    pill.classList.toggle("active", active);
    pill.setAttribute("aria-pressed", String(active));
  });
  $$(".doctor-item").forEach((card) => {
    const match = specialtyKey === "todas" || card.dataset.specialty === specialtyKey;
    card.classList.toggle("d-none", !match);
    if (match) {
      visible += 1;
      $(".doctor-card", card)?.classList.add("in");   // garante visibilidade após filtrar
    }
  });
  $("#doctorsEmpty").classList.toggle("d-none", visible > 0);
  if (scroll) $("#equipe").scrollIntoView({ behavior: motionOK ? "smooth" : "auto", block: "start" });
}

const doctorModalEl = $("#doctorModal");
let pendingBooking = null;

function openDoctorModal(slug) {
  const doc = state.byDoctor.get(slug);
  if (!doc || !window.bootstrap?.Modal) return;

  const section = (title, iconName, content) =>
    el("section", { class: "dm-section" }, el("h3", {}, icon(iconName, 16), title), content);

  const photo = el("img", { src: doc.photo_url, alt: `Foto de ${doc.name}` });
  const photoWrap = el("div", { class: "dm-photo" }, photo,
    el("span", { class: "doctor-initials", "aria-hidden": "true", text: initials(doc.name) }),
    el("span", { class: "doctor-modality", text: modalityLabel(doc.modalities) }));
  photo.addEventListener("error", () => photoWrap.classList.add("no-photo"), { once: true });

  $("#doctorModalBody").replaceChildren(el("div", { class: "dm-grid" },
    photoWrap,
    el("div", { class: "dm-info" },
      el("span", { class: "doctor-specialty", text: doc.specialty_label }),
      el("h2", { class: "dm-name", id: "doctorModalName", text: doc.name }),
      el("p", { class: "doctor-registry mb-3", text: doc.credential }),
      el("dl", { class: "dm-stats" },
        el("div", {}, el("dt", { text: "Experiência" }), el("dd", { text: `${doc.years_experience} anos` })),
        el("div", {}, el("dt", { text: "Atendimento" }), el("dd", { text: modalityLabel(doc.modalities) })),
        el("div", {}, el("dt", { text: "Idiomas" }), el("dd", { text: doc.languages.join(", ") }))),
      el("p", { class: "dm-about", text: doc.about }),
      section("Formação", "cap", el("ul", { class: "dm-list" }, doc.education.map((e) => el("li", { text: e })))),
      section("Áreas de atuação", "check", el("div", { class: "dm-chips" }, doc.focus_areas.map((a) => el("span", { class: "chip chip-static", text: a })))),
      section("Agenda de atendimento", "clock", el("ul", { class: "dm-list dm-schedule" }, doc.schedule.map((s) => el("li", { text: s })))),
      el("p", { class: "dm-note", text: "A recepção confirma o horário exato após o pré-agendamento." }),
      el("div", { class: "dm-actions" },
        el("button", { type: "button", class: "btn btn-outline-clinic", "data-bs-dismiss": "modal", text: "Fechar" }),
        el("button", { type: "button", class: "btn btn-primary-clinic flex-grow-1", text: `Agendar com ${doc.first_name}`,
          onclick: () => {
            pendingBooking = [doc.specialty_slug, doc.slug];
            window.bootstrap.Modal.getInstance(doctorModalEl)?.hide();
          } })))));

  window.bootstrap.Modal.getOrCreateInstance(doctorModalEl).show();
}

doctorModalEl.addEventListener("hidden.bs.modal", () => {
  if (!pendingBooking) return;
  const [spec, doc] = pendingBooking;
  pendingBooking = null;
  prefillBooking(spec, doc);
});

// ---------------------------------------------------------------- 6. Convênios: marquee infinito + busca
function renderInsurances(insurances) {
  const track = $("#insuranceTrack");
  const item = (ins, clone = false) => el("li", { class: `logo-item${ins.is_private ? " is-private" : ""}`, "aria-hidden": clone ? "true" : null },
    el("span", { class: "logo-mark", "aria-hidden": "true", text: ins.monogram }),
    el("span", { class: "logo-text" }, el("strong", { text: ins.name }), el("small", { text: ins.note })));

  track.replaceChildren(...insurances.map((ins) => item(ins)));
  if (motionOK) {
    // Duplica a lista para o loop contínuo; a cópia fica oculta para leitores de tela
    track.append(...insurances.map((ins) => item(ins, true)));
    track.style.setProperty("--marquee-duration", `${insurances.length * 4.5}s`);
    $("#insuranceMarquee").classList.add("is-animated");
  }

  const input = $("#insuranceSearch");
  const result = $("#insuranceResult");
  const index = insurances.map((ins) => ({ ins, haystack: normalizeText([ins.name, ...(ins.keywords || [])].join(" ")) }));

  input.addEventListener("input", () => {
    const query = normalizeText(input.value);
    if (!query) {
      result.replaceChildren();
      result.classList.remove("has-content");
      return;
    }
    const matches = index.filter(({ haystack }) => haystack.includes(query)).map(({ ins }) => ins);
    result.classList.add("has-content");

    if (matches.length) {
      result.replaceChildren(
        el("p", { class: "insurance-result-title", text: matches.length === 1 ? "Boa notícia: atendemos este plano." : `${matches.length} opções encontradas:` }),
        el("ul", { class: "insurance-result-list" }, matches.map((ins) => el("li", {},
          icon("check", 16), el("strong", { text: ins.name }), el("span", { text: ` — ${ins.note}` })))));
    } else {
      result.replaceChildren(
        el("p", { class: "insurance-result-title is-empty", text: `Não encontramos “${input.value.trim()}” na nossa lista.` }),
        el("p", { class: "insurance-result-copy", text: "Você pode ser atendido como particular, com nota fiscal para reembolso, ou confirmar a cobertura com a recepção." }),
        el("button", { type: "button", class: "btn btn-sm btn-soft-clinic", text: "Perguntar à assistente",
          onclick: () => window.ClinicAssistant?.open(`Vocês aceitam o convênio ${input.value.trim()}?`) }));
    }
  });
}

// ---------------------------------------------------------------- 7. FAQ
function renderFaqs(faqs) {
  const acc = $("#clinicFaqAccordion");
  acc.replaceChildren(...faqs.map((faq, i) => {
    const id = `faq${faq.id}`;
    const open = i === 0;
    return el("div", { class: "accordion-item" },
      el("h3", { class: "accordion-header" },
        el("button", {
          class: `accordion-button${open ? "" : " collapsed"}`, type: "button",
          "data-bs-toggle": "collapse", "data-bs-target": `#${id}`,
          "aria-expanded": String(open), "aria-controls": id, text: faq.question,
        })),
      el("div", { id, class: `accordion-collapse collapse${open ? " show" : ""}`, "data-bs-parent": "#clinicFaqAccordion" },
        el("div", { class: "accordion-body", text: faq.answer })));
  }));
  Reveal.add($$(".clinic-accordion .accordion-item"), "up");
}

// ---------------------------------------------------------------- 8. Pré-agendamento (envio para a API)
const bookingForm = $("#clinicBookingForm");
const fields = {
  patient_name: $("#patientName"),
  phone: $("#patientPhone"),
  specialty: $("#specialtySelect"),
  doctor: $("#doctorSelect"),
  modality: $("#modalitySelect"),
  insurance: $("#insuranceSelect"),
  preferred_date: $("#preferredDate"),
  period: $("#preferredPeriod"),
  consent: $("#privacyConsent"),
};
const modalityHint = $("#modalityHint");
const dateHint = $("#dateHint");
const dateInvalidMsg = $("#dateInvalidMsg");
const bookingAlert = $("#bookingAlert");
const submitBtn = $("#bookingSubmit");

function fillFormOptions(specialties, insurances) {
  fields.specialty.append(...specialties.map((s) => el("option", { value: s.slug, text: s.name })));
  fields.insurance.replaceChildren(
    ...insurances.filter((i) => i.is_private).map((i) => el("option", { value: i.slug, text: i.name })),
    ...insurances.filter((i) => !i.is_private).map((i) => el("option", { value: i.slug, text: i.name })),
    el("option", { value: "outro", text: "Outro convênio (reembolso)" }));
}

function updateDoctorOptions(specialtyKey, preselectedDoctor = "") {
  const spec = state.bySpecialty.get(specialtyKey);
  fields.doctor.replaceChildren(el("option", { value: "", text: "Sem preferência (primeiro horário)" }),
    ...(spec?.doctors || []).map((d) => el("option", { value: d.slug, text: d.name })));
  fields.doctor.value = preselectedDoctor;
  updateModalityOptions();
}

function updateModalityOptions() {
  const spec = state.bySpecialty.get(fields.specialty.value);
  if (!spec) return;
  const doctor = spec.doctors.find((d) => d.slug === fields.doctor.value);
  const allowed = (doctor || spec).modalities;
  const current = fields.modality.value;
  fields.modality.replaceChildren(...allowed.map((m) => el("option", { value: m, text: m === "Presencial" ? "Presencial na clínica" : "Teleconsulta (online)" })));
  if (allowed.includes(current)) fields.modality.value = current;
  modalityHint.textContent = allowed.length === 1
    ? `${doctor ? doctor.name : spec.name} atende exclusivamente ${allowed[0] === "Presencial" ? "de forma presencial" : "por teleconsulta"}.`
    : "Disponível presencialmente na clínica ou por teleconsulta.";
}

fields.specialty.addEventListener("change", () => updateDoctorOptions(fields.specialty.value));
fields.doctor.addEventListener("change", updateModalityOptions);

function prefillBooking(specialtyKey, doctorSlug = "") {
  fields.specialty.value = specialtyKey;
  updateDoctorOptions(specialtyKey, doctorSlug);
  [fields.specialty, fields.doctor].forEach((f) => f.classList.add("is-prefilled"));
  setTimeout(() => [fields.specialty, fields.doctor].forEach((f) => f.classList.remove("is-prefilled")), 1600);
  $("#agendamento").scrollIntoView({ behavior: motionOK ? "smooth" : "auto", block: "start" });
  setTimeout(() => (fields.patient_name.value ? fields.preferred_date : fields.patient_name).focus({ preventScroll: true }), motionOK ? 700 : 0);
}

// Máscara de telefone brasileiro
function formatPhoneBR(value) {
  const digits = value.replace(/\D/g, "").slice(0, 11);
  if (!digits) return "";
  if (digits.length <= 2) return `(${digits}`;
  const ddd = digits.slice(0, 2);
  const rest = digits.slice(2);
  const firstLen = rest.length > 8 ? 5 : 4;
  const part1 = rest.slice(0, firstLen);
  const part2 = rest.slice(firstLen, firstLen + 4);
  return rest.length <= firstLen ? `(${ddd}) ${part1}` : `(${ddd}) ${part1}-${part2}`;
}
fields.phone.addEventListener("input", (e) => { e.target.value = formatPhoneBR(e.target.value); });

// Datas: bloqueia passado e domingos; sábado só pela manhã
function getTodayISO() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}
function formatDateBR(isoDate) {
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Intl.DateTimeFormat("pt-BR", { weekday: "long", day: "2-digit", month: "long" }).format(new Date(y, m - 1, d));
}
fields.preferred_date.min = getTodayISO();

function validatePreferredDate(showFeedback = false) {
  const input = fields.preferred_date;
  const val = input.value;
  const afternoon = $('option[value="tarde"]', fields.period);
  input.setCustomValidity("");
  afternoon.disabled = false;
  afternoon.textContent = "Tarde (13h às 19h)";
  dateHint.textContent = "Segunda a sábado. Fechado aos domingos.";
  dateHint.classList.remove("text-danger");
  if (!val) return false;

  if (val < input.min) {
    input.setCustomValidity("Escolha hoje ou uma data futura.");
    dateInvalidMsg.textContent = "Não é possível selecionar datas que já passaram.";
  } else {
    const [y, m, d] = val.split("-").map(Number);
    const dayOfWeek = new Date(y, m - 1, d).getDay();
    if (dayOfWeek === 0) {
      input.setCustomValidity("A clínica não funciona aos domingos.");
      dateInvalidMsg.textContent = "Não atendemos aos domingos. Escolha outra data.";
    } else if (dayOfWeek === 6) {
      dateHint.textContent = "Aos sábados atendemos apenas pela manhã (08h às 13h).";
      afternoon.disabled = true;
      afternoon.textContent = "Tarde — indisponível aos sábados";
      if (fields.period.value === "tarde") fields.period.value = "manha";
    }
  }
  const valid = input.checkValidity();
  input.classList.toggle("is-invalid", !valid && showFeedback);
  return valid;
}
fields.preferred_date.addEventListener("change", () => validatePreferredDate(true));
fields.preferred_date.addEventListener("input", () => validatePreferredDate(false));

// Erros vindos da API → mensagem no campo correspondente
function feedbackFor(field) {
  const holder = field.closest(".col-md-6, .col-12, .form-check");
  return holder?.querySelector(".invalid-feedback");
}
function clearServerErrors() {
  Object.values(fields).forEach((f) => {
    if (f.dataset.serverError) {
      f.setCustomValidity("");
      delete f.dataset.serverError;
      f.classList.remove("is-invalid");
    }
  });
  bookingAlert.classList.add("d-none");
}
Object.values(fields).forEach((f) => ["input", "change"].forEach((ev) => f.addEventListener(ev, () => {
  if (!f.dataset.serverError) return;
  f.setCustomValidity("");
  delete f.dataset.serverError;
  f.classList.remove("is-invalid");
})));

function showServerErrors(detail) {
  let first = null;
  (Array.isArray(detail) ? detail : []).forEach(({ field, msg }) => {
    const input = fields[field];
    if (!input) return;
    input.setCustomValidity(msg);
    input.dataset.serverError = "1";
    input.classList.add("is-invalid");
    const fb = feedbackFor(input);
    if (fb) fb.textContent = msg;
    first ||= input;
  });
  first?.focus();
}

function showAlert(message, tone = "error") {
  bookingAlert.textContent = message;
  bookingAlert.dataset.tone = tone;
  bookingAlert.classList.remove("d-none");
}

function setSubmitting(on) {
  submitBtn.disabled = on;
  submitBtn.classList.toggle("is-loading", on);
  $(".btn-label", submitBtn).textContent = on ? "Enviando…" : "Enviar solicitação de agendamento";
}

function showSummary({ protocol, offline, values }) {
  const body = $("#bookingSummaryBody");
  $("#bookingModalEyebrow").textContent = offline ? "MODO DEMONSTRAÇÃO (SEM SERVIDOR)" : "SOLICITAÇÃO REGISTRADA";

  const items = [
    ["Paciente", values.name],
    ["WhatsApp", values.phone],
    ["Especialidade", values.specialty],
    ["Profissional", values.doctor],
    ["Modalidade", values.modality],
    ["Convênio / Plano", values.insurance],
    ["Data e período", `${values.date} — ${values.period}`],
  ];

  body.replaceChildren(
    protocol
      ? el("div", { class: "protocol-box" },
          el("span", { text: "Seu protocolo" }),
          el("strong", { text: protocol }),
          el("button", { type: "button", class: "btn btn-sm btn-soft-clinic", text: "Copiar",
            onclick: async (e) => {
              try { await navigator.clipboard.writeText(protocol); e.target.textContent = "Copiado ✓"; }
              catch { e.target.textContent = "Selecione e copie"; }
            } }))
      : null,
    el("p", { class: "mb-3", text: `Olá, ${values.name.split(" ")[0]}! ${offline
      ? "O servidor não está disponível agora, então a solicitação não foi registrada. Envie o resumo pelo WhatsApp para concluir:"
      : "Recebemos sua solicitação. A recepção vai confirmar o horário exato pelo WhatsApp:"}` }),
    el("ul", { class: "summary-list mb-3" }, items.map(([label, value]) => el("li", {}, el("strong", { text: `${label}: ` }), value))),
    el("div", { class: "alert alert-light border small mb-0", text: protocol
      ? "Guarde o protocolo: você pode consultar o status com a assistente virtual. Não enviamos dados clínicos."
      : "Projeto de portfólio: inicie o backend FastAPI para registrar as solicitações no banco SQLite." }));

  const waText = encodeURIComponent(
    `Olá! Gostaria de confirmar um pré-agendamento${protocol ? ` (protocolo ${protocol})` : ""}:\n`
    + items.filter(([l]) => l !== "WhatsApp").map(([l, v]) => `• ${l}: ${v}`).join("\n"));
  $("#whatsappConfirmLink").href = `https://wa.me/${state.data.clinic.whatsapp}?text=${waText}`;
  window.bootstrap?.Modal.getOrCreateInstance($("#bookingSummaryModal")).show();
}

bookingForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearServerErrors();
  const dateValid = validatePreferredDate(true);
  bookingForm.classList.add("was-validated");
  if (!bookingForm.checkValidity() || !dateValid) {
    bookingForm.querySelector(":invalid")?.focus();
    return;
  }

  const payload = {
    patient_name: fields.patient_name.value.trim(),
    phone: fields.phone.value.trim(),
    specialty: fields.specialty.value,
    doctor: fields.doctor.value || null,
    modality: fields.modality.value,
    insurance: fields.insurance.value,
    preferred_date: fields.preferred_date.value,
    period: fields.period.value,
    consent: fields.consent.checked,
  };
  const text = (sel) => sel.options[sel.selectedIndex].text;
  const values = {
    name: payload.patient_name, phone: payload.phone, specialty: text(fields.specialty), doctor: text(fields.doctor),
    modality: payload.modality, insurance: text(fields.insurance),
    date: formatDateBR(payload.preferred_date), period: text(fields.period),
  };

  setSubmitting(true);
  try {
    const res = await window.ClinicApi.post("/api/appointments", payload);
    showSummary({ protocol: res.protocol, offline: false, values });
  } catch (err) {
    if (err.status === 422) {
      showServerErrors(err.detail);
      showAlert("Revise os campos destacados para continuar.");
      return;
    }
    if (err.status === 0) {
      showSummary({ protocol: null, offline: true, values });
    } else {
      showAlert(err.message);
      return;
    }
  } finally {
    setSubmitting(false);
  }

  bookingForm.reset();
  bookingForm.classList.remove("was-validated");
  updateDoctorOptions("");
  fields.modality.replaceChildren(el("option", { value: "Presencial", text: "Presencial na clínica" }),
    el("option", { value: "Teleconsulta", text: "Teleconsulta (online)" }));
  modalityHint.textContent = "Escolha uma especialidade para ver as modalidades.";
  fields.preferred_date.min = getTodayISO();
  validatePreferredDate(false);
});

// Dicas e erros ligados a cada campo (aria-describedby); campo inválido é anunciado
Object.values(fields).forEach((field) => {
  const holder = field.closest(".col-md-6, .col-12");
  const notes = holder ? $$(".form-text, .invalid-feedback", holder) : [];
  notes.forEach((note, i) => { note.id ||= `${field.id}-nota-${i + 1}`; });
  if (notes.length) field.setAttribute("aria-describedby", notes.map((n) => n.id).join(" "));
});
bookingForm.addEventListener("invalid", (e) => e.target.setAttribute("aria-invalid", "true"), true);
bookingForm.addEventListener("input", (e) => e.target.removeAttribute("aria-invalid"));

// ---------------------------------------------------------------- 9b. Navegação
const navbar = $(".site-navbar");
const onScroll = () => navbar.classList.toggle("is-scrolled", window.scrollY > 8);
window.addEventListener("scroll", onScroll, { passive: true });
onScroll();

// Destaca no menu a seção visível
const navLinks = $$('#menuPrincipal .nav-link[href^="#"]');
if ("IntersectionObserver" in window) {
  const spy = new IntersectionObserver((entries) => entries.forEach((entry) => {
    if (!entry.isIntersecting) return;
    navLinks.forEach((a) => a.toggleAttribute("aria-current", a.getAttribute("href") === `#${entry.target.id}`));
  }), { rootMargin: "-45% 0px -50% 0px" });
  navLinks.forEach((a) => { const sec = $(a.getAttribute("href")); if (sec) spy.observe(sec); });
}

$$("#menuPrincipal .nav-link, #menuPrincipal .btn-nav").forEach((link) => link.addEventListener("click", () => {
  const nav = $("#menuPrincipal");
  if (nav.classList.contains("show") && window.bootstrap?.Collapse) window.bootstrap.Collapse.getOrCreateInstance(nav).hide();
}));

$("#currentYear").textContent = new Date().getFullYear();

// Scroll reveal de todo o site (elementos estáticos; os dinâmicos entram ao serem renderizados)
function initStaticReveal() {
  if (!Reveal.enabled) return;

  Reveal.add(".section-header > *", "up");
  Reveal.add("#sobre .about-collage", "left");
  Reveal.add("#sobre .col-lg-7 > :not(.row)", "up");
  Reveal.add(".pillar-card, .step-card, .quote-card", "up");
  Reveal.add(".spec-toolbar, .filter-bar", "fade");
  Reveal.add("#convenios .col-lg-7 > *", "up");
  Reveal.add("#convenios .col-lg-5", "right");
  Reveal.add(".logo-marquee", "fade");
  Reveal.add("#agendamento .col-lg-5 > *", "left");
  Reveal.add(".booking-card", "right");
  Reveal.add(".assistant-shortcut", "zoom");
  Reveal.add("#contato .col-lg-5 > *", "left");
  Reveal.add(".location-card", "right");
  Reveal.add(".compliance-note", "fade");
  Reveal.add(".site-footer .row > *", "up");
}

// ---------------------------------------------------------------- 10. API pública (usada pelo assistente)
window.ClinicUI = {
  book: prefillBooking,
  openDoctor: openDoctorModal,
  filterTeam: (spec) => filterTeam(spec, true),
  scrollTo: (target) => $(target)?.scrollIntoView({ behavior: motionOK ? "smooth" : "auto", block: "start" }),
  get data() { return state.data; },
};

// ---------------------------------------------------------------- Inicialização
initTypewriter();
initHeroCarousel();
initStaticReveal();

window.ClinicApi.loadCatalog().then((data) => {
  state.data = data;
  data.specialties.forEach((s) => state.bySpecialty.set(s.slug, s));
  data.doctors.forEach((d) => state.byDoctor.set(d.slug, d));

  renderSpecialties(data.specialties);
  renderTeam(data.specialties, data.doctors);
  renderInsurances(data.insurances);
  renderFaqs(data.faqs);
  fillFormOptions(data.specialties, data.insurances);
  document.dispatchEvent(new CustomEvent("clinic:ready", { detail: data }));
});
