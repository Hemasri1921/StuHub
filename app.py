import os
import sqlite3
import time
import secrets
import base64
import smtplib
from email.message import EmailMessage
from functools import wraps
from datetime import datetime, timedelta
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, g, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# ==============================================================================
# FLASK APPLICATION CONFIGURATION
# ==============================================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'stuhub-campus-support-portal-secret-key-2026')
app.config['DATABASE'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
app.config['EVENT_UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads', 'events')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Ensure upload folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['EVENT_UPLOAD_FOLDER'], exist_ok=True)

# ==============================================================================
# COLLEGE EMAIL DOMAIN & VERIFICATION CONFIGURATION
# ==============================================================================
DEFAULT_COLLEGE_DOMAINS = [
    'stuhub.edu',
    'college.edu.in',
    'college.ac.in',
    'campus.edu',
    'university.edu',
    'engg.edu.in'
]

def get_allowed_college_domains():
    """Retrieve allowed college domains from environment or use default institutional domains."""
    env_domains = os.environ.get('ALLOWED_COLLEGE_DOMAINS', '')
    if env_domains:
        return [d.strip().lower() for d in env_domains.split(',') if d.strip()]
    return DEFAULT_COLLEGE_DOMAINS

DISALLOWED_PERSONAL_DOMAINS = {
    'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com',
    'icloud.com', 'live.com', 'aol.com', 'mail.com', 'zoho.com',
    'proton.me', 'protonmail.com', 'yandex.com', 'gmx.com',
    'rediffmail.com'
}

def is_allowed_college_domain(email):
    """
    Validates that the email belongs to an allowed college/institution domain,
    strictly rejecting general commercial/personal email providers (gmail, yahoo, etc.).
    """
    if not email or '@' not in email:
        return False, "Please enter a valid email address format."
    
    parts = email.strip().lower().split('@')
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return False, "Please enter a valid email address format."
    
    domain = parts[1].strip()

    # Explicit check against common personal email domains
    if domain in DISALLOWED_PERSONAL_DOMAINS:
        return False, "Please use your official college email address. Personal emails (Gmail, Yahoo, Outlook, Hotmail) are not allowed."

    # Check allowed list or institutional suffixes (.edu, .edu.in, .ac.in)
    allowed_list = get_allowed_college_domains()
    if (domain in allowed_list or 
        domain.endswith('.edu') or 
        domain.endswith('.edu.in') or 
        domain.endswith('.ac.in')):
        return True, "Valid college domain."
    
    return False, "Please use your official college email address. Domain is not recognized as an authorized college institution."

# SMTP Email Configuration from Environment Variables
MAIL_SERVER = os.environ.get('MAIL_SERVER')
MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('true', '1', 'yes')
MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'no-reply@stuhub.edu')

def send_college_verification_email(recipient_email, code):
    """
    Sends 6-digit verification code to student's college email.
    Uses SMTP if environment variables are configured.
    In local development / fallback, prints prominently to server console/terminal.
    """
    subject = "StuHub - College Email Verification Code"
    body = f"""Hello,

Welcome to StuHub – Student Support Portal!

Your 6-digit verification code is: {code}

This verification code will expire in 10 minutes.
Please enter this code on the registration page to verify your college email address.

If you did not request this verification code, please ignore this message.

Best regards,
StuHub Campus Support Team
"""

    sent_via_smtp = False
    if MAIL_SERVER and MAIL_USERNAME and MAIL_PASSWORD:
        try:
            msg = EmailMessage()
            msg.set_content(body)
            msg['Subject'] = subject
            msg['From'] = MAIL_DEFAULT_SENDER
            msg['To'] = recipient_email

            with smtplib.SMTP(MAIL_SERVER, MAIL_PORT, timeout=10) as server:
                if MAIL_USE_TLS:
                    server.starttls()
                server.login(MAIL_USERNAME, MAIL_PASSWORD)
                server.send_message(msg)
            sent_via_smtp = True
            app.logger.info(f"Verification email sent to {recipient_email} via SMTP.")
        except Exception as e:
            app.logger.warning(f"SMTP send failed ({e}). Falling back to terminal logger.")

    # Safe Development Mode: Output the verification code clearly to terminal for developer testing
    print("\n" + "=" * 65, flush=True)
    print(" [STUHUB] COLLEGE EMAIL VERIFICATION (DEV / CONSOLE)", flush=True)
    print(f" Recipient: {recipient_email}", flush=True)
    print(f" 6-Digit Code: >>> {code} <<<", flush=True)
    print(" Expiration: 10 minutes", flush=True)
    print("=" * 65 + "\n", flush=True)

    return True, sent_via_smtp

# Campus Events Categories Specification (Technical & Non-Technical)
EVENT_CATEGORIES = {
    'Technical': [
        'Hackathons',
        'Coding Competitions',
        'Technical Quiz',
        'Workshops',
        'Project Expo',
        'Paper Presentation',
        'Tech Fest',
        'Seminars'
    ],
    'Non-Technical': [
        'Dancing',
        'Singing',
        'Debate',
        'Photography',
        'Drawing & Painting',
        'Cultural Events',
        'Sports',
        'College Fest',
        'Quiz',
        'Student Activities'
    ]
}


def allowed_file(filename):
    """Check if uploaded file has a valid image extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_submitted_photo(file_obj, base64_str, prefix, user_id):
    """Safely save photo from either uploaded file or camera capture base64."""
    if base64_str and base64_str.startswith('data:image'):
        try:
            header, encoded = base64_str.split(',', 1)
            img_data = base64.b64decode(encoded)
            filename = f"{prefix}_{int(time.time())}_{user_id}.jpg"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            with open(filepath, 'wb') as f:
                f.write(img_data)
            return filename
        except Exception:
            pass
    if file_obj and hasattr(file_obj, 'filename') and file_obj.filename != '' and allowed_file(file_obj.filename):
        ext = secure_filename(file_obj.filename).rsplit('.', 1)[1].lower()
        filename = f"{prefix}_{int(time.time())}_{user_id}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file_obj.save(filepath)
        return filename
    return None



# ==============================================================================
# DATABASE HELPERS (SQLite)
# ==============================================================================
def get_db():
    """Open a new database connection for the current request context."""
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'], timeout=30.0)
        g.db.row_factory = sqlite3.Row  # Access columns by name like a dictionary
        g.db.execute("PRAGMA journal_mode=WAL;")
    return g.db


@app.template_filter('date_format')
def date_format(value):
    """Format date to YYYY-MM-DD safely."""
    if not value:
        return 'Recent'
    return str(value)[:10]


@app.template_filter('datetime_format')
def datetime_format(value):
    """Format timestamp to YYYY-MM-DD HH:MM safely."""
    if not value:
        return 'Recent'
    return str(value)[:16]


@app.template_filter('event_poster_url')
def event_poster_url(poster_filename):
    """
    Resolves the URL for an event poster.
    Prioritizes admin-uploaded or event-specific posters in static/uploads/events/,
    falls back to static/uploads/, and finally to static/uploads/events/event_default.jpg.
    """
    if not poster_filename:
        return url_for('static', filename='uploads/events/event_default.jpg')
    clean_name = os.path.basename(str(poster_filename).strip())
    # 1. Check in static/uploads/events/
    events_file = os.path.join(app.config.get('EVENT_UPLOAD_FOLDER', ''), clean_name)
    if os.path.isfile(events_file):
        return url_for('static', filename=f'uploads/events/{clean_name}')
    # 2. Check in static/uploads/
    uploads_file = os.path.join(app.config.get('UPLOAD_FOLDER', ''), clean_name)
    if os.path.isfile(uploads_file):
        return url_for('static', filename=f'uploads/{clean_name}')
    # 3. Default fallback
    return url_for('static', filename='uploads/events/event_default.jpg')

app.jinja_env.globals['event_poster_url'] = event_poster_url


@app.teardown_appcontext
def close_db(error):
    """Close the database connection at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Create tables if they don't already exist and seed initial demo data."""
    db = get_db()
    cursor = db.cursor()

    # 1. Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            roll_number TEXT,
            branch TEXT,
            year TEXT,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'student',
            profile_pic TEXT DEFAULT 'default_avatar.png',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Ensure profile columns and email verification exist on existing database
    for col, col_type in [
        ('roll_number', 'TEXT'),
        ('branch', 'TEXT'),
        ('year', 'TEXT'),
        ('email_verified', 'INTEGER DEFAULT 0')
    ]:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass

    # Ensure demo accounts have verified status
    cursor.execute("UPDATE users SET email_verified = 1 WHERE email IN ('rahul@stuhub.edu', 'admin@stuhub.edu')")

    # Email verifications tracking table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            attempts INTEGER DEFAULT 0,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. Lost Items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lost_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            location TEXT NOT NULL,
            date TEXT NOT NULL,
            contact_details TEXT NOT NULL,
            photo TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # 3. Found Items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS found_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            location TEXT NOT NULL,
            date TEXT NOT NULL,
            contact_details TEXT NOT NULL,
            photo TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # 4. Complaints table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL,
            photo TEXT,
            status TEXT DEFAULT 'Pending',
            date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    try:
        cursor.execute("ALTER TABLE complaints ADD COLUMN date TEXT")
    except sqlite3.OperationalError:
        pass

    # 5. Announcements table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            posted_by TEXT DEFAULT 'Campus Admin',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 6. Notifications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            type TEXT DEFAULT 'general',
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # 7. Campus Events table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            main_category TEXT NOT NULL,
            sub_category TEXT NOT NULL,
            description TEXT NOT NULL,
            poster TEXT DEFAULT 'event_default.jpg',
            event_date TEXT NOT NULL,
            event_time TEXT NOT NULL,
            venue TEXT NOT NULL,
            organized_by TEXT NOT NULL,
            eligibility TEXT DEFAULT 'Open to all students',
            reg_start_date TEXT,
            reg_end_date TEXT,
            total_seats INTEGER DEFAULT 100,
            fee INTEGER DEFAULT 0,
            contact_person TEXT,
            contact_email TEXT,
            contact_phone TEXT,
            status TEXT DEFAULT 'Open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 8. Event Registrations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            student_name TEXT NOT NULL,
            roll_number TEXT NOT NULL,
            branch TEXT NOT NULL,
            year TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            registration_id TEXT UNIQUE NOT NULL,
            payment_status TEXT DEFAULT 'Free',
            registration_status TEXT DEFAULT 'Confirmed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    db.commit()



def seed_demo_data():
    """Populate database with sample student, admin, lost/found items, complaints, and announcements."""
    db = get_db()
    cursor = db.cursor()

    # Check if users already exist
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        # Create default Admin
        admin_pass = generate_password_hash(os.environ.get('ADMIN_INITIAL_PASSWORD', 'admin123'))
        cursor.execute('''
            INSERT INTO users (name, roll_number, branch, year, email, phone, password_hash, role, profile_pic, email_verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', ('Campus Administrator', 'ADMIN01', 'Administration', 'Staff', 'admin@stuhub.edu', '9876500000', admin_pass, 'admin', 'default_avatar.png'))
        admin_id = cursor.lastrowid

        # Create demo Student
        student_pass = generate_password_hash(os.environ.get('STUDENT_INITIAL_PASSWORD', 'student123'))
        cursor.execute('''
            INSERT INTO users (name, roll_number, branch, year, email, phone, password_hash, role, profile_pic, email_verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', ('Rahul Sharma', '22CSE045', 'Computer Science & Engineering', '3rd Year', 'rahul@stuhub.edu', '9876543210', student_pass, 'student', 'default_avatar.png'))
        student_id = cursor.lastrowid

        # Seed sample Lost Items
        sample_lost = [
            (student_id, 'Scientific Calculator (Casio fx-991EX)', 'Calculator',
             'Black scientific calculator with name initial RS carved on back lid.',
             'Central Library, 2nd Floor, Desk 14', '2026-09-08', 'rahul@stuhub.edu / 9876543210', 'calculator.jpg'),
            (student_id, 'College ID Card & Lanyard', 'ID Card',
             'Blue CSE department lanyard with student ID card of Rahul Sharma (Roll 22CSE045).',
             'Campus Cafeteria, Counter 2', '2026-09-07', 'rahul@stuhub.edu / 9876543210', 'id_card.jpg'),
            (student_id, 'Data Structures Textbook', 'Books',
             'Standard textbook by Cormen (CLRS), paperback with yellow sticky notes inside.',
             'Main Auditorium, Row F', '2026-09-05', 'rahul@stuhub.edu / 9876543210', 'book.jpg')
        ]
        cursor.executemany('''
            INSERT INTO lost_items (user_id, item_name, category, description, location, date, contact_details, photo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_lost)

        # Seed sample Found Items
        sample_found = [
            (admin_id, 'Stainless Steel Water Bottle', 'Water Bottle',
             'Blue insulated Milton stainless steel bottle, 750ml, almost new.',
             'Near Seminar Hall A', '2026-09-08', 'Security Desk Ground Floor / security@stuhub.edu', 'water_bottle.jpg'),
            (admin_id, 'Wireless Bluetooth Earbuds', 'Headphones',
             'Black charging case with wireless earbuds found on lab bench.',
             'Computer Lab 3, Terminal 18', '2026-09-06', 'Lab Assistant desk / lab3@stuhub.edu', 'headphones.jpg')
        ]
        cursor.executemany('''
            INSERT INTO found_items (user_id, item_name, category, description, location, date, contact_details, photo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_found)

        # Seed sample Complaints
        sample_complaints = [
            (student_id, 'Fan', 'Ceiling fan is wobbling excessively and making high screeching noise during lectures.',
             'Classroom 302, 3rd Row Right Wing', 'fan_repair.jpg', 'In Progress'),
            (student_id, 'Washroom', 'Water tap in sink 2 is continuously dripping and causing drainage backup.',
             'Block B, Ground Floor Boys Washroom', 'washroom_tap.jpg', 'Pending'),
            (student_id, 'Light', 'Two central tube lights in reading section are flickering continuously.',
             'Central Library, Left Wing Reading Hall', 'light_fixture.jpg', 'Resolved')
        ]
        cursor.executemany('''
            INSERT INTO complaints (user_id, category, description, location, photo, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', sample_complaints)

        # Seed sample Announcements
        sample_announcements = [
            ('College Cultural Fest "Tarang 2026" Registration Open',
             'Registrations for music, dance, dramatics, and coding hackathon events are now live at the Student Welfare Office. Last date: September 25th.',
             'Student Welfare Committee'),
            ('Central Library Extended Timings for Mid-Term Exams',
             'The central reading halls will remain open until 10:00 PM starting next Monday to assist students during exam preparations.',
             'Chief Librarian'),
            ('Campus Cleanliness & Green Plantation Drive This Friday',
             'Join the NSS student volunteer team at 9:00 AM near the Main Quadrangle. Certificates and refreshments will be provided to all participants.',
             'NSS Coordinator')
        ]
        cursor.executemany('''
            INSERT INTO announcements (title, description, posted_by)
            VALUES (?, ?, ?)
        ''', sample_announcements)

        # Seed initial Notifications for student
        sample_notifications = [
            (student_id, 'Reported a Lost Item', 'You reported lost item: Scientific Calculator (Casio fx-991EX)', 'lost', 0),
            (student_id, 'Reported a Found Item', 'Campus security reported found item: Stainless Steel Water Bottle', 'found', 0),
            (student_id, 'New Complaint Reported', 'Complaint submitted for Fan in Classroom 302 (Status: In Progress)', 'complaint', 0),
            (student_id, 'New Announcement', 'College Cultural Fest "Tarang 2026" Registration Open', 'announcement', 0)
        ]
        cursor.executemany('''
            INSERT INTO notifications (user_id, title, message, type, is_read)
            VALUES (?, ?, ?, ?, ?)
        ''', sample_notifications)

        db.commit()
    else:
        # Update existing demo accounts with roll, branch, year and verified status
        cursor.execute('''
            UPDATE users SET roll_number = '22CSE045', branch = 'Computer Science & Engineering', year = '3rd Year', email_verified = 1
            WHERE email = 'rahul@stuhub.edu'
        ''')
        cursor.execute('''
            UPDATE users SET roll_number = 'ADMIN01', branch = 'Administration', year = 'Staff', email_verified = 1
            WHERE email = 'admin@stuhub.edu'
        ''')
        db.commit()

    # Ensure existing demo accounts always have email_verified enabled
    cursor.execute("UPDATE users SET email_verified = 1 WHERE email IN ('rahul@stuhub.edu', 'admin@stuhub.edu')")
    db.commit()

    # Update any legacy events to use Non-Technical main_category
    cursor.execute("UPDATE events SET main_category = 'Non-Technical' WHERE main_category = 'Student Activities'")
    db.commit()

    # Check if events count is low; seed full sample set if needed
    cursor.execute("SELECT COUNT(*) FROM events")
    if cursor.fetchone()[0] < 10:
        sample_events = [
            (
                'AI Innovation Hackathon',
                'Technical',
                'Hackathons',
                'Build groundbreaking artificial intelligence and machine learning solutions to solve real-world problems in 24 hours. Mentorship, cloud credits, and prizes up to ₹50,000 for top 3 teams!',
                'hackathon.jpg',
                '2026-09-25',
                '09:00 AM - 05:00 PM',
                'Campus Innovation & Incubation Center, Lab 5',
                'Department of Computer Science & AI Club',
                'Open to all UG/PG engineering students',
                '2026-09-10',
                '2026-09-24',
                80,
                0,
                'Dr. K. Srinivas',
                'hackathon@stuhub.edu',
                '9876501122',
                'Open'
            ),
            (
                'Code Sprint Challenge',
                'Technical',
                'Coding Competitions',
                'Speed coding contest testing data structures, algorithms, and logical problem solving. Individual participation with live automated judge and real-time leaderboard.',
                'code_sprint.jpg',
                '2026-09-28',
                '02:00 PM - 05:00 PM',
                'Turing Computer Center, Block C',
                'Coding & Algorithms Society',
                'All engineering students (1st to 4th year)',
                '2026-09-10',
                '2026-09-27',
                60,
                100,
                'Prof. Ananya Roy',
                'codesprint@stuhub.edu',
                '9876502233',
                'Open'
            ),
            (
                'Web Development Hands-on Workshop',
                'Technical',
                'Workshops',
                'Full-stack web application development masterclass covering HTML5, CSS3, Vanilla JavaScript, Flask, and API integrations with live project deployment.',
                'workshop.jpg',
                '2026-10-02',
                '10:00 AM - 04:00 PM',
                'Seminar Hall 2, Main Block',
                'Web Development Student Forum',
                'Beginner to Intermediate students',
                '2026-09-12',
                '2026-10-01',
                100,
                0,
                'Sameer Verma',
                'webdev@stuhub.edu',
                '9876503344',
                'Open'
            ),
            (
                'Technical Quiz Battle',
                'Technical',
                'Technical Quiz',
                'Fast-paced technical trivia testing computer science fundamentals, circuits, core engineering principles, and emerging tech revolutions.',
                'quiz_tech.jpg',
                '2026-10-05',
                '03:00 PM - 05:30 PM',
                'Auditorium Hall B',
                'Technical Quiz Society',
                'All Branches',
                '2026-09-15',
                '2026-10-04',
                50,
                50,
                'Dr. Preeti Nair',
                'techquiz@stuhub.edu',
                '9876503399',
                'Open'
            ),
            (
                'State Level Project Expo 2026',
                'Technical',
                'Project Expo',
                'Grand exhibition of final year hardware and software projects evaluated by prestigious industry jury members.',
                'project_expo.jpg',
                '2026-08-20',
                '09:30 AM - 04:30 PM',
                'Indoor Sports Complex',
                'Academic Affairs & Research Board',
                'All Final Year Engineering Teams',
                '2026-07-15',
                '2026-08-15',
                120,
                0,
                'Prof. V. Sharma',
                'expo@stuhub.edu',
                '9876503388',
                'Closed'
            ),
            (
                'National Paper Presentation Contest',
                'Technical',
                'Paper Presentation',
                'Symposium on original research papers in AI, IoT, Renewable Energy, and Smart Cities.',
                'paper_pres.jpg',
                '2026-08-15',
                '10:00 AM - 04:00 PM',
                'Seminar Hall 1',
                'IEEE Student Branch',
                'UG/PG Students',
                '2026-07-10',
                '2026-08-10',
                40,
                0,
                'Dr. S. K. Gupta',
                'ieee@stuhub.edu',
                '9876503377',
                'Closed'
            ),
            (
                'Annual Dance Fest "Rhythm 2026"',
                'Non-Technical',
                'Dancing',
                'Showcase your talent in solo, duet, and group dance across classical, western, hip-hop, and folk genres. Trophies and cash prizes for winners!',
                'dance.jpg',
                '2026-10-08',
                '05:00 PM - 09:30 PM',
                'Open Air Amphitheatre, Campus Quadrangle',
                'Cultural Activities Board',
                'All college students',
                '2026-09-12',
                '2026-10-06',
                50,
                150,
                'Pooja Reddy',
                'dancefest@stuhub.edu',
                '9876504455',
                'Open'
            ),
            (
                'Campus Singing Competition (Voice of Campus)',
                'Non-Technical',
                'Singing',
                'Annual inter-department vocal competition featuring Indian classical, light music, western pop, and band performances with celebrity judges.',
                'singing.jpg',
                '2026-10-12',
                '03:00 PM - 07:00 PM',
                'Central Auditorium, 1st Floor',
                'Music & Performing Arts Club',
                'All departments and branches',
                '2026-09-15',
                '2026-10-10',
                40,
                0,
                'Vikram Sen',
                'singing@stuhub.edu',
                '9876505566',
                'Open'
            ),
            (
                'Inter-College Debate Championship',
                'Non-Technical',
                'Debate',
                'Parliamentary style debate on contemporary topics including technological ethics, campus life, and global economics.',
                'debate.jpg',
                '2026-10-15',
                '11:00 AM - 03:30 PM',
                'Conference Hall A, Administrative Block',
                'Literary & Debating Society',
                'UG & PG students',
                '2026-09-15',
                '2026-10-14',
                30,
                0,
                'Neha Sharma',
                'debate@stuhub.edu',
                '9876506677',
                'Open'
            ),
            (
                'Photography Contest & Campus Exhibition',
                'Non-Technical',
                'Photography',
                'Theme: Campus Life & Shadows. Submit high-res digital photography for live gallery exhibition and judging.',
                'photography.jpg',
                '2026-10-18',
                '10:00 AM - 05:00 PM',
                'Art Gallery, Student Center',
                'Photography Club',
                'Open to all students',
                '2026-09-15',
                '2026-10-16',
                45,
                50,
                'Rohan Mehta',
                'photo@stuhub.edu',
                '9876506611',
                'Open'
            ),
            (
                'NSS Community Service & Cleanliness Drive',
                'Non-Technical',
                'Student Activities',
                'Campus and nearby community development initiative including tree plantation, digital literacy outreach, and hygiene awareness.',
                'nss.jpg',
                '2026-09-30',
                '08:30 AM - 01:00 PM',
                'Campus Main Gate Assembly Point',
                'National Service Scheme (NSS) Unit',
                'All students & NSS volunteers',
                '2026-09-10',
                '2026-09-29',
                120,
                0,
                'Prof. M. Ramesh (NSS Program Officer)',
                'nss@stuhub.edu',
                '9876507788',
                'Open'
            ),
            (
                'NCC Leadership & Adventure Camp',
                'Non-Technical',
                'Student Activities',
                'Physical endurance drills, map reading, obstacle courses, leadership development sessions, and first-aid training.',
                'ncc.jpg',
                '2026-10-20',
                '07:00 AM - 04:00 PM',
                'College Sports Ground & Parade Field',
                'NCC Cadet Corps Battalion',
                'NCC cadets and interested students',
                '2026-09-15',
                '2026-10-18',
                75,
                0,
                'Capt. Rajesh Kumar',
                'ncc@stuhub.edu',
                '9876508899',
                'Open'
            ),
            (
                'Drawing & Painting Carnival',
                'Non-Technical',
                'Drawing & Painting',
                'Creative canvas and water color painting workshop and contest on nature and futuristic visions.',
                'art_carnival.jpg',
                '2026-08-25',
                '02:00 PM - 05:00 PM',
                'Fine Arts Studio',
                'Fine Arts & Creative Club',
                'All students',
                '2026-08-01',
                '2026-08-24',
                50,
                0,
                'Anita Sen',
                'art@stuhub.edu',
                '9876506633',
                'Closed'
            ),
            (
                'General Campus Quiz 2026',
                'Non-Technical',
                'Quiz',
                'General knowledge, sports, cinema, literature, and current affairs quiz competition.',
                'quiz_general.jpg',
                '2026-08-10',
                '03:00 PM - 05:30 PM',
                'Auditorium Hall C',
                'Quiz Club',
                'All students',
                '2026-07-20',
                '2026-08-08',
                60,
                0,
                'Kunal Roy',
                'quiz@stuhub.edu',
                '9876506644',
                'Closed'
            )
        ]
        # Insert any that do not exist by title
        for evt in sample_events:
            cursor.execute("SELECT id FROM events WHERE title = ?", (evt[0],))
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO events (
                        title, main_category, sub_category, description, poster,
                        event_date, event_time, venue, organized_by, eligibility,
                        reg_start_date, reg_end_date, total_seats, fee,
                        contact_person, contact_email, contact_phone, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', evt)
        db.commit()



def create_notification(title, message, notif_type='general', user_id=None):
    """Create an in-app notification for a specific student or for all students."""
    db = get_db()
    cursor = db.cursor()

    if user_id is not None:
        cursor.execute('''
            INSERT INTO notifications (user_id, title, message, type, is_read)
            VALUES (?, ?, ?, ?, 0)
        ''', (user_id, title, message, notif_type))
    else:
        # Broadcast to all users
        cursor.execute("SELECT id FROM users")
        all_users = cursor.fetchall()
        for u in all_users:
            cursor.execute('''
                INSERT INTO notifications (user_id, title, message, type, is_read)
                VALUES (?, ?, ?, ?, 0)
            ''', (u['id'], title, message, notif_type))

    db.commit()


# ==============================================================================
# TEMPLATE CONTEXT PROCESSOR
# ==============================================================================
@app.context_processor
def inject_globals():
    """Inject current logged-in user details and unread notifications count into all templates."""
    user = None
    unread_count = 0

    if 'user_id' in session:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
        user = cursor.fetchone()

        if user:
            cursor.execute(
                "SELECT COUNT(*) FROM notifications WHERE (user_id = ? OR user_id IS NULL) AND is_read = 0",
                (session['user_id'],)
            )
            unread_count = cursor.fetchone()[0]

    return dict(current_user=user, unread_count=unread_count, current_year=datetime.now().year)


# ==============================================================================
# AUTHENTICATION DECORATORS
# ==============================================================================
def login_required(f):
    """Decorator to protect student & authenticated routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to protect admin-only routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in as Administrator to access this area.', 'warning')
            return redirect(url_for('login', next=request.path))
        if session.get('role') != 'admin':
            flash('Access denied. Administrator privileges required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


# ==============================================================================
# 1. WELCOME / COVER PAGE
# ==============================================================================
@app.route('/')
def index():
    """Welcome / Cover page: Hero display with 'Get Started' button."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


# ==============================================================================
# 2. AUTHENTICATION & EMAIL VERIFICATION (LOGIN / REGISTER / LOGOUT)
# ==============================================================================
@app.route('/api/send-verification-code', methods=['POST'])
def api_send_verification_code():
    """Generate and send a 6-digit verification code to student's college email."""
    data = request.get_json(silent=True) or request.form
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'success': False, 'message': 'Please enter your college email address.'}), 400

    # 1. Validate College Email Domain
    valid, domain_msg = is_allowed_college_domain(email)
    if not valid:
        return jsonify({'success': False, 'message': domain_msg}), 400

    db = get_db()
    cursor = db.cursor()

    # 2. Check if this email is already registered and verified
    cursor.execute("SELECT id, email_verified FROM users WHERE email = ?", (email,))
    existing_user = cursor.fetchone()
    if existing_user and existing_user['email_verified'] == 1:
        return jsonify({'success': False, 'message': 'An account with this college email already exists. Please login.'}), 400

    # 3. Rate limiting / Cooldown: 60 seconds
    last_sent = session.get('last_code_sent_at')
    now_ts = time.time()
    if last_sent and (now_ts - last_sent) < 60:
        remaining = int(60 - (now_ts - last_sent))
        return jsonify({
            'success': False,
            'message': f'Please wait {remaining} seconds before requesting a new code.',
            'cooldown_remaining': remaining
        }), 429

    # 4. Generate secure 6-digit verification code
    code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = datetime.now() + timedelta(minutes=10)

    # 5. Store in database
    cursor.execute('''
        INSERT INTO email_verifications (email, code, attempts, expires_at)
        VALUES (?, ?, 0, ?)
    ''', (email, code, expires_at.strftime('%Y-%m-%d %H:%M:%S')))
    db.commit()

    # 6. Store in session
    session['pending_verification_email'] = email
    session['verification_code'] = code
    session['code_expires_at'] = expires_at.timestamp()
    session['last_code_sent_at'] = now_ts
    session['code_attempts'] = 0

    # 7. Send code to college email (or log to dev console)
    _, sent_via_smtp = send_college_verification_email(email, code)

    res = {
        'success': True,
        'cooldown': 60
    }
    if sent_via_smtp:
        res['message'] = f'A 6-digit verification code has been sent to {email}. Valid for 10 minutes.'
    else:
        res['message'] = f'Demo Mode: Verification code generated: {code}. Enter this code below or use demo code 123456.'
        res['dev_code'] = code
        res['demo_mode'] = True

    return jsonify(res), 200


@app.route('/api/verify-code', methods=['POST'])
def api_verify_code():
    """Verify the 6-digit code entered by student."""
    data = request.get_json(silent=True) or request.form
    email = data.get('email', '').strip().lower()
    code = data.get('code', '').strip()

    if not email or not code:
        return jsonify({'success': False, 'message': 'Please enter both your college email and the 6-digit verification code.'}), 400

    db = get_db()
    cursor = db.cursor()

    cursor.execute('''
        SELECT * FROM email_verifications 
        WHERE email = ? 
        ORDER BY id DESC LIMIT 1
    ''', (email,))
    record = cursor.fetchone()

    if not record:
        return jsonify({'success': False, 'message': 'No verification code was requested for this email. Please click "Send Verification Code".'}), 400

    # Check and increment attempts (max 5)
    new_attempts = record['attempts'] + 1
    cursor.execute("UPDATE email_verifications SET attempts = ? WHERE id = ?", (new_attempts, record['id']))
    db.commit()

    if new_attempts > 5:
        return jsonify({'success': False, 'message': 'Maximum attempts exceeded. Please request a new verification code.'}), 400

    # Check expiration (10 minutes)
    try:
        exp_time = datetime.strptime(record['expires_at'], '%Y-%m-%d %H:%M:%S')
    except Exception:
        exp_time = datetime.now() - timedelta(seconds=1)

    if datetime.now() > exp_time:
        return jsonify({'success': False, 'message': 'Verification Code Expired. Please request a new code.'}), 400

    # Constant-time comparison (accept generated code or demo fallback 123456 when SMTP is not configured)
    has_smtp = bool(MAIL_SERVER and MAIL_USERNAME and MAIL_PASSWORD)
    is_valid = secrets.compare_digest(record['code'], code)
    if not is_valid and (not has_smtp or app.config.get('TESTING')) and code == '123456':
        is_valid = True

    if not is_valid:
        return jsonify({'success': False, 'message': 'Invalid Verification Code. Please check and re-enter.'}), 400

    # Success: mark email as verified
    session['verified_college_email'] = email
    session.pop('verification_code', None)

    # If an existing user account exists with this email, update their verified status
    cursor.execute("UPDATE users SET email_verified = 1 WHERE email = ?", (email,))
    db.commit()

    return jsonify({
        'success': True,
        'message': 'Email Verified Successfully! You can now complete your registration.'
    }), 200


@app.route('/verify-email', methods=['GET', 'POST'])
def verify_email():
    """Dedicated page for unverified users to verify college email address."""
    email = request.args.get('email', '').strip().lower()
    has_smtp = bool(MAIL_SERVER and MAIL_USERNAME and MAIL_PASSWORD)
    demo_code = None

    if not has_smtp:
        demo_code = session.get('verification_code')
        if not demo_code and email:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT code FROM email_verifications WHERE email = ? AND datetime('now') <= datetime(expires_at) ORDER BY id DESC LIMIT 1", (email,))
            row = cursor.fetchone()
            if row:
                demo_code = row['code']

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        code = request.form.get('code', '').strip()
        action = request.form.get('action')

        if action == 'resend':
            valid, msg = is_allowed_college_domain(email)
            if not valid:
                flash(msg, 'danger')
            else:
                code_gen = f"{secrets.randbelow(900000) + 100000}"
                expires_at = datetime.now() + timedelta(minutes=10)
                db = get_db()
                db.cursor().execute('''
                    INSERT INTO email_verifications (email, code, attempts, expires_at)
                    VALUES (?, ?, 0, ?)
                ''', (email, code_gen, expires_at.strftime('%Y-%m-%d %H:%M:%S')))
                db.commit()
                _, sent_via_smtp = send_college_verification_email(email, code_gen)
                session['verification_code'] = code_gen
                demo_code = code_gen
                if sent_via_smtp:
                    flash(f'A fresh verification code has been sent to {email}.', 'info')
                else:
                    flash(f'Demo Mode: Verification code generated: {code_gen}. Enter this code below or use demo code 123456.', 'info')
        elif action == 'verify':
            if not code:
                flash('Please enter the 6-digit verification code.', 'danger')
            else:
                db = get_db()
                cursor = db.cursor()
                cursor.execute("SELECT * FROM email_verifications WHERE email = ? ORDER BY id DESC LIMIT 1", (email,))
                rec = cursor.fetchone()
                
                is_valid = False
                if rec:
                    try:
                        exp_time = datetime.strptime(rec['expires_at'], '%Y-%m-%d %H:%M:%S')
                    except Exception:
                        exp_time = datetime.now() - timedelta(seconds=1)

                    if datetime.now() > exp_time:
                        flash('Verification Code Expired. Please request a new code.', 'danger')
                        return render_template('verify_email.html', email=email, demo_code=demo_code, has_smtp=has_smtp)
                    
                    if secrets.compare_digest(rec['code'], code):
                        is_valid = True

                # Allow safe demo fallback 123456 when SMTP is not configured
                if not is_valid and (not has_smtp or app.config.get('TESTING')) and code == '123456':
                    is_valid = True

                if not is_valid:
                    flash('Invalid Verification Code. For demo testing without SMTP, you can use the code displayed above or 123456.', 'danger')
                else:
                    cursor.execute("UPDATE users SET email_verified = 1 WHERE email = ?", (email,))
                    db.commit()
                    session['verified_college_email'] = email
                    session.pop('verification_code', None)
                    flash('College Email Verified Successfully! You can now log in.', 'success')
                    return redirect(url_for('login'))

    return render_template('verify_email.html', email=email, demo_code=demo_code, has_smtp=has_smtp)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login with separate Student Login and Admin Login options, enforcing strict RBAC."""
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin'))
        return redirect(url_for('dashboard'))

    unverified_email = None
    active_tab = request.args.get('mode', 'student').strip().lower()
    if active_tab not in ('student', 'admin'):
        active_tab = 'student'

    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '').strip()
        login_type = request.form.get('login_type', 'student').strip().lower()
        if login_type not in ('student', 'admin'):
            login_type = 'student'
        active_tab = login_type

        if not identifier or not password:
            flash('Please enter your credentials and password.', 'danger')
            return render_template('login.html', active_tab=active_tab, identifier=identifier)

        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE email = ? OR name = ?",
            (identifier, identifier)
        )
        user = cursor.fetchone()

        if user and check_password_hash(user['password_hash'], password):
            # Check if attempting Admin Login
            if login_type == 'admin':
                if user['role'] != 'admin':
                    flash('Access Denied: This account does not have administrator privileges. Please use Student Login.', 'danger')
                    return render_template('login.html', active_tab='admin', identifier=identifier)

                session['user_id'] = user['id']
                session['user_name'] = user['name']
                session['user_email'] = user['email']
                session['role'] = user['role']
                flash('Welcome, Admin! Access granted to Campus Administration Dashboard.', 'success')
                return redirect(url_for('admin'))

            # Attempting Student Login
            if user['role'] == 'admin':
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                session['user_email'] = user['email']
                session['role'] = user['role']
                flash('Administrator logged in. Redirected to Admin Dashboard.', 'info')
                return redirect(url_for('admin'))

            # Check if college email is verified for student
            # The existing demo student account is explicitly exempt from the email verification requirement
            demo_student_email = os.environ.get('DEMO_STUDENT_EMAIL', 'rahul@stuhub.edu').strip().lower()
            is_demo_student = (user['email'].strip().lower() == demo_student_email)

            if is_demo_student:
                # Ensure demo student is permanently marked verified in database
                if user['email_verified'] == 0:
                    cursor.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (user['id'],))
                    db.commit()
            elif user['email_verified'] == 0:
                # Normal student registration retains strict email verification
                flash('Please verify your college email before logging in.', 'warning')
                return render_template('login.html', unverified_email=user['email'], active_tab='student')

            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            session['role'] = user['role']

            flash(f'Welcome back, {user["name"]}!', 'success')
            next_url = request.args.get('next')
            if next_url and next_url.startswith('/') and not next_url.startswith('/admin'):
                return redirect(next_url)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid college email or password. Please try again.', 'danger')
            return render_template('login.html', active_tab=active_tab, identifier=identifier)

    return render_template('login.html', unverified_email=unverified_email, active_tab=active_tab)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Register a new student account requiring official college email verification."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        roll_number = request.form.get('roll_number', '').strip()
        branch = request.form.get('branch', '').strip()
        year = request.form.get('year', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        # Basic validations
        if not name or not email or not password:
            flash('Name, College Email, and Password are required fields.', 'danger')
            return render_template('register.html')

        # 1. Enforce College Email Domain
        valid_domain, domain_err = is_allowed_college_domain(email)
        if not valid_domain:
            flash(domain_err, 'danger')
            return render_template('register.html')

        if len(password) < 4:
            flash('Password must be at least 4 characters long.', 'danger')
            return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match. Please re-enter.', 'danger')
            return render_template('register.html')

        db = get_db()
        cursor = db.cursor()

        # Check if email is already taken
        cursor.execute("SELECT id, email_verified FROM users WHERE email = ?", (email,))
        existing = cursor.fetchone()
        if existing and existing['email_verified'] == 1:
            flash('An account with this college email already exists. Please login.', 'warning')
            return redirect(url_for('login'))

        # 2. Enforce Email Verification
        is_verified = (session.get('verified_college_email') == email)
        if not is_verified:
            # Check if there is an unexpired verified code in email_verifications table
            cursor.execute('''
                SELECT * FROM email_verifications 
                WHERE email = ? AND datetime('now') <= datetime(expires_at)
                ORDER BY id DESC LIMIT 1
            ''', (email,))
            rec = cursor.fetchone()
            # If testing or direct verification was done:
            if not is_verified:
                flash('Please verify your college email address with the 6-digit code before completing registration.', 'danger')
                return render_template('register.html')

        # Create new verified student account
        password_hash = generate_password_hash(password)
        cursor.execute('''
            INSERT INTO users (name, roll_number, branch, year, email, phone, password_hash, role, profile_pic, email_verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'student', 'default_avatar.png', 1)
        ''', (name, roll_number, branch, year, email, phone, password_hash))
        db.commit()

        new_user_id = cursor.lastrowid

        # Clean session verification marker
        session.pop('verified_college_email', None)

        # Automatically log in the registered student
        session['user_id'] = new_user_id
        session['user_name'] = name
        session['user_email'] = email
        session['role'] = 'student'

        # Send welcome in-app notification
        create_notification(
            title='Welcome to StuHub!',
            message=f'Hello {name}, your college email has been verified and your account is active.',
            notif_type='general',
            user_id=new_user_id
        )

        flash('Registration successful! Your college email has been verified. Welcome to StuHub!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('register.html')


@app.route('/logout')
def logout():
    """Clear session and log user out."""
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))


# ==============================================================================
# 3. DASHBOARD & RECENT ACTIVITY
# ==============================================================================
@app.route('/dashboard')
@login_required
def dashboard():
    """Main student dashboard displaying feature cards and recent campus activity."""
    if session.get('role') == 'admin':
        return redirect(url_for('admin'))

    db = get_db()
    cursor = db.cursor()
    user_id = session['user_id']

    # Counts for student summary
    cursor.execute("SELECT COUNT(*) FROM lost_items WHERE user_id = ?", (user_id,))
    my_lost_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM found_items WHERE user_id = ?", (user_id,))
    my_found_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE user_id = ?", (user_id,))
    my_complaints_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM announcements")
    total_announcements = cursor.fetchone()[0]

    # JUST YOUR ACTIVITY: STRICTLY for the currently logged-in student (WHERE user_id = ?)
    your_activity = []

    cursor.execute("SELECT item_name, category, created_at FROM lost_items WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user_id,))
    for r in cursor.fetchall():
        your_activity.append({
            'type': 'lost',
            'icon': '👜',
            'badge': 'Lost Item',
            'title': f"You reported a lost item: {r['item_name']}",
            'detail': f"Category: {r['category']}",
            'date': r['created_at']
        })

    cursor.execute("SELECT item_name, category, created_at FROM found_items WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user_id,))
    for r in cursor.fetchall():
        your_activity.append({
            'type': 'found',
            'icon': '🔍',
            'badge': 'Found Item',
            'title': f"You reported a found item: {r['item_name']}",
            'detail': f"Category: {r['category']}",
            'date': r['created_at']
        })

    cursor.execute("SELECT category, location, status, created_at FROM complaints WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user_id,))
    for r in cursor.fetchall():
        your_activity.append({
            'type': 'complaint',
            'icon': '🔧',
            'badge': 'Complaint',
            'title': f"You raised a complaint: {r['category']}",
            'detail': f"Location: {r['location']} • Status: {r['status']}",
            'date': r['created_at']
        })

    # Recent Event Registrations for this student
    cursor.execute('''
        SELECT er.registration_id, er.created_at, e.title
        FROM event_registrations er
        JOIN events e ON er.event_id = e.id
        WHERE er.user_id = ?
        ORDER BY er.id DESC LIMIT 5
    ''', (user_id,))
    for r in cursor.fetchall():
        your_activity.append({
            'type': 'event',
            'icon': '🎟️',
            'badge': 'Event Registration',
            'title': f"You registered for an event: {r['title']}",
            'detail': f"Registration ID: {r['registration_id']}",
            'date': r['created_at']
        })

    # Sort personal activity by date descending
    your_activity.sort(key=lambda x: str(x['date']), reverse=True)
    recent_activity = your_activity[:8]

    # Upcoming Campus Events (calculated dynamically from current date)
    cursor.execute('''
        SELECT * FROM events 
        WHERE event_date >= date('now') 
        ORDER BY event_date ASC 
        LIMIT 3
    ''')
    upcoming_events = cursor.fetchall()
    if not upcoming_events:
        cursor.execute("SELECT * FROM events ORDER BY id DESC LIMIT 3")
        upcoming_events = cursor.fetchall()

    # Latest Official Announcements
    cursor.execute("SELECT * FROM announcements ORDER BY id DESC LIMIT 3")
    latest_announcements = cursor.fetchall()

    # Count student's registered events
    cursor.execute('SELECT COUNT(*) FROM event_registrations WHERE user_id = ?', (user_id,))
    my_registrations_count = cursor.fetchone()[0]

    return render_template(
        'dashboard.html',
        my_lost_count=my_lost_count,
        my_found_count=my_found_count,
        my_complaints_count=my_complaints_count,
        my_registrations_count=my_registrations_count,
        total_announcements=total_announcements,
        recent_activity=recent_activity,
        your_activity=recent_activity,
        upcoming_events=upcoming_events,
        latest_announcements=latest_announcements
    )


# ==============================================================================
# 5. REPORT LOST ITEM
# ==============================================================================
@app.route('/lost', methods=['GET', 'POST'])
@app.route('/lost-item', methods=['GET', 'POST'])
@login_required
def report_lost_item():
    """Report a lost item on campus."""
    categories = ['ID Card', 'Calculator', 'Books', 'Headphones', 'Water Bottle', 'Electronics', 'Notebook', 'Other']

    if request.method == 'POST':
        item_name = request.form.get('item_name', '').strip()
        category = request.form.get('category', '').strip()
        description = request.form.get('description', '').strip()
        location = request.form.get('location', '').strip()
        date = request.form.get('date', '').strip()
        contact_details = request.form.get('contact_details', '').strip()

        if not item_name or not category or not location or not date or not contact_details:
            flash('Please fill in all required fields.', 'danger')
            return render_template('lost.html', categories=categories)

        # Handle photo (either uploaded file or camera capture base64)
        camera_photo = request.form.get('camera_photo')
        file_obj = request.files.get('photo')
        photo_filename = save_submitted_photo(file_obj, camera_photo, 'lost', session['user_id'])

        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            INSERT INTO lost_items (user_id, item_name, category, description, location, date, contact_details, photo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], item_name, category, description, location, date, contact_details, photo_filename))
        db.commit()

        # In-app notification
        create_notification(
            title='Reported a Lost Item',
            message=f'You reported a lost item: {item_name} at {location}.',
            notif_type='lost',
            user_id=session['user_id']
        )

        flash('Lost Item Reported Successfully', 'success')
        return redirect(url_for('search', type='lost'))

    return render_template('lost.html', categories=categories)


# ==============================================================================
# 6. REPORT FOUND ITEM
# ==============================================================================
@app.route('/found', methods=['GET', 'POST'])
@app.route('/found-item', methods=['GET', 'POST'])
@login_required
def report_found_item():
    """Report a found item on campus."""
    categories = ['ID Card', 'Calculator', 'Books', 'Headphones', 'Water Bottle', 'Electronics', 'Notebook', 'Other']

    if request.method == 'POST':
        item_name = request.form.get('item_name', '').strip()
        category = request.form.get('category', '').strip()
        description = request.form.get('description', '').strip()
        location = request.form.get('location', '').strip()
        date = request.form.get('date', '').strip()
        contact_details = request.form.get('contact_details', '').strip()

        if not item_name or not category or not location or not date or not contact_details:
            flash('Please fill in all required fields.', 'danger')
            return render_template('found.html', categories=categories)

        # Handle photo (either uploaded file or camera capture base64)
        camera_photo = request.form.get('camera_photo')
        file_obj = request.files.get('photo')
        photo_filename = save_submitted_photo(file_obj, camera_photo, 'found', session['user_id'])

        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            INSERT INTO found_items (user_id, item_name, category, description, location, date, contact_details, photo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], item_name, category, description, location, date, contact_details, photo_filename))
        db.commit()

        # In-app notification
        create_notification(
            title='Reported a Found Item',
            message=f'You reported a found item: {item_name} at {location}. Thank you for helping!',
            notif_type='found',
            user_id=session['user_id']
        )

        flash('Found Item Reported Successfully', 'success')
        return redirect(url_for('search', type='found'))

    return render_template('found.html', categories=categories)


# ==============================================================================
# 7. SEARCH LOST & FOUND ITEMS
# ==============================================================================
@app.route('/search')
@login_required
def search():
    """Search and filter reported Lost and Found items."""
    query = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    item_type = request.args.get('type', 'all').strip().lower()  # 'all', 'lost', 'found'

    categories = ['All', 'ID Card', 'Calculator', 'Books', 'Headphones', 'Water Bottle', 'Electronics', 'Other']

    db = get_db()
    cursor = db.cursor()

    items = []

    # Query Lost items if type is 'all' or 'lost'
    if item_type in ('all', 'lost'):
        sql = "SELECT id, item_name, category, description, location, date, contact_details, photo, created_at, 'Lost' AS item_type FROM lost_items WHERE 1=1"
        params = []

        if query:
            sql += " AND (item_name LIKE ? OR description LIKE ? OR location LIKE ?)"
            params.extend([f'%{query}%', f'%{query}%', f'%{query}%'])

        if category and category != 'All':
            sql += " AND category = ?"
            params.append(category)

        sql += " ORDER BY id DESC"
        cursor.execute(sql, params)
        items.extend([dict(r) for r in cursor.fetchall()])

    # Query Found items if type is 'all' or 'found'
    if item_type in ('all', 'found'):
        sql = "SELECT id, item_name, category, description, location, date, contact_details, photo, created_at, 'Found' AS item_type FROM found_items WHERE 1=1"
        params = []

        if query:
            sql += " AND (item_name LIKE ? OR description LIKE ? OR location LIKE ?)"
            params.extend([f'%{query}%', f'%{query}%', f'%{query}%'])

        if category and category != 'All':
            sql += " AND category = ?"
            params.append(category)

        sql += " ORDER BY id DESC"
        cursor.execute(sql, params)
        items.extend([dict(r) for r in cursor.fetchall()])

    # Sort combined results by creation date
    items.sort(key=lambda x: str(x['created_at']), reverse=True)

    return render_template(
        'search.html',
        items=items,
        query=query,
        selected_category=category,
        selected_type=item_type,
        categories=categories
    )


# ==============================================================================
# 8. CAMPUS COMPLAINTS (SUBMIT)
# ==============================================================================
@app.route('/complaints', methods=['GET', 'POST'])
@login_required
def complaints():
    """Submit a new campus facility complaint."""
    categories = ['Classroom', 'Fan', 'Light', 'Washroom', 'Water', 'Electricity', 'Benches', 'Cleanliness', 'Other']

    if request.method == 'POST':
        category = request.form.get('category', '').strip()
        location = request.form.get('location', '').strip()
        description = request.form.get('description', '').strip()
        date_reported = request.form.get('date', '').strip() or datetime.now().strftime('%Y-%m-%d')

        if not category or not location or not description:
            flash('Please fill in all required complaint details.', 'danger')
            return render_template('complaints.html', categories=categories)

        # Handle photo (either uploaded file or camera capture base64)
        camera_photo = request.form.get('camera_photo')
        file_obj = request.files.get('photo')
        photo_filename = save_submitted_photo(file_obj, camera_photo, 'complaint', session['user_id'])

        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            INSERT INTO complaints (user_id, category, description, location, photo, status, date)
            VALUES (?, ?, ?, ?, ?, 'Pending', ?)
        ''', (session['user_id'], category, description, location, photo_filename, date_reported))
        db.commit()

        # In-app notification
        create_notification(
            title='New Complaint Reported',
            message=f'Your complaint for {category} at {location} has been registered with status "Pending".',
            notif_type='complaint',
            user_id=session['user_id']
        )

        flash('Complaint Submitted Successfully', 'success')
        return redirect(url_for('my_complaints'))

    return render_template('complaints.html', categories=categories)


# ==============================================================================
# 9. MY COMPLAINTS STATUS
# ==============================================================================
@app.route('/my-complaints')
@login_required
def my_complaints():
    """View complaints submitted by the logged-in student and track status."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        SELECT * FROM complaints
        WHERE user_id = ?
        ORDER BY id DESC
    ''', (session['user_id'],))
    complaints_list = cursor.fetchall()

    return render_template('my_complaints.html', complaints=complaints_list)


# ==============================================================================
# 10. ANNOUNCEMENTS
# ==============================================================================
@app.route('/announcements')
@login_required
def announcements():
    """View official campus announcements."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM announcements ORDER BY id DESC")
    announcements_list = cursor.fetchall()

    return render_template('announcements.html', announcements=announcements_list)


# ==============================================================================
# 11. IN-APP NOTIFICATIONS
# ==============================================================================
@app.route('/notifications')
@login_required
def notifications():
    """View in-app notifications with newest first."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        SELECT * FROM notifications
        WHERE user_id = ? OR user_id IS NULL
        ORDER BY id DESC
    ''', (session['user_id'],))
    notif_list = cursor.fetchall()

    return render_template('notifications.html', notifications=notif_list)


@app.route('/notifications/read/<int:notif_id>', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    """Mark a single notification as read."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        UPDATE notifications SET is_read = 1
        WHERE id = ? AND (user_id = ? OR user_id IS NULL)
    ''', (notif_id, session['user_id']))
    db.commit()

    flash('Notification marked as read.', 'info')
    return redirect(url_for('notifications'))


@app.route('/notifications/read-all', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all notifications as read for current user."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        UPDATE notifications SET is_read = 1
        WHERE user_id = ? OR user_id IS NULL
    ''', (session['user_id'],))
    db.commit()

    flash('All notifications marked as read.', 'success')
    return redirect(url_for('notifications'))


# ==============================================================================
# 12. MY PROFILE
# ==============================================================================
@app.route('/profile')
@login_required
def profile():
    """View student profile and activity statistics."""
    db = get_db()
    cursor = db.cursor()
    user_id = session['user_id']

    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()

    # Statistics
    cursor.execute("SELECT COUNT(*) FROM lost_items WHERE user_id = ?", (user_id,))
    lost_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM found_items WHERE user_id = ?", (user_id,))
    found_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE user_id = ?", (user_id,))
    complaints_count = cursor.fetchone()[0]

    stats = {
        'lost_count': lost_count,
        'found_count': found_count,
        'complaints_count': complaints_count
    }

    return render_template('profile.html', user=user, stats=stats)


@app.route('/profile/edit', methods=['POST'])
@login_required
def edit_profile():
    """Update student profile details and photo."""
    name = request.form.get('name', '').strip()
    roll_number = request.form.get('roll_number', '').strip()
    branch = request.form.get('branch', '').strip()
    year = request.form.get('year', '').strip()
    phone = request.form.get('phone', '').strip()
    new_password = request.form.get('new_password', '').strip()

    if not name:
        flash('Name cannot be empty.', 'danger')
        return redirect(url_for('profile'))

    db = get_db()
    cursor = db.cursor()
    user_id = session['user_id']

    # Handle optional avatar upload
    if 'profile_pic' in request.files:
        file = request.files['profile_pic']
        if file and file.filename != '' and allowed_file(file.filename):
            ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
            pic_filename = f"avatar_{int(time.time())}_{user_id}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], pic_filename))
            cursor.execute("UPDATE users SET profile_pic = ? WHERE id = ?", (pic_filename, user_id))

    # Update profile fields
    cursor.execute('''
        UPDATE users 
        SET name = ?, roll_number = ?, branch = ?, year = ?, phone = ? 
        WHERE id = ?
    ''', (name, roll_number, branch, year, phone, user_id))
    session['user_name'] = name

    # Update password if provided
    if new_password:
        if len(new_password) < 4:
            flash('Password must be at least 4 characters.', 'warning')
        else:
            new_hash = generate_password_hash(new_password)
            cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))

    db.commit()
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('profile'))


# ==============================================================================
# ==============================================================================
# 13. ADMIN DASHBOARD & DEDICATED PORTALS
# ==============================================================================
@app.route('/admin')
@admin_required
def admin():
    """Admin Home Page: displays ONLY the 4 main options in a clean 2x2 grid."""
    return render_template('admin.html')


@app.route('/admin/announcements', methods=['GET', 'POST'])
@admin_required
def admin_announcements():
    """Dedicated Announcements Management Portal for Admin."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM announcements ORDER BY id DESC")
    announcements_list = cursor.fetchall()
    return render_template('admin_announcements.html', announcements=announcements_list)


@app.route('/admin/complaints')
@admin_required
def admin_complaints():
    """Dedicated Complaints Management Portal for Admin."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        SELECT c.*, u.name AS student_name, u.email AS student_email
        FROM complaints c
        JOIN users u ON c.user_id = u.id
        ORDER BY c.id DESC
    ''')
    complaints_list = cursor.fetchall()
    return render_template('admin_complaints.html', complaints=complaints_list)


@app.route('/admin/students')
@admin_required
def admin_students():
    """Dedicated Registered Students Directory for Admin."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT id, name, email, phone, roll_number, branch, year, email_verified, created_at 
        FROM users 
        WHERE role = 'student' 
        ORDER BY id DESC
    """)
    students = cursor.fetchall()
    return render_template('admin_students.html', students=students)


@app.route('/admin/complaint/status/<int:complaint_id>', methods=['POST'])
@app.route('/admin/complaint/update/<int:complaint_id>', methods=['POST'])
@admin_required
def update_complaint_status(complaint_id):
    """Admin: change complaint status (Pending -> In Progress -> Resolved)."""
    new_status = request.form.get('status', '').strip()
    if new_status not in ('Pending', 'In Progress', 'Resolved'):
        flash('Invalid status choice.', 'danger')
        return redirect(request.referrer or url_for('admin_complaints'))

    db = get_db()
    cursor = db.cursor()

    # Get complaint details
    cursor.execute("SELECT user_id, category, location FROM complaints WHERE id = ?", (complaint_id,))
    complaint = cursor.fetchone()

    if complaint:
        cursor.execute("UPDATE complaints SET status = ? WHERE id = ?", (new_status, complaint_id))
        db.commit()

        # Notify the student about status change
        create_notification(
            title='Complaint Status Updated',
            message=f"Your complaint for {complaint['category']} at {complaint['location']} is now marked as '{new_status}'.",
            notif_type='complaint',
            user_id=complaint['user_id']
        )
        flash(f'Complaint #{complaint_id} status changed to {new_status}.', 'success')
    else:
        flash('Complaint not found.', 'danger')

    return redirect(request.referrer or url_for('admin_complaints'))


@app.route('/admin/announcement/add', methods=['POST'])
@admin_required
def add_announcement():
    """Admin: publish a new campus announcement and broadcast in-app notification."""
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    priority = request.form.get('priority', 'Normal').strip()
    is_important = 1 if priority == 'Important' else 0
    posted_by = request.form.get('posted_by', '').strip() or 'Campus Administration'

    if not title or not description:
        flash('Announcement title and description are required.', 'danger')
        return redirect(request.referrer or url_for('admin_announcements'))

    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        INSERT INTO announcements (title, description, posted_by, priority, is_important)
        VALUES (?, ?, ?, ?, ?)
    ''', (title, description, posted_by, priority, is_important))
    db.commit()

    # Broadcast notification to all students
    create_notification(
        title='New Announcement',
        message=f"{title}: {description[:90]}...",
        notif_type='announcement',
        user_id=None
    )

    flash('New announcement broadcasted successfully to all students!', 'success')
    return redirect(request.referrer or url_for('admin_announcements'))


@app.route('/admin/announcement/edit/<int:announcement_id>', methods=['POST'])
@admin_required
def admin_edit_announcement(announcement_id):
    """Admin edit an existing announcement."""
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    priority = request.form.get('priority', 'Normal').strip()
    is_important = 1 if priority == 'Important' else 0

    if not title or not description:
        flash('Title and description are required.', 'danger')
        return redirect(request.referrer or url_for('admin_announcements'))

    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        UPDATE announcements
        SET title = ?, description = ?, priority = ?, is_important = ?
        WHERE id = ?
    ''', (title, description, priority, is_important, announcement_id))
    db.commit()

    flash(f'Announcement #{announcement_id} updated successfully.', 'success')
    return redirect(request.referrer or url_for('admin_announcements'))


@app.route('/admin/item/delete/<string:item_type>/<int:item_id>', methods=['POST'])
@admin_required
def delete_item(item_type, item_id):
    """Admin: delete inappropriate report from lost_items or found_items."""
    db = get_db()
    cursor = db.cursor()

    if item_type == 'lost':
        cursor.execute("DELETE FROM lost_items WHERE id = ?", (item_id,))
        db.commit()
        flash(f'Lost item #{item_id} deleted successfully.', 'info')
    elif item_type == 'found':
        cursor.execute("DELETE FROM found_items WHERE id = ?", (item_id,))
        db.commit()
        flash(f'Found item #{item_id} deleted successfully.', 'info')
    elif item_type == 'complaint':
        cursor.execute("DELETE FROM complaints WHERE id = ?", (item_id,))
        db.commit()
        flash(f'Complaint #{item_id} deleted successfully.', 'info')
    elif item_type == 'announcement':
        cursor.execute("DELETE FROM announcements WHERE id = ?", (item_id,))
        db.commit()
        flash(f'Announcement #{item_id} deleted.', 'info')
    else:
        flash('Invalid item type.', 'danger')

    ref = request.referrer
    if ref:
        return redirect(ref)
    if item_type == 'complaint':
        return redirect(url_for('admin_complaints'))
    elif item_type == 'announcement':
        return redirect(url_for('admin_announcements'))
    return redirect(url_for('admin'))


# ==============================================================================
# 14. CAMPUS EVENTS MODULE (TECHNICAL, NON-TECHNICAL, STUDENT ACTIVITIES)
# ==============================================================================
def get_event_seats_left(event_id, total_seats):
    """Calculate remaining available seats for an event."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        SELECT COUNT(*) FROM event_registrations
        WHERE event_id = ? AND registration_status = 'Confirmed'
    ''', (event_id,))
    taken = cursor.fetchone()[0]
    return max(0, total_seats - taken)


@app.route('/events')
@login_required
def campus_events():
    """Campus Events Directory: Show 2 primary options (Technical / Non-Technical) or filtered event streams."""
    category = request.args.get('category', '').strip() or request.args.get('type', '').strip()
    sub_category = request.args.get('sub_category', '').strip()
    query = request.args.get('q', '').strip()
    view = request.args.get('view', '').strip().lower()  # 'upcoming', 'past', or ''

    # If no category, search query, or specific view is requested, FIRST show the 2 options (Technical vs Non-Technical)
    show_two_options = bool(not category and not sub_category and not query and not view)

    db = get_db()
    cursor = db.cursor()

    sql = "SELECT * FROM events WHERE 1=1"
    params = []

    if category and category != 'All':
        sql += " AND main_category = ?"
        params.append(category)

    if sub_category and sub_category != 'All':
        sql += " AND sub_category = ?"
        params.append(sub_category)

    if query:
        sql += " AND (title LIKE ? OR description LIKE ? OR venue LIKE ? OR sub_category LIKE ?)"
        params.extend([f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%'])

    sql += " ORDER BY event_date ASC, id DESC"
    cursor.execute(sql, params)
    raw_events = cursor.fetchall()

    events_list = []
    user_id = session.get('user_id')
    today_str = datetime.now().strftime('%Y-%m-%d')

    for e in raw_events:
        event_dict = dict(e)
        event_dict['seats_left'] = get_event_seats_left(e['id'], e['total_seats'])
        event_dict['is_past'] = bool(e['event_date'] and str(e['event_date'])[:10] < today_str)

        # Check if current student is already registered
        cursor.execute('''
            SELECT id FROM event_registrations
            WHERE event_id = ? AND user_id = ? AND registration_status = 'Confirmed'
        ''', (e['id'], user_id))
        event_dict['is_registered'] = bool(cursor.fetchone())
        events_list.append(event_dict)

    upcoming_events = [e for e in events_list if not e['is_past']]
    past_events = [e for e in events_list if e['is_past']]

    # Filter by specific view if requested (e.g. /events/upcoming or /events/past)
    if view == 'upcoming':
        events_list = upcoming_events
    elif view == 'past':
        events_list = past_events

    # Sub-categories for current category
    sub_categories = []
    if category in EVENT_CATEGORIES:
        sub_categories = EVENT_CATEGORIES[category]
    else:
        for subs in EVENT_CATEGORIES.values():
            sub_categories.extend(subs)

    # Count stats for the two primary cards
    cursor.execute("SELECT COUNT(*) FROM events WHERE main_category = 'Technical'")
    technical_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM events WHERE main_category = 'Non-Technical'")
    non_technical_count = cursor.fetchone()[0]

    return render_template(
        'events.html',
        events=events_list,
        upcoming_events=upcoming_events,
        past_events=past_events,
        selected_category=category,
        selected_sub_category=sub_category,
        query=query,
        view=view,
        today_str=today_str,
        show_two_options=show_two_options,
        technical_count=technical_count,
        non_technical_count=non_technical_count,
        event_categories=EVENT_CATEGORIES,
        available_sub_categories=sub_categories
    )


@app.route('/events/technical')
@login_required
def events_technical():
    """Direct route for Technical events stream."""
    return redirect(url_for('campus_events', category='Technical'))


@app.route('/events/non-technical')
@login_required
def events_non_technical():
    """Direct route for Non-Technical events stream."""
    return redirect(url_for('campus_events', category='Non-Technical'))


@app.route('/events/upcoming')
@login_required
def events_upcoming():
    """Direct route for all Upcoming events."""
    return redirect(url_for('campus_events', view='upcoming'))


@app.route('/events/past')
@login_required
def events_past():
    """Direct route for all Past events."""
    return redirect(url_for('campus_events', view='past'))


@app.route('/events/<int:event_id>')
@login_required
def event_details(event_id):
    """Detailed view for a specific campus event."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    event = cursor.fetchone()

    if not event:
        flash('Event not found.', 'danger')
        return redirect(url_for('campus_events'))

    seats_left = get_event_seats_left(event['id'], event['total_seats'])

    # Check if student is already registered
    cursor.execute('''
        SELECT * FROM event_registrations
        WHERE event_id = ? AND user_id = ? AND registration_status = 'Confirmed'
    ''', (event_id, session['user_id']))
    existing_reg = cursor.fetchone()

    return render_template(
        'event_details.html',
        event=event,
        seats_left=seats_left,
        existing_reg=existing_reg
    )


@app.route('/events/<int:event_id>/register', methods=['GET', 'POST'])
@app.route('/register-event/<int:event_id>', methods=['GET', 'POST'])
@login_required
def event_register(event_id):
    """Student event registration form and submission."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    event = cursor.fetchone()

    if not event:
        flash('Event not found.', 'danger')
        return redirect(url_for('campus_events'))

    if event['status'] != 'Open':
        flash('Registration for this event is currently closed.', 'warning')
        return redirect(url_for('event_details', event_id=event_id))

    seats_left = get_event_seats_left(event['id'], event['total_seats'])
    if seats_left <= 0:
        flash('Sorry, this event is already fully booked!', 'warning')
        return redirect(url_for('event_details', event_id=event_id))

    # Check if already registered
    cursor.execute('''
        SELECT id, registration_id FROM event_registrations
        WHERE event_id = ? AND user_id = ? AND registration_status = 'Confirmed'
    ''', (event_id, session['user_id']))
    already_reg = cursor.fetchone()
    if already_reg:
        flash('You are already registered for this event.', 'info')
        return redirect(url_for('event_confirmation', reg_id=already_reg['registration_id']))

    # Fetch user details to pre-fill
    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()

    if request.method == 'POST':
        student_name = request.form.get('student_name', '').strip()
        roll_number = request.form.get('roll_number', '').strip()
        branch = request.form.get('branch', '').strip()
        year = request.form.get('year', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()

        if not student_name or not roll_number or not branch or not year or not email or not phone:
            flash('Please fill in all registration fields.', 'danger')
            return render_template('register_event.html', event=event, user=user, seats_left=seats_left)

        # If FREE EVENT:
        if event['fee'] == 0:
            reg_id = f"REG-EVT{event_id}-{secrets.token_hex(3).upper()}"
            cursor.execute('''
                INSERT INTO event_registrations (
                    event_id, user_id, student_name, roll_number,
                    branch, year, email, phone, registration_id,
                    payment_status, registration_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Free', 'Confirmed')
            ''', (event_id, session['user_id'], student_name, roll_number, branch, year, email, phone, reg_id))
            db.commit()

            # In-app notification
            create_notification(
                title='Event Registration Confirmed',
                message=f"You have successfully registered for '{event['title']}'! Reg ID: {reg_id}",
                notif_type='general',
                user_id=session['user_id']
            )

            flash('Registration Successful! Your seat has been reserved.', 'success')
            return redirect(url_for('event_confirmation', reg_id=reg_id))

        # If PAID EVENT:
        else:
            session['temp_event_reg'] = {
                'event_id': event_id,
                'student_name': student_name,
                'roll_number': roll_number,
                'branch': branch,
                'year': year,
                'email': email,
                'phone': phone,
                'fee': event['fee']
            }
            return redirect(url_for('event_payment', event_id=event_id))

    return render_template('register_event.html', event=event, user=user, seats_left=seats_left)


@app.route('/events/<int:event_id>/payment', methods=['GET', 'POST'])
@login_required
def event_payment(event_id):
    """Demo payment gateway page for paid event registrations."""
    temp_reg = session.get('temp_event_reg')
    if not temp_reg or temp_reg.get('event_id') != event_id:
        flash('Please fill out the registration form first.', 'warning')
        return redirect(url_for('event_register', event_id=event_id))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    event = cursor.fetchone()

    if not event:
        flash('Event not found.', 'danger')
        return redirect(url_for('campus_events'))

    if request.method == 'POST':
        reg_id = f"PAID-EVT{event_id}-{secrets.token_hex(3).upper()}"
        cursor.execute('''
            INSERT INTO event_registrations (
                event_id, user_id, student_name, roll_number,
                branch, year, email, phone, registration_id,
                payment_status, registration_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Confirmed')
        ''', (
            event_id,
            session['user_id'],
            temp_reg['student_name'],
            temp_reg['roll_number'],
            temp_reg['branch'],
            temp_reg['year'],
            temp_reg['email'],
            temp_reg['phone'],
            reg_id,
            f"Paid (₹{event['fee']})"
        ))
        db.commit()

        # Clean session
        session.pop('temp_event_reg', None)

        # In-app notification
        create_notification(
            title='Event Registration Confirmed',
            message=f"Payment Successful (₹{event['fee']})! Registered for '{event['title']}'. Reg ID: {reg_id}",
            notif_type='general',
            user_id=session['user_id']
        )

        flash('Payment Successful! Registration Confirmed.', 'success')
        return redirect(url_for('event_confirmation', reg_id=reg_id))

    return render_template('event_payment.html', event=event, reg=temp_reg)


@app.route('/events/confirmation/<string:reg_id>')
@login_required
def event_confirmation(reg_id):
    """Registration confirmation receipt page."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        SELECT r.*, e.title AS event_title, e.event_date, e.event_time, e.venue, e.organized_by, e.fee
        FROM event_registrations r
        JOIN events e ON r.event_id = e.id
        WHERE r.registration_id = ?
    ''', (reg_id,))
    reg = cursor.fetchone()

    if not reg:
        flash('Registration record not found.', 'danger')
        return redirect(url_for('campus_events'))

    return render_template('event_confirmation.html', reg=reg)


@app.route('/events/my-registrations')
@login_required
def my_event_registrations():
    """View events registered by the logged-in student."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        SELECT r.*, e.title AS event_title, e.main_category, e.sub_category,
               e.event_date, e.event_time, e.venue, e.poster
        FROM event_registrations r
        JOIN events e ON r.event_id = e.id
        WHERE r.user_id = ?
        ORDER BY r.id DESC
    ''', (session['user_id'],))
    registrations = cursor.fetchall()

    return render_template('my_registrations.html', registrations=registrations)


# ==============================================================================
# ADMIN CAMPUS EVENTS PORTAL & MANAGEMENT
# ==============================================================================
@app.route('/admin/events')
@admin_required
def admin_events_portal():
    """
    Dedicated Admin Events Portal:
    Consolidates event creation, event management, and complete student registration tracking.
    Divides events into Upcoming Events and Past Events.
    """
    db = get_db()
    cursor = db.cursor()

    today_str = datetime.now().strftime('%Y-%m-%d')

    cursor.execute("SELECT * FROM events ORDER BY event_date ASC, id DESC")
    all_events = cursor.fetchall()

    upcoming_events = []
    past_events = []

    total_seats_sum = 0
    total_registrations_sum = 0

    for ev in all_events:
        ev_dict = dict(ev)
        cursor.execute("SELECT COUNT(*) FROM event_registrations WHERE event_id = ? AND registration_status = 'Confirmed'", (ev['id'],))
        reg_count = cursor.fetchone()[0]
        ev_dict['registered_count'] = reg_count
        ev_dict['available_seats'] = max(0, ev['total_seats'] - reg_count)
        
        total_seats_sum += ev['total_seats']
        total_registrations_sum += reg_count

        if ev['event_date'] and str(ev['event_date']) < today_str:
            past_events.append(ev_dict)
        else:
            upcoming_events.append(ev_dict)

    # Sort past events most recent first
    past_events.sort(key=lambda x: str(x['event_date']), reverse=True)

    stats = {
        'total_events': len(all_events),
        'upcoming_count': len(upcoming_events),
        'past_count': len(past_events),
        'total_registrations': total_registrations_sum,
        'total_capacity': total_seats_sum
    }

    return render_template(
        'admin_events_portal.html',
        upcoming_events=upcoming_events,
        past_events=past_events,
        stats=stats
    )


@app.route('/admin/events/add', methods=['GET', 'POST'])
@app.route('/admin/events/new', methods=['GET', 'POST'])
@admin_required
def admin_add_event():
    """Admin: create a new campus event."""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        main_category = request.form.get('main_category', '').strip()
        sub_category = request.form.get('sub_category', '').strip()
        description = request.form.get('description', '').strip()
        event_date = request.form.get('event_date', '').strip()
        event_time = request.form.get('event_time', '').strip()
        venue = request.form.get('venue', '').strip()
        organized_by = request.form.get('organized_by', '').strip()
        eligibility = request.form.get('eligibility', 'Open to all students').strip()
        reg_start_date = request.form.get('reg_start_date', '').strip()
        reg_end_date = request.form.get('reg_end_date', '').strip()
        total_seats = int(request.form.get('total_seats', 100))
        fee = int(request.form.get('fee', 0))
        contact_person = request.form.get('contact_person', '').strip()
        contact_email = request.form.get('contact_email', '').strip()
        contact_phone = request.form.get('contact_phone', '').strip()
        status = request.form.get('status', 'Open').strip()

        if not title or not main_category or not sub_category or not event_date or not venue:
            flash('Please fill in all mandatory event details.', 'danger')
            return render_template('admin_event_form.html', event=None, categories=EVENT_CATEGORIES)

        poster_filename = 'event_default.jpg'
        if 'poster' in request.files:
            file = request.files['poster']
            if file and file.filename != '' and allowed_file(file.filename):
                ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
                poster_filename = f"event_{int(time.time())}.{ext}"
                event_dest = os.path.join(app.config['EVENT_UPLOAD_FOLDER'], poster_filename)
                file.save(event_dest)
                try:
                    import shutil
                    shutil.copy(event_dest, os.path.join(app.config['UPLOAD_FOLDER'], poster_filename))
                except Exception:
                    pass

        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            INSERT INTO events (
                title, main_category, sub_category, description, poster,
                event_date, event_time, venue, organized_by, eligibility,
                reg_start_date, reg_end_date, total_seats, fee,
                contact_person, contact_email, contact_phone, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            title, main_category, sub_category, description, poster_filename,
            event_date, event_time, venue, organized_by, eligibility,
            reg_start_date, reg_end_date, total_seats, fee,
            contact_person, contact_email, contact_phone, status
        ))
        db.commit()

        # In-app notification to all students
        create_notification(
            title='New Event Added',
            message=f"New event '{title}' under {main_category} ({sub_category}) is now open for registration!",
            notif_type='general',
            user_id=None
        )

        flash('Campus Event published successfully!', 'success')
        return redirect(url_for('admin_events_portal'))

    return render_template('admin_event_form.html', event=None, categories=EVENT_CATEGORIES)


@app.route('/admin/events/edit/<int:event_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_event(event_id):
    """Admin: edit an existing campus event."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    event = cursor.fetchone()

    if not event:
        flash('Event not found.', 'danger')
        return redirect(url_for('admin_events_portal'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        main_category = request.form.get('main_category', '').strip()
        sub_category = request.form.get('sub_category', '').strip()
        description = request.form.get('description', '').strip()
        event_date = request.form.get('event_date', '').strip()
        event_time = request.form.get('event_time', '').strip()
        venue = request.form.get('venue', '').strip()
        organized_by = request.form.get('organized_by', '').strip()
        eligibility = request.form.get('eligibility', 'Open to all students').strip()
        reg_start_date = request.form.get('reg_start_date', '').strip()
        reg_end_date = request.form.get('reg_end_date', '').strip()
        total_seats = int(request.form.get('total_seats', 100))
        fee = int(request.form.get('fee', 0))
        contact_person = request.form.get('contact_person', '').strip()
        contact_email = request.form.get('contact_email', '').strip()
        contact_phone = request.form.get('contact_phone', '').strip()
        status = request.form.get('status', 'Open').strip()

        poster_filename = event['poster']
        if 'poster' in request.files:
            file = request.files['poster']
            if file and file.filename != '' and allowed_file(file.filename):
                ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
                poster_filename = f"event_{int(time.time())}.{ext}"
                event_dest = os.path.join(app.config['EVENT_UPLOAD_FOLDER'], poster_filename)
                file.save(event_dest)
                try:
                    import shutil
                    shutil.copy(event_dest, os.path.join(app.config['UPLOAD_FOLDER'], poster_filename))
                except Exception:
                    pass

        cursor.execute('''
            UPDATE events SET
                title = ?, main_category = ?, sub_category = ?, description = ?,
                poster = ?, event_date = ?, event_time = ?, venue = ?,
                organized_by = ?, eligibility = ?, reg_start_date = ?,
                reg_end_date = ?, total_seats = ?, fee = ?, contact_person = ?,
                contact_email = ?, contact_phone = ?, status = ?
            WHERE id = ?
        ''', (
            title, main_category, sub_category, description, poster_filename,
            event_date, event_time, venue, organized_by, eligibility,
            reg_start_date, reg_end_date, total_seats, fee,
            contact_person, contact_email, contact_phone, status, event_id
        ))
        db.commit()

        flash(f"Event '{title}' updated successfully!", 'success')
        return redirect(url_for('admin_events_portal'))

    return render_template('admin_event_form.html', event=event, categories=EVENT_CATEGORIES)


@app.route('/admin/events/delete/<int:event_id>', methods=['POST'])
@admin_required
def admin_delete_event(event_id):
    """Admin: delete a campus event."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
    db.commit()
    flash('Event deleted successfully.', 'info')
    return redirect(request.referrer or url_for('admin_events_portal'))


@app.route('/admin/events/toggle-status/<int:event_id>', methods=['POST'])
@admin_required
def admin_toggle_event_status(event_id):
    """Admin: toggle Open / Closed registration status."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, title, status FROM events WHERE id = ?", (event_id,))
    event = cursor.fetchone()

    if event:
        new_status = 'Closed' if event['status'] == 'Open' else 'Open'
        cursor.execute("UPDATE events SET status = ? WHERE id = ?", (new_status, event_id))
        db.commit()

        if new_status == 'Closed':
            create_notification(
                title='Event Registration Closed',
                message=f"Registration for '{event['title']}' has been closed.",
                notif_type='general',
                user_id=None
            )

        flash(f"Event '{event['title']}' registration status set to {new_status}.", 'info')
    return redirect(request.referrer or url_for('admin_events_portal'))


@app.route('/admin/events/<int:event_id>/registrations')
@admin_required
def admin_event_registrations(event_id):
    """
    Admin: View complete student information and registrations for a specific event (or all events).
    Displays student name, roll number, branch, year, college email, phone, event name,
    registration ID, date, payment status, and registration status.
    Protected strictly for Admin users.
    """
    db = get_db()
    cursor = db.cursor()

    # Query all events for the filter dropdown
    cursor.execute("SELECT id, title FROM events ORDER BY title ASC")
    all_events_list = cursor.fetchall()

    if event_id == 0:
        event = {
            'id': 0,
            'title': 'All Campus Events',
            'main_category': 'All Categories',
            'sub_category': 'All Streams',
            'event_date': 'All Dates',
            'venue': 'All Venues',
            'total_seats': sum(e['total_seats'] for e in all_events_list) if all_events_list else 0,
            'fee': 0
        }
        cursor.execute('''
            SELECT r.*, e.title AS event_title, e.main_category, e.sub_category, e.event_date, e.venue
            FROM event_registrations r
            JOIN events e ON r.event_id = e.id
            ORDER BY r.id DESC
        ''')
        registrations = cursor.fetchall()
    else:
        cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        event = cursor.fetchone()

        if not event:
            flash('Event not found.', 'danger')
            return redirect(url_for('admin_events_portal'))

        cursor.execute('''
            SELECT r.*, e.title AS event_title, e.main_category, e.sub_category, e.event_date, e.venue
            FROM event_registrations r
            JOIN events e ON r.event_id = e.id
            WHERE r.event_id = ?
            ORDER BY r.id DESC
        ''', (event_id,))
        registrations = cursor.fetchall()

    return render_template(
        'admin_event_registrations.html',
        event=event,
        registrations=registrations,
        all_events_list=all_events_list,
        total_registered=len(registrations)
    )



# ==============================================================================
# APPLICATION BOOTSTRAP
# ==============================================================================
with app.app_context():
    init_db()
    seed_demo_data()

if __name__ == '__main__':
    # Bind to 0.0.0.0 and dynamic port for Render and production deployment
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", 10000))
    app.run(host=host, port=port, debug=False)

