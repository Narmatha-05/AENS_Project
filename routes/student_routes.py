from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from database.db import get_connection
import os, uuid
from datetime import datetime

student_bp = Blueprint("student_bp", __name__)

# -----------------------------
# FILE UPLOAD SETTINGS
# -----------------------------
ALLOWED_EXT = {"pdf", "doc", "docx", "jpg", "jpeg", "png"}

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

@student_bp.route("/dashboard")
@login_required
def dashboard():
    conn = get_connection()
    cur = conn.cursor()

    # Upcoming Events count
    cur.execute("SELECT COUNT(*) AS c FROM events")
    upcoming_events_count = cur.fetchone()["c"]

    # My registrations count
    cur.execute("SELECT COUNT(*) AS c FROM event_registrations WHERE user_id = ?", (current_user.id,))
    my_reg_count = cur.fetchone()["c"]

    # Mentorship status (latest from mentorship_requests)
    cur.execute("""
        SELECT status
        FROM mentorship_requests
        WHERE student_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (current_user.id,))
    row = cur.fetchone()
    mentorship_status = row["status"] if row else "None"

    # Notifications count (Students + All Users)
    cur.execute("""
        SELECT COUNT(*) AS c
        FROM notifications
        WHERE target_group IN ('Students','All Users')
    """)
    new_notif_count = cur.fetchone()["c"]

    # Recent notifications (top 5)
    cur.execute("""
        SELECT created_at, notif_type, title, target_group
        FROM notifications
        WHERE target_group IN ('Students','All Users')
        ORDER BY datetime(created_at) DESC
        LIMIT 5
    """)
    recent_notifications = [dict(r) for r in cur.fetchall()]

    conn.commit()
    conn.close()

    return render_template(
        "student/dashboard.html",
        upcoming_events_count=upcoming_events_count,
        my_reg_count=my_reg_count,
        mentorship_status=mentorship_status,
        new_notif_count=new_notif_count,
        recent_notifications=recent_notifications
    )

@student_bp.route('/create_post', methods=['POST'])
@login_required
def create_post():
    content = request.form.get('content')
    if content:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO posts (content, author_name) VALUES (?, ?)", 
                    (content, current_user.username))
        conn.commit()
        conn.close()
    return redirect(url_for('student_bp.dashboard'))

# -----------------------------
# JOB LISTINGS (Student View)
# -----------------------------
@student_bp.route("/jobs")
@login_required
def jobs():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE status='Published' ORDER BY id DESC")
    jobs = cur.fetchall()
    conn.commit()
    conn.close()
    return render_template("student/jobs.html", jobs=jobs, active_page="jobs")

# -----------------------------
# JOB DETAILS
# -----------------------------
@student_bp.route("/job/<int:job_id>")
@login_required
def job_details(job_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM jobs WHERE id = ? AND status='Published'", (job_id,))
    job = cur.fetchone()

    if not job:
        conn.close()
        flash("Job not found or not available.", "error")
        return redirect(url_for("student_bp.jobs"))

    cur.execute("SELECT status FROM applications WHERE job_id=? AND user_id=?", (job_id, current_user.id))
    row = cur.fetchone()
    application_status = row["status"] if row else None
    already_applied = True if row else False

    conn.commit()
    conn.close()
    return render_template("student/component/job_details.html",
                       job=job,
                       already_applied=already_applied,
                       application_status=application_status)

# -----------------------------
# APPLY JOB
# -----------------------------
@student_bp.route("/job/<int:job_id>/apply", methods=["GET"])
@login_required
def apply_job(job_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    job = cur.fetchone()

    if not job:
        conn.close()
        flash("Job not found.", "error")
        return redirect(url_for("student_bp.jobs"))

    cur.execute("SELECT id FROM applications WHERE job_id=? AND user_id=?", (job_id, current_user.id))
    already = cur.fetchone() is not None

    conn.commit()
    conn.close()

    if already:
        flash("You already applied for this job.", "error")
        return redirect(url_for("student_bp.job_details", job_id=job_id))

    return render_template("student/component/apply_job.html", job=job)

@student_bp.route("/job/<int:job_id>/apply", methods=["POST"])
@login_required
def submit_job_application(job_id):
    applicant_name = request.form.get("applicant_name", "").strip()
    applicant_identifier = request.form.get("applicant_identifier", "").strip()

    if not applicant_name or not applicant_identifier:
        flash("Please complete all required fields.", "error")
        return redirect(url_for("student_bp.apply_job", job_id=job_id))

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, status FROM jobs WHERE id=?", (job_id,))
    job = cur.fetchone()
    if not job or job["status"] != "Published":
        conn.close()
        flash("Job not available.", "error")
        return redirect(url_for("student_bp.jobs"))

    cur.execute("SELECT id FROM applications WHERE job_id=? AND user_id=?", (job_id, current_user.id))
    if cur.fetchone():
        conn.close()
        flash("Already applied.", "error")
        return redirect(url_for("student_bp.job_details", job_id=job_id))

    resume = request.files.get("resume")
    resume_file = None

    if resume and resume.filename:
        filename = secure_filename(resume.filename)
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext not in {"pdf", "doc", "docx"}:
            conn.close()
            flash("Invalid file type.", "error")
            return redirect(url_for("student_bp.apply_job", job_id=job_id))

        upload_dir = os.path.join(current_app.root_path, "static", "uploads", "resumes")
        os.makedirs(upload_dir, exist_ok=True)
        saved_name = f"job{job_id}_user{current_user.id}_{uuid.uuid4().hex}.{ext}"
        resume.save(os.path.join(upload_dir, saved_name))
        resume_file = f"uploads/resumes/{saved_name}"

    cur.execute("""
        INSERT INTO applications (job_id, user_id, applicant_name, applicant_identifier, applicant_role, status, resume_file)
        VALUES (?, ?, ?, ?, ?, 'Pending', ?)
    """, (job_id, current_user.id, applicant_name, applicant_identifier, "Student", resume_file))

    conn.commit()
    conn.close()

    flash("Application submitted successfully.", "success")
    return redirect(url_for("student_bp.job_details", job_id=job_id))

# -----------------------------
# EVENTS
# -----------------------------
@student_bp.route("/events")
@login_required
def events():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM events ORDER BY id DESC")
    events = cur.fetchall()
    cur.execute("SELECT event_id FROM event_registrations WHERE user_id = ?", (current_user.id,))
    registered_ids = [row["event_id"] for row in cur.fetchall()]
    conn.commit()
    conn.close()
    return render_template("student/events.html", active_page="events", events=events, registered_ids=registered_ids)

@student_bp.route("/event/<int:event_id>")
@login_required
def event_details(event_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    event = cur.fetchone()
    if not event:
        conn.close()
        flash("Event not found.", "error")
        return redirect(url_for("student_bp.events"))

    cur.execute("SELECT 1 FROM event_registrations WHERE user_id=? AND event_id=?", (current_user.id, event_id))
    is_registered = cur.fetchone() is not None

    cur.execute("""
        SELECT ef.id, ef.title, ef.description, ef.rating, ef.is_anonymous, ef.created_at,
               COALESCE(u.username, 'Anonymous') AS username
        FROM event_feedback ef
        LEFT JOIN users u ON u.id = ef.user_id
        WHERE ef.event_id = ?
        ORDER BY ef.id DESC
    """, (event_id,))
    feedback_list = cur.fetchall()

    cur.execute("SELECT * FROM event_feedback WHERE event_id=? AND user_id=? ORDER BY id DESC LIMIT 1", (event_id, current_user.id))
    my_feedback = cur.fetchone()

    conn.commit()
    conn.close()
    return render_template("student/component/event_details.html", active_page="events", event=event, is_registered=is_registered, feedback_list=feedback_list, my_feedback=my_feedback)

@student_bp.route("/register/<int:event_id>", methods=["POST"])
@login_required
def register_event(event_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM event_registrations WHERE user_id=? AND event_id=?", (current_user.id, event_id))
    if not cur.fetchone():
        cur.execute("INSERT INTO event_registrations (user_id, event_id) VALUES (?, ?)", (current_user.id, event_id))
        conn.commit()
        flash("Successfully registered!", "success")
    else:
        flash("You are already registered.", "info")
    conn.close()
    return redirect(url_for("student_bp.event_details", event_id=event_id))

@student_bp.route("/unregister/<int:event_id>", methods=["POST"])
@login_required
def unregister_event(event_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM event_registrations WHERE user_id=? AND event_id=?", (current_user.id, event_id))
    conn.commit()
    conn.close()
    flash("Registration cancelled.", "success")
    return redirect(url_for("student_bp.event_details", event_id=event_id))

@student_bp.route("/event/<int:event_id>/feedback", methods=["POST"])
@login_required
def submit_event_feedback(event_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT date_str, time_str FROM events WHERE id = ?", (event_id,))
    event = cur.fetchone()

    if not event:
        conn.close()
        flash("Event not found.", "error")
        return redirect(url_for("student_bp.events"))

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    rating = request.form.get("rating")
    is_anonymous = 1 if request.form.get("anonymous") == "1" else 0

    if not title or not description or not rating:
        conn.close()
        flash("Please complete all fields.", "error")
        return redirect(url_for("student_bp.event_details", event_id=event_id))

    # Check registration
    cur.execute("SELECT 1 FROM event_registrations WHERE user_id=? AND event_id=?", (current_user.id, event_id))
    if not cur.fetchone():
        conn.close()
        flash("You must register first.", "error")
        return redirect(url_for("student_bp.event_details", event_id=event_id))

    # File upload logic (simplified for brevity, assume similar to above)
    attachment_path = None
    f = request.files.get("attachment")
    if f and f.filename and allowed_file(f.filename):
        upload_dir = os.path.join(current_app.root_path, "static", "uploads", "feedback")
        os.makedirs(upload_dir, exist_ok=True)
        filename = secure_filename(f"{event_id}_{current_user.id}_{uuid.uuid4().hex[:8]}_{f.filename}")
        f.save(os.path.join(upload_dir, filename))
        attachment_path = f"uploads/feedback/{filename}"

    db_user_id = None if is_anonymous else current_user.id
    try:
        cur.execute("""
            INSERT INTO event_feedback (event_id, user_id, title, description, rating, is_anonymous, attachment_file)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (event_id, db_user_id, title, description, int(rating), is_anonymous, attachment_path))
        conn.commit()
        flash("Feedback submitted!", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    finally:
        conn.close()

    return redirect(url_for("student_bp.event_details", event_id=event_id))

# =========================================================
# MENTORSHIP (Unified to 'mentorship_requests' table)
# =========================================================

@student_bp.route("/mentorship")
@login_required
def mentorship():
    conn = get_connection()
    cur = conn.cursor()

    # 1. Ensure table exists (Same definition as Officer Dashboard)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mentorship_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            mentor_id INTEGER,
            mentee_name TEXT,
            mentee_identifier TEXT,
            mentee_role TEXT DEFAULT 'Student',
            goals TEXT,
            reason TEXT,
            mentor_name TEXT,
            mentor_identifier TEXT,
            status TEXT DEFAULT 'Pending',
            requested_at TEXT DEFAULT (datetime('now','+8 hours')),
            approved_at TEXT,
            assigned_at TEXT,
            progress_note TEXT
        )
    """)

    # 2. List potential mentors (Alumni/Mentor role)
    cur.execute("""
        SELECT id, username, role, full_name, headline, bio, skills
        FROM users
        WHERE role IN ('Alumni','Mentor')
        ORDER BY id DESC
    """)
    mentors = cur.fetchall()

    # 3. Get status map for current student
    cur.execute("""
        SELECT mentor_id, status
        FROM mentorship_requests
        WHERE student_id = ?
    """, (current_user.id,))
    rows = cur.fetchall()
    
    # Map mentor_id -> status (to disable buttons in UI)
    status_map = {r["mentor_id"]: r["status"] for r in rows if r["mentor_id"]}

    conn.commit()
    conn.close()
    return render_template("student/mentorship.html", mentors=mentors, status_map=status_map)


@student_bp.route("/mentor/<int:mentor_id>")
@login_required
def mentor_details(mentor_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE id = ?", (mentor_id,))
    mentor = cur.fetchone()

    if not mentor:
        conn.close()
        flash("Mentor not found.", "error")
        return redirect(url_for("student_bp.mentorship"))

    # Check status in mentorship_requests
    cur.execute("""
        SELECT status
        FROM mentorship_requests
        WHERE student_id = ? AND mentor_id = ?
        ORDER BY id DESC
    """, (current_user.id, mentor_id))
    req = cur.fetchone()
    status = req["status"] if req else None

    conn.commit()
    conn.close()
    return render_template("student/component/mentor_details.html", mentor=mentor, status=status)


@student_bp.route("/request_mentor/<int:mentor_id>", methods=["POST"])
@login_required
def request_mentor(mentor_id):
    conn = get_connection()
    cur = conn.cursor()

    # Get Mentor Details
    cur.execute("SELECT username, full_name FROM users WHERE id=?", (mentor_id,))
    mentor_user = cur.fetchone()
    if not mentor_user:
        conn.close()
        flash("Mentor does not exist.", "error")
        return redirect(url_for("student_bp.mentorship"))

    mentor_name = mentor_user["full_name"] or mentor_user["username"]
    mentor_identifier = mentor_user["username"]

    # Check for existing pending/active request
    cur.execute("""
        SELECT id FROM mentorship_requests
        WHERE student_id = ? AND mentor_id = ? AND status IN ('Pending','Approved','Assigned')
    """, (current_user.id, mentor_id))

    if cur.fetchone():
        flash("You already have an active request with this mentor.", "warning")
        conn.close()
        return redirect(url_for("student_bp.mentor_details", mentor_id=mentor_id))

    # Insert into mentorship_requests (Compatible with Officer view)
    cur.execute("""
        INSERT INTO mentorship_requests 
        (student_id, mentor_id, mentee_name, mentee_identifier, mentor_name, mentor_identifier, status, requested_at, goals, reason)
        VALUES (?, ?, ?, ?, ?, ?, 'Pending', datetime('now','+8 hours'), 'General Mentorship', 'Requested via Profile')
    """, (
        current_user.id, 
        mentor_id, 
        current_user.full_name or current_user.username, 
        current_user.username,
        mentor_name,
        mentor_identifier
    ))

    conn.commit()
    conn.close()
    flash("Mentorship request sent! Waiting for Officer approval.", "success")
    return redirect(url_for("student_bp.mentor_details", mentor_id=mentor_id))


@student_bp.route("/cancel_request/<int:mentor_id>", methods=["POST"])
@login_required
def cancel_request(mentor_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM mentorship_requests
        WHERE student_id=? AND mentor_id=? AND status='Pending'
    """, (current_user.id, mentor_id))
    
    conn.commit()
    conn.close()

    flash("Mentorship request cancelled.", "success")
    return redirect(url_for("student_bp.mentor_details", mentor_id=mentor_id))


# --- NOTIFICATIONS ---
@student_bp.route("/notifications", methods=["GET"])
@login_required
def notifications():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM notifications
        WHERE target_group IN ('All Users', 'Students')
        ORDER BY id DESC
    """)
    notifications = cur.fetchall()
    conn.commit()
    conn.close()
    return render_template("student/notifications.html", notifications=notifications)

@student_bp.route("/notifications/<int:notif_id>", methods=["GET"])
@login_required
def view_notification(notif_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM notifications WHERE id = ? AND target_group IN ('All Users', 'Students')", (notif_id,))
    notif = cur.fetchone()
    conn.commit()
    conn.close()

    if not notif:
        flash("Notification not found.", "error")
        return redirect(url_for("student_bp.notifications"))
    return render_template("student/component/notification_view.html", notif=notif)

# --- PROFILE ---
@student_bp.route('/profile')
@login_required
def profile():
    return render_template('student/profile.html', active_page='profile', user=current_user, posts=[], event_count=0, job_count=0, mentor_count=0)

@student_bp.route('/edit_profile', methods=['POST'])
@login_required
def edit_profile():
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    location = request.form.get('location')
    address = request.form.get('address')
    headline = request.form.get('headline')
    skills = request.form.get('skills')
    bio = request.form.get('bio')

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users 
        SET full_name=?, email=?, phone=?, location=?, address=?, headline=?, skills=?, bio=?
        WHERE id=?
    """, (full_name, email, phone, location, address, headline, skills, bio, current_user.id))
    
    conn.commit()
    conn.close()
    
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('student_bp.profile'))