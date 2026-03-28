/*
   SafeSpace UG — Client JavaScript
   Modern interactions with smooth transitions
*/

// ─── API Helper ──────────────────────────────────────────────────
async function api(url, method = "GET", body = null) {
    const opts = {
        method,
        headers: { "Content-Type": "application/json" },
    };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    return res.json();
}

// ─── Mood Logging ────────────────────────────────────────────────
function selectMood(value) {
    const btns = document.querySelectorAll(".mood-btn");
    const colors = { 1: "#EF6B6B", 2: "#F0B95A", 3: "#8B90A5", 4: "#6C9BF2", 5: "#5ECE8A" };

    btns.forEach(btn => {
        btn.classList.remove("selected");
        btn.style.borderColor = "";
        btn.style.background = "";
        btn.querySelector(".mood-label").style.color = "";
    });

    const selected = document.querySelector(`.mood-btn[data-value="${value}"]`);
    if (selected) {
        selected.classList.add("selected");
        selected.style.borderColor = colors[value];
        selected.style.background = colors[value] + "18";
        selected.querySelector(".mood-label").style.color = colors[value];

        // Bounce animation on the emoji
        const emoji = selected.querySelector(".mood-emoji");
        emoji.style.transform = "scale(1.4)";
        setTimeout(() => { emoji.style.transform = ""; }, 200);
    }

    api("/api/mood", "POST", { value: parseInt(value) }).then(data => {
        const feedback = document.getElementById("mood-feedback");
        if (feedback) {
            feedback.style.display = "flex";
            feedback.textContent = "✓ Mood logged";
        }
        setTimeout(() => { if (window.loadMoodChart) window.loadMoodChart(); }, 500);
    });
}

// ─── Journal ─────────────────────────────────────────────────────
function saveJournal() {
    const textarea = document.getElementById("journal-input");
    const btn = document.getElementById("journal-save-btn");
    const content = textarea.value.trim();

    if (!content) return;

    btn.textContent = "Saving...";
    btn.disabled = true;

    api("/api/journal", "POST", { content }).then(data => {
        if (data.ok) {
            btn.textContent = "✓ Saved";
            btn.style.background = "linear-gradient(135deg, var(--green), #4CB87A)";
            btn.style.boxShadow = "0 2px 12px rgba(94,206,138,0.3)";
            textarea.value = "";

            // Update character counter
            const jc = document.getElementById("journal-char-count");
            if (jc) jc.textContent = "";

            setTimeout(() => {
                btn.textContent = "Save Entry";
                btn.style.background = "";
                btn.style.boxShadow = "";
                btn.disabled = false;
                if (window.loadJournalEntries) window.loadJournalEntries();
            }, 2000);
        }
    });
}

// ─── Group Chat ──────────────────────────────────────────────────
function sendGroupMessage(groupId) {
    const input = document.getElementById("chat-input");
    const text = input.value.trim();
    if (!text) return;

    input.value = "";

    api(`/api/group/${groupId}/send`, "POST", { text }).then(data => {
        if (data.ok) {
            appendChatMessage(data.message, true);
            scrollChatBottom();
        }
    });
}

function appendChatMessage(msg, isMine) {
    const container = document.getElementById("chat-messages");
    // Remove empty state if present
    const emptyState = container.querySelector("[style*='text-align: center']");
    if (emptyState && emptyState.textContent.includes("first")) emptyState.remove();

    const div = document.createElement("div");
    div.className = `chat-msg ${isMine ? "mine" : msg.is_guide ? "guide" : "theirs"}`;
    div.id = `msg-${msg._id}`;
    div.innerHTML = `
        ${!isMine ? `<div class="chat-sender">${escapeHtml(msg.anon_name || "Anonymous")}</div>` : ""}
        <div>${escapeHtml(msg.text)}</div>
        <div class="chat-time">
            ${msg.created_at ? new Date(msg.created_at).toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"}) : "Now"}
            ${isMine ? `<span class="delete-msg" onclick="deleteMessage('${msg.group_id}', '${msg._id}')" title="Delete">🗑️</span>` : ""}
        </div>
    `;
    container.appendChild(div);
}

function deleteMessage(groupId, msgId) {
    if (!confirm("Delete this message?")) return;
    api(`/api/group/${groupId}/message/${msgId}`, "DELETE").then(data => {
        if (data.ok) {
            const el = document.getElementById(`msg-${msgId}`);
            if (el) {
                el.style.transition = "all 0.3s ease";
                el.style.opacity = "0";
                el.style.transform = "scale(0.9)";
                setTimeout(() => el.remove(), 300);
            }
        }
    });
}

function scrollChatBottom() {
    const container = document.getElementById("chat-messages");
    if (container) {
        container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
    }
}

// ─── Counsellor Chat (Student Side) ──────────────────────────────
function sendToCounsellor() {
    const input = document.getElementById("counsel-input");
    const text = input.value.trim();
    if (!text) return;

    input.value = "";

    api("/api/counsellor/send", "POST", { text }).then(data => {
        if (data.ok) {
            const container = document.getElementById("counsel-messages");
            // Remove empty state
            const emptyState = container.querySelector("[style*='text-align: center']");
            if (emptyState) emptyState.remove();

            const div = document.createElement("div");
            div.className = "chat-msg mine";
            div.innerHTML = `<div>${escapeHtml(text)}</div><div class="chat-time">Now</div>`;
            container.appendChild(div);
            container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
        }
    });
}

// Poll for new counsellor messages
function pollCounsellorMessages() {
    api("/api/counsellor/messages").then(msgs => {
        const container = document.getElementById("counsel-messages");
        if (!container) return;
        container.innerHTML = "";
        msgs.forEach(msg => {
            const div = document.createElement("div");
            const isUser = msg.from === "user";
            div.className = `chat-msg ${isUser ? "mine" : "counsellor"}`;
            div.innerHTML = `
                ${!isUser ? '<div class="chat-sender">🛡️ UG Counsellor</div>' : ""}
                <div>${escapeHtml(msg.text)}</div>
                <div class="chat-time">${new Date(msg.created_at).toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"})}</div>
            `;
            container.appendChild(div);
        });
        container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
    });
}

// ─── Staff: Flag Actions ─────────────────────────────────────────
function reviewFlag(flagId) {
    api(`/api/staff/flag/${flagId}/review`, "POST").then(data => {
        if (data.ok) {
            const card = document.getElementById(`flag-${flagId}`);
            if (card) {
                const badge = card.querySelector(".badge-pending");
                if (badge) {
                    badge.className = "badge badge-reviewed";
                    badge.textContent = "Reviewed";
                    badge.style.transition = "all 0.3s ease";
                }
                // Subtle flash
                card.style.borderColor = "rgba(94,206,138,0.4)";
                setTimeout(() => { card.style.borderColor = ""; }, 1500);
            }
        }
    });
}

function initiateChat(flagId, sessionNum) {
    api(`/api/staff/flag/${flagId}/chat`, "POST", { session: sessionNum }).then(data => {
        if (data.ok) {
            const card = document.getElementById(`flag-${flagId}`);
            if (card) {
                card.style.borderColor = "rgba(167,139,250,0.4)";
                setTimeout(() => location.reload(), 600);
            }
        }
    });
}

function generateToken(flagId) {
    api(`/api/staff/flag/${flagId}/token`, "POST").then(data => {
        if (data.ok) {
            const card = document.getElementById(`flag-${flagId}`);
            if (card) {
                card.style.borderColor = "rgba(240,185,90,0.4)";
            }
            // Show inline notification instead of alert
            const meta = card ? card.querySelector(".flag-meta") : null;
            if (meta) {
                const note = document.createElement("div");
                note.style.cssText = "color: var(--amber); font-size: 12px; font-weight: 600; margin-top: 8px; animation: fadeInUp 0.3s ease both;";
                note.textContent = `🔑 Token generated: #${data.code} — user notified`;
                meta.parentNode.insertBefore(note, meta.nextSibling);
            }
            setTimeout(() => location.reload(), 2000);
        }
    });
}

function staffSendMessage(userId) {
    const input = document.getElementById(`staff-input-${userId}`);
    const text = input.value.trim();
    if (!text) return;

    input.value = "";

    api(`/api/staff/chat/${userId}/send`, "POST", { text }).then(data => {
        if (data.ok) {
            const container = document.getElementById("staff-chat-messages");
            // Remove empty state
            const emptyState = container.querySelector("[style*='text-align: center']");
            if (emptyState) emptyState.remove();

            const div = document.createElement("div");
            div.className = "chat-msg counsellor";
            div.innerHTML = `
                <div class="chat-sender">🛡️ You (Counsellor)</div>
                <div>${escapeHtml(text)}</div>
                <div class="chat-time">Now</div>
            `;
            container.appendChild(div);
            container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
        }
    });
}

function runFlagging() {
    const btn = document.getElementById("run-flagging-btn");
    btn.textContent = "Running checks...";
    btn.disabled = true;

    api("/api/staff/run-flagging", "POST").then(data => {
        btn.textContent = `✓ ${data.flags_created} new flags`;
        btn.style.color = "var(--green)";
        btn.style.borderColor = "rgba(94,206,138,0.3)";
        setTimeout(() => {
            btn.textContent = "🔄 Run Flagging Check";
            btn.style.color = "";
            btn.style.borderColor = "";
            btn.disabled = false;
            if (data.flags_created > 0) location.reload();
        }, 2000);
    });
}

// Set demo email recipient
function setDemoEmail() {
    const input = document.getElementById("demo-email");
    const feedback = document.getElementById("email-feedback");
    const email = input.value.trim();
    if (!email) return;

    api("/api/staff/set-email", "POST", { email }).then(data => {
        if (data.ok) {
            feedback.textContent = `✓ Alerts now go to ${data.email}`;
            feedback.style.color = "var(--green)";
            feedback.style.display = "block";
            input.style.borderColor = "rgba(94,206,138,0.3)";
            setTimeout(() => { input.style.borderColor = ""; }, 2000);
        } else {
            feedback.textContent = data.error || "Failed";
            feedback.style.color = "var(--red)";
            feedback.style.display = "block";
        }
    });
}

// ─── Utilities ───────────────────────────────────────────────────
function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

// ─── Init ────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    // Auto-scroll chats smoothly
    scrollChatBottom();

    // Enter key for chat inputs
    document.querySelectorAll("[data-enter-send]").forEach(input => {
        input.addEventListener("keydown", e => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                const fn = input.getAttribute("data-enter-send");
                if (fn && window[fn]) window[fn]();
                else {
                    const form = input.closest("form");
                    if (form) form.dispatchEvent(new Event("submit"));
                }
            }
        });
    });

    // Poll counsellor messages if on that page
    if (document.getElementById("counsel-messages")) {
        setInterval(pollCounsellorMessages, 5000);
    }

    // Add focus ring effect to inputs
    document.querySelectorAll(".input").forEach(input => {
        input.addEventListener("focus", () => {
            input.parentElement && input.parentElement.style && (input.parentElement.style.transition = "all 0.3s");
        });
    });
});
