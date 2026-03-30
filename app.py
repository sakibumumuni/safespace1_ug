"""
SafeSpace UG — MVP Backend
University of Ghana Mental Health Support Platform
Stack: Flask + MongoDB + SMTP Email Alerts
"""

import os
import re
import secrets
import string
import smtplib
import json
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps
import threading

from dotenv import load_dotenv
load_dotenv()

from flask import (
    Flask, render_template, request, jsonify,
    session, redirect, url_for
)
import pymongo
from bson import ObjectId
import anthropic


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# Database connection
MONGO_URI = os.environ.get("MONGO_URI")
client = pymongo.MongoClient(MONGO_URI)
print(client.list_database_names())
db = client["safespace_ug"]

# Collections
users_col       = db["users"]        # anonymous user accounts
moods_col       = db["moods"]        # mood entries
journals_col    = db["journals"]     # journal entries
groups_col      = db["peer_groups"]  # peer support groups
messages_col    = db["messages"]     # group chat messages
flags_col       = db["flags"]        # flagged cases for directorate
counsel_col     = db["counsel_msgs"] # counsellor ↔ user anonymous chat
tokens_col      = db["session_tokens"] # one-time meeting codes
assessments_col = db["assessments"]  # therapy assessments after mood check

# Base URL for links in emails (set APP_URL in .env when deployed)
APP_URL = os.environ.get("APP_URL", f"http://localhost:{os.environ.get('PORT', 5000)}").strip().rstrip("/")

# Email Config (UG Counselling Directorate)
EMAIL_CONFIG = {
    "smtp_server": os.environ.get("SMTP_SERVER", "smtp.gmail.com"),
    "smtp_port": int(os.environ.get("SMTP_PORT", 587)),
    "sender_email": os.environ.get("SENDER_EMAIL", "safespace.ug.alerts@gmail.com"),
    "sender_password": os.environ.get("SENDER_PASSWORD", ""),
    "directorate_email": os.environ.get(
        "DIRECTORATE_EMAIL",
        "counselling@ug.edu.gh"  # UG Counselling Directorate
    ),
}

# Flag Check Intervals (hours) per severity
FLAG_INTERVALS = {
    "urgent": 24,    # check every 24h
    "concern": 48,   # check every 48h
    "watch": 72,     # check every 72h
}

# Claude API client for intelligent flagging
claude_client = anthropic.Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY")
)


# HELPERS

def generate_anon_name():
    """Generate anonymous display name like Anon-Butterfly."""
    adjectives = ["Quiet", "Gentle", "Bright", "Calm", "Brave", "Kind", "Warm", "Still"]
    nouns = ["River", "Butterfly", "Star", "Cloud", "Wave", "Leaf", "Moon", "Rain"]
    import random
    return f"Anon-{random.choice(adjectives)}{random.choice(nouns)}"


def generate_token():
    """Generate one-time session code like UG-7742."""
    digits = ''.join(secrets.choice(string.digits) for _ in range(4))
    return f"UG-{digits}"


def get_current_user():
    """Get current anonymous user from session."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return users_col.find_one({"_id": ObjectId(user_id)})


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("landing"))
        # Verify user still exists in DB (handles stale sessions after DB wipe)
        if not users_col.find_one({"_id": ObjectId(session["user_id"])}):
            session.clear()
            return redirect(url_for("landing"))
        return f(*args, **kwargs)
    return decorated


def staff_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_staff"):
            # API calls get JSON error, page requests redirect to login
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized"}), 403
            return redirect(url_for("staff_login"))
        return f(*args, **kwargs)
    return decorated


def json_serial(obj):
    """JSON serializer for MongoDB objects."""
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")



# EMAIL ALERT SYSTEM — Sends flags to UG Counselling Directorate


def send_flag_email(flag_data):
    """Send structured alert email to UG Counselling Directorate."""
    cfg = EMAIL_CONFIG
    
    severity_colors = {
        "urgent": "#EF6B6B",
        "concern": "#F0B95A", 
        "watch": "#6C9BF2",
    }
    severity = flag_data.get("severity", "watch")
    color = severity_colors.get(severity, "#6C9BF2")
    token = flag_data.get("user_token", "Unknown")
    flag_type = flag_data.get("flag_type", "periodic")

    # Build email — distinguish check-in flags from periodic AI flags
    if flag_type == "checkin":
        subject = f"[SafeSpace PHQ-9 {severity.upper()}] Anonymous user {token} — Pre-session check-in"
    else:
        subject = f"[SafeSpace AI {severity.upper()}] Anonymous user {token} — Periodic risk assessment"
    
    # Plain text version
    text_body = f"""
SafeSpace UG — Flagged User Alert
{'=' * 45}

Severity: {severity.upper()}
User Token: {token}
Flagged At: {flag_data.get('flagged_at', datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'))}

Reason:
{flag_data.get('reason', 'No reason provided')}

Mood Trend (last 7 entries):
{' → '.join(str(m) for m in flag_data.get('mood_trend', []))}

{f"Journal Excerpt:{chr(10)}{flag_data.get('journal_excerpt', '')}" if flag_data.get('journal_excerpt') else ""}

{f"PHQ-9 Assessment (Score: {flag_data.get('assessment_score')}/27 — {flag_data.get('assessment_risk', '').replace('_', ' ').upper()}):{chr(10)}{flag_data.get('assessment_summary', '')}" if flag_data.get('assessment_summary') else ""}

Review this case at: {flag_data.get('dashboard_url', f"{APP_URL}/staff/dashboard")}

Actions Available:
1. Open anonymous chat with this user
2. Generate a private session token for in-person visit
3. Mark as reviewed / escalate

— SafeSpace UG Automated Alert System
University of Ghana Counselling Directorate
"""

    # HTML version
    html_body = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 600px; margin: 0 auto; background: #0F1117; color: #E8EAF0; border-radius: 12px; overflow: hidden;">
        <div style="background: {color}; padding: 16px 24px;">
            <h2 style="margin: 0; color: #fff; font-size: 16px;">
                {"📋" if flag_type == "checkin" else "🤖"} SafeSpace {"PHQ-9 Check-in" if flag_type == "checkin" else "Periodic AI"} Alert — {severity.upper()}
            </h2>
        </div>
        <div style="padding: 24px;">
            <div style="background: #181B25; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
                <div style="font-size: 12px; color: #8B90A5;">Anonymous User</div>
                <div style="font-size: 24px; font-weight: 700; color: {color}; font-family: monospace; margin-top: 4px;">
                    #{token}
                </div>
            </div>
            
            <div style="margin-bottom: 16px;">
                <div style="font-size: 12px; color: #8B90A5; margin-bottom: 4px;">FLAG REASON</div>
                <div style="font-size: 14px; line-height: 1.5;">{flag_data.get('reason', 'N/A')}</div>
            </div>
            
            <div style="margin-bottom: 16px;">
                <div style="font-size: 12px; color: #8B90A5; margin-bottom: 4px;">MOOD TREND (7 days)</div>
                <div style="font-size: 18px; letter-spacing: 4px;">
                    {''.join(['😞' if m<=1 else '😔' if m==2 else '😐' if m==3 else '🙂' if m==4 else '😊' for m in flag_data.get('mood_trend', [])])}
                </div>
            </div>
            
            {"<div style='margin-bottom: 16px;'><div style=font-size:12px;color:#8B90A5;margin-bottom:4px;>JOURNAL EXCERPT</div><div style=font-size:13px;color:#F0B95A;font-style:italic;background:#1E2230;padding:12px;border-radius:8px;border-left:3px solid " + color + ";>" + flag_data.get('journal_excerpt', '') + "</div></div>" if flag_data.get('journal_excerpt') else ""}

            {"<div style='margin-bottom:16px;'><div style='font-size:12px;color:#A78BFA;margin-bottom:4px;'>PHQ-9 ASSESSMENT (Score: " + str(flag_data.get('assessment_score', '')) + "/27 — " + str(flag_data.get('assessment_risk', '')).replace('_', ' ').upper() + ")</div><div style='font-size:13px;color:#E8EAF0;background:#1E2230;padding:12px;border-radius:8px;border-left:3px solid #A78BFA;line-height:1.5;'>" + flag_data.get('assessment_summary', '') + "</div></div>" if flag_data.get('assessment_summary') else ""}

            <div style="margin-top: 24px; text-align: center;">
                <a href="{flag_data.get('dashboard_url', APP_URL + '/staff/dashboard')}"
                   target="_blank" rel="noopener noreferrer"
                   style="background: {color}; color: #fff; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px; display: inline-block;">
                    Review in Dashboard →
                </a>
                <div style="margin-top: 8px; font-size: 11px; color: #5A5F75;">
                    <a href="{flag_data.get('dashboard_url', APP_URL + '/staff/dashboard')}"
                       target="_blank" rel="noopener noreferrer"
                       style="color: #8B90A5; word-break: break-all;">
                        {flag_data.get('dashboard_url', APP_URL + '/staff/dashboard')}
                    </a>
                </div>
            </div>
            
            <div style="margin-top: 24px; font-size: 11px; color: #5A5F75; text-align: center;">
                SafeSpace UG · University of Ghana Counselling Directorate<br>
                This is an automated alert. The student's identity is protected.
            </div>
        </div>
    </div>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = cfg["sender_email"]
        msg["To"] = cfg["directorate_email"]
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        if cfg["smtp_port"] == 465:
            with smtplib.SMTP_SSL(cfg["smtp_server"], cfg["smtp_port"]) as server:
                server.login(cfg["sender_email"], cfg["sender_password"])
                server.sendmail(cfg["sender_email"], cfg["directorate_email"], msg.as_string())
        else:
            with smtplib.SMTP(cfg["smtp_server"], cfg["smtp_port"]) as server:
                server.starttls()
                server.login(cfg["sender_email"], cfg["sender_password"])
                server.sendmail(cfg["sender_email"], cfg["directorate_email"], msg.as_string())
        
        return True
    except Exception as e:
        import traceback
        print(f"[EMAIL ERROR] Failed to send flag email: {e}")
        print(f"[EMAIL CONFIG] server={cfg['smtp_server']}, port={cfg['smtp_port']}, sender={cfg['sender_email']}, recipient={cfg['directorate_email']}, password_set={bool(cfg['sender_password'])}")
        traceback.print_exc()
        return False



# FLAGGING ENGINE — Periodic checks per user

def check_and_flag_user(user_id):
    """
    Run Claude-powered flagging for a single user.
    Gathers mood trends, journal entries, and activity data, then sends
    them to Claude for intelligent risk assessment instead of hardcoded rules.

    Returns flag document if flagged, None otherwise.
    """
    user = users_col.find_one({"_id": ObjectId(user_id)})
    if not user:
        return None

    token = user.get("token", generate_token())

    # ── Gather user data for analysis ──────────────────────
    recent_moods = list(moods_col.find(
        {"user_id": str(user_id)},
        sort=[("created_at", -1)],
    ).limit(7))
    mood_trend = [m["value"] for m in reversed(recent_moods)]

    recent_journals = list(journals_col.find(
        {"user_id": str(user_id)},
        sort=[("created_at", -1)],
    ).limit(5))
    journal_texts = [
        j.get("content", "")[:300] for j in recent_journals
    ]
    journal_excerpt = journal_texts[0][:200] if journal_texts else ""

    last_activity = user.get("last_active")
    days_inactive = (datetime.utcnow() - last_activity).days if last_activity else 0
    usage_streak = user.get("usage_streak", 0)

    # If there's no data at all, nothing to analyse
    if not mood_trend and not journal_texts and days_inactive < 3:
        return None

    # ── Build the Claude prompt ────────────────────────────
    analysis_payload = json.dumps({
        "mood_trend_last_7": mood_trend,
        "journal_excerpts": journal_texts,
        "days_inactive": days_inactive,
        "usage_streak": usage_streak,
    }, ensure_ascii=False)

    system_prompt = """You are a mental-health risk assessment agent for SafeSpace UG, a University of Ghana student wellness platform.

Your job: analyse the student data provided and decide whether the student should be flagged for follow-up by the UG Counselling Directorate.

Context:
- Mood values are 1-5 (1 = Struggling, 5 = Great).
- Journal entries may be in English, Ghanaian Pidgin English, or Twi.
- Students are anonymous — never try to identify them.

Assessment criteria (use your judgement — these are guidelines, not rigid rules):
• Crisis language in journals (suicidal ideation, self-harm, hopelessness — in any language/dialect)
• Persistently low moods (e.g. 3+ entries at ≤ 2)
• Steady mood decline over multiple days
• Sudden inactivity after a consistent usage streak (e.g. 7+ day streak then 3+ days silent)
• Combinations of the above that suggest compounding distress

You MUST respond with ONLY a valid JSON object (no markdown, no extra text):
{
  "should_flag": true/false,
  "severity": "urgent" | "concern" | "watch",
  "reasons": ["reason 1", "reason 2"]
}

Severity guide:
- "urgent": crisis language, suicidal ideation, or extremely low moods (1) sustained
- "concern": persistent low moods (≤2), steady decline reaching low levels, or worrying inactivity
- "watch": mild patterns that warrant monitoring but not immediate action

If the data shows no concerning patterns, return:
{"should_flag": false, "severity": "watch", "reasons": []}"""

    # ── Call Claude ─────────────────────────────────────────
    try:
        message = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=system_prompt,
            messages=[
                {"role": "user", "content": f"Analyse this student's data:\n{analysis_payload}"}
            ],
        )
        response_text = message.content[0].text.strip()
        # Strip markdown fences if Claude wraps the JSON
        if response_text.startswith("```"):
            response_text = re.sub(r"^```(?:json)?\s*", "", response_text)
            response_text = re.sub(r"\s*```$", "", response_text)
        assessment = json.loads(response_text)
    except Exception as e:
        print(f"[CLAUDE FLAGGING ERROR] {e}")
        return None

    if not assessment.get("should_flag"):
        return None

    severity = assessment.get("severity", "watch")
    reasons = assessment.get("reasons", ["AI-detected concern"])

    # ── Deduplicate: skip if flagged recently ──────────────
    interval_hours = FLAG_INTERVALS.get(severity, 72)
    recent_flag = flags_col.find_one({
        "user_id": str(user_id),
        "created_at": {"$gte": datetime.utcnow() - timedelta(hours=interval_hours)},
    })
    if recent_flag:
        return None

    # ── Pull latest assessment if available ──────────────
    latest_assessment = assessments_col.find_one(
        {"user_id": str(user_id)},
        sort=[("created_at", -1)],
    )

    # ── Create flag document ───────────────────────────────
    flag = {
        "user_id": str(user_id),
        "user_token": token,
        "flag_type": "periodic",
        "severity": severity,
        "reasons": reasons,
        "reason": "; ".join(reasons),
        "mood_trend": mood_trend,
        "journal_excerpt": journal_excerpt,
        "assessment_score": latest_assessment.get("total_score") if latest_assessment else None,
        "assessment_risk": latest_assessment.get("risk_level") if latest_assessment else None,
        "assessment_summary": latest_assessment.get("clinical_summary") if latest_assessment else None,
        "status": "pending",
        "created_at": datetime.utcnow(),
        "flagged_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "dashboard_url": f"{APP_URL}/staff/dashboard",
        "reviewed_by": None,
        "action_taken": None,
    }

    result = flags_col.insert_one(flag)
    flag["_id"] = result.inserted_id

    send_flag_email(flag)
    return flag


def run_periodic_flagging():
    """
    Run flagging checks for all active users.
    In production, this would be a scheduled job (cron/celery).
    For MVP: called via /api/admin/run-flagging endpoint.
    """
    active_users = users_col.find({
        "last_active": {"$gte": datetime.utcnow() - timedelta(days=14)}
    })
    
    flags_created = []
    for user in active_users:
        flag = check_and_flag_user(str(user["_id"]))
        if flag:
            flags_created.append(flag)
    
    return flags_created



# Standardized Patient Health Questionnaire (PHQ-9)
# 9 items, each scored 0-3, total 0-27
PHQ9_QUESTIONS = [
    {
        "id": "phq1",
        "text": "Little interest or pleasure in doing things?",
        "options": [
            {"value": 0, "label": "Not at all"},
            {"value": 1, "label": "Several days"},
            {"value": 2, "label": "More than half the days"},
            {"value": 3, "label": "Nearly every day"},
        ],
    },
    {
        "id": "phq2",
        "text": "Feeling down, depressed, or hopeless?",
        "options": [
            {"value": 0, "label": "Not at all"},
            {"value": 1, "label": "Several days"},
            {"value": 2, "label": "More than half the days"},
            {"value": 3, "label": "Nearly every day"},
        ],
    },
    {
        "id": "phq3",
        "text": "Trouble falling or staying asleep, or sleeping too much?",
        "options": [
            {"value": 0, "label": "Not at all"},
            {"value": 1, "label": "Several days"},
            {"value": 2, "label": "More than half the days"},
            {"value": 3, "label": "Nearly every day"},
        ],
    },
    {
        "id": "phq4",
        "text": "Feeling tired or having little energy?",
        "options": [
            {"value": 0, "label": "Not at all"},
            {"value": 1, "label": "Several days"},
            {"value": 2, "label": "More than half the days"},
            {"value": 3, "label": "Nearly every day"},
        ],
    },
    {
        "id": "phq5",
        "text": "Poor appetite or overeating?",
        "options": [
            {"value": 0, "label": "Not at all"},
            {"value": 1, "label": "Several days"},
            {"value": 2, "label": "More than half the days"},
            {"value": 3, "label": "Nearly every day"},
        ],
    },
    {
        "id": "phq6",
        "text": "Feeling bad about yourself — or that you are a failure or have let yourself or your family down?",
        "options": [
            {"value": 0, "label": "Not at all"},
            {"value": 1, "label": "Several days"},
            {"value": 2, "label": "More than half the days"},
            {"value": 3, "label": "Nearly every day"},
        ],
    },
    {
        "id": "phq7",
        "text": "Trouble concentrating on things, such as reading or watching television?",
        "options": [
            {"value": 0, "label": "Not at all"},
            {"value": 1, "label": "Several days"},
            {"value": 2, "label": "More than half the days"},
            {"value": 3, "label": "Nearly every day"},
        ],
    },
    {
        "id": "phq8",
        "text": "Moving or speaking so slowly that other people could have noticed? Or the opposite — being so fidgety or restless that you have been moving around a lot more than usual?",
        "options": [
            {"value": 0, "label": "Not at all"},
            {"value": 1, "label": "Several days"},
            {"value": 2, "label": "More than half the days"},
            {"value": 3, "label": "Nearly every day"},
        ],
    },
    {
        "id": "phq9",
        "text": "Thoughts that you would be better off dead, or of hurting yourself in some way?",
        "options": [
            {"value": 0, "label": "Not at all"},
            {"value": 1, "label": "Several days"},
            {"value": 2, "label": "More than half the days"},
            {"value": 3, "label": "Nearly every day"},
        ],
    },
]


# Page Routes

@app.route("/")
def landing():
    if session.get("user_id"):
        return redirect(url_for("home"))
    if session.get("is_staff"):
        return redirect(url_for("staff_dashboard"))
    return render_template("landing.html")

#    Mandatory daily check-in: free-text mood + survey. Will remove checkin into the beginning of a chat with a counsellor

"""@app.route("/checkin")
@login_required
def checkin_page():
    user = get_current_user()
    # If already checked in today, skip to home
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_checkin = assessments_col.find_one({
        "user_id": str(user["_id"]),
        "created_at": {"$gte": today_start}
    })
    if today_checkin:
        session.pop("needs_checkin", None)
        return redirect(url_for("home"))
    return render_template("checkin.html", user=user, questions=ASSESSMENT_QUESTIONS)"""


@app.route("/home")
@login_required
def home():
    user = get_current_user()
    """Redirect to check-in if not done today, needs work because of checkin relocation
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_checkin = assessments_col.find_one({
        "user_id": str(user["_id"]),
        "created_at": {"$gte": today_start}
    })
    if not today_checkin:
        return redirect(url_for("checkin_page"))
    # Get today's mood
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_mood = moods_col.find_one({
        "user_id": str(user["_id"]),
        "created_at": {"$gte": today_start}
    })"""
    # Get today's mood
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_mood = moods_col.find_one({
        "user_id": str(user["_id"]),
        "created_at": {"$gte": today_start}
    })

    # Get recent moods for chart
    recent_moods = list(moods_col.find(
        {"user_id": str(user["_id"])},
        sort=[("created_at", -1)]
    ).limit(7))
    recent_moods.reverse()

    # Check for counsellor messages / tokens
    notifications = list(counsel_col.find({
        "user_id": str(user["_id"]),
        "read": False,
        "from": "counsellor"
    }))
    
    active_token = tokens_col.find_one({
        "user_id": str(user["_id"]),
        "used": False,
        "expires_at": {"$gte": datetime.utcnow()}
    })
    
    return render_template("home.html",
        user=user,
        today_mood=today_mood,
        recent_moods=recent_moods,
        notifications=notifications,
        active_token=active_token,
        groups=PEER_GROUPS_DATA,
    )


@app.route("/journal")
@login_required
def journal_page():
    user = get_current_user()
    entries = list(journals_col.find(
        {"user_id": str(user["_id"])},
        sort=[("created_at", -1)]
    ).limit(20))
    return render_template("journal.html", user=user, entries=entries)


@app.route("/groups")
@login_required
def groups_page():
    groups = list(groups_col.find())
    return render_template("groups.html", groups=groups)


@app.route("/group/<group_id>")
@login_required
def group_chat(group_id):
    group = groups_col.find_one({"_id": ObjectId(group_id)})
    if not group:
        return redirect(url_for("groups_page"))
    msgs = list(messages_col.find(
        {"group_id": group_id},
        sort=[("created_at", -1)]
    ).limit(50))
    msgs.reverse()
    return render_template("group_chat.html", group=group, messages=msgs)


@app.route("/crisis")
@login_required
def crisis_page():
    return render_template("crisis.html")


@app.route("/counsellor-chat")
@login_required
def counsellor_chat():
    user = get_current_user()
    user_id = str(user["_id"])

    # Check if PHQ-9 was completed today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_checkin = assessments_col.find_one({
        "user_id": user_id,
        "created_at": {"$gte": today_start}
    })
    needs_checkin = today_checkin is None

    msgs = list(counsel_col.find(
        {"user_id": user_id},
        sort=[("created_at", 1)]
    ).limit(100))
    return render_template("counsellor_chat.html",
        user=user,
        messages=msgs,
        needs_checkin=needs_checkin,
        questions=PHQ9_QUESTIONS,
    )


# Staff Routes
@app.route("/staff/login", methods=["GET", "POST"])
def staff_login():
    if request.method == "POST":
        code = request.form.get("access_code", "")
        # In production: proper auth against UG staff directory
        STAFF_CODE = os.environ.get("STAFF_CODE", "UG-COUNSEL-2026")
        if code == STAFF_CODE:
            session["is_staff"] = True
            session["staff_name"] = request.form.get("name", "Counsellor")
            return redirect(url_for("staff_dashboard"))
        return render_template("staff_login.html", error="Invalid access code")
    return render_template("staff_login.html")


@app.route("/staff/dashboard")
@staff_required
def staff_dashboard():
    flags = list(flags_col.find(sort=[
        ("severity", -1),  # urgent first
        ("created_at", -1)
    ]).limit(50))
    
    stats = {
        "total_users": users_col.count_documents({}),
        "active_today": users_col.count_documents({
            "last_active": {"$gte": datetime.utcnow() - timedelta(hours=24)}
        }),
        "pending_flags": flags_col.count_documents({"status": "pending"}),
        "urgent_flags": flags_col.count_documents({"status": "pending", "severity": "urgent"}),
    }
    return render_template("staff_dashboard.html", flags=flags, stats=stats)


@app.route("/staff/chat/<user_id>")
@staff_required
def staff_chat(user_id):
    user = users_col.find_one({"_id": ObjectId(user_id)})
    msgs = list(counsel_col.find(
        {"user_id": user_id},
        sort=[("created_at", 1)]
    ).limit(100))
    flag = flags_col.find_one({"user_id": user_id, "status": {"$ne": "resolved"}})
    return render_template("staff_chat.html", anon_user=user, messages=msgs, flag=flag)



# API ROUTES
@app.route("/api/auth/register", methods=["POST"])
def register():
    """Create anonymous account — no personal info needed."""
    anon_name = generate_anon_name()
    token = generate_token()
    user = {
        "anon_name": anon_name,
        "token": token,
        "created_at": datetime.utcnow(),
        "last_active": datetime.utcnow(),
        "usage_streak": 0,
        "groups_joined": [],
    }
    result = users_col.insert_one(user)
    session["user_id"] = str(result.inserted_id)
    session["anon_name"] = anon_name
    session["needs_checkin"] = True
    return jsonify({"ok": True, "anon_name": anon_name, "token": token})


@app.route("/api/mood", methods=["POST"])
@login_required
def log_mood():
    """Log mood entry and trigger flag check."""
    data = request.json
    value = data.get("value")
    if not value or value not in [1, 2, 3, 4, 5]:
        return jsonify({"error": "Invalid mood value"}), 400
    
    user_id = session["user_id"]
    mood = {
        "user_id": user_id,
        "value": value,
        "note": data.get("note", ""),
        "created_at": datetime.utcnow(),
    }
    moods_col.insert_one(mood)
    
    # Update user activity
    users_col.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"last_active": datetime.utcnow()}, "$inc": {"usage_streak": 1}}
    )
    
    # Run flag check in background so mood log responds instantly
    threading.Thread(target=check_and_flag_user, args=(user_id,), daemon=False).start()

    return jsonify({"ok": True, "flagged": False})


@app.route("/api/checkin", methods=["POST"])
@login_required
def submit_checkin():
    """
    Mandatory daily check-in: free-text mood description + survey answers.
    Completely separate from the periodic flagging engine.
    Generates a clinical intake summary for counselling staff and creates
    its own flag so staff see the user's state before any in-person session.
    """
    data = request.json
    answers = data.get("answers", {})
    mood_text = data.get("mood_text", "").strip()

    if not answers or not mood_text:
        return jsonify({"error": "Please describe how you feel and answer all questions"}), 400

    user_id = session["user_id"]
    user = users_col.find_one({"_id": ObjectId(user_id)})
    if not user:
        return jsonify({"error": "User not found"}), 404

    token = user.get("token", generate_token())

    # Calculate raw score (PHQ-9: 0-27)
    total_score = sum(int(v) for v in answers.values())

    # Build readable answers for clinical summary
    answer_lines = []
    for q in PHQ9_QUESTIONS:
        val = answers.get(q["id"])
        if val is not None:
            val = int(val)
            chosen = next((o["label"] for o in q["options"] if o["value"] == val), "Unknown")
            answer_lines.append(f"Q: {q['text']}\nA: {chosen} ({val}/3)")

    answers_text = "\n\n".join(answer_lines)

    # ── PHQ-9 severity thresholds ──────
    # 0-4: Minimal, 5-9: Mild, 10-14: Moderate, 15-19: Moderately severe, 20-27: Severe
    if total_score <= 4:
        risk_level = "minimal"
    elif total_score <= 9:
        risk_level = "mild"
    elif total_score <= 14:
        risk_level = "moderate"
    elif total_score <= 19:
        risk_level = "moderately_severe"
    else:
        risk_level = "severe"

    risk_labels = {
        "minimal": "Minimal depression",
        "mild": "Mild depression",
        "moderate": "Moderate depression",
        "moderately_severe": "Moderately severe depression",
        "severe": "Severe depression",
    }
    clinical_summary = (
        f"PHQ-9: {risk_labels[risk_level]} — score {total_score}/27. "
        f"Student wrote: \"{mood_text[:120]}{'…' if len(mood_text) > 120 else ''}\". "
        f"Review survey responses and mood text before session."
    )

    # Save the check-in
    checkin_doc = {
        "user_id": user_id,
        "user_token": token,
        "mood_text": mood_text,
        "answers": answers,
        "total_score": total_score,
        "risk_level": risk_level,
        "clinical_summary": clinical_summary,
        "created_at": datetime.utcnow(),
    }
    assessments_col.insert_one(checkin_doc)

    # Derive mood value (1-5) from PHQ-9 score (0-27, higher = worse)
    if total_score <= 4:
        mood_value = 5   # minimal
    elif total_score <= 9:
        mood_value = 4   # mild
    elif total_score <= 14:
        mood_value = 3   # moderate
    elif total_score <= 19:
        mood_value = 2   # moderately severe
    else:
        mood_value = 1   # severe

    # Save mood to moods_col so AI flagging engine has data
    moods_col.insert_one({
        "user_id": user_id,
        "value": mood_value,
        "note": mood_text[:200],
        "source": "checkin",
        "created_at": datetime.utcnow(),
    })

    # Save mood text as journal entry so AI can analyse the language
    if mood_text:
        journals_col.insert_one({
            "user_id": user_id,
            "content": mood_text,
            "source": "checkin",
            "created_at": datetime.utcnow(),
        })

    # Update user activity
    users_col.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"last_active": datetime.utcnow()}, "$inc": {"usage_streak": 1}}
    )

    # ── Create a check-in flag for staff and send email report ──
    # Every daily check-in generates a report for the directorate
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    existing_checkin_flag = flags_col.find_one({
        "user_id": user_id,
        "flag_type": "checkin",
        "created_at": {"$gte": today_start},
    })
    if not existing_checkin_flag:
        # PHQ-9 severity → flag severity
        if risk_level in ("severe", "moderately_severe"):
            severity = "urgent"
        elif risk_level == "moderate":
            severity = "concern"
        else:
            severity = "watch"
        # PHQ-9 item 9 (self-harm thoughts) always escalates to urgent
        phq9_val = int(answers.get("phq9", 0))
        if phq9_val >= 1:
            severity = "urgent"
        flag = {
            "user_id": user_id,
            "user_token": token,
            "flag_type": "checkin",
            "severity": severity,
            "reasons": [f"PHQ-9 check-in: {risk_labels[risk_level]} ({total_score}/27)"],
            "reason": f"PHQ-9 check-in: {risk_labels[risk_level]} ({total_score}/27)",
            "mood_trend": [],
            "journal_excerpt": mood_text[:200],
            "assessment_score": total_score,
            "assessment_risk": risk_level,
            "assessment_summary": clinical_summary,
            "status": "pending",
            "created_at": datetime.utcnow(),
            "flagged_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "dashboard_url": f"{APP_URL}/staff/dashboard",
            "reviewed_by": None,
            "action_taken": None,
        }
        result = flags_col.insert_one(flag)
        flag["_id"] = result.inserted_id
        # Send email synchronously so we can catch errors
        email_sent = send_flag_email(flag)
        email_error = None if email_sent else "Email send returned False"

    # Run AI-powered flag check in background
    threading.Thread(target=check_and_flag_user, args=(user_id,), daemon=False).start()

    # Clear the needs_checkin flag
    session.pop("needs_checkin", None)

    return jsonify({
        "ok": True,
        "risk_level": risk_level,
        "total_score": total_score,
        "max_score": 27,
        "summary": clinical_summary,
        "email_sent": email_sent if not existing_checkin_flag else "skipped_existing",
        "email_to": EMAIL_CONFIG["directorate_email"],
    })


@app.route("/api/journal", methods=["POST"])
@login_required
def save_journal():
    """Save journal entry and check for crisis keywords."""
    data = request.json
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "Empty entry"}), 400
    
    user_id = session["user_id"]
    entry = {
        "user_id": user_id,
        "content": content,
        "created_at": datetime.utcnow(),
    }
    journals_col.insert_one(entry)
    
    # Update activity
    users_col.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"last_active": datetime.utcnow()}}
    )
    
    # Run Claude-powered flag check in background after journal save
    threading.Thread(target=check_and_flag_user, args=(user_id,), daemon=False).start()

    return jsonify({"ok": True})


@app.route("/api/journal/entries", methods=["GET"])
@login_required
def get_journal_entries():
    user_id = session["user_id"]
    entries = list(journals_col.find(
        {"user_id": user_id},
        sort=[("created_at", -1)]
    ).limit(20))
    for e in entries:
        e["_id"] = str(e["_id"])
    return jsonify(entries)


@app.route("/api/group/<group_id>/messages", methods=["GET"])
@login_required
def get_group_messages(group_id):
    msgs = list(messages_col.find(
        {"group_id": group_id},
        sort=[("created_at", -1)]
    ).limit(50))
    msgs.reverse()
    for m in msgs:
        m["_id"] = str(m["_id"])
    return jsonify(msgs)


@app.route("/api/group/<group_id>/send", methods=["POST"])
@login_required
def send_group_message(group_id):
    data = request.json
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Empty message"}), 400
    
    msg = {
        "group_id": group_id,
        "user_id": session["user_id"],
        "anon_name": session.get("anon_name", "Anonymous"),
        "text": text,
        "is_guide": False,
        "created_at": datetime.utcnow(),
    }
    messages_col.insert_one(msg)
    msg["_id"] = str(msg["_id"])

    # Track membership: increment group member count on first message
    user_id = session["user_id"]
    user = users_col.find_one({"_id": ObjectId(user_id)})
    joined = user.get("groups_joined", [])
    if group_id not in joined:
        users_col.update_one(
            {"_id": ObjectId(user_id)},
            {"$push": {"groups_joined": group_id}}
        )
        groups_col.update_one(
            {"_id": ObjectId(group_id)},
            {"$inc": {"members": 1}}
        )

    return jsonify({"ok": True, "message": msg})


@app.route("/api/group/<group_id>/message/<msg_id>", methods=["DELETE"])
@login_required
def delete_group_message(group_id, msg_id):
    """Delete a message — only the sender can delete their own."""
    result = messages_col.delete_one({
        "_id": ObjectId(msg_id),
        "group_id": group_id,
        "user_id": session["user_id"],
    })
    if result.deleted_count == 0:
        return jsonify({"error": "Message not found or not yours"}), 404
    return jsonify({"ok": True})


@app.route("/api/counsellor/messages", methods=["GET"])
@login_required
def get_counsellor_messages():
    user_id = session["user_id"]
    msgs = list(counsel_col.find(
        {"user_id": user_id},
        sort=[("created_at", 1)]
    ))
    # Mark as read
    counsel_col.update_many(
        {"user_id": user_id, "read": False, "from": "counsellor"},
        {"$set": {"read": True}}
    )
    for m in msgs:
        m["_id"] = str(m["_id"])
    return jsonify(msgs)


@app.route("/api/counsellor/send", methods=["POST"])
@login_required
def send_to_counsellor():
    data = request.json
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Empty"}), 400
    
    msg = {
        "user_id": session["user_id"],
        "from": "user",
        "text": text,
        "read": False,
        "created_at": datetime.utcnow(),
    }
    counsel_col.insert_one(msg)
    msg["_id"] = str(msg["_id"])
    return jsonify({"ok": True})


# Staff API

@app.route("/api/staff/flag/<flag_id>/review", methods=["POST"])
@staff_required
def review_flag(flag_id):
    """Mark flag as reviewed."""
    flags_col.update_one(
        {"_id": ObjectId(flag_id)},
        {"$set": {
            "status": "reviewed",
            "reviewed_by": session.get("staff_name", "Staff"),
            "reviewed_at": datetime.utcnow(),
        }}
    )
    return jsonify({"ok": True})


@app.route("/api/staff/flag/<flag_id>/chat", methods=["POST"])
@staff_required
def initiate_chat(flag_id):
    """
    Counsellor initiates anonymous chat.
    Sends a gentle first message — user sees notification.
    """
    flag = flags_col.find_one({"_id": ObjectId(flag_id)})
    if not flag:
        return jsonify({"error": "Flag not found"}), 404
    
    data = request.json
    session_num = data.get("session", 1)
    
    messages_map = {
        1: "Resources are available if you need them. You are not alone.",
        2: "A counsellor is ready to chat — no names needed.",
        3: "You do not have to go through this alone. We are here for you.",
    }
    
    text = messages_map.get(session_num, messages_map[1])
    
    msg = {
        "user_id": flag["user_id"],
        "from": "counsellor",
        "text": text,
        "read": False,
        "staff_name": session.get("staff_name"),
        "created_at": datetime.utcnow(),
    }
    counsel_col.insert_one(msg)
    
    # Update flag status
    flags_col.update_one(
        {"_id": ObjectId(flag_id)},
        {"$set": {"status": "action_taken", "action_taken": f"Chat initiated (Session {session_num})"}}
    )
    
    return jsonify({"ok": True})


@app.route("/api/staff/flag/<flag_id>/token", methods=["POST"])
@staff_required
def generate_session_token(flag_id):
    """
    Generate one-time anonymous meeting code.
    User can walk into counselling centre with just this code.
    """
    flag = flags_col.find_one({"_id": ObjectId(flag_id)})
    if not flag:
        return jsonify({"error": "Flag not found"}), 404
    
    code = generate_token()
    token_doc = {
        "user_id": flag["user_id"],
        "flag_id": str(flag_id),
        "code": code,
        "used": False,
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(days=7),
        "created_by": session.get("staff_name"),
    }
    tokens_col.insert_one(token_doc)
    
    # Notify user
    msg = {
        "user_id": flag["user_id"],
        "from": "counsellor",
        "text": f"A counsellor would like to offer you support. Your private session code is: #{code}. Visit the Counselling Centre or use this code to start an anonymous session. No one will know who you are.",
        "read": False,
        "is_token": True,
        "token_code": code,
        "created_at": datetime.utcnow(),
    }
    counsel_col.insert_one(msg)
    
    # Update flag
    flags_col.update_one(
        {"_id": ObjectId(flag_id)},
        {"$set": {"status": "action_taken", "action_taken": f"Token generated: #{code}"}}
    )
    
    return jsonify({"ok": True, "code": code})


@app.route("/api/staff/chat/<user_id>/send", methods=["POST"])
@staff_required
def staff_send_message(user_id):
    """Counsellor sends message to anonymous user."""
    data = request.json
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Empty"}), 400
    
    msg = {
        "user_id": user_id,
        "from": "counsellor",
        "text": text,
        "read": False,
        "staff_name": session.get("staff_name"),
        "created_at": datetime.utcnow(),
    }
    counsel_col.insert_one(msg)
    msg["_id"] = str(msg["_id"])
    return jsonify({"ok": True})


@app.route("/api/staff/run-flagging", methods=["POST"])
@staff_required
def trigger_flagging():
    """Manually trigger flagging check (or hook to cron)."""
    flags = run_periodic_flagging()
    return jsonify({
        "ok": True,
        "flags_created": len(flags),
        "details": [{"token": f.get("user_token"), "severity": f.get("severity")} for f in flags]
    })


@app.route("/api/staff/set-email", methods=["POST"])
@staff_required
def set_demo_email():
    """Live-swap the alert recipient email (for demo/pitch)."""
    data = request.json
    email = data.get("email", "").strip()
    if not email or "@" not in email:
        return jsonify({"error": "Invalid email"}), 400
    EMAIL_CONFIG["directorate_email"] = email
    return jsonify({"ok": True, "email": email})


@app.route("/api/staff/test-email", methods=["POST"])
@staff_required
def test_email():
    """Send a test email to verify SMTP is working."""
    cfg = EMAIL_CONFIG
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "[SafeSpace] Test Email — SMTP Working"
        msg["From"] = cfg["sender_email"]
        msg["To"] = cfg["directorate_email"]
        msg.attach(MIMEText("This is a test email from SafeSpace UG. If you see this, email alerts are working.", "plain"))
        msg.attach(MIMEText("<div style='font-family:sans-serif;padding:20px;'><h2>SafeSpace UG — Test Email</h2><p>If you see this, email alerts are working correctly.</p><p>Recipient: " + cfg["directorate_email"] + "</p></div>", "html"))

        if cfg["smtp_port"] == 465:
            with smtplib.SMTP_SSL(cfg["smtp_server"], cfg["smtp_port"]) as server:
                server.login(cfg["sender_email"], cfg["sender_password"])
                server.sendmail(cfg["sender_email"], cfg["directorate_email"], msg.as_string())
        else:
            with smtplib.SMTP(cfg["smtp_server"], cfg["smtp_port"]) as server:
                server.starttls()
                server.login(cfg["sender_email"], cfg["sender_password"])
                server.sendmail(cfg["sender_email"], cfg["directorate_email"], msg.as_string())

        return jsonify({"ok": True, "sent_to": cfg["directorate_email"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ─── Default peer groups seed 
PEER_GROUPS_DATA = [
    {"name": "Anxiety & Worry", "emoji": "🌊", "desc": "A safe space to share what weighs on your mind", "head": "Peer Guide Ama"},
    {"name": "Loneliness", "emoji": "🌙", "desc": "You're not alone in feeling alone", "head": "Peer Guide Kwame"},
    {"name": "Academic Pressure", "emoji": "📚", "desc": "When school feels like too much", "head": "Peer Guide Efua"},
    {"name": "Grief & Loss", "emoji": "🕊️", "desc": "Healing together, at your own pace", "head": "Peer Guide Kofi"},
    {"name": "Self-Worth", "emoji": "🪞", "desc": "Rediscovering who you are", "head": "Peer Guide Esi"},
    {"name": "Relationships", "emoji": "💔", "desc": "Navigating connections & heartbreak", "head": "Peer Guide Yaw"},
]


def seed_groups():
    """Seed peer groups if empty."""
    if groups_col.count_documents({}) == 0:
        for g in PEER_GROUPS_DATA:
            g["members"] = 0
            g["created_at"] = datetime.utcnow()
            groups_col.insert_one(g)
        print("[SEED] Peer groups created.")



# RUN

if __name__ == "__main__":
    seed_groups()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
