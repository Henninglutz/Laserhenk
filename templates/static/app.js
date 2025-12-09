/* HENK Frontend — minimal, dependency-free
 * Configure your backend endpoint below. The backend is expected to accept:
 * POST /api/henk/chat { message: string, history?: Message[] }
 * and return: { reply: string }
 */

const CONFIG = {
  // Laserhenk backend chat endpoint
  BACKEND_URL: "/api/chat",
  USE_SPEECH: true,                      // voice input if supported
  MAX_HISTORY: 20                        // how many last messages to send along
};

const els = {
  chat: document.getElementById("chat"),
  form: document.getElementById("composer"),
  input: document.getElementById("message"),
  send: document.getElementById("sendBtn"),
  mic: document.getElementById("micBtn"),
  clear: document.getElementById("clearBtn"),
  voiceStatus: document.getElementById("voiceStatus"),
  backendLabel: document.getElementById("backendUrlLabel")
};

let history = []; // {role:"user"|"assistant", content:string}
let recognizing = false;
let recognition = null;
let currentStage = "HENK1"; // Track orchestrator stage
let lastPayload = null; // Store last orchestrator payload

// Init labels
els.backendLabel.textContent = CONFIG.BACKEND_URL;

// Voice setup
(function initVoice(){
  if (!CONFIG.USE_SPEECH) {
    els.voiceStatus.textContent = "disabled";
    els.mic.disabled = true;
    return;
  }
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR){
    els.voiceStatus.textContent = "not supported";
    els.mic.disabled = true;
    return;
  }
  recognition = new SR();
  recognition.lang = "en-US";
  recognition.interimResults = true;
  recognition.continuous = false;

  recognition.onstart = () => {
    recognizing = true;
    els.mic.setAttribute("aria-pressed", "true");
    els.mic.title = "Listening… click to stop";
    els.voiceStatus.textContent = "listening…";
  };
  recognition.onerror = (e) => {
    recognizing = false;
    els.mic.setAttribute("aria-pressed", "false");
    els.voiceStatus.textContent = `error: ${e.error || "unknown"}`;
  };
  recognition.onend = () => {
    recognizing = false;
    els.mic.setAttribute("aria-pressed", "false");
    els.mic.title = "Start voice input";
    if (els.voiceStatus.textContent.startsWith("listening")) {
      els.voiceStatus.textContent = "stopped";
    }
  };
  recognition.onresult = (e) => {
    let transcript = "";
    for (let i = e.resultIndex; i < e.results.length; ++i) {
      transcript += e.results[i][0].transcript;
    }
    els.input.value = transcript.trim();
  };
  els.voiceStatus.textContent = "ready";
})();

// UI helpers
function scrollToBottom(){
  requestAnimationFrame(() => {
    els.chat.scrollTop = els.chat.scrollHeight;
  });
}

function el(tag, className, text){
  const n = document.createElement(tag);
  if (className) n.className = className;
  if (text) n.textContent = text;
  return n;
}

function addMessage(role, content, imageUrl = null){
  const wrap = el("div", `msg ${role}`);
  const bubble = el("div", "bubble");
  bubble.innerHTML = sanitize(content).replace(/\n/g, "<br/>");

  // Add image if provided
  if (imageUrl) {
    const img = document.createElement("img");
    img.src = imageUrl;
    img.alt = "Moodboard";
    img.style.maxWidth = "100%";
    img.style.marginTop = "10px";
    img.style.borderRadius = "8px";
    bubble.appendChild(img);
  }

  wrap.appendChild(bubble);
  els.chat.appendChild(wrap);
  scrollToBottom();
}

function sanitize(str){
  return str.replace(/[&<>"]/g, c => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;"
  }[c]));
}

function setBusy(isBusy){
  els.chat.setAttribute("aria-busy", isBusy ? "true" : "false");
  els.send.disabled = !!isBusy;
  els.input.disabled = !!isBusy;
  els.mic.disabled = !!isBusy || els.voiceStatus.textContent === "not supported";
}

// Networking
async function sendMessage(userText){
  const payload = {
    message: userText,
    history: history.slice(-CONFIG.MAX_HISTORY),
    stage: currentStage
  };

  // Include handoff_state from last payload if available
  // CRITICAL FIX: Must include styling_choices, not just handoff field
  // Early turns (0-4) return styling_choices directly in payload, not in handoff
  if (lastPayload) {
    payload.handoff_state = {
      styling_choices: lastPayload.styling_choices || {},
      crm_status: lastPayload.crm || {},
      handoff: lastPayload.handoff || "",
      user_uuid: lastPayload.user_uuid || null,
      deal_id: lastPayload.deal_id || null,
      correlation_id: lastPayload.correlation_id || null,
      look_ready: lastPayload.look_ready || false
    };
  }

  try{
    setBusy(true);
    const res = await fetch(CONFIG.BACKEND_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if(!res.ok){
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();
    const reply = (data && data.reply) ? String(data.reply) : "(no reply)";

    // Update stage and payload from orchestrator
    if (data.stage) {
      currentStage = data.stage;
    }
    if (data.payload) {
      lastPayload = data.payload;
    }

    history.push({ role: "assistant", content: reply });
    addMessage("assistant", reply);

    // Handle moodboard display if scheduled
    if (data.payload && data.payload.moodboard) {
      const moodboard = data.payload.moodboard;
      if (moodboard.status === "scheduled" && moodboard.image_url) {
        const delaySeconds = moodboard.display_after_seconds || 15;
        console.log(`[HENK] Moodboard scheduled - will display in ${delaySeconds}s`);

        // Show countdown message
        const countdownMsg = `(Moodbild wird in ${delaySeconds} Sekunden generiert...)`;
        addMessage("assistant", countdownMsg);

        // Display image after delay
        setTimeout(() => {
          addMessage("assistant", "Hier ist dein Moodbild:", moodboard.image_url);
        }, delaySeconds * 1000);
      } else if (moodboard.status === "ready" && moodboard.image_url) {
        // Display image immediately
        addMessage("assistant", "Hier ist dein Moodbild:", moodboard.image_url);
      }
    }
  }catch(err){
    console.error(err);
    addMessage("assistant", `Sorry, I couldn't reach the server. (${err.message})`);
  }finally{
    setBusy(false);
  }
}

// Events
els.form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = els.input.value.trim();
  if(!text) return;
  els.input.value = "";
  history.push({ role: "user", content: text });
  addMessage("user", text);
  await sendMessage(text);
});

els.input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    els.form.requestSubmit();
  }
});

els.mic.addEventListener("click", () => {
  if (!recognition) return;
  if (recognizing){
    recognition.stop();
  } else {
    try{ recognition.start(); } catch { /* start can throw if called too fast */ }
  }
});

els.clear.addEventListener("click", () => {
  history = [];
  currentStage = "HENK1";
  lastPayload = null;
  els.chat.innerHTML = "";
  addMessage("assistant",
    "Hallo! Ich bin HENK, dein persönlicher Maßschneider für exklusive Herrenmode.\n\n" +
    "Erzähl mir von deinem Anlass – ich erstelle dir ein komplettes Outfit mit Sakko, Hemd, Hose (und Weste, wenn passend).\n\n" +
    "Drei Infos genügen für den Start:\n" +
    "• Was ist der Anlass? (z.B. Hochzeit, Gala, Business)\n" +
    "• Welcher Stil-Vibe? (klassisch, modern, auffällig)\n" +
    "• Welche Farbrichtung? (z.B. dunkle Töne, helle Farben)"
  );
});

// Optional: preload hint for faster first paint
if ("requestIdleCallback" in window) {
  requestIdleCallback(() => new Image().decode?.());
}

/* Notes:
 * - To integrate images (fabric swatches, color palettes), let the backend return markdown-style image links
 *   and extend `sanitize` to allow <img> for whitelisted domains.
 * - For streaming responses, replace fetch with ReadableStream handling.
 * - Für WhatsApp/Twilio integriere direkt dein Backend unter BACKEND_URL.
 */

// ======================================================
// USER AUTHENTICATION & SIDEBAR
// ======================================================

const userEls = {
  loginBtn: document.getElementById("loginBtn"),
  userMenuBtn: document.getElementById("userMenuBtn"),
  userEmail: document.getElementById("userEmail"),
  sidebar: document.getElementById("userSidebar"),
  closeSidebar: document.getElementById("closeSidebar"),
  userEmailSidebar: document.getElementById("userEmailSidebar"),
  userInitials: document.getElementById("userInitials"),
  styleProfiles: document.getElementById("styleProfiles"),
  orders: document.getElementById("orders"),
  logoutBtn: document.getElementById("logoutBtn")
};

let currentUser = null;

// Check if user is logged in on page load
function checkAuth() {
  const accessToken = localStorage.getItem("access_token");
  if (accessToken) {
    // Verify token and load user data
    loadUserData(accessToken);
  } else {
    showLoginButton();
  }
}

function showLoginButton() {
  userEls.loginBtn.style.display = "inline-flex";
  userEls.userMenuBtn.style.display = "none";
}

function showUserButton(email) {
  userEls.loginBtn.style.display = "none";
  userEls.userMenuBtn.style.display = "inline-flex";
  userEls.userEmail.textContent = email.split("@")[0];
}

async function loadUserData(accessToken) {
  try {
    const response = await fetch("/portal/api/profile", {
      headers: {
        "Authorization": `Bearer ${accessToken}`
      }
    });

    if (!response.ok) {
      if (response.status === 401) {
        // Token expired, try to refresh
        await refreshToken();
        return;
      }
      throw new Error(`HTTP ${response.status}`);
    }

    const profile = await response.json();
    currentUser = profile;
    showUserButton(profile.email);

  } catch (error) {
    console.error("Failed to load user data:", error);
    logout();
  }
}

async function refreshToken() {
  const refreshToken = localStorage.getItem("refresh_token");
  if (!refreshToken) {
    logout();
    return;
  }

  try {
    const response = await fetch("/auth/refresh", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ refresh_token: refreshToken })
    });

    if (!response.ok) {
      throw new Error("Refresh failed");
    }

    const data = await response.json();
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);

    // Retry loading user data
    loadUserData(data.access_token);

  } catch (error) {
    console.error("Token refresh failed:", error);
    logout();
  }
}

function logout() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  currentUser = null;
  showLoginButton();
  userEls.sidebar.style.display = "none";
}

async function loadStyleProfiles() {
  const accessToken = localStorage.getItem("access_token");
  if (!accessToken) return;

  try {
    const response = await fetch("/portal/api/style-profiles", {
      headers: {
        "Authorization": `Bearer ${accessToken}`
      }
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const data = await response.json();
    const profiles = data.style_profiles || [];

    if (profiles.length === 0) {
      userEls.styleProfiles.innerHTML = '<p class="loading">Noch keine Style-Profile vorhanden.</p>';
      return;
    }

    userEls.styleProfiles.innerHTML = profiles.map(p => `
      <div class="data-item">
        <strong>${p.event_type || "Maßanfertigung"}</strong>
        <p>Vibe: ${p.vibe || "nicht angegeben"}</p>
        <p>Fit: ${p.fit_preference || "nicht angegeben"}</p>
        ${p.fabric_reference ? `<p>Stoff: ${p.fabric_reference}</p>` : ""}
      </div>
    `).join("");

  } catch (error) {
    console.error("Failed to load style profiles:", error);
    userEls.styleProfiles.innerHTML = '<p class="loading">Fehler beim Laden der Daten.</p>';
  }
}

async function loadOrders() {
  const accessToken = localStorage.getItem("access_token");
  if (!accessToken) return;

  try {
    const response = await fetch("/portal/api/orders", {
      headers: {
        "Authorization": `Bearer ${accessToken}`
      }
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const data = await response.json();
    const orders = data.orders || [];

    if (orders.length === 0) {
      userEls.orders.innerHTML = '<p class="loading">Noch keine Bestellungen vorhanden.</p>';
      return;
    }

    userEls.orders.innerHTML = orders.map(o => `
      <div class="data-item">
        <strong>${o.outfit_name || "Maßanfertigung"}</strong>
        <p>Status: ${o.status || "pending"}</p>
        ${o.fabric_reference ? `<p>Stoff: ${o.fabric_reference}</p>` : ""}
        ${o.event_date ? `<p>Termin: ${new Date(o.event_date).toLocaleDateString("de-DE")}</p>` : ""}
      </div>
    `).join("");

  } catch (error) {
    console.error("Failed to load orders:", error);
    userEls.orders.innerHTML = '<p class="loading">Fehler beim Laden der Bestellungen.</p>';
  }
}

function openSidebar() {
  userEls.sidebar.style.display = "block";

  // Set user info
  if (currentUser) {
    userEls.userEmailSidebar.textContent = currentUser.email;
    const initials = currentUser.email.substring(0, 2).toUpperCase();
    userEls.userInitials.textContent = initials;
  }

  // Load data
  loadStyleProfiles();
  loadOrders();
}

function closeSidebar() {
  userEls.sidebar.style.display = "none";
}

// Event listeners
userEls.loginBtn.addEventListener("click", () => {
  window.location.href = "/portal/login";
});

userEls.userMenuBtn.addEventListener("click", () => {
  openSidebar();
});

userEls.closeSidebar.addEventListener("click", () => {
  closeSidebar();
});

userEls.logoutBtn.addEventListener("click", () => {
  logout();
  closeSidebar();
});

// Close sidebar when clicking outside
userEls.sidebar.addEventListener("click", (e) => {
  if (e.target === userEls.sidebar) {
    closeSidebar();
  }
});

// Initialize auth on page load
checkAuth();
