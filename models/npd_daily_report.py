"""
models/npd_daily_report.py
──────────────────────────
NPD Daily Work Report Dashboard — Database Models

Tables:
  - NPDWorkActivityLog      → Enhanced per-action activity tracker (auto-fed from NPDActivityLog hooks)
  - NPDDailyReport          → Aggregated daily summary snapshots
  - NPDEmployeeProductivity → Per-employee per-day productivity metrics
  - NPDTaskTimeTracking     → Session-level time tracking per user per project

These tables are populated automatically via SQLAlchemy event listeners
(see npd_daily_report_routes.py → register_activity_hooks()).
No manual entry is required from NPD team members.
"""

from datetime import datetime, date
from .base import db


# ─────────────────────────────────────────────────────────────
# 1. Work Activity Log  (mirrors + enriches NPDActivityLog)
# ─────────────────────────────────────────────────────────────

class NPDWorkActivityLog(db.Model):
    """
    Stores every NPD team action with rich metadata for dashboard analytics.

    Populated automatically via two routes:
      a) SQLAlchemy after_insert event on NPDActivityLog
      b) Direct calls from npd_daily_report_routes.track_activity()

    action_type values (used for grouping):
        task_created  | task_updated | task_completed | status_changed
        milestone_updated | comment_added | formulation_added
        artwork_uploaded  | packing_updated | project_viewed
        project_closed    | project_deleted
    """
    __tablename__ = 'npd_work_activity_logs'

    id              = db.Column(db.Integer, primary_key=True)
    project_id      = db.Column(db.Integer, db.ForeignKey('npd_projects.id'), nullable=False)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    employee_id     = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)

    # Category of action
    action_type     = db.Column(db.String(50), nullable=False, default='task_updated')
    # Human-readable description (copied from NPDActivityLog.action)
    action_detail   = db.Column(db.String(600), nullable=False)

    # Status transition metadata
    old_status      = db.Column(db.String(50), nullable=True)
    new_status      = db.Column(db.String(50), nullable=True)

    # Linked entities (optional)
    milestone_id    = db.Column(db.Integer, nullable=True)

    # Time tracking — seconds spent on THIS action's session
    # Populated by NPDTaskTimeTracking aggregation (cron every hour)
    time_spent_seconds = db.Column(db.Integer, default=0)

    # The calendar date this activity counts towards (for daily bucketing)
    activity_date   = db.Column(db.Date, default=date.today, nullable=False, index=True)

    created_at      = db.Column(db.DateTime, default=datetime.now, nullable=False)

    # Relationships
    project         = db.relationship('NPDProject', backref='work_activity_logs', lazy=True)
    user            = db.relationship('User', backref='work_activity_logs', lazy=True)

    def __repr__(self):
        return f'<NPDWorkActivityLog proj={self.project_id} type={self.action_type}>'


# ─────────────────────────────────────────────────────────────
# 2. Task Time Tracking  (session-level)
# ─────────────────────────────────────────────────────────────

class NPDTaskTimeTracking(db.Model):
    """
    Tracks how long each user actively works on a project in a single session.

    A session starts when a user opens/updates a project and ends either:
      - When they explicitly leave (next route visit closes the session), OR
      - After SESSION_TIMEOUT_MINUTES (default 30) minutes of inactivity.

    Populated via the /npd/api/time-ping endpoint called by the frontend
    every 60 seconds while the user is on a project view page.
    """
    __tablename__ = 'npd_task_time_tracking'

    id              = db.Column(db.Integer, primary_key=True)
    project_id      = db.Column(db.Integer, db.ForeignKey('npd_projects.id'), nullable=False)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    employee_id     = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)

    session_start   = db.Column(db.DateTime, default=datetime.now, nullable=False)
    session_end     = db.Column(db.DateTime, nullable=True)
    # Calculated on session close or daily cron
    duration_seconds = db.Column(db.Integer, default=0)

    action_type     = db.Column(db.String(50), default='project_viewed')
    activity_date   = db.Column(db.Date, default=date.today, nullable=False, index=True)

    # Indicates if this session was automatically closed by timeout
    auto_closed     = db.Column(db.Boolean, default=False)

    created_at      = db.Column(db.DateTime, default=datetime.now)

    project         = db.relationship('NPDProject', backref='time_tracking', lazy=True)
    user            = db.relationship('User', backref='time_tracking_sessions', lazy=True)

    @property
    def duration_minutes(self):
        return round((self.duration_seconds or 0) / 60, 1)

    def __repr__(self):
        return f'<NPDTaskTimeTracking proj={self.project_id} user={self.user_id} dur={self.duration_seconds}s>'


# ─────────────────────────────────────────────────────────────
# 3. Employee Productivity  (daily rollup)
# ─────────────────────────────────────────────────────────────

class NPDEmployeeProductivity(db.Model):
    """
    One row per (user, date) — aggregated daily stats for each NPD team member.

    Populated/refreshed by:
      - /npd/api/refresh-productivity  (called after each activity event)
      - Nightly cron via /npd/api/generate-daily-report?auto=1

    productivity_score (0–100) formula:
        score = min(100, (tasks_completed * 20) + (tasks_updated * 5)
                         + min(40, total_time_hours * 5))
    """
    __tablename__ = 'npd_employee_productivity'

    id                  = db.Column(db.Integer, primary_key=True)
    user_id             = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    employee_id         = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    report_date         = db.Column(db.Date, nullable=False, index=True)

    # Counters
    tasks_created       = db.Column(db.Integer, default=0)
    tasks_completed     = db.Column(db.Integer, default=0)
    tasks_updated       = db.Column(db.Integer, default=0)
    milestones_updated  = db.Column(db.Integer, default=0)
    comments_added      = db.Column(db.Integer, default=0)
    status_changes      = db.Column(db.Integer, default=0)
    total_actions       = db.Column(db.Integer, default=0)

    # Time
    total_time_seconds  = db.Column(db.Integer, default=0)
    active_sessions     = db.Column(db.Integer, default=0)

    # Score
    productivity_score  = db.Column(db.Float, default=0.0)   # 0–100

    # Computed helpers
    avg_task_time_seconds = db.Column(db.Integer, default=0)

    computed_at         = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    user                = db.relationship('User', backref='npd_productivity', lazy=True)

    __table_args__      = (db.UniqueConstraint('user_id', 'report_date', name='uq_npd_emp_prod'),)

    @property
    def total_time_hours(self):
        return round((self.total_time_seconds or 0) / 3600, 2)

    @property
    def total_time_label(self):
        secs = self.total_time_seconds or 0
        h, rem = divmod(secs, 3600)
        m = rem // 60
        if h:
            return f'{h}h {m}m'
        return f'{m}m'

    def recalculate_score(self):
        """Recompute productivity_score in-place."""
        score = (
            (self.tasks_completed or 0) * 20 +
            (self.tasks_updated    or 0) * 5  +
            (self.milestones_updated or 0) * 8 +
            (self.comments_added   or 0) * 3  +
            min(40, self.total_time_hours * 5)
        )
        self.productivity_score = round(min(100.0, score), 1)

    def __repr__(self):
        return f'<NPDEmployeeProductivity user={self.user_id} date={self.report_date} score={self.productivity_score}>'


# ─────────────────────────────────────────────────────────────
# 4. Daily Report  (one per calendar day)
# ─────────────────────────────────────────────────────────────

class NPDDailyReport(db.Model):
    """
    One row per calendar day — stores the fully-aggregated daily snapshot.

    report_data (JSON text) contains:
    {
        "total_tasks_worked": int,
        "completed_tasks": int,
        "pending_tasks": int,
        "late_tasks": int,
        "new_tasks_today": int,
        "active_employees": int,
        "top_employee": {"user_id": int, "name": str, "score": float},
        "employee_summary": [
            {"name": str, "completed": int, "updated": int,
             "time_label": str, "score": float},
            ...
        ],
        "recently_updated": [
            {"project_code": str, "product_name": str, "status": str,
             "updated_by": str, "updated_at": str},
            ...
        ],
        "dept_summary": { "NPD": {"completed":int,"pending":int}, ... }
    }

    Generated by /npd/api/generate-daily-report.
    Cron command: curl -X POST https://<host>/npd/api/generate-daily-report
    """
    __tablename__ = 'npd_daily_reports'

    id              = db.Column(db.Integer, primary_key=True)
    report_date     = db.Column(db.Date, nullable=False, unique=True, index=True)

    # Denormalised counters for fast dashboard card rendering
    total_tasks_worked  = db.Column(db.Integer, default=0)
    completed_tasks     = db.Column(db.Integer, default=0)
    pending_tasks       = db.Column(db.Integer, default=0)
    late_tasks          = db.Column(db.Integer, default=0)
    new_tasks_today     = db.Column(db.Integer, default=0)
    active_employees    = db.Column(db.Integer, default=0)
    total_time_seconds  = db.Column(db.Integer, default=0)

    # Full JSON snapshot for WhatsApp & rich rendering
    report_data         = db.Column(db.Text, nullable=True)   # JSON

    # Lifecycle
    is_finalized        = db.Column(db.Boolean, default=False)
    generated_at        = db.Column(db.DateTime, default=datetime.now)
    finalized_at        = db.Column(db.DateTime, nullable=True)
    generated_by        = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    @property
    def total_time_label(self):
        secs = self.total_time_seconds or 0
        h, rem = divmod(secs, 3600)
        m = rem // 60
        return f'{h}h {m}m' if h else f'{m}m'

    def __repr__(self):
        return f'<NPDDailyReport {self.report_date} tasks={self.total_tasks_worked}>'
