from flask_login import UserMixin
from database.db import get_connection

class User(UserMixin):
    def __init__(
        self,
        id,
        username,
        password,
        role,
        full_name=None,
        email=None,
        phone=None,
        address=None,
        headline=None,
        location=None,
        bio=None,
        skills=None,
        status="Pending"  # ✅ Added status field (Default to Pending)
    ):
        self.id = id
        self.username = username
        self.password = password
        self.role = role
        self.full_name = full_name
        self.email = email
        self.phone = phone
        self.address = address
        self.headline = headline
        self.location = location
        self.bio = bio
        self.skills = skills
        self.status = status  # ✅ Assign to self

    @staticmethod
    def from_row(row):
        """
        row can be sqlite3.Row.
        Convert to dict so .get() works safely even if some columns don't exist.
        """
        d = dict(row)

        return User(
            id=d.get("id"),
            username=d.get("username"),
            password=d.get("password"),
            role=d.get("role"),
            full_name=d.get("full_name") or d.get("name"),
            email=d.get("email"),
            phone=d.get("phone") or d.get("phone_number"),
            address=d.get("address"),
            headline=d.get("headline"),
            location=d.get("location"),
            bio=d.get("bio"),
            skills=d.get("skills"),
            status=d.get("status", "Pending")  # ✅ Extract status from DB (Default to Pending if missing)
        )

    @staticmethod
    def get(user_id):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        return User.from_row(row) if row else None

    @staticmethod
    def find_by_username(username):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        conn.close()
        return User.from_row(row) if row else None

    @staticmethod
    def find_by_email(email):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        conn.close()
        return User.from_row(row) if row else None