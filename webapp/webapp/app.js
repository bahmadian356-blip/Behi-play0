/*
 * BEHI PLAY — Mini App client
 *
 * توجه: SUPABASE_ANON_KEY و API_BASE_URL اطلاعات محرمانه نیستند (anon key برای همین طراحی شده)
 * اما SERVICE_ROLE_KEY هرگز نباید اینجا قرار بگیرد.
 */
const CONFIG = {
  API_BASE_URL: "https://YOUR-API-DOMAIN.example.com", // آدرس دیپلوی api/main.py (FastAPI)
  SUPABASE_URL: "https://YOUR-PROJECT.supabase.co",
  SUPABASE_ANON_KEY: "YOUR_SUPABASE_ANON_PUBLIC_KEY",
};

const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

const initData = tg?.initData || "";

// ---------- State ----------
let currentProfile = null;
let currentGameId = null;
let currentQuestions = [];
let currentQuestionIndex = 0;
let quizTimerInterval = null;
let realtimeChannel = null;

// ---------- Supabase (client-side, anon key, فقط برای خواندن Realtime) ----------
let supabaseClient = null;
function loadSupabaseSdk(callback) {
  if (window.supabase) return callback();
  const script = document.createElement("script");
  script.src = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.js";
  script.onload = callback;
  document.head.appendChild(script);
}

// ---------- API helper ----------
async function api(path, method = "GET", body = null) {
  const res = await fetch(`${CONFIG.API_BASE_URL}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

// ---------- Navigation ----------
function navigate(view) {
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  document.getElementById(`view-${view}`)?.classList.add("active");
  document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
  document.querySelector(`.nav-btn[data-nav="${view}"]`)?.classList.add("active");

  if (view === "leaderboard") loadLeaderboard();
  if (view === "profile") loadProfile();
}

document.querySelectorAll("[data-nav]").forEach((el) => {
  el.addEventListener("click", () => navigate(el.dataset.nav));
});

// ---------- Boot ----------
async function boot() {
  try {
    const { profile } = await api("/auth/verify", "POST", { init_data: initData });
    currentProfile = profile;
    renderHero();
  } catch (e) {
    document.getElementById("heroName").textContent = "خطا در ورود — دوباره امتحان کن";
    console.error(e);
  }

  loadSupabaseSdk(() => {
    supabaseClient = window.supabase.createClient(CONFIG.SUPABASE_URL, CONFIG.SUPABASE_ANON_KEY);
  });

  // اگر بات با game_id باز کرده باشد (از start param یا query)
  const params = new URLSearchParams(window.location.search);
  const gameId = params.get("game_id") || tg?.initDataUnsafe?.start_param?.replace("game_", "");
  if (gameId) {
    currentGameId = gameId;
    await joinGameFlow(gameId);
  }
}

function renderHero() {
  if (!currentProfile) return;
  const name = currentProfile.first_name || currentProfile.username || "بازیکن";
  document.getElementById("heroName").textContent = name;
  document.getElementById("xpChip").textContent = `Lv. ${currentProfile.level} · ${currentProfile.xp} XP`;

  const xpIntoLevel = currentProfile.xp % 100;
  document.getElementById("xpFill").style.width = `${xpIntoLevel}%`;
  document.getElementById("xpSub").textContent = `${xpIntoLevel} / 100 XP`;
}

// ---------- Create game ----------
document.getElementById("btnCreateGame").addEventListener("click", async () => {
  const name = prompt("نام اتاق را وارد کن:", "اتاق دوستانه");
  if (!name) return;
  try {
    const { game } = await api("/games", "POST", {
      init_data: initData,
      name,
      game_type: "quiz",
      max_players: 8,
      is_public: false,
    });
    currentGameId = game.id;
    enterRoom(game);
    navigate("compete");
  } catch (e) {
    alert("خطا در ساخت بازی: " + e.message);
  }
});

async function joinGameFlow(gameId) {
  try {
    await api(`/games/${gameId}/join`, "POST", { init_data: initData, game_id: gameId });
    const { game } = await api(`/games/${gameId}`);
    enterRoom(game);
    navigate("compete");
  } catch (e) {
    alert("پیوستن به بازی ناموفق بود: " + e.message);
  }
}

function enterRoom(game) {
  document.getElementById("roomEmpty").classList.add("hidden");
  document.getElementById("roomActive").classList.remove("hidden");
  document.getElementById("roomName").textContent = game.name;

  const isHost = currentProfile && game.host_id === currentProfile.telegram_id;
  document.getElementById("btnStartGame").classList.toggle("hidden", !isHost);

  refreshRoomPlayers();
  subscribeToRoom(game.id);
}

async function refreshRoomPlayers() {
  if (!currentGameId) return;
  const { game, players } = await api(`/games/${currentGameId}`);
  const list = document.getElementById("roomPlayers");
  list.innerHTML = players
    .map(
      (p) =>
        `<div class="player-row"><span>${p.profiles?.first_name || "بازیکن"}${p.is_host ? " (میزبان)" : ""}</span><span>${p.score || 0} امتیاز</span></div>`
    )
    .join("");

  if (game.status === "in_progress") startQuizFlow(currentGameId);
}

function subscribeToRoom(gameId) {
  if (!supabaseClient) {
    // اگر SDK هنوز لود نشده، کمی صبر کن
    setTimeout(() => subscribeToRoom(gameId), 500);
    return;
  }
  if (realtimeChannel) supabaseClient.removeChannel(realtimeChannel);

  realtimeChannel = supabaseClient
    .channel(`game-${gameId}`)
    .on(
      "postgres_changes",
      { event: "*", schema: "public", table: "games", filter: `id=eq.${gameId}` },
      (payload) => {
        if (payload.new?.status === "in_progress") startQuizFlow(gameId);
      }
    )
    .on(
      "postgres_changes",
      { event: "*", schema: "public", table: "game_players", filter: `game_id=eq.${gameId}` },
      () => refreshRoomPlayers()
    )
    .subscribe();
}

document.getElementById("btnStartGame").addEventListener("click", async () => {
  try {
    await api(`/games/${currentGameId}/start`, "POST", {
      init_data: initData,
      game_id: currentGameId,
    });
  } catch (e) {
    alert("شروع بازی ناموفق بود: " + e.message);
  }
});

document.getElementById("btnCopyInvite").addEventListener("click", () => {
  if (!currentGameId) return;
  const link = `https://t.me/YOUR_BOT_USERNAME?start=game_${currentGameId}`;
  navigator.clipboard?.writeText(link);
  tg?.showPopup ? tg.showPopup({ message: "لینک دعوت کپی شد!" }) : alert("لینک کپی شد: " + link);
});

// ---------- Quiz flow ----------
async function startQuizFlow(gameId) {
  currentGameId = gameId;
  const { questions } = await api(`/quiz/${gameId}/questions`);
  currentQuestions = questions;
  currentQuestionIndex = 0;
  navigate("quiz");
  renderQuestion();
}

function renderQuestion() {
  const q = currentQuestions[currentQuestionIndex];
  if (!q) {
    finishQuizIfHost();
    return;
  }

  document.getElementById("quizProgress").textContent =
    `سوال ${currentQuestionIndex + 1} از ${currentQuestions.length}`;
  document.getElementById("quizQuestion").textContent = q.question_text;

  const optionsEl = document.getElementById("quizOptions");
  optionsEl.innerHTML = "";
  (q.options || []).forEach((opt, idx) => {
    const btn = document.createElement("div");
    btn.className = "quiz-option";
    btn.textContent = opt;
    btn.addEventListener("click", () => selectAnswer(q, idx, btn));
    optionsEl.appendChild(btn);
  });

  let timeLeft = q.time_limit_seconds || 15;
  const startedAt = Date.now();
  document.getElementById("quizTimer").textContent = timeLeft;
  clearInterval(quizTimerInterval);
  quizTimerInterval = setInterval(() => {
    timeLeft -= 1;
    document.getElementById("quizTimer").textContent = Math.max(timeLeft, 0);
    if (timeLeft <= 0) {
      clearInterval(quizTimerInterval);
      nextQuestion();
    }
  }, 1000);

  optionsEl.dataset.startedAt = startedAt;
}

async function selectAnswer(question, selectedIndex, btnEl) {
  clearInterval(quizTimerInterval);
  const startedAt = Number(document.getElementById("quizOptions").dataset.startedAt || Date.now());
  const timeTaken = Date.now() - startedAt;

  document.querySelectorAll(".quiz-option").forEach((el) => (el.style.pointerEvents = "none"));

  try {
    const result = await api("/quiz/answer", "POST", {
      init_data: initData,
      game_id: currentGameId,
      question_id: question.id,
      selected_option: selectedIndex,
      time_taken_ms: timeTaken,
    });
    btnEl.classList.add(result.is_correct ? "correct" : "wrong");
  } catch (e) {
    console.error(e);
  }

  setTimeout(nextQuestion, 900);
}

function nextQuestion() {
  currentQuestionIndex += 1;
  renderQuestion();
}

async function finishQuizIfHost() {
  if (!currentProfile) return;
  try {
    const { game } = await api(`/games/${currentGameId}`);
    if (game.host_id === currentProfile.telegram_id) {
      await api(`/games/${currentGameId}/finish`, "POST", {
        init_data: initData,
        game_id: currentGameId,
      });
    }
  } catch (e) {
    console.error(e);
  }
  navigate("leaderboard");
  loadLeaderboard();
}

// ---------- Leaderboard ----------
async function loadLeaderboard() {
  try {
    const { leaderboard } = await api("/leaderboard?limit=20");
    const list = document.getElementById("leaderboardList");
    list.innerHTML = leaderboard
      .map(
        (p, idx) =>
          `<li><span class="rank-badge">#${idx + 1}</span><span>${p.first_name || p.username || "بازیکن"}</span><span>${p.xp} XP</span></li>`
      )
      .join("");
  } catch (e) {
    console.error(e);
  }
}

// ---------- Profile ----------
async function loadProfile() {
  if (!currentProfile) return;
  const card = document.getElementById("profileCard");
  card.innerHTML = `
    <div class="profile-row"><span>یوزرنیم</span><b>@${currentProfile.username || "—"}</b></div>
    <div class="profile-row"><span>Level</span><b>${currentProfile.level}</b></div>
    <div class="profile-row"><span>XP</span><b>${currentProfile.xp}</b></div>
    <div class="profile-row"><span>بازی‌ها</span><b>${currentProfile.games_played}</b></div>
    <div class="profile-row"><span>برد</span><b>${currentProfile.wins}</b></div>
    <div class="profile-row"><span>باخت</span><b>${currentProfile.losses}</b></div>
  `;
}

boot();
