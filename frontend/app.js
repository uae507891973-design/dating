/* epic-davinci — визуальный прототип реализованного функционала.
   Данные моковые, но повторяют формат реального API backend. */

// --- Каталог вопросов теста (как в app/services/psychotest.py) ---
const QUESTIONS = [
  { id: "val_shared", category: "values", text: "Для меня важны общие ценности с партнёром" },
  { id: "goal_serious", category: "goals", text: "Я ищу серьёзные долгосрочные отношения" },
  { id: "goal_marriage", category: "goals", text: "Для меня важно прийти к браку" },
  { id: "fam_children", category: "family", text: "Я хочу детей" },
  { id: "fam_traditional", category: "family", text: "Мне близки традиционные ценности" },
  { id: "life_active", category: "lifestyle", text: "Я веду активный и здоровый образ жизни" },
  { id: "com_open", category: "communication", text: "Я открыто говорю о своих чувствах" },
];
const SCALE = ["Совсем не про меня", "Скорее нет", "Нейтрально", "Скорее да", "Точно про меня"];
const CAT_LABEL = {
  values: "общие ценности", goals: "совпадение целей", lifestyle: "образ жизни",
  family: "взгляды на семью", communication: "стиль общения",
};

// --- Мок-данные ---
const grad = (a, b) => `linear-gradient(135deg, ${a}, ${b})`;
const CANDIDATES = [
  { user_id: "u1", display_name: "Анна", age: 31, city: "Москва",
    bio: "Люблю книги, горы и тёплые разговоры по вечерам.",
    primary_photo: grad("#ffd1e3", "#b34cf1"), is_verified: true, score: 94,
    common_questions: 7, reasons: ["Оба настроены на создание семьи", "Общие ценности", "Совпадение целей"],
    online: true, video_enabled: true },
  { user_id: "u2", display_name: "Мария", age: 28, city: "Москва",
    bio: "Архитектор. Ищу серьёзные отношения и партнёра по путешествиям.",
    primary_photo: grad("#c8f7d4", "#6c4cf1"), is_verified: true, score: 81,
    common_questions: 7, reasons: ["Совпадение целей", "Взгляды на семью"],
    online: false, video_enabled: true },
  { user_id: "u3", display_name: "Екатерина", age: 34, city: "Химки",
    bio: "Врач. Ценю честность и заботу.",
    primary_photo: grad("#ffe7b3", "#ff5e8a"), is_verified: false, score: 67,
    common_questions: 6, reasons: ["Стиль общения"],
    online: true, video_enabled: false },
];

// Состояние видеозвонка к кандидату (зеркало backend video_state).
function videoState(c) {
  if (c.video_enabled === false) return "disabled";
  if (!c.online) return "offline";
  return "available";
}
const VIDEO_HINT = {
  disabled: "Собеседник отключил видеозвонки",
  offline: "Видеозвонок доступен, когда собеседник онлайн",
};
let MATCHES = [
  { match_id: "m1", other: CANDIDATES[0], last: "Привет! Рада мэтчу 🙂", unread: 1,
    messages: [{ me: false, body: "Привет! Рада мэтчу 🙂" }] },
];
const PREFS = { values: "normal", goals: "important", lifestyle: "normal", family: "normal", communication: "normal" };

// --- Юридические документы (как в /v1/legal/documents) ---
const LEGAL_DOCS = [
  { type: "privacy", version: "1.0", required: true,
    title: "Согласие на обработку персональных данных", url: "/legal/privacy" },
  { type: "terms", version: "1.0", required: true,
    title: "Пользовательское соглашение и оферта", url: "/legal/terms" },
  { type: "marketing", version: "1.0", required: false,
    title: "Согласие на информационные рассылки", url: "/legal/marketing" },
];

// --- Состояние ---
const state = {
  registered: false,
  reg: { step: "welcome", phone: "", code: "", consents: {} },
  tab: "discovery", qIndex: 0, answers: {}, importance: {}, cardIndex: 0, chat: null, video: null,
  favorites: [], verified: false, videoEnabledSelf: true,
};

const el = (id) => document.getElementById(id);
const screen = () => el("screen");

// --- Навигация ---
document.querySelectorAll(".tab").forEach((b) =>
  b.addEventListener("click", () => { setTab(b.dataset.tab); }));
function setTab(tab) {
  state.tab = tab;
  document.querySelectorAll(".tab").forEach((t) =>
    t.classList.toggle("active", t.dataset.tab === tab));
  render();
}

function render() {
  const tabbar = el("tabbar");
  const topbar = document.querySelector(".topbar");
  if (!state.registered) {
    if (tabbar) tabbar.style.display = "none";
    if (topbar) topbar.style.display = "none"; // верификация/шапка — только после регистрации
    screen().innerHTML = "";
    renderRegister();
    return;
  }
  if (tabbar) tabbar.style.display = "flex";
  if (topbar) topbar.style.display = "flex";
  const badge = el("trust-badge");
  if (badge) {
    badge.textContent = state.verified ? "✓ Verified" : "○ Не верифицирован";
    badge.style.opacity = state.verified ? "1" : ".7";
  }
  const r = { onboarding: renderOnboarding, discovery: renderDiscovery,
    matches: state.chat ? renderChat : renderMatches, profile: renderProfile,
    favorites: renderFavorites };
  screen().innerHTML = "";
  (r[state.tab] || renderDiscovery)();
}

// --- Приветствие (УТП + призыв к действию) ---
const USP = [
  ["🎯", "Совместимость, а не свайпы", "Подбор по ценностям и целям — с объяснением «почему вы подходите»"],
  ["🛡️", "Только реальные люди", "Верификация по селфи и антифрод — без ботов и анкет-пустышек"],
  ["🎥", "Видеознакомство «вслепую»", "Безопасный первый контакт до обмена контактами"],
  ["💍", "Для серьёзных отношений", "Аудитория, нацеленная на семью и долгие отношения"],
];

function renderWelcome() {
  screen().innerHTML = `
    <div class="welcome">
      <div class="hero">
        <div class="wlogo">❤</div>
        <h1>Найдите того, кто действительно подходит</h1>
        <p>Серьёзные знакомства, основанные на доверии и совместимости.</p>
      </div>
      <ul class="usp">
        ${USP.map(([i, t, s]) => `<li><span class="ico">${i}</span><span><b>${t}</b><small>${s}</small></span></li>`).join("")}
      </ul>
      <div class="cta">
        <button class="btn" onclick="goRegister()">Начать знакомиться →</button>
        <div class="sub">Бесплатно · 18+ · конфиденциально</div>
      </div>
    </div>`;
}
window.goRegister = () => { state.reg.step = "phone"; renderRegister(); };

// --- Регистрация + согласия (152-ФЗ) ---
function renderRegister() {
  const reg = state.reg;
  if (reg.step === "welcome") { renderWelcome(); return; }

  const requiredChecked = LEGAL_DOCS.filter((d) => d.required).every((d) => reg.consents[d.type]);
  const phoneValid = /^\+?[1-9]\d{9,14}$/.test((reg.phone || "").replace(/[\s()-]/g, ""));

  // ВАЖНО: oninput не перерисовывает экран (иначе поле теряет фокус после
  // каждой цифры) — обновляем состояние и только disabled-статус кнопки.
  const phoneStep = `
    <p class="muted" style="font-size:13px;margin:0 0 12px">
      Сначала примите обязательные документы, затем укажите номер — мы отправим код.</p>
    ${LEGAL_DOCS.map((d) => consentRow(d)).join("")}
    <div class="field" style="margin-top:14px">
      <label>Номер телефона</label>
      <input id="reg-phone" inputmode="tel" placeholder="+7 999 123-45-67"
        value="${reg.phone}"
        oninput="state.reg.phone=this.value;updateRegButtons()" />
    </div>
    <button class="btn" id="reg-submit" ${requiredChecked && phoneValid ? "" : "disabled"} onclick="reqCode()">
      Получить код</button>
    <div class="reg-legal">Нажимая «Получить код», вы подтверждаете, что вам исполнилось 18 лет.</div>`;

  const codeOk = (reg.code || "").length >= 4;
  const codeStep = `
    <div class="field">
      <label>Код из SMS</label>
      <input id="reg-code" inputmode="numeric" maxlength="6" placeholder="••••••"
        value="${reg.code}"
        oninput="state.reg.code=this.value;updateRegButtons()" />
      <div class="otp-note">Код отправлен на <b>${reg.phone}</b> · демо: введите любые 4–6 цифр</div>
    </div>
    <button class="btn" id="code-submit" ${codeOk ? "" : "disabled"} onclick="finishReg()">Зарегистрироваться</button>`;

  screen().innerHTML = `
    <div class="reg-head">
      <div class="logo-big">❤</div>
      <h2>${reg.step === "phone" ? "Регистрация" : "Подтверждение"}</h2>
      <p>${reg.step === "phone" ? "Согласия и номер телефона" : "Введите код из SMS"}</p>
    </div>
    ${reg.step === "phone" ? phoneStep : codeStep}`;
}

function consentRow(d) {
  const on = !!state.reg.consents[d.type];
  return `
    <div class="consent ${on ? "checked" : ""}" onclick="toggleConsent('${d.type}')">
      <div class="box">${on ? "✓" : ""}</div>
      <div class="ctext">
        Я принимаю <a href="${d.url}" onclick="event.stopPropagation()">«${d.title}»</a>
        ${d.required ? '<span class="req"> · обязательно</span>' : '<span class="opt"> · по желанию</span>'}
      </div>
    </div>`;
}
window.reqCode = () => {
  const required = LEGAL_DOCS.filter((d) => d.required);
  if (!required.every((d) => state.reg.consents[d.type])) {
    toast("Примите обязательные документы"); return;
  }
  const p = (state.reg.phone || "").replace(/[\s()-]/g, "");
  if (!/^\+?[1-9]\d{9,14}$/.test(p)) { toast("Введите корректный номер"); return; }
  state.reg.step = "code"; renderRegister();
};
window.updateRegButtons = () => {
  // Точечное обновление кнопок без перерисовки экрана (сохраняет фокус ввода).
  const submit = el("reg-submit");
  if (submit) {
    const requiredChecked = LEGAL_DOCS.filter((d) => d.required)
      .every((d) => state.reg.consents[d.type]);
    const phoneValid = /^\+?[1-9]\d{9,14}$/.test(
      (state.reg.phone || "").replace(/[\s()-]/g, "")
    );
    submit.disabled = !(requiredChecked && phoneValid);
  }
  const codeSubmit = el("code-submit");
  if (codeSubmit) {
    codeSubmit.disabled = (state.reg.code || "").length < 4;
  }
};
window.toggleConsent = (t) => { state.reg.consents[t] = !state.reg.consents[t]; renderRegister(); };
window.finishReg = () => {
  const accepted = LEGAL_DOCS.filter((d) => d.required).every((d) => state.reg.consents[d.type]);
  if (!accepted) { toast("Примите обязательные согласия"); return; }
  state.registered = true;
  state.tab = "onboarding";
  toast("Добро пожаловать! Согласия сохранены ✓");
  render();
};

// --- Онбординг ---
function renderOnboarding() {
  const total = QUESTIONS.length;
  const done = Object.keys(state.answers).length;
  if (state.qIndex >= total) {
    screen().innerHTML = `
      <h2 class="title">Тест пройден 🎉</h2>
      <div class="card">
        <p>Психопрофиль построен по ${total} ответам. Теперь подбор учитывает
        ваши ценности, цели и взгляды на семью.</p>
        <p class="muted">Намерение: <b>создание семьи</b></p>
        <button class="btn" onclick="setTab('discovery')">Перейти к подбору →</button>
      </div>
      ${state.verified ? "" : `
      <div class="card" style="text-align:center">
        <div class="heartbeat" style="font-size:32px">🪪</div>
        <p style="margin:6px 0 4px;font-weight:600">Повысьте доверие</p>
        <p class="muted" style="font-size:13px;margin:0 0 10px">
          Верифицированные анкеты получают больше внимания и приоритет в подборе.</p>
        <button class="btn secondary" onclick="verifyMe()">Пройти верификацию</button>
      </div>`}`;
    return;
  }
  const q = QUESTIONS[state.qIndex];
  const sel = state.answers[q.id];
  const imp = state.importance[q.id] || "medium";
  screen().innerHTML = `
    <h2 class="title">Тест совместимости</h2>
    <p class="muted" style="font-size:12px;margin:-8px 0 10px">Займёт ~1 минуту —
      и подбор станет точным. <a href="#" style="color:var(--primary)"
      onclick="event.preventDefault();setTab('discovery')">Заполнить позже</a></p>
    <div class="progress"><i style="width:${(done / total) * 100}%"></i></div>
    <div class="muted" style="font-size:13px">${CAT_LABEL[q.category]} · вопрос ${state.qIndex + 1}/${total}</div>
    <div class="q-text">${q.text}</div>
    <div class="scale">
      ${SCALE.map((s, i) => `<button class="${sel === i + 1 ? "sel" : ""}" onclick="answer('${q.id}',${i + 1})">${s}</button>`).join("")}
    </div>
    <div class="muted" style="font-size:12px;margin-top:16px">Насколько это важно для вас?</div>
    <div class="importance">
      ${["low", "medium", "high"].map((lv) => `<div class="chip ${imp === lv ? "sel" : ""}" onclick="setImp('${q.id}','${lv}')">${{ low: "Не важно", medium: "Обычно", high: "Важно" }[lv]}</div>`).join("")}
    </div>`;
}
window.answer = (id, v) => { state.answers[id] = v; setTimeout(() => { state.qIndex++; render(); }, 180); };
window.setImp = (id, lv) => { state.importance[id] = lv; render(); };

// --- Подбор (объяснимый мэтчинг) ---
function renderDiscovery() {
  // Гейт (как 409 profile_incomplete на backend): без теста — только превью.
  const testDone = Object.keys(state.answers).length >= QUESTIONS.length;
  if (!testDone) {
    screen().innerHTML = `
      <h2 class="title">Подбор</h2>
      <div class="swipe" aria-hidden="true" style="filter:blur(7px);pointer-events:none">
        <div class="profile-card">
          <div class="photo" style="background:${CANDIDATES[0].primary_photo}">
            <div class="gradient"></div>
            <div class="score-ring" style="--p:90"><i>90%</i></div>
            <div class="pname"><b>Ваши совпадения ждут</b></div>
          </div>
        </div>
      </div>
      <div class="card" style="text-align:center;margin-top:-40px;position:relative">
        <div style="font-size:30px">🔒</div>
        <p style="font-weight:600;margin:6px 0 4px">Пройдите тест — откроем подбор</p>
        <p class="muted" style="font-size:13px;margin:0 0 10px">
          1 минута — и мы покажем людей, совместимых именно с вами.</p>
        <button class="btn" onclick="setTab('onboarding')">Пройти тест (~1 мин)</button>
      </div>`;
    return;
  }

  // Пустое состояние: кандидаты на сегодня закончились.
  if (state.cardIndex >= CANDIDATES.length) {
    screen().innerHTML = `
      <h2 class="title">Подбор</h2>
      <div class="card" style="text-align:center;padding:30px 16px">
        <div class="heartbeat" style="font-size:42px">🌙</div>
        <p style="font-weight:600;margin:8px 0 4px">На сегодня всё</p>
        <p class="muted" style="font-size:13px;margin:0 0 12px">
          Качество важнее количества. Новые совместимые анкеты появятся позже —
          или расширьте параметры поиска.</p>
        <button class="btn secondary" onclick="widenSearch()">Расширить радиус поиска</button>
      </div>
      ${renderPrefs()}`;
    return;
  }

  const c = CANDIDATES[state.cardIndex];
  const vs = videoState(c);
  const videoBtn = {
    available: `<button class="fab video" onclick="openVideo('${c.user_id}')"
      title="Видеознакомство" aria-label="Видеознакомство вслепую">🎥</button>`,
    offline: `<button class="fab video off" onclick="toast('${VIDEO_HINT.offline}')"
      title="${VIDEO_HINT.offline}" aria-label="${VIDEO_HINT.offline}" aria-disabled="true">🎥<i class="fab-sub">zzz</i></button>`,
    disabled: `<button class="fab video off" onclick="toast('${VIDEO_HINT.disabled}')"
      title="${VIDEO_HINT.disabled}" aria-label="${VIDEO_HINT.disabled}" aria-disabled="true">🚫</button>`,
  }[vs];

  screen().innerHTML = `
    <h2 class="title">Подбор</h2>
    <div class="swipe">
      <div class="profile-card">
        <div class="photo" style="background:${c.primary_photo}">
          <div class="gradient"></div>
          ${c.is_verified ? '<span class="vbadge">✓ Verified</span>' : ""}
          <div class="score-ring" style="--p:${c.score}"><i>${c.score}%</i></div>
          <div class="pname">
            <b>${c.display_name}, ${c.age}</b>
            <div>📍 ${c.city} ·
              <span class="online-chip ${c.online ? "on" : ""}">${c.online ? "● онлайн" : "○ офлайн"}</span>
            </div>
          </div>
        </div>
        <div class="reasons">
          <h4>Почему вы подходите</h4>
          ${c.reasons.map((x) => `<div class="reason"><span class="dot"></span>${x}</div>`).join("")}
          <p class="muted" style="font-size:13px;margin-top:10px">${c.bio}</p>
        </div>
        <div class="actions">
          <button class="fab" onclick="nextCard()" title="Пропустить" aria-label="Пропустить анкету">✕</button>
          <button class="fab msg" onclick="openChatFromCard('${c.user_id}')" title="Написать сообщение" aria-label="Написать сообщение">💬</button>
          ${videoBtn}
          <button class="fab like" onclick="likeCard('${c.user_id}')" title="Лайк" aria-label="Поставить лайк">❤</button>
        </div>
      </div>
    </div>
    ${renderPrefs()}`;
}

// Переписка прямо с карточки (диалог без взаимного лайка, как на backend).
window.openChatFromCard = (uid) => {
  const c = CANDIDATES.find((x) => x.user_id === uid);
  let m = MATCHES.find((x) => x.other.user_id === uid);
  if (!m) {
    m = { match_id: "d" + uid, other: c, last: "Напишите первым 👋",
      unread: 0, messages: [], origin: "direct" };
    MATCHES.unshift(m);
  }
  state.chat = m;
  setTab("matches");
};

function renderPrefs() {
  const opts = [["muted", "Не важно"], ["normal", "Обычно"], ["important", "Важно"]];
  return `<div class="card" style="margin-top:24px">
    <h4 style="margin:0 0 6px;font-size:13px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em">Что важнее в подборе</h4>
    <p class="muted" style="font-size:12px;margin:0 0 8px">Влияет на ранжирование (scrutability)</p>
    ${Object.keys(CAT_LABEL).map((cat) => `
      <div class="pref">
        <span style="font-size:14px">${CAT_LABEL[cat]}</span>
        <div class="seg">
          ${opts.map(([v, l]) => `<button class="${PREFS[cat] === v ? "sel" : ""}" onclick="setPref('${cat}','${v}')">${l}</button>`).join("")}
        </div>
      </div>`).join("")}
  </div>`;
}
window.setPref = (cat, v) => { PREFS[cat] = v; render(); };
window.nextCard = () => { state.cardIndex++; render(); };
window.widenSearch = () => {
  state.cardIndex = 0;  // демо: расширение радиуса возвращает анкеты
  toast("Радиус поиска расширен 📍");
  render();
};
window.likeCard = (id) => {
  const c = CANDIDATES.find((x) => x.user_id === id);
  if (!state.favorites.find((f) => f.user_id === id)) state.favorites.push(c);
  if (!MATCHES.find((m) => m.other.user_id === id)) {
    MATCHES.unshift({ match_id: "m" + id, other: c, last: "Вы мэтчнулись!", unread: 0, messages: [] });
  }
  toast(`Это мэтч с ${c.display_name}! 💜`);
  state.cardIndex++; render();
};

// --- Избранное ---
function renderFavorites() {
  if (!state.favorites.length) {
    screen().innerHTML = `
      <h2 class="title">Избранное</h2>
      <div class="card" style="text-align:center;padding:30px 16px">
        <div class="heartbeat" style="font-size:44px">⭐</div>
        <p class="muted">Здесь будут анкеты, которым вы поставили ❤.<br>Лайкайте в подборе.</p>
        <button class="btn secondary" onclick="setTab('discovery')">К подбору</button>
      </div>`;
    return;
  }
  screen().innerHTML = `<h2 class="title">Избранное</h2>
    <div class="fav-grid">
      ${state.favorites.map((c) => `
        <div class="fav-card" onclick="openChatByUser('${c.user_id}')">
          <div class="fav-photo" style="background:${c.primary_photo}">
            <span class="fav-score">${c.score}%</span>
            ${c.is_verified ? '<span class="fav-v">✓</span>' : ""}
          </div>
          <div class="fav-name">${c.display_name}, ${c.age}</div>
          <div class="muted" style="font-size:12px">📍 ${c.city}</div>
        </div>`).join("")}
    </div>`;
}
window.openChatByUser = (uid) => {
  const m = MATCHES.find((x) => x.other.user_id === uid);
  if (m) { openChat(m.match_id); } else { setTab("matches"); }
};

// --- Мэтчи и чат ---
function renderMatches() {
  if (!MATCHES.length) { screen().innerHTML = `<h2 class="title">Чат</h2><p class="muted">Пока нет мэтчей. Лайкайте в подборе ❤</p>`; return; }
  screen().innerHTML = `<h2 class="title">Мэтчи</h2>` + MATCHES.map((m) => `
    <div class="match-item" onclick="openChat('${m.match_id}')">
      <div class="avatar" style="background:${m.other.primary_photo}"></div>
      <div class="match-meta">
        <b>${m.other.display_name} ${m.other.is_verified ? "✓" : ""}</b>
        <small>${m.last}</small>
      </div>
      ${m.unread ? `<span class="pill info">${m.unread}</span>` : ""}
    </div>`).join("");
}
window.openChat = (id) => { state.chat = MATCHES.find((m) => m.match_id === id); state.chat.unread = 0; setTab("matches"); };

function renderChat() {
  const m = state.chat;
  const ice = ["Что в анкете зацепило вас больше всего?", "Оба за серьёзное — каким видите будущее?"];
  screen().innerHTML = `
    <div class="chat">
      <div class="chat-head">
        <button class="btn ghost" style="width:auto;padding:4px 8px" onclick="closeChat()" aria-label="Назад">←</button>
        <div class="avatar" style="width:40px;height:40px;background:${m.other.primary_photo}"></div>
        <div><b>${m.other.display_name}</b>
          <div class="muted" style="font-size:12px">${m.other.online ? "онлайн" : "офлайн"}</div></div>
        ${(() => {
          const vs = videoState(m.other);
          if (vs === "available") return `<button class="btn video-chip" onclick="openVideo('${m.other.user_id}')" aria-label="Видеозвонок">🎥</button>`;
          const hint = VIDEO_HINT[vs];
          const icon = vs === "disabled" ? "🚫" : "🎥";
          return `<button class="btn video-chip off" onclick="toast('${hint}')" title="${hint}" aria-label="${hint}" aria-disabled="true">${icon}</button>`;
        })()}
      </div>
      ${m.safetyDismissed ? "" : `
      <div class="card" style="margin:0 0 10px;padding:10px 12px;background:#f0fbf5">
        <div style="display:flex;gap:8px;align-items:flex-start">
          <span style="font-size:18px">🛡️</span>
          <div style="flex:1;font-size:12px;line-height:1.45">
            <b>Безопасное знакомство:</b> не переводите деньги, не делитесь
            адресом и документами. Первая встреча — в людном месте; предупредите
            близких. Видеозвонок в приложении — безопасный способ проверить собеседника.
          </div>
          <button class="btn ghost" style="width:auto;padding:0 4px" aria-label="Скрыть совет"
            onclick="state.chat.safetyDismissed=true;render()">✕</button>
        </div>
      </div>`}
      <div class="bubbles" id="bubbles">
        ${m.messages.map((b) => `<div class="bubble ${b.me ? "me" : "them"}">${b.body}${
          b.me ? `<span style="font-size:10px;opacity:.75;margin-left:6px">${b.status === "read" ? "✓✓" : "✓"}</span>` : ""
        }</div>`).join("") || '<p class="muted" style="text-align:center">Начните разговор 👇</p>'}
        ${m.typing ? '<div class="bubble them" style="opacity:.7">печатает<span class="dots">…</span></div>' : ""}
      </div>
      <div class="icebreakers">
        ${ice.map((t) => `<button class="ice" onclick="sendMsg(this.textContent)">${t}</button>`).join("")}
      </div>
      <div class="composer">
        <input id="msg" placeholder="Сообщение..." onkeydown="if(event.key==='Enter')sendMsg(this.value)" />
        <button onclick="sendMsg(document.getElementById('msg').value)">➤</button>
      </div>
    </div>`;
  const b = el("bubbles"); if (b) b.scrollTop = b.scrollHeight;
}
window.closeChat = () => { state.chat = null; render(); };
window.sendMsg = (text) => {
  if (!text || !text.trim()) return;
  state.chat.messages.push({ me: true, body: text.trim(), status: "sent" });
  state.chat.last = text.trim();
  state.chat.typing = true;  // собеседник «печатает»
  render();
  setTimeout(() => {
    // Собеседник прочитал и отвечает: мои сообщения -> ✓✓.
    state.chat.messages.forEach((b) => { if (b.me) b.status = "read"; });
    state.chat.typing = false;
    state.chat.messages.push({ me: false, body: "Это так приятно слышать 🙂 Расскажешь подробнее?" });
    render();
  }, 1100);
};

// --- Видеознакомство «вслепую» ---
window.openVideo = (uid) => {
  const c = CANDIDATES.find((x) => x.user_id === uid) || state.chat?.other;
  // Guard (зеркало backend 409 video_unavailable): запрет или офлайн.
  const vs = videoState(c);
  if (vs !== "available") { toast(VIDEO_HINT[vs]); return; }
  state.video = { other: c, blur: 1, revealed: false, continueMe: false, continueThem: true, seconds: 180, status: "active" };
  drawVideo();
  state.video.timer = setInterval(() => {
    if (!state.video) return;
    state.video.seconds--; drawVideo();
    if (state.video.seconds <= 0) endVideo();
  }, 1000);
};
function drawVideo() {
  const v = state.video; if (!v) return;
  const mm = String(Math.floor(v.seconds / 60)).padStart(1, "0");
  const ss = String(v.seconds % 60).padStart(2, "0");
  const blurPx = (v.revealed ? 0 : v.blur * 18).toFixed(0);
  let modal = el("video-modal");
  if (!modal) { modal = document.createElement("div"); modal.id = "video-modal"; modal.className = "modal"; document.querySelector(".phone").appendChild(modal); }
  modal.innerHTML = `
    <div class="video-box">
      <div class="video-feed" style="background:${v.other.primary_photo};filter:blur(${blurPx}px)">
        <span class="timer">⏱ ${mm}:${ss}</span>
        <span class="blurtag">${v.revealed ? "Открыто 👀" : "Блюр " + Math.round(v.blur * 100) + "%"}</span>
      </div>
      <div class="video-controls">
        <div style="font-weight:600">${v.other.display_name} · видеознакомство «вслепую»</div>
        ${v.revealed ? '<div class="reveal-note">Вы оба согласились — видео открыто ✨</div>' : `
          <label>Уровень размытия (управляет получатель)</label>
          <input type="range" min="0" max="1" step="0.05" value="${v.blur}" oninput="setBlur(this.value)" />
          <div class="reveal-note">Собеседник готов открыть видео. Согласны?</div>`}
        <div class="video-actions">
          ${v.revealed ? "" : `<button class="btn secondary" onclick="continueVideo()">${v.continueMe ? "Вы за ✓" : "Продолжить"}</button>`}
          <button class="btn danger" onclick="endVideo()">Завершить</button>
        </div>
      </div>
    </div>`;
}
window.setBlur = (val) => { state.video.blur = parseFloat(val); drawVideo(); };
window.continueVideo = () => {
  state.video.continueMe = true;
  if (state.video.continueThem && state.video.continueMe) { state.video.revealed = true; state.video.blur = 0; }
  drawVideo();
};
window.endVideo = () => {
  if (state.video?.timer) clearInterval(state.video.timer);
  const reached = state.video?.revealed;
  state.video = null;
  const m = el("video-modal"); if (m) m.remove();
  toast(reached ? "Видеознакомство состоялось — +доверие 💚" : "Звонок завершён");
};

// --- Профиль ---
function renderProfile() {
  const answered = Object.keys(state.answers).length;
  const v = state.verified;
  screen().innerHTML = `
    <div class="profile-head">
      <div class="big-ava" style="background:${grad("#b34cf1", "#ff5e8a")}"></div>
      <h2 style="margin:0">Вы</h2>
      <span class="pill ${v ? "ok" : "info"}">${v ? "✓ Verified" : "○ Не верифицирован"}</span>
    </div>
    ${v ? "" : `
    <div class="card" style="text-align:center">
      <div class="heartbeat" style="font-size:36px">🪪</div>
      <p style="margin:8px 0 4px;font-weight:600">Пройдите верификацию</p>
      <p class="muted" style="font-size:13px;margin:0 0 12px">Селфи-проверка повышает доверие и приоритет в подборе.</p>
      <button class="btn" onclick="verifyMe()">Сделать селфи и верифицироваться</button>
    </div>`}
    <div class="card">
      <div class="stat"><span>Намерение</span><b>Создание семьи</b></div>
      <div class="stat"><span>Тест совместимости</span><b>${answered}/${QUESTIONS.length} ответов</b></div>
      <div class="stat"><span>Верификация (селфи)</span><span class="pill ${v ? "ok" : "info"}">${v ? "пройдена" : "не пройдена"}</span></div>
      <div class="stat"><span>Доверие (внутренне)</span><span class="pill info">${v ? 100 : 90}/100</span></div>
      <div class="stat"><span>Город</span><b>Москва</b></div>
    </div>
    <div class="card">
      <h4 style="margin:0 0 8px;font-size:13px;color:var(--muted);text-transform:uppercase">Приватность</h4>
      <div class="stat">
        <span>Принимать видеозвонки</span>
        <button class="switch ${state.videoEnabledSelf ? "on" : ""}" role="switch"
          aria-checked="${state.videoEnabledSelf}" aria-label="Принимать видеозвонки"
          onclick="toggleMyVideo()"><i></i></button>
      </div>
      ${state.videoEnabledSelf ? "" : `<p class="muted" style="font-size:12px;margin:6px 0 0">
        Вам не смогут звонить — кнопка видеозвонка у собеседников будет отключена.</p>`}
    </div>
    <div class="card">
      <h4 style="margin:0 0 8px;font-size:13px;color:var(--muted);text-transform:uppercase">Безопасность</h4>
      <div class="stat"><span>Согласие 152-ФЗ</span><span class="pill ok">принято</span></div>
      <div class="stat"><span>Модерация фото</span><b>AI + ручная</b></div>
      <div class="stat"><span>Антифрод</span><b>активен</b></div>
    </div>`;
}

window.toggleMyVideo = () => {
  state.videoEnabledSelf = !state.videoEnabledSelf;
  // На backend: PUT /v1/profile { video_calls_enabled: ... }
  toast(state.videoEnabledSelf
    ? "Видеозвонки включены 🎥"
    : "Видеозвонки отключены — вам не смогут звонить");
  render();
};

window.verifyMe = () => {
  state.verified = true;
  toast("Верификация пройдена ✓ +доверие");
  render();
};

// --- Тост ---
function toast(text) {
  let t = document.createElement("div");
  t.textContent = text;
  Object.assign(t.style, { position: "absolute", bottom: "78px", left: "50%", transform: "translateX(-50%)",
    background: "#1d1b29", color: "#fff", padding: "10px 16px", borderRadius: "20px", fontSize: "13px", zIndex: 30, boxShadow: "0 8px 20px rgba(0,0,0,.3)" });
  document.querySelector(".phone").appendChild(t);
  setTimeout(() => t.remove(), 1800);
}

// --- Легенда (что реализовано) ---
el("legend").innerHTML = [
  ["Стадия 0", "фундамент, БД, CI"],
  ["Стадия 1", "регистрация, тест, анкета, верификация"],
  ["Стадия 2", "подбор, объяснимый мэтчинг, чат"],
  ["Стадия 3", "антифрод, видео «вслепую», уведомления"],
].map(([a, b]) => `<li><b>${a}:</b> ${b}</li>`).join("");

// Прелоудер: показываем сплеш, затем приветственный экран.
render();
setTimeout(() => {
  const pl = document.getElementById("preloader");
  if (pl) pl.classList.add("hidden");
}, 1700);
