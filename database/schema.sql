
-- CREATE TABLE Student (
--     StudentID INT AUTO_INCREMENT PRIMARY KEY,
--     UserID INT UNIQUE,
--     Major VARCHAR(100),
--     EnrollmentYear YEAR,
--     FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE CASCADE
-- );

-- CREATE TABLE Alumni (
--     AlumniID INT AUTO_INCREMENT PRIMARY KEY,
--     UserID INT UNIQUE,
--     GraduationYear YEAR,
--     CurrentJob VARCHAR(100),
--     Industry VARCHAR(100),
--     FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE CASCADE
-- );

-- CREATE TABLE Career_Officer (
--     OfficerID INT AUTO_INCREMENT PRIMARY KEY,
--     UserID INT UNIQUE,
--     Department VARCHAR(100),
--     FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE CASCADE
-- );

-- CREATE TABLE Admin (
--     AdminID INT AUTO_INCREMENT PRIMARY KEY,
--     UserID INT UNIQUE,
--     AdminLevel VARCHAR(50),
--     FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE CASCADE
-- );

-- CREATE TABLE Notification (
--     NotificationID INT AUTO_INCREMENT PRIMARY KEY,
--     UserID INT,
--     Message TEXT,
--     Type VARCHAR(50),
--     IsRead BOOLEAN DEFAULT FALSE,
--     FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE CASCADE
-- );

-- CREATE TABLE Feedback (
--     FeedbackID INT AUTO_INCREMENT PRIMARY KEY,
--     UserID INT,
--     Category VARCHAR(50),
--     Comments TEXT,
--     Rating INT CHECK (Rating BETWEEN 1 AND 5),
--     FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE CASCADE
-- );

-- CREATE TABLE Event (
--     EventID INT AUTO_INCREMENT PRIMARY KEY,
--     Title VARCHAR(100),
--     Description TEXT,
--     EventDate DATE,
--     Location VARCHAR(100),
--     CreatedBy_AdminID INT,
--     FOREIGN KEY (CreatedBy_AdminID) REFERENCES Admin(AdminID)
-- );

-- CREATE TABLE Event_Registration (
--     RegistrationID INT AUTO_INCREMENT PRIMARY KEY,
--     UserID INT,
--     EventID INT,
--     RegistrationDate DATE,
--     Status VARCHAR(50),
--     FOREIGN KEY (UserID) REFERENCES Users(UserID),
--     FOREIGN KEY (EventID) REFERENCES Event(EventID)
-- );

-- CREATE TABLE Job_Application (
--     ApplicationID INT AUTO_INCREMENT PRIMARY KEY,
--     JobID INT,
--     StudentID INT,
--     AppliedDate DATE,
--     Status VARCHAR(50),
--     FOREIGN KEY (JobID) REFERENCES Job_Post(JobID),
--     FOREIGN KEY (StudentID) REFERENCES Student(StudentID)
-- );

-- CREATE TABLE Mentorship_Request (
--     RequestID INT AUTO_INCREMENT PRIMARY KEY,
--     Mentee_StudentID INT,
--     Mentor_AlumniID INT,
--     Goals TEXT,
--     Reason TEXT,
--     Status VARCHAR(50),
--     FOREIGN KEY (Mentee_StudentID) REFERENCES Student(StudentID),
--     FOREIGN KEY (Mentor_AlumniID) REFERENCES Alumni(AlumniID)
-- );

PRAGMA foreign_keys = ON;

-- USERS
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL,
  role TEXT NOT NULL,              -- Student / Alumni / Officer
  full_name TEXT,
  headline TEXT,                   -- e.g., "Software Engineering Student at MMU"
  bio TEXT,                        -- e.g., "Passionate about AI and Data Science."
  location TEXT,                   -- e.g., "Cyberjaya, Malaysia"
  skills TEXT ,
  email TEXT,
  phone INT,    
  address TEXT,
  status TEXT DEFAULT 'Pending'   -- e.g., "Python, SQL, Flask"
);

-- JOBS
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_title TEXT NOT NULL,
  company TEXT NOT NULL,
  job_type TEXT,
  deadline TEXT NOT NULL,
  location TEXT,
  salary TEXT,
  description TEXT NOT NULL,
  requirements TEXT NOT NULL,
  notes TEXT,
  status TEXT DEFAULT 'Published',
  created_at TEXT DEFAULT (datetime('now','+8 hours'))
);

CREATE TABLE IF NOT EXISTS Job_Post (
    JobID INT AUTO_INCREMENT PRIMARY KEY,
    Title VARCHAR(100),
    Description TEXT,
    Requirements TEXT,
    Status VARCHAR(50),
    PostedBy_AlumniID INT,
    ApprovedBy_OfficerID INT,
    FOREIGN KEY (PostedBy_AlumniID) REFERENCES Alumni(AlumniID),
    FOREIGN KEY (ApprovedBy_OfficerID) REFERENCES Career_Officer(OfficerID)
);


-- APPLICATIONS (✅ MATCH YOUR REAL TABLE)
CREATE TABLE IF NOT EXISTS applications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER,
  user_id INTEGER,
  applicant_name TEXT,
  applicant_identifier TEXT NOT NULL,
  applicant_role TEXT,
  applied_date TEXT DEFAULT (date('now')),
  status TEXT DEFAULT 'Pending',
  resume_file TEXT,
  FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
);


-- ✅ EVENTS
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  location TEXT,
  date_str TEXT,
  time_str TEXT,
  description TEXT,
  created_by INTEGER,                 -- who created it (optional)
  created_at TEXT DEFAULT (datetime('now','+8 hours')),
  status TEXT DEFAULT 'Active',
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

-- ✅ EVENT REGISTRATION
CREATE TABLE IF NOT EXISTS event_registrations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  event_id INTEGER NOT NULL,
  created_at TEXT DEFAULT (datetime('now','+8 hours')),
  UNIQUE(user_id, event_id),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
);

-- ✅ EVENT FEEDBACK (Submit Event Feedback feature)
CREATE TABLE IF NOT EXISTS event_feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id INTEGER NOT NULL,
  user_id INTEGER,                    -- NULL if anonymous
  is_anonymous INTEGER DEFAULT 0,      -- 0/1
  title TEXT NOT NULL,
  rating INT CHECK (rating BETWEEN 1 AND 5),
  description TEXT NOT NULL,
  attachment_file TEXT,               -- optional file path
  created_at TEXT DEFAULT (datetime('now','+8 hours')),
  FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- ✅ NOTIFICATIONS
CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  notif_type TEXT NOT NULL,
  target_group TEXT NOT NULL,
  title TEXT NOT NULL,
  message TEXT NOT NULL,
  schedule_mode TEXT DEFAULT 'now',
  scheduled_at TEXT,
  status TEXT DEFAULT 'Sent',
  created_at TEXT DEFAULT (datetime('now','+8 hours'))
);

-- ✅ MENTORSHIP
CREATE TABLE IF NOT EXISTS mentorship (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL,
  mentor_id INTEGER NOT NULL,
  status TEXT DEFAULT 'Pending',
  created_at TEXT DEFAULT (datetime('now','+8 hours')),
  UNIQUE(student_id, mentor_id),
  FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (mentor_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ✅ MENTORSHIP REQUESTS (if you still want separate table)
CREATE TABLE IF NOT EXISTS mentorship_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    mentor_id INTEGER NOT NULL,
    mentee_name TEXT NOT NULL,
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


CREATE TABLE IF NOT EXISTS Testimonial (
    TestimonialID INT AUTO_INCREMENT PRIMARY KEY,
    AlumniID INT,
    Content TEXT,
    DateSubmitted DATE,
    IsApproved BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (AlumniID) REFERENCES Alumni(AlumniID)
);