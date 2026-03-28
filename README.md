# safespace1_ug
Mental health is taking the lives of young Ghanaians, especially university students, yet is not properly addressed. This inspires me and my team to pick the topic of Neuroscience and mental health in this particular hackathon, to build a solution that goes a long way to solve this menace
# SafeSpace UG

**Anonymous Mental Health Support for University of Ghana Students**

A mobile-first web app where UG students can anonymously track mood, journal, chat in peer support groups, and get connected to crisis support — all without ever revealing their identity. An AI-powered flagging engine monitors for signs of distress and alerts the UG Counselling Directorate via structured email so staff can intervene early.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                      STUDENT APP                          │
│   Landing  ->  Home  ->  Mood / Journal / Groups / Crisis │
│                  ↕  Anonymous Counsellor Chat              │
└────────────────────────┬─────────────────────────────────┘
                         │  Flask API
                         v
                ┌────────────────┐
                │    MongoDB     │
                │  Atlas Cluster │
                └───────┬────────┘
                        │
           ┌────────────┴────────────┐
           v                         v
   ┌───────────────┐      ┌─────────────────────┐
   │  CLAUDE AI    │      │  STAFF DASHBOARD     │
   │  FLAG ENGINE  │─────>│  Review flags        │
   │  (Haiku 4.5)  │      │  Initiate chat       │
   │  Risk assess  │      │  Generate tokens     │
   │  per user     │      │  Set alert email     │
   └───────┬───────┘      └─────────────────────┘
           │
           v
   ┌───────────────┐
   │  EMAIL ALERT  │  Structured HTML email to
   │  (SMTP SSL)   │  configurable recipient
   └───────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Flask 3.1.0 (Python) |
| Database | MongoDB Atlas (pymongo 4.9.1) |
| AI/Flagging | Anthropic Claude API (Haiku 4.5) |
| Frontend | Vanilla JS, custom CSS (dark theme, mobile-first) |
| Email Alerts | SMTP SSL (Gmail / institutional, port 465) |
| Auth | Session-based (students), access code (staff) |

---

## Features

### Student-Facing

- **Anonymous Entry** -- No signup, no email, no personal data. Students click "Enter Anonymously" and receive a generated identity (e.g. `Anon-BraveRiver`, token `#UG-7742`).
- **Mood Tracking** -- Daily 5-point mood picker (Struggling to Great) with a 7-day bar chart trend on the home dashboard.
- **Private Journal** -- Free-form writing space. Entries are stored per user and never shared unless the AI detects crisis signals.
- **Peer Support Groups** -- Six themed anonymous group chats (Anxiety & Worry, Loneliness, Academic Pressure, Grief & Loss, Self-Worth, Relationships), each with a named peer guide. Member count increases automatically when a user sends their first message in a group.
- **Message Deletion** -- Users can delete their own messages in group chats via a trash icon next to the timestamp.
- **Anonymous Counsellor Chat** -- Direct messaging line to UG Counselling. Messages poll every 5 seconds. Students see a notification banner on the home page when a counsellor replies.
- **Crisis Resources** -- Dedicated page with UG Counselling (030 290 2014), Mental Health Authority Ghana (0800 678 678), Ghana Health Service (112), and UG Health Services (030 250 0301).
- **Session Tokens** -- If a counsellor generates a one-time code (e.g. `#UG-3391`), the student sees it on their home page and can walk into the Counselling Centre with just that code — no name needed.

### Staff-Facing

- **Staff Dashboard** -- Protected view showing stats (total users, active today, pending flags, urgent flags) and all flag cards sorted by severity.
- **Live Email Recipient Swap** -- A card on the dashboard lets staff change the alert email recipient on the fly — useful for demos and pitches without restarting the app.
- **Flag Review Workflow** -- Each flag card shows the anonymous token, severity badge, mood emoji trend, journal excerpt, and action buttons.
- **3-Stage Chat Initiation** -- Pre-written outreach messages that staff can send in sequence:
  1. "Resources are available if you need them. You are not alone."
  2. "A counsellor is ready to chat — no names needed."
  3. "You do not have to go through this alone. We are here for you."
- **Token Generation** -- Create a one-time anonymous meeting code (expires in 7 days) for bridging digital support to in-person care.
- **Free-Form Chat** -- Full anonymous conversation view per flagged user with context card showing the flag reason and journal excerpt.
- **Manual Flagging Trigger** -- "Run Flagging Check" button that scans all recently active users through the AI engine.

---

## AI-Powered Flagging Engine

The core of SafeSpace UG's early-intervention system. Instead of brittle keyword lists, the flagging engine sends structured student data to **Claude Haiku 4.5** for intelligent risk assessment.

### How It Works

1. **Trigger** -- Every mood log and every journal save calls `check_and_flag_user()`.
2. **Data Gathering** -- The engine collects:
   - Last 7 mood entries (values 1-5)
   - Last 5 journal excerpts (up to 300 chars each)
   - Days of inactivity and usage streak length
3. **Claude Analysis** -- All data is sent as a JSON payload to Claude with a system prompt that instructs it to assess risk across multiple dimensions:
   - Crisis language (suicidal ideation, self-harm, hopelessness) in **English, Ghanaian Pidgin, and Twi**
   - Persistently low moods (3+ entries at 2 or below)
   - Steady mood decline over multiple days
   - Sudden inactivity after a consistent usage streak
   - Compounding patterns across data sources
4. **Structured Response** -- Claude returns a JSON verdict:
   ```json
   {
     "should_flag": true,
     "severity": "urgent",
     "reasons": ["Sustained mood at 1 over 3 days", "Journal expresses hopelessness in Twi"]
   }
   ```
5. **Markdown Stripping** -- The response is cleaned of any markdown fences before JSON parsing.
6. **Deduplication** -- If the same user was flagged within the severity-based interval, the flag is skipped to avoid alert spam.
7. **Flag Creation** -- A flag document is stored in MongoDB with severity, reasons, mood trend, and journal excerpt.
8. **Email Alert** -- A styled HTML email is sent to the configured recipient with the anonymous token, severity, reasons, mood emoji trend, journal excerpt, and a clickable link to the staff dashboard.

### Severity Levels & Intervals

| Severity | Meaning | Re-check Interval |
|----------|---------|-------------------|
| **Urgent** | Crisis language, suicidal ideation, sustained mood at 1 | 24 hours |
| **Concern** | Persistent low moods, steady decline, worrying inactivity | 48 hours |
| **Watch** | Mild patterns that warrant monitoring | 72 hours |

### Why Claude Instead of Keywords

- **Multilingual understanding** -- Detects distress in English, Ghanaian Pidgin ("I no fit again", "chale I give up"), and Twi ("me pe se me wu") without maintaining fragile regex lists.
- **Context awareness** -- A journal saying "I killed it on the exam" won't trigger a false positive. Claude understands intent, not just words.
- **Compound signals** -- Claude can weigh declining moods + concerning journal language + inactivity together, catching cases that no single rule would flag.
- **Evolving coverage** -- No need to manually update keyword lists as language evolves.

---

## Email Alerts

### Configuration

Email is sent via **SMTP SSL on port 465** (Gmail). The recipient can be changed live from the staff dashboard without restarting the app.

### What the Email Contains

```
Subject: [SafeSpace URGENT] Anonymous user UG-7742 flagged for review

- Anonymous token: #UG-7742 (never real identity)
- Severity: URGENT
- Reason: "Sustained mood at 1 over 3 days; journal expresses hopelessness"
- Mood trend: 😐😔😔😞😔😞😞
- Journal excerpt: "I don't see the point anymore..."
- Clickable link to staff dashboard
```

### Staff Actions After Receiving Email

1. **Review** -- Mark flag as reviewed on the dashboard
2. **Chat Sessions 1-3** -- Send staged outreach messages to the student
3. **Generate Token** -- Create a one-time code for anonymous in-person visit
4. **Open Full Chat** -- Start a free-form anonymous conversation

---

## Database Schema

**Database:** `safespace_ug` (MongoDB Atlas)

| Collection | Purpose | Key Fields |
|------------|---------|------------|
| `users` | Anonymous accounts | `anon_name`, `token`, `last_active`, `usage_streak`, `groups_joined` |
| `moods` | Daily mood entries | `user_id`, `value` (1-5), `note`, `created_at` |
| `journals` | Private journal entries | `user_id`, `content`, `created_at` |
| `peer_groups` | Support group definitions | `name`, `emoji`, `desc`, `head`, `members` |
| `messages` | Group chat messages | `group_id`, `user_id`, `anon_name`, `text`, `is_guide` |
| `flags` | AI-generated risk flags | `user_token`, `severity`, `reasons`, `mood_trend`, `journal_excerpt`, `status` |
| `counsel_msgs` | Counsellor-student chat | `user_id`, `from` (user/counsellor), `text`, `read` |
| `session_tokens` | One-time meeting codes | `code`, `used`, `expires_at`, `created_by` |

---

## API Reference

### Student Endpoints

| Method | Route | Purpose |
|--------|-------|---------|
| POST | `/api/auth/register` | Create anonymous account |
| POST | `/api/mood` | Log mood (1-5) + trigger flag check |
| POST | `/api/journal` | Save journal entry + trigger flag check |
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

### Pages

| Route | Page |
|-------|------|
| `/` | Landing (anonymous entry) |
| `/home` | Student dashboard |
| `/journal` | Journal |
| `/groups` | Peer groups listing |
| `/group/<id>` | Group chat room |
| `/counsellor-chat` | Anonymous counsellor chat |
| `/crisis` | Crisis resources & hotlines |
| `/staff/login` | Staff authentication |
| `/staff/dashboard` | Flag review dashboard |
| `/staff/chat/<user_id>` | Counsellor-to-student chat |

---

## Project Structure

```
safespace_ug/
├── app.py                   # Flask backend — routes, API, AI flagging engine, email
├── requirements.txt         # Python dependencies (Flask, pymongo, anthropic, python-dotenv)
├── .env                     # Environment config (keys, DB URI, SMTP, staff code)
├── static/
│   ├── css/
│   │   └── style.css        # Dark theme, mobile-first stylesheet
│   └── js/
│       └── app.js           # Client-side JS (mood, journal, chat, delete, staff actions)
└── templates/
    ├── base.html             # Master layout (head, scripts)
    ├── nav.html              # Bottom navigation bar
    ├── landing.html          # Anonymous entry page
    ├── home.html             # Student dashboard (mood, chart, notifications)
    ├── journal.html          # Private journal
    ├── groups.html           # Peer group listing
    ├── group_chat.html       # Group chat room (with message deletion)
    ├── counsellor_chat.html  # Student-side counsellor chat
    ├── crisis.html           # Crisis resources & hotlines
    ├── staff_login.html      # Staff authentication
    ├── staff_dashboard.html  # Flag review dashboard (with live email swap)
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
cd safespace_ug

# Create virtual environment
python -m venv myenv
source myenv/bin/activate        # Linux/Mac
myenv\Scripts\activate           # Windows

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
| `SMTP_PORT` | Email port (465 for SSL, 587 for TLS) | `465` |
| `SENDER_EMAIL` | Alert sender address | `safespace.ug.alerts@gmail.com` |
| `SENDER_PASSWORD` | Gmail App Password (not regular password) | 16-char app-specific password |
| `DIRECTORATE_EMAIL` | Default alert recipient | `counselling@ug.edu.gh` |
| `STAFF_CODE` | Staff dashboard access code | `UG-COUNSEL-2026` |
| `PORT` | Server port | `5000` |

---

## Design Decisions

### Privacy First
- No signup, no email, no personal data collected
- Students get anonymous tokens (e.g. `Anon-BraveRiver`, `#UG-7742`)
- Counsellors never see real identity unless the student chooses to reveal it
- Journal and mood data are tied only to the anonymous user document

### Email as Integration Layer
- UG staff already use institutional email -- zero new software needed on their side
- Email serves as the notification; the dashboard is where action happens
- HTML emails are styled and include clickable links to the dashboard
- Supports both SMTP SSL (port 465) and STARTTLS (port 587)
- Recipient email can be swapped live from the dashboard for demos

### Anonymous Token Meeting System
- One-time codes (e.g. `#UG-3391`) bridge digital support to face-to-face care
- Student walks into the Counselling Centre with just the code
- Codes expire after 7 days

### AI Over Hardcoded Rules
- Claude understands context, dialect, and compound signals
- No false positives from benign uses of flagged words
- Covers English, Ghanaian Pidgin, and Twi without manual pattern maintenance

### Auto Group Membership
- Member count tracks actual participants, not signups
- A user becomes a member on their first message in a group
- Tracked via `groups_joined` on the user document to prevent double-counting

---

## Production Considerations

1. **Scheduled Flagging** -- Use APScheduler or Celery to run `run_periodic_flagging()` on a cron schedule instead of manual trigger
2. **Email Queue** -- Use a task queue (Redis + Celery) for reliable email delivery with retries
3. **WebSocket Chat** -- Replace 5-second polling with Socket.IO for real-time messaging
4. **Encryption** -- Encrypt journal entries at rest (AES-256)
5. **HTTPS** -- Deploy with SSL (required for any health data)
6. **Rate Limiting** -- Add Flask-Limiter to prevent abuse
7. **Staff Auth** -- Integrate with UG's SSO/LDAP instead of static access codes
8. **Monitoring** -- Add logging and error tracking (Sentry) for the Claude API calls
9. **Fallback** -- Implement a simple keyword-based fallback if the Claude API is unreachable
10. **Persistent Identity** -- Allow students to re-enter their token to resume a previous session

---

## Built For

University of Ghana Counselling Directorate
Claude Builder Club Hackathon -- March 2026

*"You are not alone."*
