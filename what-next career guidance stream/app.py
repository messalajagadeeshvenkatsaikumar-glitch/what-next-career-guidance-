import json
import logging
import os
import sys
from functools import wraps
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
from flask import (Flask, render_template, request, redirect, url_for,
                    session, flash, g, send_file, jsonify)
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from mysql.connector import Error

from db import connect_db, is_connected
from question_management import question_management_bp
from question_management.services import ensure_seed_data, get_published_questions, score_and_record

load_dotenv(BASE_DIR / ".env")

from config import Config

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

app = Flask(__name__)
app.config.from_object(Config)


def parse_allowed_origins(raw_value):
    if not raw_value:
        return ['http://localhost:5000']
    return [item.strip() for item in raw_value.split(',') if item.strip()]


allowed_origins = parse_allowed_origins(app.config.get('CORS_ALLOWED_ORIGINS') or app.config.get('MAIN_SITE_URL'))
CORS(
    app,
    resources={
        r'/api/*': {'origins': allowed_origins},
        r'/health': {'origins': allowed_origins},
        r'/admin/*': {'origins': allowed_origins},
    },
    supports_credentials=True,
)

app.register_blueprint(question_management_bp)
app.extensions["main_db"] = lambda: get_db()


@app.errorhandler(Exception)
def handle_exception(error):
    app.logger.exception('Unhandled application error: %s', error)
    if hasattr(error, 'code') and error.code in {404, 405}:
        return error
    return "An internal server error occurred.", 500


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = connect_db()
        app.logger.info("Connected to MySQL database: %s", app.config["MYSQL_DATABASE"])
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        schema_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "database.sql"))
        with open(schema_path, "r", encoding="utf-8") as f:
            for statement in f.read().split(";"):
                statement = statement.strip()
                if statement:
                    db.execute(statement)
        db.commit()
        ensure_seed_data(db, CAREER_DATA)


@app.before_request
def ensure_app_database():
    if request.path.startswith('/health') or request.path.startswith('/static'):
        return None
    if not app.config.get("DB_INITIALIZED"):
        try:
            init_db()
            app.config["DB_INITIALIZED"] = True
        except Exception:
            app.logger.exception("Database initialization failed during request handling.")
            return jsonify({"status": "error", "database": "disconnected"}), 503


def get_admin_db():
    return get_db()


def init_admin_db():
    with app.app_context():
        db = get_db()
        db.execute("""CREATE TABLE IF NOT EXISTS admins (
            id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            full_name VARCHAR(150),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB""")
        db.commit()

# ---------------------------------------------------------------------------
# Career data: categories, courses, colleges, jobs, roadmap
# ---------------------------------------------------------------------------

CAREER_DATA = {
    "Engineering & Technology": {
        "blurb": "You enjoy solving problems logically and building things. "
                 "A path in engineering, software, or applied technology "
                 "could suit you well.",
        "courses": [
            "B.Tech / B.E. in Computer Science, Electronics, or Mechanical Engineering",
            "B.Sc. in Computer Science or Information Technology",
            "Diploma in Engineering (Polytechnic)",
            "BCA (Bachelor of Computer Applications)",
        ],
        "colleges": [
            "Indian Institutes of Technology (IITs)",
            "National Institutes of Technology (NITs)",
            "State Engineering Colleges / Government Polytechnics",
            "Private Technical Universities (e.g., VIT, SRM, Manipal)",
        ],
        "jobs": [
            "Software Engineer / Developer",
            "Data Analyst / Data Scientist",
            "Electronics or Mechanical Engineer",
            "Systems Administrator / DevOps Engineer",
            "Product Engineer",
        ],
        "roadmap": [
            "Class 11-12: Take Science stream with Mathematics (PCM).",
            "Prepare for entrance exams (JEE, state CETs) or aptitude-based admissions.",
            "Complete a 3-4 year engineering or computing degree.",
            "Build projects, do internships, and learn in-demand tools during college.",
            "Consider specialization or a Master's degree for advanced roles.",
        ],
    },
    "Medical & Healthcare": {
        "blurb": "You're drawn to helping people and have an interest in "
                 "biology and health sciences. Medicine or allied health "
                 "fields may be a great fit.",
        "courses": [
            "MBBS (Bachelor of Medicine and Surgery)",
            "BDS (Dental Surgery)",
            "B.Sc. Nursing",
            "B.Pharm (Pharmacy)",
            "BPT (Physiotherapy) / Allied Health Sciences",
        ],
        "colleges": [
            "Government Medical Colleges",
            "AIIMS and other central institutes",
            "State Nursing and Pharmacy Colleges",
            "Private Medical & Health Science Universities",
        ],
        "jobs": [
            "Doctor / Physician (after MBBS + specialization)",
            "Nurse / Nurse Practitioner",
            "Pharmacist",
            "Physiotherapist",
            "Medical Lab Technologist",
        ],
        "roadmap": [
            "Class 11-12: Take Science stream with Biology (PCB).",
            "Prepare for entrance exams (NEET or equivalent).",
            "Complete the required medical/health science degree.",
            "Undergo mandatory internship/residency where applicable.",
            "Pursue specialization or licensing exams for advanced practice.",
        ],
    },
    "Commerce & Business": {
        "blurb": "You think in numbers, enjoy organizing and strategizing, "
                 "and are interested in how businesses and money work. "
                 "Commerce, finance, or management could be your path.",
        "courses": [
            "B.Com (Bachelor of Commerce)",
            "BBA (Bachelor of Business Administration)",
            "CA / CS / CMA (professional accounting & finance courses)",
            "BBA-LLB or other business-law combined degrees",
        ],
        "colleges": [
            "Commerce Colleges affiliated with major universities",
            "Institutes offering CA/CS/CMA programs",
            "Business Schools offering integrated BBA programs",
        ],
        "jobs": [
            "Accountant / Chartered Accountant",
            "Financial Analyst",
            "Business Manager / Entrepreneur",
            "Marketing Executive",
            "Investment Banking Analyst",
        ],
        "roadmap": [
            "Class 11-12: Take Commerce stream (with or without Maths).",
            "Pursue a bachelor's degree in Commerce, Business, or a professional course (CA/CS/CMA).",
            "Gain internships in finance, accounting, or business operations.",
            "Consider an MBA or professional certification for leadership roles.",
            "Build practical skills in analytics, Excel, and financial tools.",
        ],
    },
    "Arts & Humanities": {
        "blurb": "You're curious about people, society, culture, and ideas. "
                 "A career in humanities, social science, law, or public "
                 "policy could be rewarding for you.",
        "courses": [
            "BA in History, Political Science, Psychology, Sociology, or Economics",
            "BA LLB (Integrated Law)",
            "Bachelor of Social Work (BSW)",
            "Journalism & Mass Communication",
        ],
        "colleges": [
            "Arts & Humanities Colleges at major universities",
            "National Law Universities (for law aspirants)",
            "Institutes of Mass Communication and Journalism",
        ],
        "jobs": [
            "Lawyer / Legal Advisor",
            "Journalist / Content Writer",
            "Psychologist / Counselor",
            "Civil Services Officer",
            "Social Worker / Policy Researcher",
        ],
        "roadmap": [
            "Class 11-12: Take Arts/Humanities stream.",
            "Pursue a BA or integrated law degree aligned with your interest.",
            "Explore internships in NGOs, media houses, or law firms.",
            "Consider a Master's degree or competitive exams (UPSC, judiciary, etc.).",
            "Build strong writing, research, and communication skills.",
        ],
    },
    "Creative & Design": {
        "blurb": "You express yourself best through visuals, design, or "
                 "storytelling. A creative career in design, media, or the "
                 "arts could let your imagination thrive.",
        "courses": [
            "B.Des (Bachelor of Design) — Fashion, Product, or Communication Design",
            "BFA (Bachelor of Fine Arts)",
            "Animation & Multimedia courses",
            "Film making / Mass Media programs",
        ],
        "colleges": [
            "National Institute of Design (NID) and similar design schools",
            "Fine Arts Colleges",
            "Film and Television Institutes",
            "Private Design & Media Institutes",
        ],
        "jobs": [
            "Graphic Designer / UI-UX Designer",
            "Animator / Illustrator",
            "Fashion Designer",
            "Film Maker / Video Editor",
            "Art Director",
        ],
        "roadmap": [
            "Class 11-12: Any stream, though Arts is common; build a portfolio early.",
            "Prepare for design entrance exams (UCEED, NID DAT, etc.) if applicable.",
            "Pursue a design, fine arts, or media degree.",
            "Build a strong personal portfolio through projects and internships.",
            "Keep learning new tools (design software, animation, editing).",
        ],
    },
    "Government & Public Service": {
        "blurb": "You care about public welfare, order, and structured "
                 "responsibility. Government services, defense, or public "
                 "administration roles may suit you.",
        "courses": [
            "Any Bachelor's degree (BA/B.Com/B.Sc.) as a base for competitive exams",
            "Public Administration programs",
            "National Defence Academy (NDA) pathway after Class 12",
        ],
        "colleges": [
            "Any recognized university for a bachelor's degree",
            "Institutes offering Public Administration",
            "Defence training academies (NDA, OTA)",
        ],
        "jobs": [
            "Civil Services Officer (IAS/IPS/IFS equivalent)",
            "Defence Officer",
            "Public Sector Undertaking (PSU) Officer",
            "Police Services",
            "Government Policy Analyst",
        ],
        "roadmap": [
            "Class 11-12: Any stream; focus on general knowledge and current affairs.",
            "Complete a bachelor's degree in any discipline.",
            "Prepare systematically for competitive exams (UPSC, state PSC, NDA, etc.).",
            "Consider coaching or self-study with mock tests.",
            "Build discipline, communication, and leadership skills.",
        ],
    },
}

# Each question maps to a category it scores points for.
QUIZ_QUESTIONS = [
    {"id": 1, "text": "I enjoy solving mathematical or logical puzzles.", "category": "Engineering & Technology"},
    {"id": 2, "text": "I like understanding how machines, gadgets, or software work.", "category": "Engineering & Technology"},
    {"id": 3, "text": "I would enjoy building or coding something from scratch.", "category": "Engineering & Technology"},
    {"id": 4, "text": "I'm interested in biology and how the human body works.", "category": "Medical & Healthcare"},
    {"id": 5, "text": "I feel fulfilled when I help someone who is unwell or in distress.", "category": "Medical & Healthcare"},
    {"id": 6, "text": "I can stay calm and focused in high-pressure situations.", "category": "Medical & Healthcare"},
    {"id": 7, "text": "I enjoy working with numbers, budgets, or financial planning.", "category": "Commerce & Business"},
    {"id": 8, "text": "I like the idea of starting or managing a business.", "category": "Commerce & Business"},
    {"id": 9, "text": "I'm curious about markets, trade, or investments.", "category": "Commerce & Business"},
    {"id": 10, "text": "I enjoy reading about history, society, or human behavior.", "category": "Arts & Humanities"},
    {"id": 11, "text": "I like debating ideas and forming well-reasoned arguments.", "category": "Arts & Humanities"},
    {"id": 12, "text": "I'm interested in law, justice, or social issues.", "category": "Arts & Humanities"},
    {"id": 13, "text": "I express myself well through drawing, design, or writing creatively.", "category": "Creative & Design"},
    {"id": 14, "text": "I notice and appreciate aesthetics, color, and visual composition.", "category": "Creative & Design"},
    {"id": 15, "text": "I enjoy imagining and creating original stories or designs.", "category": "Creative & Design"},
    {"id": 16, "text": "I feel a strong sense of duty toward public service or the nation.", "category": "Government & Public Service"},
    {"id": 17, "text": "I'm comfortable with discipline, structure, and following procedures.", "category": "Government & Public Service"},
    {"id": 18, "text": "I would like a career that involves serving or leading communities.", "category": "Government & Public Service"},
    {"id": 19, "text": "Basic logic puzzle: I enjoy finding the next number in a simple sequence.", "category": "Engineering & Technology"},
    {"id": 20, "text": "Basic logic puzzle: I can quickly identify patterns in shapes, letters, or symbols.", "category": "Engineering & Technology"},
    {"id": 21, "text": "Basic logic puzzle: I like solving simple ordering and matching problems.", "category": "Engineering & Technology"},
    {"id": 22, "text": "Basic logic puzzle: I enjoy working out which statement must be true from a few clues.", "category": "Engineering & Technology"},
    {"id": 23, "text": "Basic logic puzzle: I can spot the odd item out and explain why it does not belong.", "category": "Engineering & Technology"},
    {"id": 24, "text": "Basic logic puzzle: I enjoy using a simple process of elimination to reach an answer.", "category": "Engineering & Technology"},
    {"id": 25, "text": "Medium logic puzzle: I enjoy solving multi-step deduction problems with several clues.", "category": "Engineering & Technology"},
    {"id": 26, "text": "Medium logic puzzle: I can compare different possibilities and remove the ones that cannot work.", "category": "Engineering & Technology"},
    {"id": 27, "text": "Medium logic puzzle: I like reasoning through seating, scheduling, or arrangement problems.", "category": "Engineering & Technology"},
    {"id": 28, "text": "Medium logic puzzle: I enjoy finding hidden rules in number or symbol patterns.", "category": "Engineering & Technology"},
    {"id": 29, "text": "Medium logic puzzle: I can connect several pieces of information to reach a logical conclusion.", "category": "Engineering & Technology"},
    {"id": 30, "text": "Medium logic puzzle: I enjoy puzzles that require planning more than one step ahead.", "category": "Engineering & Technology"},
]


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Admin login required.", "warning")
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route('/health')
def health():
    try:
        connected = is_connected()
    except (Error, KeyError, OSError, ValueError) as error:
        app.logger.warning('Health check failed: %s', safe_error_message(error))
        connected = False
    if connected:
        return jsonify({"status": "ok", "database": "connected"}), 200
    app.logger.warning('Health check failed: MySQL database not reachable.')
    return jsonify({"status": "error", "database": "disconnected"}), 503


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()

        if not name or not email or not message:
            flash("Please fill in all required fields.", "danger")
            return redirect(url_for("contact"))

        try:
            db = get_db()
            db.execute(
                "INSERT INTO contact_messages (name, email, subject, message) "
                "VALUES (%s, %s, %s, %s)",
                (name, email, subject, message),
            )
            db.commit()
            app.logger.info('Saved contact message for %s <%s>', name, email)
        except Error:
            if 'db' in locals():
                db.rollback()
            app.logger.exception('Failed to insert contact message for %s <%s>', name, email)
            flash("Unable to send your message right now. Please try again later.", "danger")
            return redirect(url_for("contact"))

        flash("Thanks for reaching out! We'll get back to you soon.", "success")
        return redirect(url_for("contact"))

    return render_template("contact.html")


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        age = request.form.get("age") or None
        education_level = request.form.get("education_level", "").strip()

        if not full_name or not email or not password:
            flash("Please fill in all required fields.", "danger")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("register"))

        try:
            db = get_db()
            existing = db.execute(
                "SELECT id FROM users WHERE email = %s", (email,)
            ).fetchone()
            if existing:
                flash("An account with that email already exists.", "danger")
                return redirect(url_for("register"))

            password_hash = generate_password_hash(password)
            db.execute(
                "INSERT INTO users (full_name, email, password_hash, age, education_level) "
                "VALUES (%s, %s, %s, %s, %s)",
                (full_name, email, password_hash, age, education_level),
            )
            db.commit()
            app.logger.info('Registered user %s <%s>', full_name, email)
        except Error:
            if 'db' in locals():
                db.rollback()
            app.logger.exception('Failed to create user %s <%s>', full_name, email)
            flash("Unable to create your account right now. Please try again later.", "danger")
            return redirect(url_for("register"))

        flash("Account created! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email = %s", (email,)
        ).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))

        session.clear()
        session["user_id"] = user["id"]
        session["full_name"] = user["full_name"]
        flash(f"Welcome back, {user['full_name']}!", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    db = get_db()
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        age = request.form.get("age") or None
        education_level = request.form.get("education_level", "").strip()

        if not full_name or not email:
            flash("Please enter your full name and email.", "danger")
            return redirect(url_for("profile"))

        if age is not None:
            try:
                age = int(age)
                if age < 10 or age > 120:
                    raise ValueError
            except ValueError:
                flash("Please enter an age between 10 and 120.", "danger")
                return redirect(url_for("profile"))

        try:
            existing = db.execute(
                "SELECT id FROM users WHERE email = %s AND id != %s",
                (email, session["user_id"]),
            ).fetchone()
            if existing:
                flash("That email address is already in use.", "danger")
                return redirect(url_for("profile"))

            values = [full_name, email, age, education_level]
            values.append(session["user_id"])
            db.execute(
                "UPDATE users SET full_name = %s, email = %s, age = %s, education_level = %s"
                " WHERE id = %s",
                tuple(values),
            )
            db.commit()
            session["full_name"] = full_name
            session["email"] = email
            flash("Profile updated successfully.", "success")
        except Error:
            db.rollback()
            app.logger.exception("Failed to update profile for user %s", session["user_id"])
            flash("Unable to update your profile right now. Please try again.", "danger")
        return redirect(url_for("profile"))

    user = db.execute(
        "SELECT id, full_name, email, age, education_level, created_at FROM users WHERE id = %s",
        (session["user_id"],),
    ).fetchone()
    if user is None:
        session.clear()
        flash("Your account could not be found. Please log in again.", "warning")
        return redirect(url_for("login"))
    return render_template("profile.html", user=user)


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        app.logger.info('Admin login attempt for username=%s', username)

        try:
            admin_db = get_admin_db()
            row = admin_db.execute(
                "SELECT id, username, password_hash FROM admins WHERE username = %s",
                (username,),
            ).fetchone()
            if row and check_password_hash(row["password_hash"], password):
                session.clear()
                session["is_admin"] = True
                session["admin_id"] = row["id"]
                flash("Welcome, admin.", "success")
                return redirect(url_for("admin_dashboard"))
        except Error:
            app.logger.exception('Admin DB lookup failed for username=%s', username)

        flash("Invalid admin credentials.", "danger")
        return redirect(url_for("admin_login"))

    return render_template("admin_login.html")


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    try:
        db = get_db()
        users = db.execute(
            "SELECT id, full_name, email, age, education_level, created_at "
            "FROM users ORDER BY created_at DESC"
        ).fetchall()
        feedback = db.execute(
            "SELECT f.id, f.user_id, f.name, f.email, f.message, f.rating, f.created_at, u.full_name AS user_name "
            "FROM feedback f LEFT JOIN users u ON u.id = f.user_id "
            "ORDER BY f.created_at DESC"
        ).fetchall()
        messages = db.execute(
            "SELECT * FROM contact_messages ORDER BY created_at DESC"
        ).fetchall()
        quiz_results = db.execute(
            "SELECT qr.id, qr.user_id, u.full_name, qr.top_category, qr.scores, qr.taken_at "
            "FROM quiz_results qr LEFT JOIN users u ON u.id = qr.user_id "
            "ORDER BY qr.taken_at DESC"
        ).fetchall()
        app.logger.info('Admin dashboard counts: users=%s feedback=%s messages=%s results=%s', len(users), len(feedback), len(messages), len(quiz_results))
    except Error:
        app.logger.exception('Failed to load admin dashboard data')
        flash('Unable to load dashboard data. Please check the database connection.', 'danger')
        return redirect(url_for('admin_login'))

    return render_template(
        "admin_dashboard.html",
        users=users,
        feedback=feedback,
        messages=messages,
        quiz_results=quiz_results,
    )


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("Admin logged out.", "info")
    return redirect(url_for("admin_login"))


@app.route("/admin/delete/user/<int:user_id>", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    try:
        db = get_db()
        db.execute("DELETE FROM quiz_results WHERE user_id = %s", (user_id,))
        db.execute("DELETE FROM feedback WHERE user_id = %s", (user_id,))
        db.execute("DELETE FROM users WHERE id = %s", (user_id,))
        db.commit()
        app.logger.info("Deleted user %s and related records.", user_id)
    except Error:
        db.rollback()
        app.logger.exception("Failed to delete user %s", user_id)
        flash("Unable to delete user. Please try again.", "danger")
        return redirect(url_for("admin_dashboard"))
    flash("User and related data deleted.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/delete/feedback/<int:feedback_id>", methods=["POST"])
@admin_required
def admin_delete_feedback(feedback_id):
    db = get_db()
    db.execute("DELETE FROM feedback WHERE id = %s", (feedback_id,))
    db.commit()
    flash("Feedback entry deleted.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/delete/message/<int:message_id>", methods=["POST"])
@admin_required
def admin_delete_message(message_id):
    db = get_db()
    db.execute("DELETE FROM contact_messages WHERE id = %s", (message_id,))
    db.commit()
    flash("Contact message deleted.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/setup", methods=["GET"])
def admin_setup():
    """Initialize admin DB and insert default admin if none exist."""
    init_admin_db()
    admin_db = get_admin_db()
    existing = admin_db.execute("SELECT COUNT(1) AS cnt FROM admins").fetchone()["cnt"]
    if existing == 0:
        username = app.config.get("ADMIN_USERNAME")
        password = app.config.get("ADMIN_PASSWORD")
        password_hash = generate_password_hash(password)
        admin_db.execute(
            "INSERT INTO admins (username, password_hash, full_name) VALUES (%s, %s, %s)",
            (username, password_hash, "Administrator"),
        )
        admin_db.commit()
        return "Admin DB initialized and default admin created."
    return "Admin DB already initialized."


@app.route("/admin/schema")
@admin_required
def admin_schema():
    """Serve the `database.sql` schema file to admins for inspection/download."""
    schema_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "database.sql"))
    if not os.path.exists(schema_path):
        return "Schema file not found.", 404
    return send_file(schema_path, as_attachment=True)


# ---------------------------------------------------------------------------
# Dashboard / quiz / results routes
# ---------------------------------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    latest = db.execute(
        "SELECT * FROM quiz_results WHERE user_id = %s "
        "ORDER BY taken_at DESC LIMIT 1",
        (session["user_id"],),
    ).fetchone()
    return render_template("dashboard.html", latest=latest)


@app.route("/interest-test", methods=["GET", "POST"])
@login_required
def interest_test():
    db = get_db()
    questions = get_published_questions(db)
    if not questions:
        flash("No published questions are available. Please contact the administrator.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        answers = {}
        try:
            for q in questions:
                value = int(request.form.get(f"q{q['id']}"))
                if value not in range(4):
                    raise ValueError
                answers[q["id"]] = value
            top_category, scores = score_and_record(db, session["user_id"], answers)
            db.execute(
                "INSERT INTO quiz_results (user_id, top_category, scores) VALUES (%s, %s, %s)",
                (session["user_id"], top_category, json.dumps(scores)),
            )
            db.commit()
        except (TypeError, ValueError):
            db.rollback()
            flash("Please answer every question before submitting.", "danger")
            return redirect(url_for("interest_test"))
        except Error:
            db.rollback()
            app.logger.exception("Failed to save quiz response")
            flash("Unable to save your quiz right now. Please try again.", "danger")
            return redirect(url_for("interest_test"))
        return redirect(url_for("result"))

    return render_template("interest_test.html", questions=questions)


@app.route("/result")
@login_required
def result():
    db = get_db()
    latest = db.execute(
        "SELECT * FROM quiz_results WHERE user_id = %s "
        "ORDER BY taken_at DESC LIMIT 1",
        (session["user_id"],),
    ).fetchone()

    if latest is None:
        flash("Please take the interest test first.", "info")
        return redirect(url_for("interest_test"))

    scores = json.loads(latest["scores"])
    category = latest["top_category"]
    recommendation = db.execute(
        "SELECT category, blurb, courses, colleges, jobs, roadmap FROM career_recommendations WHERE category=%s",
        (category,),
    ).fetchone()
    if recommendation is None:
        flash("Career recommendation data is unavailable.", "danger")
        return redirect(url_for("dashboard"))
    info = {
        "blurb": recommendation["blurb"],
        "courses": json.loads(recommendation["courses"]),
        "colleges": json.loads(recommendation["colleges"]),
        "jobs": json.loads(recommendation["jobs"]),
        "roadmap": json.loads(recommendation["roadmap"]),
    }

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    return render_template(
        "result.html",
        category=category,
        info=info,
        sorted_scores=sorted_scores,
    )


@app.route("/courses")
def courses():
    category = request.args.get("category")
    db = get_db()
    rows = db.execute("SELECT category, blurb, courses, colleges, jobs, roadmap FROM career_recommendations ORDER BY category").fetchall()
    data = {}
    for row in rows:
        data[row["category"]] = {
            "blurb": row["blurb"],
            "courses": json.loads(row["courses"]),
            "colleges": json.loads(row["colleges"]),
            "jobs": json.loads(row["jobs"]),
            "roadmap": json.loads(row["roadmap"]),
        }
    return render_template("courses.html", data=data, selected=category)


@app.route("/colleges")
def colleges():
    category = request.args.get("category")
    db = get_db()
    rows = db.execute("SELECT category, blurb, courses, colleges, jobs, roadmap FROM career_recommendations ORDER BY category").fetchall()
    data = {}
    for row in rows:
        data[row["category"]] = {
            "blurb": row["blurb"],
            "courses": json.loads(row["courses"]),
            "colleges": json.loads(row["colleges"]),
            "jobs": json.loads(row["jobs"]),
            "roadmap": json.loads(row["roadmap"]),
        }
    return render_template("colleges.html", data=data, selected=category)


@app.route("/jobs")
def jobs():
    category = request.args.get("category")
    db = get_db()
    rows = db.execute("SELECT category, blurb, courses, colleges, jobs, roadmap FROM career_recommendations ORDER BY category").fetchall()
    data = {}
    for row in rows:
        data[row["category"]] = {
            "blurb": row["blurb"],
            "courses": json.loads(row["courses"]),
            "colleges": json.loads(row["colleges"]),
            "jobs": json.loads(row["jobs"]),
            "roadmap": json.loads(row["roadmap"]),
        }
    return render_template("jobs.html", data=data, selected=category)


@app.route("/roadmap")
def roadmap():
    category = request.args.get("category")
    db = get_db()
    rows = db.execute("SELECT category, blurb, courses, colleges, jobs, roadmap FROM career_recommendations ORDER BY category").fetchall()
    data = {}
    for row in rows:
        data[row["category"]] = {
            "blurb": row["blurb"],
            "courses": json.loads(row["courses"]),
            "colleges": json.loads(row["colleges"]),
            "jobs": json.loads(row["jobs"]),
            "roadmap": json.loads(row["roadmap"]),
        }
    return render_template("roadmap.html", data=data, selected=category)


@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()
        rating_value = request.form.get("rating")
        try:
            rating = int(rating_value) if rating_value else None
        except (TypeError, ValueError):
            rating = None

        if not message or (rating is not None and rating not in range(1, 6)):
            flash("Please enter your feedback message.", "danger")
            return redirect(url_for("feedback"))

        try:
            db = get_db()
            db.execute(
                "INSERT INTO feedback (user_id, name, email, message, rating) "
                "VALUES (%s, %s, %s, %s, %s)",
                (session.get("user_id"), name, email, message, rating),
            )
            db.commit()
            app.logger.info('Saved feedback from %s <%s>', name or 'anonymous', email or 'n/a')
        except Error:
            if 'db' in locals():
                db.rollback()
            app.logger.exception('Failed to save feedback from %s <%s>', name or 'anonymous', email or 'n/a')
            flash("Unable to save your feedback right now. Please try again later.", "danger")
            return redirect(url_for("feedback"))

        flash("Thank you for your feedback!", "success")
        return redirect(url_for("feedback"))

    return render_template("feedback.html")


if __name__ == "__main__":
    init_db()
    init_admin_db()
    with app.app_context():
        db = get_db()
        existing = db.execute("SELECT COUNT(1) AS cnt FROM admins").fetchone()["cnt"]
        if existing == 0:
            db.execute(
                "INSERT INTO admins (username, password_hash, full_name) VALUES (%s, %s, %s)",
                (Config.ADMIN_USERNAME, generate_password_hash(Config.ADMIN_PASSWORD), "Administrator"),
            )
            db.commit()
    app.run(debug=Config.DEBUG, host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
