from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

from database.db import init_db
from user_model import User

# ✅ Import the seed function here
from routes.admin_routes import admin_bp, ensure_admin_seed
from routes.student_routes import student_bp
from routes.officer_routes import officer_bp
from routes.alumni_routes import alumni_bp  

def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "aens-secret-key"

    # ✅ 1. Create tables first
    init_db()

    # ✅ 2. Now it is safe to seed the Admin
    try:
        ensure_admin_seed()
        print("✅ Admin seed check complete.")
    except Exception as e:
        print(f"⚠️ Note: Admin seed skipped or failed: {e}")

    # ✅ Login manager
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "login"

    @login_manager.user_loader
    def load_user(user_id):
        return User.get(user_id)

    # ✅ Blueprints
    app.register_blueprint(student_bp)
    app.register_blueprint(officer_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(alumni_bp)

    # =====================================================
    # ROOT → ROLE DASHBOARD
    # =====================================================
    @app.route("/")
    def root():
        if current_user.is_authenticated:
            if current_user.role == "Admin":
                return redirect(url_for("admin.dashboard")) # Check if this is admin_bp.dashboard or admin.dashboard in your code
            if current_user.role == "Officer":
                return redirect(url_for("officer_bp.dashboard"))
            if current_user.role == "Alumni":
                return redirect(url_for("alumni_bp.dashboard"))
            return redirect(url_for("student_bp.dashboard"))
        return render_template("base.html")

# =====================================================
    # LOGIN (Updated with Status Check)
    # =====================================================
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()

            user = User.find_by_username(username)
            
            # 1. Check credentials
            if user and user.password == password:
                
                # 2. Check Status (Block if not Active)
                # Ensure your User model has a .status attribute!
                status = getattr(user, "status", "Active") # Default to Active if missing to prevent crash

                if status == "Pending":
                    flash("Your account is waiting for Admin approval.", "warning")
                    return render_template("login.html")
                
                if status == "Rejected" or status == "Suspended":
                    flash("Your account has been suspended or rejected. Contact Admin.", "error")
                    return render_template("login.html")

                # 3. If Active, Log them in
                login_user(user)

                if user.role == "Admin":
                    return redirect(url_for("admin.dashboard"))
                if user.role == "Officer":
                    return redirect(url_for("officer_bp.dashboard"))
                if user.role == "Alumni":
                    return redirect(url_for("alumni_bp.dashboard")) # Check if blueprint is alumni or alumni_bp
                return redirect(url_for("student_bp.dashboard"))

            flash("Invalid username or password", "error")

        return render_template("login.html")

    # =====================================================
    # SIGNUP (Updated to set status='Pending')
    # =====================================================
    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        from database.db import get_connection

        if request.method == "POST":
            full_name = request.form.get("full_name", "").strip()
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            role = request.form.get("role", "").strip() # Student, Alumni, Officer

            if not full_name or not username or not password or not role:
                flash("Please fill all fields.", "error")
                return redirect(url_for("signup"))

            # Validate role again just in case
            if role not in ["Student", "Alumni", "Officer"]:
                flash("Invalid role selected.", "error")
                return redirect(url_for("signup"))

            conn = get_connection()
            cur = conn.cursor()

            # Check if username exists
            cur.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cur.fetchone():
                conn.close()
                flash("Username already exists.", "error")
                return redirect(url_for("signup"))

            # ✅ INSERT WITH 'Pending' STATUS
            # Note: We added 'status' to the INSERT statement
            try:
                cur.execute(
                    "INSERT INTO users (username, password, role, full_name, status) VALUES (?,?,?,?, 'Pending')",
                    (username, password, role, full_name)
                )
                conn.commit()
                flash("Account created! Please wait for Admin approval before logging in.", "info")
            except Exception as e:
                flash(f"Error creating account: {e}", "error")
            finally:
                conn.close()

            return redirect(url_for("login"))

        return render_template("signup.html")
    # =====================================================
    # LOGOUT
    # =====================================================
    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5500)