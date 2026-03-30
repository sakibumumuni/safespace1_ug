# SafeSpace UG

**Anonymous Mental Health Support for University of Ghana Students**

A mobile-first web app where UG students can anonymously track mood, journal, chat in peer support groups, and get connected to crisis support — all without ever revealing their identity. A standardized PHQ-9 check-in is completed when a student wants to speak with a counsellor, giving staff an overview of their mental state before engagement. An AI-powered flagging engine (Claude Haiku 4.5) monitors for signs of distress and alerts the UG Counselling Directorate via structured email so staff can intervene early.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        STUDENT APP                            │
│  Landing -> Home -> Mood (with notes) / Journal / Groups       │
│         -> Counsellor Chat (PHQ-9 gate) / Crisis              │
└────────────────────────┬─────────────────────────────────────┘
                         │  Flask API
                         v
                ┌────────────────┐
                │    MongoDB     │
                │  Atlas Cluster │
                └───────┬────────┘
                        │
        ┌───────────────┼───────────────────┐
        v               v                   v
┌───────────────┐ ┌─────────────┐ ┌─────────────────────┐
│  CLAUDE AI    │ │  PHQ-9      │ │  STAFF DASHBOARD     │
│  FLAG ENGINE  │ │  CHECK-IN   │ │  Review flags        │
│  (Haiku 4.5)  │ │  (before    │ │  Read PHQ-9 summary  │
│  Periodic     │ │  counsellor │ │  Initiate chat       │
│  risk assess  │ │  chat)      │ │  Generate tokens     │
│  per user     │ │  9 items    │ │  Test & set email    │
│  (background) │ │  0-27 score │ │                      │
└───────┬───────┘ └──────┬──────┘ └─────────────────────┘
        │                │
        v                v
┌───────────────┐  ┌───────────────┐
│  AI PERIODIC  │  │  PHQ-9        │
│  EMAIL ALERT  │  │  CHECK-IN     │
│  (background  │  │  EMAIL ALERT  │
│   thread)     │  │  (background  │
│  Separate     │  │   thread)     │
│  from PHQ-9   │  │  With severity│
└───────────────┘  └───────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Flask 3.1.0 (Python) |
| Database | MongoDB Atlas (pymongo 4.9.1) |
| AI/Flagging | Anthropic Claude API (Haiku 4.5) — periodic risk assessment |
| Intake | PHQ-9 standardized questionnaire with local scoring (instant) |
| Frontend | Vanilla JS, custom CSS (dark theme, glassmorphism, mobile-first) |
| Email Alerts | SMTP SSL (Gmail, port 465) — sent in background threads |
| Auth | Session-based (students), access code (staff) |
| Deployment | Render.com |

---

## Features

### Student-Facing

- **Anonymous Entry** — No signup, no email, no personal data. Students click "Enter Anonymously" and receive a generated identity (e.g. `Anon-BraveRiver`, token `#UG-7742`).
- **Mood Tracking with Notes** — Daily 5-point emoji mood picker (Struggling to Great) with an optional notes field to add context about how they're feeling. 7-day bar chart trend on the home dashboard.
- **PHQ-9 Check-in Before Counsellor Chat** — When a student wants to speak with a counsellor, they complete:
  1. **Free-text mood description** — "How are you feeling?" in their own words (English, Ghanaian Pidgin, or Twi). Minimum 10 characters.
  2. **PHQ-9 Questionnaire** — Standardized 9-item Patient Health Questionnaire. Each question scored 0-3 (max total 27). Covers: anhedonia, depressed mood, sleep, fatigue, appetite, self-worth, concentration, psychomotor changes, and suicidal ideation.
  - The system generates an instant clinical intake summary locally — no API call, instant results.
  - PHQ-9 item 9 (self-harm thoughts) automatically escalates to urgent severity if non-zero.
  - After submission, the student proceeds to the anonymous counsellor chat.
  - If already completed today, the student goes straight to the chat.
- **Private Journal** — Free-form writing space with character counter. Entries are stored per user and never shared unless the AI detects crisis signals.
- **Peer Support Groups** — Six themed anonymous group chats (Anxiety & Worry, Loneliness, Academic Pressure, Grief & Loss, Self-Worth, Relationships), each with a named peer guide.
- **Message Deletion** — Users can delete their own messages in group chats.
- **Anonymous Counsellor Chat** — Direct messaging line to UG Counselling. Messages poll every 5 seconds. Students see a notification banner on the home page when a counsellor replies.
- **Crisis Resources** — Dedicated page with UG Counselling (030 290 2014), Mental Health Authority Ghana (0800 678 678), Ghana Health Service (112), and UG Health Services (030 250 0301).
- **Session Tokens** — If a counsellor generates a one-time code (e.g. `#UG-3391`), the student sees it on their home page and can walk into the Counselling Centre with just that code — no name needed.

### Staff-Facing

- **Staff Dashboard** — Protected view showing stats (total users, active today, pending flags, urgent flags) and all flag cards sorted by severity. Email link redirects to staff login if not authenticated.
- **Two Separate Flag & Email Systems**:
  - **PHQ-9 Check-in flags** (purple badge) — Generated when a student completes the PHQ-9 before speaking to a counsellor. Includes the student's own words, PHQ-9 score (/27), severity level, and clinical summary. Sends a separate email with subject `[SafeSpace PHQ-9 ...]`.
  - **AI Periodic flags** (blue badge) — Generated by the Claude AI flagging engine (Haiku 4.5) from mood trends and journal patterns. Sends a separate email with subject `[SafeSpace AI ...]`.
- **PHQ-9 Assessment Display** — Each check-in flag shows:
  - The student's free-text mood description ("Student's own words")
  - PHQ-9 score out of 27 with severity badge (minimal/mild/moderate/moderately severe/severe)
  - Clinical summary that counsellors can read before engagement
- **Test Email Button** — Verify SMTP delivery directly from the dashboard. Shows success or the exact error.
- **Live Email Recipient Swap** — Change the alert email recipient on the fly for demos.
- **3-Stage Chat Initiation** — Pre-written outreach messages that staff can send in sequence.
- **Token Generation** — Create a one-time anonymous meeting code (expires in 7 days).
- **Free-Form Chat** — Full anonymous conversation view per flagged user.
- **Manual Flagging Trigger** — "Run Flagging Check" button that scans all recently active users through the AI engine.

---

## PHQ-9 Check-in System

The PHQ-9 check-in is initiated when a student wants to speak with a counsellor, giving the counselling team an overview of the student's state before engagement.

### How It Works

1. **Counsellor chat gate** — When a student navigates to the counsellor chat, the app checks if they've completed today's PHQ-9. If not, they must complete it first.
2. **Step 1: Free text** — The student describes how they're feeling in their own words. Supports English, Ghanaian Pidgin English, and Twi.
3. **Step 2: PHQ-9** — Nine standardized questions ("Over the last 2 weeks, how often have you been bothered by..."), each scored 0-3.
4. **Instant Summary** — The system generates a clinical intake summary locally. No external API call — zero latency.
5. **Flagging & Email** — A check-in flag is created with severity based on PHQ-9 score, and an email is sent to the counselling directorate in a background thread (non-blocking).
6. **Proceed to chat** — After submission, the student continues to the anonymous counsellor chat.
7. **Once per day** — If already completed today, subsequent visits go straight to chat.

### PHQ-9 Severity Levels

| Score | Level | Flag Severity |
|-------|-------|---------------|
| 0-4 | Minimal depression | watch |
| 5-9 | Mild depression | watch |
| 10-14 | Moderate depression | concern |
| 15-19 | Moderately severe depression | urgent |
| 20-27 | Severe depression | urgent |

**Special rule:** PHQ-9 item 9 (thoughts of self-harm) at any non-zero value automatically escalates to **urgent** severity regardless of total score.

---

## AI-Powered Periodic Flagging Engine

Separate from the PHQ-9 check-in, this engine runs in background threads on mood logs and journal saves to catch patterns over time.

### How It Works

1. **Trigger** — Every mood log and every journal save triggers `check_and_flag_user()` in a background thread (non-blocking).
2. **Data Gathering** — The engine collects:
   - Last 7 mood entries (values 1-5)
   - Last 5 journal excerpts (up to 300 chars each)
   - Days of inactivity and usage streak length
   - Latest PHQ-9 assessment (if available)
3. **Claude Analysis** — All data is sent to Claude Haiku 4.5 for risk assessment across:
   - Crisis language (suicidal ideation, self-harm, hopelessness) in **English, Ghanaian Pidgin, and Twi**
   - Persistently low moods (3+ entries at 2 or below)
   - Steady mood decline over multiple days
   - Sudden inactivity after a consistent usage streak
   - Compounding patterns across data sources
4. **Structured Response** — Claude returns a JSON verdict with severity and reasons.
5. **Deduplication** — If the same user was flagged within the severity-based interval, the flag is skipped.
6. **Flag Creation** — A flag document is stored with `flag_type: "periodic"`.
7. **Email Alert** — A styled HTML email is sent in a background thread, separate from PHQ-9 check-in emails.

### Severity Levels & Intervals

| Severity | Meaning | Re-check Interval |
|----------|---------|-------------------|
| **Urgent** | Crisis language, suicidal ideation, sustained mood at 1 | 24 hours |
| **Concern** | Persistent low moods, steady decline, worrying inactivity | 48 hours |
| **Watch** | Mild patterns that warrant monitoring | 72 hours |

### Why Claude Instead of Keywords

- **Multilingual understanding** — Detects distress in English, Ghanaian Pidgin ("I no fit again"), and Twi ("me pe se me wu") without fragile regex lists.
- **Context awareness** — "I killed it on the exam" won't trigger a false positive.
- **Compound signals** — Weighs declining moods + concerning language + inactivity together.
- **Evolving coverage** — No manual keyword list maintenance needed.

---

## Email Alerts

### Two Separate Email Systems

Check-in emails and periodic AI emails are **independent** — each has its own subject line, trigger, and content.

| Type | Subject Format | Trigger |
|------|---------------|---------|
| PHQ-9 Check-in | `[SafeSpace PHQ-9 SEVERITY] ... Pre-session check-in` | Student completes PHQ-9 before counsellor chat |
| AI Periodic | `[SafeSpace AI SEVERITY] ... Periodic risk assessment` | Mood log or journal save triggers Claude analysis |

### Configuration

- SMTP SSL on port 465 (Gmail)
- Emails sent in **background threads** so the app responds instantly
- Recipient can be changed live from the staff dashboard
- Test email button on dashboard to verify delivery

### What the Email Contains

- Anonymous token (never real identity)
- Severity level with color coding
- Reason for flagging
- Mood trend as emoji sequence
- Student's own words / journal excerpt
- PHQ-9 score (/27) and severity level (if available)
- Clinical summary
- **Clickable "Review in Dashboard" button** with `target="_blank"` — opens in browser
- Fallback plain-text URL below the button

### Staff Actions After Receiving Email

1. Click dashboard link → login → review flag
2. Read PHQ-9 summary and student's own words
3. Send staged outreach messages (Sessions 1-3)
4. Generate one-time anonymous meeting code
5. Open full anonymous chat

---

## Database Schema

**Database:** `safespace_ug` (MongoDB Atlas)

| Collection | Purpose | Key Fields |
|------------|---------|------------|
| `users` | Anonymous accounts | `anon_name`, `token`, `last_active`, `usage_streak`, `groups_joined` |
| `moods` | Mood entries with notes | `user_id`, `value` (1-5), `note`, `created_at`, `source` |
| `journals` | Private journal entries | `user_id`, `content`, `source`, `created_at` |
| `peer_groups` | Support group definitions | `name`, `emoji`, `desc`, `head`, `members` |
| `messages` | Group chat messages | `group_id`, `user_id`, `anon_name`, `text`, `is_guide` |
| `flags` | Risk flags (check-in + periodic) | `user_token`, `flag_type` ("checkin"/"periodic"), `severity`, `reasons`, `mood_trend`, `journal_excerpt`, `assessment_score`, `assessment_risk`, `assessment_summary`, `status` |
| `counsel_msgs` | Counsellor-student chat | `user_id`, `from` (user/counsellor), `text`, `read` |
| `session_tokens` | One-time meeting codes | `code`, `used`, `expires_at`, `created_by` |
| `assessments` | PHQ-9 check-in records | `user_id`, `user_token`, `mood_text`, `answers`, `total_score` (/27), `risk_level`, `clinical_summary`, `created_at` |

---

## API Reference

### Student Endpoints

| Method | Route | Purpose |
|--------|-------|---------|
| POST | `/api/auth/register` | Create anonymous account |
| POST | `/api/checkin` | Submit PHQ-9 check-in (mood text + 9 answers) |
| POST | `/api/mood` | Log emoji mood (1-5) with optional note + trigger background flag check |
| POST | `/api/journal` | Save journal entry + trigger background flag check |
| GET | `/api/journal/entries` | Fetch past entries (limit 20) |
| GET | `/api/group/<id>/messages` | Fetch group chat messages |
| POST | `/api/group/<id>/send` | Send group chat message + auto-join group |
| DELETE | `/api/group/<id>/message/<msg_id>` | Delete own message from group chat |
| GET | `/api/counsellor/messages` | Fetch counsellor messages (marks as read) |
| POST | `/api/counsellor/send` | Send message to counsellor |

### Staff Endpoints (protected)

| Method | Route | Purpose |
|--------|-------|---------|
| POST | `/api/staff/flag/<id>/review` | Mark flag as reviewed |
| POST | `/api/staff/flag/<id>/chat` | Send staged chat message (session 1-3) |
| POST | `/api/staff/flag/<id>/token` | Generate one-time session code |
| POST | `/api/staff/chat/<user_id>/send` | Send free-form message to student |
| POST | `/api/staff/run-flagging` | Manually trigger AI flagging for all active users |
| POST | `/api/staff/set-email` | Live-swap the alert recipient email |
| POST | `/api/staff/test-email` | Send test email to verify SMTP delivery |

### Pages

| Route | Page |
|-------|------|
| `/` | Landing (anonymous entry) |
| `/home` | Student dashboard (mood picker with notes, chart, quick links) |
| `/journal` | Journal |
| `/groups` | Peer groups listing |
| `/group/<id>` | Group chat room |
| `/counsellor-chat` | PHQ-9 gate → anonymous counsellor chat |
| `/crisis` | Crisis resources & hotlines |
| `/staff/login` | Staff authentication |
| `/staff/dashboard` | Flag review dashboard (PHQ-9 + AI periodic flags) |
| `/staff/chat/<user_id>` | Counsellor-to-student chat |

---

## Project Structure

```
safespace1_ug/
├── app.py                   # Flask backend — routes, API, PHQ-9, AI flagging, email (background threads)
├── requirements.txt         # Python dependencies (Flask, pymongo, anthropic, python-dotenv)
├── .env                     # Environment config (keys, DB URI, SMTP, staff code)
├── static/
│   ├── css/
│   │   └── style.css        # Dark theme, glassmorphism, animations, mobile-first
│   └── js/
│       └── app.js           # Client-side JS (mood with notes, chat, staff actions, test email)
└── templates/
    ├── base.html             # Master layout
    ├── nav.html              # Bottom navigation bar
    ├── landing.html          # Anonymous entry page
    ├── checkin.html          # Redirect notice (check-in moved to counsellor chat)
    ├── home.html             # Student dashboard (mood picker with notes, chart, quick links)
    ├── journal.html          # Private journal
    ├── groups.html           # Peer group listing
    ├── group_chat.html       # Group chat room
    ├── counsellor_chat.html  # PHQ-9 gate + anonymous counsellor chat
    ├── crisis.html           # Crisis resources & hotlines
    ├── staff_login.html      # Staff authentication
    ├── staff_dashboard.html  # Flag review dashboard (PHQ-9 + AI periodic flags, test email)
    └── staff_chat.html       # Counsellor-to-student chat
```

---

## Quick Start

### Prerequisites

- Python 3.9+
- MongoDB Atlas cluster (or local MongoDB)
- Anthropic API key ([console.anthropic.com](https://console.anthropic.com))
- Gmail account with App Password enabled (for email alerts)

### Install & Run

```bash
cd safespace1_ug

# Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
.venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your MongoDB URI, Anthropic API key, SMTP credentials, and staff code

# Run
python app.py
```

### Access

- **Student app:** http://localhost:5000
- **Staff dashboard:** http://localhost:5000/staff/login (default code: `UG-COUNSEL-2026`)

---

## Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `SECRET_KEY` | Flask session secret | 32-byte hex string |
| `MONGO_URI` | MongoDB connection string | `mongodb+srv://user:pass@cluster.mongodb.net/` |
| `ANTHROPIC_API_KEY` | Claude API key for AI flagging | `sk-ant-api03-...` |
| `SMTP_SERVER` | Email server | `smtp.gmail.com` |
| `SMTP_PORT` | Email port (465 for SSL) | `465` |
| `SENDER_EMAIL` | Alert sender address | `ugsafespace@gmail.com` |
| `SENDER_PASSWORD` | Gmail App Password | 16-char app-specific password |
| `DIRECTORATE_EMAIL` | Default alert recipient | `sakibumumuni204@gmail.com` |
| `STAFF_CODE` | Staff dashboard access code | `UG-COUNSEL-2026` |
| `APP_URL` | Base URL for email links | `https://safespace-ug.onrender.com` |
| `PORT` | Server port | `5000` |

---

## Design Decisions

### Privacy First
- No signup, no email, no personal data collected
- Students get anonymous tokens (e.g. `Anon-BraveRiver`, `#UG-7742`)
- Counsellors never see real identity unless the student chooses to reveal it

### PHQ-9 at Counsellor Chat Entry
- The check-in happens when the student *wants* to speak to a counsellor — not as a daily gate
- Gives the counsellor an overview of the student's state before engagement
- PHQ-9 is a validated, standardized instrument recognized in clinical practice
- Item 9 (self-harm thoughts) automatically escalates to urgent regardless of total score

### Two Independent Alert Systems
- **PHQ-9 check-in flags** — From the student's self-reported state before counsellor engagement. Instant local scoring.
- **AI periodic flags** — From Claude Haiku 4.5 analysing mood trends, journal language, and activity patterns over time.
- Each system sends its own email with distinct subject lines so staff can tell them apart in their inbox.
- Both run email sending in background threads so the student never waits.

### Background Threading
- Email sending and AI flagging run in daemon threads
- The student gets instant responses — no waiting for SMTP or Claude API calls
- Errors are logged server-side without blocking the user experience

### Email as Integration Layer
- UG staff already use email — zero new software needed on their side
- Email is the alert; the dashboard is where action happens
- Dashboard link in email redirects to staff login if not authenticated
- Test email button on dashboard to verify delivery without doing a full check-in

---

## Production Considerations

1. **Scheduled Flagging** — Use APScheduler or Celery to run `run_periodic_flagging()` on a cron schedule
2. **Email Queue** — Use a task queue (Redis + Celery) for reliable email delivery with retries
3. **WebSocket Chat** — Replace 5-second polling with Socket.IO for real-time messaging
4. **Encryption** — Encrypt journal entries and check-in text at rest (AES-256)
5. **Rate Limiting** — Add Flask-Limiter to prevent abuse
6. **Staff Auth** — Integrate with UG's SSO/LDAP instead of static access codes
7. **Monitoring** — Add logging and error tracking (Sentry) for the Claude API calls

---

## Built For

University of Ghana Counselling Directorate
Claude Builder Club Hackathon — March 2026

*"You are not alone."*
