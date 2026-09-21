# 🎓 StuHub – Student Support Portal

> **"Helping Students, Simplifying Campus Life"**
> ## 🌐 Live Demo

https://stuhub-rnag.onrender.com


StuHub is an all-in-one, modern campus support web platform engineered with **Python (Flask)**, **SQLite**, **HTML5**, **CSS3**, and **Vanilla JavaScript**. It brings together **Campus Events**, **Facility Complaints**, **Lost & Found Items**, **Official Announcements**, **In-App Notifications**, and a **Minimal 2 × 2 Admin Management Portal** into a single, responsive platform tailored for college students and campus administrators.

---

## 📌 Project Purpose

On modern university campuses, student services are often fragmented across disparate message boards, separate chat groups, and paper forms. 

**StuHub** provides a single institutional portal to:
- **Streamline Campus Grievances**: Transparently submit facility tickets (electrical, laboratory, washroom, furniture) with live progress tracking (`Pending` ➔ `In Progress` ➔ `Resolved`).
- **Unify Campus Events**: Browse technical hackathons, coding contests, cultural fests, and workshops; reserve seats; make demo payments; and generate confirmed digital event passes.
- **Recover Lost Property**: Centralized lost & found registry with live search and photo/camera uploads.
- **Broadcast Official Notices**: Real-time university circulars and academic alerts.
- **Separate Administration**: A minimal, dedicated 2 × 2 Admin Home Page linking to dedicated management portals with full student registration rosters, attendee exports, and status controls.

---

## ✨ Key Features & Architecture

### 1. 🌟 Full-Screen Hero Landing Page
- Minimalist hero design featuring full-screen campus backdrop.
- Immediate call-to-actions (`[ Get Started → ]` & `[ Explore Features ]`).
- Responsive navbar with instant access to authentication.

### 2. 🔐 Two-Tier Authentication & College Email Verification
- **Dual Login**: Clearly separated **Student Login** and **Admin Login**.
- **College Email Domain Validation**: Only allows institutional domains (`@stuhub.edu`, `@college.edu.in`, `@college.ac.in`, etc.); automatically rejects personal emails (Gmail, Yahoo, Outlook).
- **6-Digit Verification Code**: Email verification flow with expiration and developer console fallback.
- **Session Security**: `@login_required` and `@admin_required` route decorators protecting student and administrative operations.

### 3. 🎓 Student Dashboard
- Personalized greeting and quick-action cards:
  1. **Lost & Found Items**
  2. **Complaints Raise**
  3. **Campus Events**
  4. **Announcements**
- **Just Your Activity**: Dedicated personal activity stream showing only the logged-in student's complaints, reports, and registered events.

### 4. 📸 Dual Photo Input (Camera Snapshot & File Upload)
- Instant camera snapshot using HTML5 Canvas & `navigator.mediaDevices.getUserMedia`.
- Traditional file upload supporting JPG, PNG, WEBP, and GIF with client-side preview.

### 5. 🎪 Campus Events Portal & Attendee Management
- **Category Streams**: Technical (Hackathons, Coding, Quiz, Workshops, Project Expo) & Non-Technical (Cultural, Sports, Arts, Fest).
- **Seat Allocation**: Real-time available seats calculation with automatic pass code generation (`REG-EVT...` / `PAID-EVT...`).
- **Demo Payment Gateway**: Integrated mock payment simulation for paid workshops and competitions.
- **My Registrations**: Digital event passbook for enrolled students.

### 6. 🛡️ Minimal Admin Dashboard (Clean 2 × 2 Grid)
- **Zero Clutter**: The Admin Home Page displays strictly **ONLY 4 OPTIONS** in a clean 2 × 2 grid:
  1. **`[ EVENTS PORTAL ]`** &rarr; Dedicated Events Management & Attendee Rosters.
  2. **`[ ANNOUNCEMENTS ]`** &rarr; Notice Publisher & Active Broadcasts.
  3. **`[ COMPLAINTS ]`** &rarr; Student Grievance Tickets & Status Controls.
  4. **`[ STUDENTS ]`** &rarr; Registered Students Directory & Profiles.
- **Dedicated Portals**: Detailed tables, photo previews, resolution controls, and attendee CSV exports reside exclusively in their respective dedicated sub-portals.

---

## 🛠️ Technology Stack

| Layer | Technology | Details |
| :--- | :--- | :--- |
| **Frontend** | **HTML5 & Jinja2** | 26 semantic templates with clean modular inheritance (`base.html`) |
| | **CSS3** | Custom design system, CSS variables, responsive 2 × 2 grid, mobile drawer |
| | **Vanilla JavaScript** | Camera capture, client-side live search, modal dialogs, status filtering |
| **Backend** | **Python 3.10+ / 3.11** | Core application logic |
| | **Flask 3.x** | Lightweight WSGI web framework, session management, routing |
| | **Werkzeug** | Secure password hashing (`generate_password_hash`, `check_password_hash`) |
| | **Gunicorn** | Production WSGI HTTP server |
| **Database** | **SQLite 3** | Relational database with WAL mode and foreign key integrity |
| **Deployment** | **Render / GitHub** | `render.yaml` Blueprint, `Procfile`, Linux compatibility verified |

---

## 📁 Directory Structure

```
StuHub/
│
├── app.py                     # Main Flask application (routes, DB helpers, seeds)
├── database.db                # SQLite database (auto-initialized with demo data)
├── requirements.txt           # Production Python dependencies (Flask, Werkzeug, Gunicorn)
├── Procfile                   # Process file for Render / Heroku (web: gunicorn app:app)
├── render.yaml                # Render Blueprint infrastructure-as-code deployment spec
├── test_app.py                # Automated unit tests (21 test cases)
├── .gitignore                 # Git ignore rules for Python bytecode, cache, virtual environments
├── README.md                  # Complete project documentation
│
├── static/
│   ├── css/
│   │   └── style.css          # Responsive styling, modern dark-accent theme, 2x2 grid
│   ├── js/
│   │   └── script.js          # Sidebar toggle, camera snapshot, upload preview, search
│   ├── images/                # Static visual cards & hero background assets
│   └── uploads/               # Uploaded photos (.gitkeep tracked for Git)
│       └── events/            # Event posters & placeholders (.gitkeep tracked)
│
└── templates/
    ├── base.html              # Master layout (navbar, sidebar drawer, flash alerts)
    ├── index.html             # Full-screen hero landing page
    ├── login.html             # Two-tier login (Student & Admin)
    ├── register.html          # Student registration with domain validation
    ├── verify_email.html      # 6-digit email code verification
    ├── dashboard.html         # Student dashboard (4 main cards + personal activity)
    ├── admin.html             # Minimal Admin Home Page (Clean 2 × 2 Grid)
    ├── admin_events_portal.html # Dedicated Events Portal (+ Post New Event, Seat metrics)
    ├── admin_event_registrations.html # Attendee roster with filters & CSV export
    ├── admin_announcements.html # Dedicated Announcements publisher & table
    ├── admin_complaints.html  # Dedicated Complaints table & status update controls
    ├── admin_students.html    # Dedicated Students directory with live search
    ├── events.html            # Campus Events directory (Technical & Non-Technical)
    ├── event_details.html     # Event specifications, seats, and register CTA
    ├── event_register.html    # Student event registration form
    ├── event_payment.html     # Demo payment gateway for paid events
    ├── event_confirmation.html# Confirmed event pass & ticket badge
    ├── my_registrations.html  # Student digital passbook
    ├── complaints.html        # Facility grievance submission form (dual photo input)
    ├── my_complaints.html     # Student personal complaints tracking
    ├── lost.html              # Report lost item form
    ├── found.html             # Report found item form
    ├── search.html            # Search & filter lost/found registry
    ├── announcements.html     # Public announcements feed
    ├── notifications.html     # In-app notifications center
    └── profile.html           # Student profile & edit details
```

---

## 🚀 Local Installation & Setup

### Prerequisites
- Python 3.10 or higher.
- `pip` and `git` installed.

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/StuHub.git
cd StuHub
```

### 2. Create and Activate a Virtual Environment
```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Development Server
```bash
python app.py
```

### 5. Access StuHub
Open your web browser and navigate to:
```
http://127.0.0.1:10000/
```
*(Or `http://127.0.0.1:5000/` if running locally with custom port).*

> **Note**: SQLite database (`database.db`) and seed data are automatically initialized on startup!

---

## 🔑 Default Credentials

| Portal | Email / Identifier | Password | Access Level |
| :--- | :--- | :--- | :--- |
| **Student Portal** | `rahul@stuhub.edu` | `student123` | Student Dashboard, Events, Complaints, Lost & Found |
| **Admin Portal** | `admin@stuhub.edu` | `admin123` | Minimal Admin Home, Events Portal, Announcements, Complaints, Students Directory |

---

## 🧪 Running Automated Tests

Run the built-in unit test suite verifying all 21 test cases:
```bash
python -m unittest test_app.py
```

**Expected output:**
```
Ran 21 tests in ~7s

OK
```

---

## 🌐 Production Deployment on Render

Deploying StuHub to [Render](https://render.com) takes less than 3 minutes.

### Method 1: Deploy with Render Blueprint (Recommended)
1. Push your repository to GitHub.
2. Sign in to [Render Dashboard](https://dashboard.render.com).
3. Click **New +** ➔ **Blueprint**.
4. Connect your `StuHub` GitHub repository.
5. Render will automatically detect `render.yaml` and configure:
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Plan**: Free
   - **Environment Variables**: `PYTHON_VERSION=3.11.0`, `SECRET_KEY` (auto-generated), `PORT=10000`.
6. Click **Apply**. Render will build and deploy your app.

### Method 2: Manual Web Service Setup
1. On Render, click **New +** ➔ **Web Service**.
2. Select your GitHub repository.
3. Configure the service settings:
   - **Name**: `stuhub`
   - **Region**: Select closest to your users (e.g., Singapore, Frankfurt, Oregon)
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Instance Type**: `Free`
4. Add **Environment Variables** (under *Advanced*):
   - `SECRET_KEY`: Enter a secure random string (e.g. `openssl rand -hex 32`)
   - `PYTHON_VERSION`: `3.11.0`
   - `ADMIN_INITIAL_PASSWORD`: *(Optional)* Custom initial password for `admin@stuhub.edu`
5. Click **Create Web Service**.

Your application will be live at:
`https://stuhub-xxxx.onrender.com`

---

## 🔒 Environment Variables Reference

| Variable | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `SECRET_KEY` | Recommended | `stuhub-campus-support-portal-secret-key-2026` | Session encryption secret |
| `PORT` | Auto (Render) | `10000` | Port for Flask / Gunicorn binding |
| `ALLOWED_COLLEGE_DOMAINS` | Optional | `stuhub.edu,college.edu.in,college.ac.in,campus.edu,university.edu,engg.edu.in` | Comma-separated list of approved college email domains |
| `ADMIN_INITIAL_PASSWORD` | Optional | `admin123` | Initial password seeded for `admin@stuhub.edu` |
| `STUDENT_INITIAL_PASSWORD`| Optional | `student123` | Initial password seeded for demo student |
| `MAIL_SERVER` | Optional | *(None)* | SMTP server host (e.g., `smtp.gmail.com`) |
| `MAIL_PORT` | Optional | `587` | SMTP port |
| `MAIL_USERNAME` | Optional | *(None)* | SMTP account email |
| `MAIL_PASSWORD` | Optional | *(None)* | SMTP app password |
| `MAIL_USE_TLS` | Optional | `true` | Enable TLS for SMTP |

---

## 📄 License

This project is licensed under the **MIT License** &ndash; free to use, modify, and distribute for educational and campus purposes.
