from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from database.db import get_connection
from datetime import datetime

alumni_bp = Blueprint("alumni_bp", __name__, url_prefix="/alumni")

# =====================================================
# DASHBOARD
# =====================================================
@alumni_bp.route("/dashboard")
@login_required
def dashboard():
    conn = get_connection()

    upcoming_events_count = conn.execute(
        "SELECT COUNT(*) FROM events"
    ).fetchone()[0]

    my_events_count = 0  
    
    # ✅ Fixed: Query using mentor_id (Standardized with Student/Officer)
    mentorship_requests_count = conn.execute(
        "SELECT COUNT(*) FROM mentorship_requests WHERE mentor_id=? AND status='Pending'",
        (current_user.id,)
    ).fetchone()[0]

    new_notif_count = conn.execute(
        "SELECT COUNT(*) FROM notifications"
    ).fetchone()[0]

    recent_notifications = conn.execute("""
        SELECT notif_type, title, target_group, created_at
        FROM notifications
        ORDER BY id DESC
        LIMIT 5
    """).fetchall()

    conn.close()

    return render_template(
        "alumni/dashboard.html",
        upcoming_events_count=upcoming_events_count,
        my_events_count=my_events_count,
        mentorship_requests=mentorship_requests_count,
        new_notif_count=new_notif_count,
        recent_notifications=recent_notifications
    )

# ... [Events Routes match your existing code] ...
# ... [Keeping Events Create/Edit/Delete same as provided] ...

@alumni_bp.route("/events")
@login_required
def events():
    conn = get_connection()
    events = conn.execute("""
        SELECT e.*, u.full_name
        FROM events e
        LEFT JOIN users u ON e.created_by = u.id
        ORDER BY e.created_at DESC
    """).fetchall()
    conn.close()
    return render_template("alumni/events.html", events=events)

@alumni_bp.route("/events/create", methods=["GET", "POST"])
@login_required
def create_event():
    if request.method == "POST":
        title = request.form.get("title")
        location = request.form.get("location")
        date_str = request.form.get("date_str")
        time_str = request.form.get("time_str")
        description = request.form.get("description")

        if not title or not date_str or not time_str:
            flash("Please fill all required fields.", "error")
            return redirect(url_for("alumni_bp.create_event"))

        conn = get_connection()
        conn.execute("""
            INSERT INTO events (title, location, date_str, time_str, description, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now','+8 hours'))
        """, (title, location, date_str, time_str, description, current_user.id))
        conn.commit()
        conn.close()
        flash("Event created successfully!", "success")
        return redirect(url_for("alumni_bp.events"))
    return render_template("alumni/event_create.html")

@alumni_bp.route("/events/edit/<int:event_id>", methods=["GET", "POST"])
@login_required
def edit_event(event_id):
    conn = get_connection()
    event = conn.execute("SELECT * FROM events WHERE id = ? AND created_by = ?", (event_id, current_user.id)).fetchone()
    if not event:
        conn.close()
        flash("Event not found or access denied.", "error")
        return redirect(url_for("alumni_bp.events"))

    if request.method == "POST":
        conn.execute("""
            UPDATE events SET title=?, location=?, date_str=?, time_str=?, description=?
            WHERE id=? AND created_by=?
        """, (request.form["title"], request.form["location"], request.form["date_str"], request.form["time_str"], request.form["description"], event_id, current_user.id))
        conn.commit()
        conn.close()
        flash("Event updated successfully!", "success")
        return redirect(url_for("alumni_bp.events"))
    conn.close()
    return render_template("alumni/event_edit.html", event=event)

@alumni_bp.route("/events/delete/<int:event_id>", methods=["POST"])
@login_required
def delete_event(event_id):
    conn = get_connection()
    conn.execute("DELETE FROM events WHERE id = ? AND created_by = ?", (event_id, current_user.id))
    conn.commit()
    conn.close()
    flash("Event deleted.", "success")
    return redirect(url_for("alumni_bp.events"))

@alumni_bp.route("/notifications")
@login_required
def notifications():
    conn = get_connection()
    notifications = conn.execute("SELECT * FROM notifications ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("alumni/notifications.html", notifications=notifications)

# ... [Jobs Routes match your existing code] ...
@alumni_bp.route("/jobs")
def jobs():
    conn = get_connection()
    jobs = conn.execute("SELECT id, job_title, company, location, deadline, description FROM jobs ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template("alumni/jobs.html", jobs=jobs)

@alumni_bp.route("/jobs/create", methods=["GET", "POST"])
def create_job():
    if request.method == "POST":
        conn = get_connection()
        try:
            conn.execute("""
                INSERT INTO jobs (job_title, company, location, deadline, description, requirements, status)
                VALUES (?, ?, ?, ?, ?, ?, 'Published')
            """, (request.form.get("job_title"), request.form.get("company"), request.form.get("location"), request.form.get("deadline"), request.form.get("description"), request.form.get("requirements")))
            conn.commit()
            flash("Job posted successfully!", "success")
        except Exception as e:
            conn.rollback()
            flash("Error posting job.", "danger")
        finally:
            conn.close()
        return redirect(url_for("alumni_bp.jobs"))
    return render_template("alumni/job_create.html")

# =====================================================
# MENTORSHIP (Unified to mentorship_requests)
# =====================================================
@alumni_bp.route("/mentorship")
@login_required
def mentorship_requests():
    conn = get_connection()
    # ✅ Fixed: Query using mentor_id
    requests = conn.execute("""
        SELECT *
        FROM mentorship_requests
        WHERE mentor_id = ?
        ORDER BY requested_at DESC
    """, (current_user.id,)).fetchall()
    conn.close()
    return render_template("alumni/mentorship.html", requests=requests)


@alumni_bp.route("/mentorship/<int:req_id>/approve", methods=["POST"])
@login_required
def approve_mentorship(req_id):
    conn = get_connection()
    # ✅ Fixed: Verify mentor_id instead of username for security
    conn.execute("""
        UPDATE mentorship_requests
        SET status='Approved', approved_at=datetime('now','+8 hours')
        WHERE id=? AND mentor_id=?
    """, (req_id, current_user.id))
    conn.commit()
    conn.close()

    flash("Mentorship request approved.", "success")
    return redirect(url_for("alumni_bp.mentorship_requests"))


@alumni_bp.route("/mentorship/<int:req_id>/reject", methods=["POST"])
@login_required
def reject_mentorship(req_id):
    conn = get_connection()
    conn.execute("""
        UPDATE mentorship_requests
        SET status='Rejected'
        WHERE id=? AND mentor_id=?
    """, (req_id, current_user.id))
    conn.commit()
    conn.close()

    flash("Mentorship request rejected.", "error")
    return redirect(url_for("alumni_bp.mentorship_requests"))

# ... [Profile Routes match your existing code] ...
@alumni_bp.route("/profile")
@login_required
def profile():
    return render_template("alumni/profile.html", user=current_user, posts=[], event_count=0, job_count=0, mentor_count=0)

@alumni_bp.route("/edit_profile", methods=["POST"])
@login_required
def edit_profile():
    conn = get_connection()
    conn.execute("""
        UPDATE users
        SET full_name=?, email=?, phone=?, location=?, address=?, headline=?, skills=?, bio=?
        WHERE id=?
    """, (request.form.get("full_name"), request.form.get("email"), request.form.get("phone"), request.form.get("location"), request.form.get("address"), request.form.get("headline"), request.form.get("skills"), request.form.get("bio"), current_user.id))
    conn.commit()
    conn.close()
    flash("Profile updated successfully.", "success")
    return redirect(url_for("alumni_bp.profile"))