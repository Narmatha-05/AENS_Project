from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from database.db import get_connection

officer_bp = Blueprint("officer_bp", __name__, url_prefix="/officer")

@officer_bp.before_request
def restrict_officer():
    if not current_user.is_authenticated:
        return redirect(url_for("login"))

    if current_user.role != "Officer":
        flash("Access Denied. Officer Only.", "error")
        return redirect(url_for("login"))


@officer_bp.route("/dashboard")
def dashboard():
    conn = get_connection()
    cur = conn.cursor()

    # ✅ Ensure mentorship_requests table exists (prevents errors on fresh DB)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mentorship_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            mentor_id INTEGER,
            mentee_name TEXT,
            mentee_identifier TEXT,
            mentee_role TEXT DEFAULT 'Student',
            goals TEXT NOT NULL,
            reason TEXT,
            mentor_name TEXT,
            mentor_identifier TEXT,
            status TEXT DEFAULT 'Pending',
            requested_at TEXT DEFAULT (datetime('now','+8 hours')),
            approved_at TEXT,
            assigned_at TEXT,
            progress_note TEXT
        );
    """)

    # 🔹 Recent jobs (latest 5)
    cur.execute("""
        SELECT id, job_title, company, deadline, status
        FROM jobs
        ORDER BY id DESC
        LIMIT 5
    """)
    recent_jobs = cur.fetchall()

    # 🔹 Active job postings (Published)
    cur.execute("""
        SELECT COUNT(*) AS cnt
        FROM jobs
        WHERE status = 'Published'
    """)
    active_count = cur.fetchone()["cnt"]

    # 🔹 TOTAL APPLICATIONS
    cur.execute("SELECT COUNT(*) AS cnt FROM applications")
    total_applications = cur.fetchone()["cnt"]

    # ✅ PENDING MENTORSHIP (from mentorship_requests — CSO queue)
    cur.execute("""
        SELECT COUNT(*) AS cnt
        FROM mentorship_requests
        WHERE status = 'Pending'
    """)
    pending_mentorship = cur.fetchone()["cnt"]

    # ✅ ALUMNI PARTICIPATION (count of requests that became active)
    cur.execute("""
        SELECT COUNT(*) AS cnt
        FROM mentorship_requests
        WHERE status IN ('Approved', 'Assigned', 'Completed')
    """)
    alumni_participation = cur.fetchone()["cnt"]

    conn.commit()
    conn.close()

    return render_template(
        "officer/dashboard.html",
        recent_jobs=recent_jobs,
        active_count=active_count,
        total_applications=total_applications,
        pending_mentorship=pending_mentorship,
        alumni_participation=alumni_participation
    )


@officer_bp.route("/jobs/create_job", methods=["GET", "POST"])
def create_job():
    if request.method == "POST":
        job_title = request.form.get("job_title", "").strip()
        company = request.form.get("company", "").strip()
        job_type = request.form.get("job_type", "").strip()
        deadline = request.form.get("deadline", "").strip()
        location = request.form.get("location", "").strip()
        salary = request.form.get("salary", "").strip()
        description = request.form.get("description", "").strip()
        requirements = request.form.get("requirements", "").strip()
        notes = request.form.get("notes", "").strip()

        if not job_title or not company or not deadline or not description or not requirements:
            flash("Please fill all required fields (*)", "error")
            return redirect(url_for("officer_bp.create_job"))

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO jobs
            (job_title, company, job_type, deadline, location, salary, description, requirements, notes, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_title, company, job_type, deadline, location, salary,
            description, requirements, notes, "Published"
        ))
        
        conn.commit()
        conn.close()

        flash("Job published successfully!", "success")
        return redirect(url_for("officer_bp.dashboard"))

    return render_template("officer/jobs/create_job.html")


@officer_bp.route("/jobs/edit_job")
def edit_job():
    edit_id = request.args.get("edit_id")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM jobs ORDER BY id DESC")
    jobs = cur.fetchall()

    selected_job = None
    if edit_id:
        cur.execute("SELECT * FROM jobs WHERE id = ?", (edit_id,))
        selected_job = cur.fetchone()

    conn.commit()
    conn.close()

    return render_template(
        "officer/jobs/edit_job.html",
        jobs=jobs,
        selected_job=selected_job
    )


@officer_bp.route("/jobs/<int:job_id>/update", methods=["POST"])
def update_job(job_id):
    job_title = request.form.get("job_title", "").strip()
    company = request.form.get("company", "").strip()
    job_type = request.form.get("job_type", "").strip()
    deadline = request.form.get("deadline", "").strip()
    location = request.form.get("location", "").strip()
    salary = request.form.get("salary", "").strip()
    description = request.form.get("description", "").strip()
    requirements = request.form.get("requirements", "").strip()
    notes = request.form.get("notes", "").strip()
    status = request.form.get("status", "").strip()

    if not job_title or not company or not deadline or not description or not requirements:
        flash("Please fill all required fields (*)", "error")
        return redirect(url_for("officer_bp.edit_job", edit_id=job_id))

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE jobs
        SET job_title = ?,
            company = ?,
            job_type = ?,
            deadline = ?,
            location = ?,
            salary = ?,
            description = ?,
            requirements = ?,
            notes = ?,
            status = ?
        WHERE id = ?
    """, (
        job_title, company, job_type, deadline, location, salary,
        description, requirements, notes, status,
        job_id
    ))

    conn.commit()
    conn.close()

    flash("Job updated successfully!", "success")
    return redirect(url_for("officer_bp.edit_job", edit_id=job_id))


@officer_bp.route("/jobs/delete/<int:job_id>", methods=["POST"])
def delete_job(job_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM jobs WHERE id=?", (job_id,))
    
    conn.commit()
    conn.close()

    flash("Job removed successfully!", "success")
    return redirect(url_for("officer_bp.edit_job"))


@officer_bp.route("/applications")
def applications():
    job_id = request.args.get("job_id", "all")
    status = request.args.get("status", "all")
    search = request.args.get("search", "").strip()
    sort = request.args.get("sort", "latest")

    conn = get_connection()
    cur = conn.cursor()
    # 🔹 Jobs for dropdown
    cur.execute("SELECT id, job_title, company FROM jobs ORDER BY id DESC")
    jobs = cur.fetchall()

    # 🔹 Base query
    query = """
        SELECT a.id,
               a.applicant_name,
               j.job_title,
               a.applied_date,
               a.status
        FROM applications a
        JOIN jobs j ON j.id = a.job_id
        WHERE 1=1
    """
    params = []

    if job_id != "all":
        query += " AND a.job_id = ?"
        params.append(job_id)

    if status != "all":
        query += " AND a.status = ?"
        params.append(status)

    if search:
        query += " AND a.applicant_name LIKE ?"
        params.append(f"%{search}%")

    if sort == "oldest":
        query += " ORDER BY a.id ASC"
    elif sort == "name":
        query += " ORDER BY a.applicant_name ASC"
    else:
        query += " ORDER BY a.id DESC"

    cur.execute(query, params)
    applications = cur.fetchall()
    conn.close()

    return render_template(
        "officer/applications.html",
        jobs=jobs,
        applications=applications,
        selected_job_id=str(job_id),
        selected_status=status,
        selected_sort=sort,
        search_query=search
    )


@officer_bp.route("/applications/<int:app_id>")
def view_application(app_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT a.id, a.job_id, a.applicant_name, a.applicant_identifier,
            a.applicant_role, a.applied_date, a.status,
            a.resume_file,
            j.job_title, j.company
        FROM applications a
        JOIN jobs j ON j.id = a.job_id
        WHERE a.id = ?
    """, (app_id,))
    application = cur.fetchone()
    conn.close()

    if not application:
        flash("Application not found.", "error")
        return redirect(url_for("officer_bp.applications"))

    return render_template("officer/application_view.html", application=application)


@officer_bp.route("/applications/<int:app_id>/status", methods=["POST"])
def update_application_status(app_id):
    new_status = request.form.get("status", "").strip()

    allowed = ["Pending", "Reviewed", "Shortlisted", "Rejected"]
    if new_status not in allowed:
        flash("Invalid status.", "error")
        return redirect(url_for("officer_bp.view_application", app_id=app_id))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE applications SET status=? WHERE id=?", (new_status, app_id))
    
    conn.commit()
    conn.close()

    flash("Application status updated.", "success")
    return redirect(url_for("officer_bp.view_application", app_id=app_id))


# =========================================================
# MENTORSHIP MANAGEMENT
# =========================================================

@officer_bp.route("/mentorship_review", methods=["GET"])
def mentorship_review():
    selected_status = request.args.get("status", "all")
    search = request.args.get("search", "").strip()

    conn = get_connection()
    cur = conn.cursor()

    # 1. Main list query: join requested mentor info from users (mentor_id = requested mentor)
    query = """
        SELECT r.*,
               m.username AS requested_mentor_username,
               m.full_name AS requested_mentor_full_name
        FROM mentorship_requests r
        LEFT JOIN users m ON m.id = r.mentor_id
        WHERE 1=1
    """
    params = []

    if selected_status != "all":
        query += " AND r.status = ?"
        params.append(selected_status)

    if search:
        s = f"%{search}%"
        query += """
            AND (
                r.mentee_name LIKE ? OR
                r.mentee_identifier LIKE ? OR
                r.mentor_name LIKE ? OR
                r.mentor_identifier LIKE ? OR
                m.username LIKE ? OR
                m.full_name LIKE ?
            )
        """
        params.extend([s, s, s, s, s, s])

    query += " ORDER BY r.id DESC"
    cur.execute(query, params)
    requests_list = cur.fetchall()

    # Stats cards
    cur.execute("SELECT COUNT(*) AS c FROM mentorship_requests")
    total_requests = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM mentorship_requests WHERE status='Pending'")
    pending_count = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM mentorship_requests WHERE status IN ('Approved','Assigned')")
    active_mentorship = cur.fetchone()["c"]

    # Mentor summary (only if search matches a mentor)
    mentor_summary = None
    if search:
        cur.execute("""
            SELECT id, username, full_name
            FROM users
            WHERE role IN ('Alumni','Mentor')
              AND (username LIKE ? OR full_name LIKE ?)
            LIMIT 1
        """, (f"%{search}%", f"%{search}%"))
        mentor = cur.fetchone()

        if mentor:
            cur.execute("""
                SELECT
                  COUNT(*) AS total,
                  SUM(CASE WHEN status='Pending' THEN 1 ELSE 0 END) AS pending,
                  SUM(CASE WHEN status='Approved' THEN 1 ELSE 0 END) AS approved,
                  SUM(CASE WHEN status='Assigned' THEN 1 ELSE 0 END) AS assigned,
                  SUM(CASE WHEN status='Rejected' THEN 1 ELSE 0 END) AS rejected
                FROM mentorship_requests
                WHERE mentor_id = ?
            """, (mentor["id"],))
            c = cur.fetchone()

            mentor_summary = {
                "name": mentor["full_name"] or mentor["username"],
                "username": mentor["username"],
                "total": c["total"] or 0,
                "pending": c["pending"] or 0,
                "approved": c["approved"] or 0,
                "assigned": c["assigned"] or 0,
                "rejected": c["rejected"] or 0,
            }

    conn.commit()
    conn.close()

    return render_template(
        "officer/mentorship_review.html",
        requests=requests_list,
        selected_status=selected_status,
        search_query=search,
        total_requests=total_requests,
        pending_count=pending_count,
        active_mentorship=active_mentorship,
        mentor_summary=mentor_summary
    )


@officer_bp.route("/mentorship/<int:req_id>", methods=["GET"])
def view_mentorship(req_id):
    conn = get_connection()
    cur = conn.cursor()

    # join requested mentor info
    cur.execute("""
        SELECT r.*,
               m.username AS requested_mentor_username,
               m.full_name AS requested_mentor_full_name,
               m.email AS requested_mentor_email
        FROM mentorship_requests r
        LEFT JOIN users m ON m.id = r.mentor_id
        WHERE r.id=?
    """, (req_id,))
    req = cur.fetchone()
    conn.close()

    if not req:
        flash("Mentorship request not found.", "error")
        return redirect(url_for("officer_bp.mentorship_review"))

    return render_template("officer/mentorship_view.html", req=req)


@officer_bp.route("/mentorship/<int:req_id>/approve", methods=["POST"])
def approve_mentorship(req_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE mentorship_requests
        SET status='Approved',
            approved_at=datetime('now','+8 hours')
        WHERE id=? AND status='Pending'
    """, (req_id,))
    
    conn.commit()
    conn.close()

    flash("Request approved. You can now assign a mentor.", "success")
    return redirect(url_for("officer_bp.view_mentorship", req_id=req_id))


@officer_bp.route("/mentorship/<int:req_id>/reject", methods=["POST"])
def reject_mentorship(req_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE mentorship_requests
        SET status='Rejected'
        WHERE id=? AND status IN ('Pending','Approved')
    """, (req_id,))
    
    conn.commit()
    conn.close()

    flash("Request rejected.", "success")
    return redirect(url_for("officer_bp.mentorship_review"))


@officer_bp.route("/mentorship/<int:req_id>/assign", methods=["POST"])
def assign_mentor(req_id):
    mentor_name = request.form.get("mentor_name", "").strip()
    mentor_identifier = request.form.get("mentor_identifier", "").strip()

    if not mentor_name:
        flash("Please enter mentor name.", "error")
        return redirect(url_for("officer_bp.view_mentorship", req_id=req_id))

    conn = get_connection()
    cur = conn.cursor()

    # 1) Check request exists
    cur.execute("SELECT * FROM mentorship_requests WHERE id=?", (req_id,))
    req = cur.fetchone()
    if not req:
        conn.close()
        flash("Request not found.", "error")
        return redirect(url_for("officer_bp.mentorship_review"))

    # 2) Validate mentee is actually a Student
    cur.execute("SELECT role FROM users WHERE id=?", (req["student_id"],))
    mentee = cur.fetchone()
    if not mentee or mentee["role"] != "Student":
        conn.close()
        flash("Invalid mentee: only Student requests can be assigned.", "error")
        return redirect(url_for("officer_bp.view_mentorship", req_id=req_id))

    # 3) Validate mentor exists and must be Alumni (or Mentor)
    cur.execute("""
        SELECT id, role, username, full_name
        FROM users
        WHERE (username = ? OR full_name = ?)
        LIMIT 1
    """, (mentor_name, mentor_name))
    mentor = cur.fetchone()

    if not mentor:
        conn.close()
        flash("Mentor not found. Please enter a registered Alumni username/full name.", "error")
        return redirect(url_for("officer_bp.view_mentorship", req_id=req_id))

    if mentor["role"] not in ("Alumni", "Mentor"):
        conn.close()
        flash("Invalid mentor role. Only Alumni/Mentor can be assigned.", "error")
        return redirect(url_for("officer_bp.view_mentorship", req_id=req_id))

    # 4) Save assignment (store mentor_id too)
    cur.execute("""
        UPDATE mentorship_requests
        SET mentor_id=?,
            mentor_name=?,
            mentor_identifier=?,
            status='Assigned',
            assigned_at=datetime('now','+8 hours')
        WHERE id=? AND status='Approved'
    """, (mentor["id"], mentor["full_name"] or mentor["username"], mentor_identifier, req_id))

    conn.commit()
    conn.close()

    flash(f"Mentor assigned to {mentor['username'] or mentor['full_name']}.", "success")
    return redirect(url_for("officer_bp.mentorship_review"))


@officer_bp.route("/mentorship/<int:req_id>/progress", methods=["POST"])
def update_mentorship_progress(req_id):
    note = request.form.get("progress_note", "").strip()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE mentorship_requests
        SET progress_note=?
        WHERE id=?
    """, (note, req_id))
    
    conn.commit()
    conn.close()

    flash("Progress updated.", "success")
    return redirect(url_for("officer_bp.view_mentorship", req_id=req_id))


# =========================================================
# FEEDBACK & NOTIFICATIONS
# =========================================================

@officer_bp.route("/feedback", methods=["GET"])
@login_required
def view_event_feedback():
    event_filter = request.args.get("event", "all")
    role_filter = request.args.get("role", "all")
    rating_filter = request.args.get("rating", "all")
    search = request.args.get("search", "").strip()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT DISTINCT title FROM events ORDER BY title ASC")
    events = [row["title"] for row in cur.fetchall()]

    query = """
        SELECT 
            ef.id, 
            e.title AS event_title, 
            COALESCE(u.role, 'Guest') AS user_role, 
            ef.rating,
            ef.title,
            ef.description AS comments, 
            ef.created_at
        FROM event_feedback ef
        JOIN events e ON ef.event_id = e.id
        LEFT JOIN users u ON ef.user_id = u.id
        WHERE 1=1
    """
    params = []

    if event_filter != "all":
        query += " AND e.title = ?"
        params.append(event_filter)

    if role_filter != "all":
        query += " AND u.role = ?"
        params.append(role_filter)

    if rating_filter != "all":
        query += " AND ef.rating = ?"
        params.append(int(rating_filter))

    if search:
        query += " AND (e.title LIKE ? OR ef.title LIKE ? OR ef.description LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    query += " ORDER BY ef.created_at DESC"

    cur.execute(query, params)
    feedback_list = cur.fetchall()
    conn.close()

    return render_template(
        "officer/feedback.html",
        feedback_list=feedback_list,
        events=events,
        selected_event=event_filter,
        selected_role=role_filter,
        selected_rating=str(rating_filter),
        search_query=search
    )


@officer_bp.route("/notifications", methods=["GET"])
def notifications():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notif_type TEXT NOT NULL,
            target_group TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT DEFAULT 'Sent',
            schedule_mode TEXT DEFAULT 'now',
            scheduled_at TEXT,
            created_at TEXT DEFAULT (datetime('now','+8 hours')) 
        )
    """)
    
    # Auto-update Scheduled -> Sent when time passed
    cur.execute("""
        UPDATE notifications
        SET status='Sent'
        WHERE status='Scheduled'
          AND scheduled_at IS NOT NULL
          AND datetime(scheduled_at) <= datetime('now','+8 hours')
    """)
    
    cur.execute("SELECT * FROM notifications ORDER BY id DESC")
    notifications = cur.fetchall()
    conn.commit()
    conn.close()

    return render_template("officer/notifications.html", notifications=notifications)

@officer_bp.route("/notifications/<int:notif_id>", methods=["GET"])
def view_notification(notif_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM notifications WHERE id=?", (notif_id,))
    notif = cur.fetchone()
    conn.close()

    if notif is None:
        flash("Notification not found.", "error")
        return redirect(url_for("officer_bp.notifications"))

    return render_template("officer/notification_view.html", notif=notif)

@officer_bp.route("/notifications/send", methods=["POST"])
def send_notification():
    notif_type = request.form.get("notif_type", "").strip()
    target_group = request.form.get("target_group", "").strip()
    title = request.form.get("title", "").strip()
    message = request.form.get("message", "").strip()
    schedule_mode = request.form.get("schedule", "now").strip()
    scheduled_at = request.form.get("schedule_time", "").strip()

    if not notif_type or not target_group or not title or not message:
        flash("Please fill all required fields (*)", "error")
        return redirect(url_for("officer_bp.notifications"))

    status = "Sent"
    save_scheduled = None

    if schedule_mode == "later":
        if not scheduled_at:
            flash("Please choose Date/Time for scheduled notifications.", "error")
            return redirect(url_for("officer_bp.notifications"))

        status = "Scheduled"
        scheduled_at = scheduled_at.replace("T", " ")
        if len(scheduled_at) == 16:
            scheduled_at += ":00"
        save_scheduled = scheduled_at

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO notifications
        (notif_type, target_group, title, message, schedule_mode, scheduled_at, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now','+8 hours'))
    """, (notif_type, target_group, title, message, schedule_mode, save_scheduled, status))

    conn.commit()
    conn.close()

    flash("Notification saved successfully!", "success")
    return redirect(url_for("officer_bp.notifications"))

@officer_bp.route("/notifications/delete/<int:notif_id>", methods=["POST"])
def delete_notification(notif_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM notifications WHERE id=?", (notif_id,))
    
    conn.commit()
    conn.close()
    flash("Notification deleted.", "success")
    return redirect(url_for("officer_bp.notifications"))