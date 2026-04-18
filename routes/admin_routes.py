import os
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename

from database.db import get_connection
from user_model import User

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


# -----------------------------
# Helpers
# -----------------------------
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def is_admin_role(role: str) -> bool:
    return (role or "").strip().lower() in ["admin", "super admin", "superadmin"]


def safe_col(row_dict: dict, key: str, default=""):
    """return value if key exists, else default"""
    return row_dict[key] if key in row_dict and row_dict[key] is not None else default


def format_event_data(rows):
    # rows can be sqlite3.Row; convert to dict first
    out = []
    for r in rows:
        d = dict(r)

        # date display
        try:
            dd = datetime.strptime(str(d.get("event_date", "")), "%Y-%m-%d")
            d["display_date"] = dd.strftime("%d-%m-%Y")
        except:
            d["display_date"] = d.get("event_date", "")

        # time display
        try:
            st = datetime.strptime(str(d.get("start_time", "")), "%H:%M")
            et = datetime.strptime(str(d.get("end_time", "")), "%H:%M")
            d["display_start"] = st.strftime("%I:%M %p")
            d["display_end"] = et.strftime("%I:%M %p")
        except:
            d["display_start"] = d.get("start_time", "")
            d["display_end"] = d.get("end_time", "")

        out.append(d)
    return out


def ensure_admin_seed():
    """
    Checks if an Admin account exists. If not, creates one.
    Refreshes the password if it exists.
    """
    conn = get_connection()
    cur = conn.cursor()

    admin_username = "admin1"
    admin_password = "admin1"  # Plain text as requested
    admin_role = "Admin"
    status = "Active"
    admin_full_name = "System Admin"

    print(f"--- Checking for Admin Account: {admin_username} ---")

    try:
        # Check if admin exists by username
        cur.execute("SELECT id FROM users WHERE username = ?", (admin_username,))
        row = cur.fetchone()

        if row:
            # Admin exists: Update password/role to ensure access
            user_id = row["id"]
            cur.execute("""
                UPDATE users 
                SET password = ?, role = ?, full_name = ?,status=?
                WHERE id = ?
            """, (admin_password, admin_role, admin_full_name, user_id,status))
            print("✅ Admin account exists. Details updated.")
        else:
            # Admin does not exist: Create it
            cur.execute("""
                INSERT INTO users (username, password, role, full_name,status)
                VALUES (?, ?, ?, ?,?)
            """, (admin_username, admin_password, admin_role, admin_full_name,status))
            print("✅ Admin account created successfully.")

        conn.commit()
    except Exception as e:
        print(f"⚠️ Admin seed failed: {e}")
    finally:
        conn.close()


# 🔴 DELETED THE LINE HERE that said: ensure_admin_seed() 
# We do NOT run it here. We run it in app.py.


# -----------------------------
# Protect /admin/*
# -----------------------------
@admin_bp.before_request
def restrict_admin():
    # allow login without authentication
    if request.endpoint in ("admin.login",):
        return None

    if not current_user.is_authenticated:
        flash("Please login as Admin.", "error")
        return redirect(url_for("admin.login"))

    if not is_admin_role(getattr(current_user, "role", "")):
        flash("Access denied. Admin only.", "error")
        return redirect(url_for("index"))


# -----------------------------
# Admin Login / Logout
# -----------------------------
@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    Admin login supports email OR username.
    Uses plain password check (as you requested).
    """
    if request.method == "POST":
        email_or_username = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT * FROM users
            WHERE email = ? OR username = ?
            LIMIT 1
            """,
            (email_or_username, email_or_username),
        )
        row = cur.fetchone()
        conn.close()

        if not row:
            flash("Invalid admin credentials.", "error")
            return redirect(url_for("admin.login"))

        data = dict(row)  # ✅ convert to dict (fix sqlite3.Row .get errors)

        if not is_admin_role(data.get("role")):
            flash("Access denied. Admin only.", "error")
            return redirect(url_for("admin.login"))

        if (data.get("password") or "") != password:
            flash("Invalid admin credentials.", "error")
            return redirect(url_for("admin.login"))

        admin_user = User.get(data["id"])
        login_user(admin_user)
        return redirect(url_for("admin.dashboard"))

    # template must be here: templates/admin/admin_login.html
    return render_template("admin/admin_login.html")


# IMPORTANT: endpoint name MUST be "logout" because your sidebar uses url_for('admin.logout')
@admin_bp.route("/logout", endpoint="logout")
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for("index"))


# -----------------------------
# Dashboard
# -----------------------------
@admin_bp.route("/dashboard")
def dashboard():
    conn = get_connection()

    # counts (safe if columns missing)
    try:
        users_active = conn.execute("SELECT COUNT(*) FROM users WHERE status='Active'").fetchone()[0]
        pending_users = conn.execute("SELECT COUNT(*) FROM users WHERE status='Pending'").fetchone()[0]
    except:
        users_active = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        pending_users = 0

    try:
        events_cnt = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        raw_events = conn.execute("SELECT * FROM events ORDER BY event_date DESC LIMIT 5").fetchall()
    except:
        events_cnt = 0
        raw_events = []

    try:
        feedback = conn.execute("SELECT COUNT(*) FROM testimonials WHERE status='Pending'").fetchone()[0]
    except:
        feedback = 0

    try:
        recent_users = conn.execute("SELECT * FROM users ORDER BY joined_date DESC LIMIT 5").fetchall()
    except:
        recent_users = conn.execute("SELECT * FROM users ORDER BY id DESC LIMIT 5").fetchall()

    conn.close()

    # Convert to dict and ensure required keys exist for your dashboard.html
    recent_users_dict = []
    for u in recent_users:
        d = dict(u)
        # Ensure template keys exist (fix "no attribute status" issues)
        if "status" not in d:
            d["status"] = "Active"
        if "phone_number" not in d:
            d["phone_number"] = ""
        if "joined_date" not in d:
            d["joined_date"] = ""
        if "name" not in d and "full_name" in d:
            d["name"] = d["full_name"]
        recent_users_dict.append(d)

    events_list = format_event_data(raw_events)

    return render_template(
        "admin/dashboard.html",
        users=users_active,
        events=events_cnt,
        pending_users=pending_users,
        feedback=feedback,
        recent_users=recent_users_dict,
        events_list=events_list
    )


# -----------------------------
# USERS: Approve
# -----------------------------
@admin_bp.route("/users/approve", methods=["GET", "POST"])
def approve_users():
    conn = get_connection()

    if request.method == "POST":
        user_id = request.form.get("user_id")
        action = request.form.get("action")  # approve / reject
        new_status = "Active" if action == "approve" else "Rejected"

        try:
            conn.execute("UPDATE users SET status=? WHERE id=?", (new_status, user_id))
            conn.commit()
            flash("User updated.", "success")
        except Exception as e:
            flash(f"Error: {e}", "error")

        conn.close()
        return redirect(url_for("admin.approve_users"))

    try:
        users = conn.execute("SELECT * FROM users WHERE status='Pending'").fetchall()
        users = [dict(u) for u in users]
    except:
        users = []
    conn.close()

    return render_template("admin/approve_users.html", users=users)



# -----------------------------
# USERS: Suspend / Activate
# -----------------------------
@admin_bp.route("/users/suspend", methods=["GET", "POST"])
def suspend_users():
    conn = get_connection()

    # -------------------------
    # POST: toggle suspend/active
    # -------------------------
    if request.method == "POST":
        user_id = request.form.get("user_id")
        current_status = (request.form.get("current_status") or "Active").strip()
        new_status = "Suspended" if current_status == "Active" else "Active"

        try:
            # ✅ This requires 'status' column to exist in users table
            conn.execute("UPDATE users SET status=? WHERE id=?", (new_status, user_id))
            conn.commit()
            flash(f"User status updated to {new_status}.", "success")
        except Exception as e:
            flash(f"Error updating status: {e}", "error")

        conn.close()
        return redirect(url_for("admin.suspend_users"))

    # -------------------------
    # GET: list users + search
    # -------------------------
    q = (request.args.get("q") or "").strip()

    try:
        # If your DB has email/student_id columns, search them too
        if q:
            rows = conn.execute("""
                SELECT * FROM users
                WHERE username LIKE ?
                   OR full_name LIKE ?
                   OR COALESCE(email,'') LIKE ?
                   OR COALESCE(student_id,'') LIKE ?
                ORDER BY id DESC
            """, (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
        else:
            rows = conn.execute("SELECT * FROM users ORDER BY id DESC").fetchall()

        users = [dict(r) for r in rows]

        # ✅ Make template-safe fields (no None / missing keys)
        for u in users:
            u["status"] = (u.get("status") or "Active")
            u["name"] = (u.get("full_name") or u.get("username") or "N/A")
            u["email"] = (u.get("email") or "N/A")
            u["student_id"] = (u.get("student_id") or "N/A")
            u["role"] = (u.get("role") or "N/A")

    except Exception as e:
        flash(f"Error loading users: {e}", "error")
        users = []

    conn.close()
    return render_template("admin/suspend_user.html", users=users)


# -----------------------------
# USERS: Assign roles
# -----------------------------
@admin_bp.route("/users/roles", methods=["GET", "POST"])
def assign_roles():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        role = request.form.get("role", "").strip()

        conn = get_connection()
        try:
            conn.execute("UPDATE users SET role=? WHERE email=?", (role, email))
            conn.commit()
            flash("Role updated.", "success")
        except Exception as e:
            flash(f"Error: {e}", "error")
        conn.close()

        return redirect(url_for("admin.assign_roles"))

    return render_template("admin/assign_roles.html")


@admin_bp.route("/users/reset-password", methods=["GET", "POST"])
def admin_reset_password():
    # POST: Handle the form submission
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        temp_pass = request.form.get("temp_password", "").strip()

        if not email:
            flash("Please provide a user email.", "error")
            return redirect(url_for("admin.admin_reset_password"))

        conn = get_connection()
        try:
            cur = conn.cursor()
            # Update password based on Email
            cur.execute(
                "UPDATE users SET password = ? WHERE email = ?", 
                (temp_pass, email)
            )
            
            if cur.rowcount > 0:
                conn.commit()
                flash(f"Success! Password for {email} reset to '{temp_pass}'.", "success")
                # Note: To actually email the user, you would add SMTP code here.
            else:
                flash(f"No user found with email: {email}", "error")

        except Exception as e:
            flash(f"Database error: {e}", "error")
        finally:
            conn.close()
            
        return redirect(url_for("admin.admin_reset_password"))

    # GET: Show the form
    return render_template("admin/reset_user_password.html")

# -----------------------------
# EVENTS: Manage
# -----------------------------
@admin_bp.route("/events/manage")
def manage_events():
    conn = get_connection()
    try:
        raw_events = conn.execute("SELECT * FROM events ORDER BY event_date DESC").fetchall()
    except:
        raw_events = []
    conn.close()

    return render_template("admin/event_management.html", events=format_event_data(raw_events))


@admin_bp.route("/events/create", methods=["GET", "POST"])
def create_event():
    if request.method == "POST":
        try:
            # 1. Get data from form
            name = request.form.get("name", "")
            date = request.form.get("date", "")
            start = request.form.get("start", "")
            end = request.form.get("end", "")
            info = request.form.get("info", "")
            location = request.form.get("location", "MMU Campus")
            
            # Combine start and end time into one string for 'time_str'
            # Example result: "09:00 - 11:00"
            full_time_str = f"{start} - {end}" if start and end else start

            # (Optional) Handle Image Upload - File is saved, but not linked in DB 
            # because 'image_path' column is missing in your new schema.
            if "image" in request.files:
                f = request.files["image"]
                if f and f.filename and allowed_file(f.filename):
                    filename = secure_filename(f.filename)
                    upload_folder = os.path.join(current_app.root_path, "static", "images")
                    os.makedirs(upload_folder, exist_ok=True)
                    f.save(os.path.join(upload_folder, filename))
            
            # 2. Insert into DB using EXACTLY your schema columns
            conn = get_connection()
            conn.execute(
                """
                INSERT INTO events (title, location, date_str, time_str, description, created_by, status)
                VALUES (?, ?, ?, ?, ?, ?, 'Active')
                """,
                (name, location, date, full_time_str, info, current_user.id),
            )
            conn.commit()
            conn.close()

            flash("Event created successfully.", "success")
            return redirect(url_for("admin.manage_events"))

        except Exception as e:
            # Print error to terminal for debugging
            print(f"Error creating event: {e}") 
            flash(f"Error: {e}", "error")
            return redirect(url_for("admin.create_event"))

    return render_template("admin/event_create.html")

@admin_bp.route("/events/edit/<int:event_id>", methods=["GET", "POST"])
def edit_event(event_id):
    conn = get_connection()

    if request.method == "POST":
        try:
            # 1. Get data from form
            name = request.form.get("name", "")
            date = request.form.get("date", "")
            start = request.form.get("start", "")
            end = request.form.get("end", "")
            info = request.form.get("info", "")
            location = request.form.get("location", "MMU Campus")

            # 2. Combine start and end into 'time_str' for the DB
            # Format: "10:00 - 12:00"
            full_time_str = f"{start} - {end}" if (start and end) else start

            # Note: We are ignoring 'image', 'price', and 'type' because 
            # they are not in your current database schema.

            # 3. Update the database
            conn.execute(
                """
                UPDATE events
                SET title=?, location=?, date_str=?, time_str=?, description=?
                WHERE id=?
                """,
                (name, location, date, full_time_str, info, event_id),
            )
            conn.commit()
            conn.close()

            flash("Event updated successfully.", "success")
            return redirect(url_for("admin.manage_events"))

        except Exception as e:
            conn.close()
            print(f"Error updating event: {e}") # Print to console for debugging
            flash(f"Error: {e}", "error")
            return redirect(url_for("admin.edit_event", event_id=event_id))

    # --- GET REQUEST (Load the form) ---
    event = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    conn.close()

    if event:
        event_dict = dict(event)
        
        # Helper: Split 'time_str' back into 'start' and 'end' for the HTML inputs
        # Assuming format is "HH:MM - HH:MM"
        time_str = event_dict.get("time_str", "")
        if " - " in time_str:
            parts = time_str.split(" - ")
            event_dict["start"] = parts[0]
            event_dict["end"] = parts[1]
        else:
            event_dict["start"] = time_str
            event_dict["end"] = ""
            
        # Map DB columns to what your template expects (if names differ)
        event_dict["date"] = event_dict.get("date_str") 
        
        return render_template("admin/edit_event.html", event=event_dict)
    
    return redirect(url_for("admin.manage_events"))

@admin_bp.route("/events/delete/<int:event_id>")
def delete_event(event_id):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM events WHERE id=?", (event_id,))
        conn.commit()
        flash("Event deleted.", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    conn.close()
    return redirect(url_for("admin.manage_events"))


# -----------------------------
# TESTIMONIALS: Moderation
# -----------------------------
@admin_bp.route("/testimonials", methods=["GET", "POST"])
def manage_testimonials():
    conn = get_connection()

    if request.method == "POST":
        tid = request.form.get("id")
        action = request.form.get("action", "Pending")  # Approved / Rejected / Pending

        try:
            conn.execute("UPDATE testimonials SET status=? WHERE id=?", (action, tid))
            conn.commit()
            flash("Testimonial updated.", "success")
        except Exception as e:
            flash(f"Error: {e}", "error")

        conn.close()
        return redirect(url_for("admin.manage_testimonials"))

    try:
        rows = conn.execute("SELECT * FROM testimonials WHERE status='Pending'").fetchall()
        testimonials = [dict(r) for r in rows]
    except:
        testimonials = []
    conn.close()

    return render_template("admin/testimonial_approval.html", testimonials=testimonials)


# -----------------------------
# Announcement + Notification pages
# -----------------------------
@admin_bp.route("/events/announce", methods=["GET", "POST"])
def publish_announcement():
    conn = get_connection()

    # ✅ FIXED: Changed 'ORDER BY event_date' to 'ORDER BY date_str'
    # ✅ FIXED: Ensure we check for 'Active' status if that's what your new schema uses
    try:
        events = conn.execute("""
            SELECT id, title
            FROM events
            WHERE status='Active' OR status='Published'
            ORDER BY date_str DESC
        """).fetchall()
    except Exception as e:
        print(f"Error fetching events: {e}")
        events = []

    events = [dict(e) for e in events]

    if request.method == "POST":
        event_id = request.form.get("event_id")
        message = request.form.get("message", "").strip()

        if not event_id or not message:
            flash("Please select an event and type an announcement message.", "error")
            conn.close()
            return render_template("admin/publish_announcement.html", events=events)

        # Save to notifications table
        try:
            conn.execute("""
                INSERT INTO notifications (notif_type, target_group, title, message, status, created_by)
                VALUES (?, ?, ?, ?, 'Sent', ?)
            """, (
                "event_announcement",
                "All",
                f"Event Announcement: {event_id}",
                message,
                getattr(current_user, "id", None)
            ))
            conn.commit()
            flash("Announcement published to news feed!", "success")
        except Exception as e:
            flash(f"Database error: {e}", "error")

    conn.close()
    return render_template("admin/publish_announcement.html", events=events)



@admin_bp.route("/system/notify", methods=["GET", "POST"])
def system_notification():
    conn = get_connection()

    if request.method == "POST":
        subject = (request.form.get("subject") or "").strip()
        group = (request.form.get("group") or "").strip()
        message = (request.form.get("message") or "").strip()

        # Map dropdown values → DB values
        group_map = {
            "all": "All",
            "alumni": "Alumni",
            "students": "Student",
            "officer": "Officer",
            "admin": "Admin",
        }
        target_group = group_map.get(group, "All")

        if not subject or not message:
            flash("Subject and Message are required.", "error")
            conn.close()
            return redirect(url_for("admin.system_notification"))

        try:
            conn.execute(
                """
                INSERT INTO notifications (notif_type, target_group, title, message, created_by)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("System", target_group, subject, message, current_user.id),
            )
            conn.commit()
            flash("✅ System notification sent successfully!", "success")
        except Exception as e:
            flash(f"Error sending notification: {e}", "error")

        conn.close()
        return redirect(url_for("admin.system_notification"))

    # For testing: show last 5 sent notifications on same page
    try:
        recent = conn.execute(
            "SELECT * FROM notifications ORDER BY created_at DESC LIMIT 5"
        ).fetchall()
        recent = [dict(r) for r in recent]
    except:
        recent = []

    conn.close()
    return render_template("admin/send_notification.html", recent=recent)