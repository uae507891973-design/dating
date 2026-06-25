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
    common_questions: 7, reasons: ["Оба настроены на создание семьи", "Общие ценности", "Совпадение целей"] },
  { user_id: "u2", display_name: "Мария", age: 28, city: "Москва",
    bio: "Архитектор. Ищу серьёзные отношения и партнёра по путешествиям.",
    primary_photo: grad("#c8f7d4", "#6c4cf1"), is_verified: true, score: 81,
    common_questions: 7, reasons: ["Совпадение целей", "Взгляды на семью"] },
  { user_id: "u3", display_name: "Екатерина", age: 34, city: "Химки",
    bio: "Врач. Ценю честность и заботу.",
    primary_photo: grad("#ffe7b3", "#ff5e8a"), is_verified: false, score: 67,
    common_questions: 6, reasons: ["Стиль общения"] },
];
let MATCHES = [
  { match_id: "m1", other: CANDIDATES[0], last: "Привет! Рада мэтчу 🙂", unread: 1,
    messages: [{ me: false, body: "Привет! Рада мэтчу 🙂" }] },
];
const PREFS = { values: "normal", goals: "important", lifestyle: "normal", family: "normal", communication: "normal" };

// --- Состояние ---
const state = { tab: "discovery", qIndex: 0, answers: {}, importance: {}, cardIndex: 0, chat: null, video: null };

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
  const r = { onboarding: renderOnboarding, discovery: renderDiscovery,
    matches: state.chat ? renderChat : renderMatches, profile: renderProfile };
  screen().innerHTML = "";
  (r[state.tab] || renderDiscovery)();
}

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
      </div>`;
    return;
  }
  const q = QUESTIONS[state.qIndex];
  const sel = state.answers[q.id];
  const imp = state.importance[q.id] || "medium";
  screen().innerHTML = `
    <h2 class="title">Тест совместимости</h2>
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
  const c = CANDIDATES[state.cardIndex % CANDIDATES.length];
  screen().innerHTML = `
    <h2 class="title">Подбор</h2>
    <div class="swipe">
      <div class="profile-card">
        <div class="photo" style="background:${c.primary_photo}">
          <div class="gradient"></div>
          ${c.is_verified ? '<span class="vbadge">✓ Verified</span>' : ""}
          <div class="score-ring" style="--p:${c.score}"><i>${c.score}%</i></div>
          <div class="pname"><b>${c.display_name}, ${c.age}</b><div>📍 ${c.city}</div></div>
        </div>
        <div class="reasons">
          <h4>Почему вы подходите</h4>
          ${c.reasons.map((x) => `<div class="reason"><span class="dot"></span>${x}</div>`).join("")}
          <p class="muted" style="font-size:13px;margin-top:10px">${c.bio}</p>
        </div>
        <div class="actions">
          <button class="fab" onclick="nextCard()" title="Пропустить">✕</button>
          <button class="fab video" onclick="openVideo('${c.user_id}')" title="Видеознакомство">🎥</button>
          <button class="fab like" onclick="likeCard('${c.user_id}')" title="Лайк">❤</button>
        </div>
      </div>
    </div>
    ${renderPrefs()}`;
}

function renderPrefs() {
  const opts = [["muted", "Не важно"], ["normal", "Обычно"], ["important", "Важно"]];
  return `<div class="card">
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
window.likeCard = (id) => {
  const c = CANDIDATES.find((x) => x.user_id === id);
  if (!MATCHES.find((m) => m.other.user_id === id)) {
    MATCHES.unshift({ match_id: "m" + id, other: c, last: "Вы мэтчнулись!", unread: 0, messages: [] });
  }
  toast(`Это мэтч с ${c.display_name}! 💜`);
  state.cardIndex++; render();
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
        <button class="btn ghost" style="width:auto;padding:4px 8px" onclick="closeChat()">←</button>
        <div class="avatar" style="width:40px;height:40px;background:${m.other.primary_photo}"></div>
        <div><b>${m.other.display_name}</b><div class="muted" style="font-size:12px">онлайн</div></div>
        <button class="btn video" style="width:auto;margin-left:auto;padding:8px 12px;border-radius:20px" onclick="openVideo('${m.other.user_id}')">🎥</button>
      </div>
      <div class="bubbles" id="bubbles">
        ${m.messages.map((b) => `<div class="bubble ${b.me ? "me" : "them"}">${b.body}</div>`).join("") || '<p class="muted" style="text-align:center">Начните разговор 👇</p>'}
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
  state.chat.messages.push({ me: true, body: text.trim() });
  state.chat.last = text.trim();
  render();
  setTimeout(() => {
    state.chat.messages.push({ me: false, body: "Это так приятно слышать 🙂 Расскажешь подробнее?" });
    render();
  }, 900);
};

// --- Видеознакомство «вслепую» ---
window.openVideo = (uid) => {
  const c = CANDIDATES.find((x) => x.user_id === uid) || state.chat?.other;
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
  screen().innerHTML = `
    <div class="profile-head">
      <div class="big-ava" style="background:${grad("#b34cf1", "#ff5e8a")}"></div>
      <h2 style="margin:0">Вы</h2>
      <span class="pill ok">✓ Verified</span>
    </div>
    <div class="card">
      <div class="stat"><span>Намерение</span><b>Создание семьи</b></div>
      <div class="stat"><span>Тест совместимости</span><b>${answered}/${QUESTIONS.length} ответов</b></div>
      <div class="stat"><span>Верификация (селфи)</span><span class="pill ok">пройдена</span></div>
      <div class="stat"><span>Доверие (внутренне)</span><span class="pill info">100/100</span></div>
      <div class="stat"><span>Город</span><b>Москва</b></div>
    </div>
    <div class="card">
      <h4 style="margin:0 0 8px;font-size:13px;color:var(--muted);text-transform:uppercase">Безопасность</h4>
      <div class="stat"><span>Согласие 152-ФЗ</span><span class="pill ok">принято</span></div>
      <div class="stat"><span>Модерация фото</span><b>AI + ручная</b></div>
      <div class="stat"><span>Антифрод</span><b>активен</b></div>
    </div>`;
}

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

render();
