"""
models/npd.py
─────────────
Product Development Workflow (NPD) Models:
  - NPDProject        → Main project record (NPD or Existing Product path)
  - MilestoneMaster   → Milestones checklist per project
  - MilestoneLog      → History/updates per milestone
  - NPDFormulation    → R&D formulation & sampling loop
  - NPDSampleLog      → Sample send/reject/approve history
  - NPDPackingMaterial → Packing material tracking
  - NPDArtwork        → Artwork & design process
  - NPDActivityLog    → Auto timeline for project
"""

from datetime import datetime
from .base import db


# ─────────────────────────────────────────────────────────────
# NPD Project (Main Project Record)
# ─────────────────────────────────────────────────────────────

class NPDProject(db.Model):
    __tablename__ = 'npd_projects'

    id              = db.Column(db.Integer, primary_key=True)
    code            = db.Column(db.String(30), unique=True, nullable=True)   # NPD-0001

    # Path: 'npd' or 'existing'
    project_type    = db.Column(db.String(20), default='npd', nullable=False)

    # Status flow
    # npd: lead_created → npd_form → formulation → client_approved → commercial → milestones → complete/cancelled
    # existing: lead_created → sample_sent → client_review → commercial → milestones → complete/cancelled
    status          = db.Column(db.String(40), default='not_started', nullable=False)

    # Lead link
    lead_id         = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=True)

    # Client & Product Info
    client_name     = db.Column(db.String(200))
    client_company  = db.Column(db.String(200))
    client_email    = db.Column(db.String(150))
    client_phone    = db.Column(db.String(20))
    product_name    = db.Column(db.String(300), nullable=False)
    product_category= db.Column(db.String(100))
    product_range   = db.Column(db.String(100))

    # Extended Product Fields (from NPD form)
    area_of_application = db.Column(db.String(200))        # Face, Body, Hair, etc.
    market_level        = db.Column(db.String(300))        # Premium, Mass, etc.
    no_of_samples       = db.Column(db.Integer, default=0)
    moq                 = db.Column(db.String(100))        # Minimum Order Qty
    product_size        = db.Column(db.String(100))        # 50ml, 100g, etc.
    description         = db.Column(db.Text)               # Product description
    ingredients         = db.Column(db.Text)               # Full ingredient list
    active_ingredients  = db.Column(db.String(500))        # Active Ing Required
    video_link          = db.Column(db.String(500))        # Reference video URL
    reference_brand     = db.Column(db.String(200))        # e.g. Foxtale
    reference_product_name = db.Column(db.String(300))     # e.g. Foxtale Oil Face Wash
    variant_type        = db.Column(db.String(200))        # Variant/Variety/Type
    appearance          = db.Column(db.String(500))        # Clear gel, Cream, etc.
    product_claim       = db.Column(db.Text)               # Product claim
    label_claim         = db.Column(db.Text)               # Label claim
    costing_range       = db.Column(db.String(200))        # e.g. as per benchmark
    ph_value            = db.Column(db.String(50))         # pH value
    packaging_type      = db.Column(db.String(200))        # fliptop cap with bottle
    fragrance           = db.Column(db.String(200))        # Fragrance/Flavours
    viscosity           = db.Column(db.String(200))        # Viscosity
    priority            = db.Column(db.String(50), default='Normal')  # Urgent/High/Normal/Low
    project_start_date  = db.Column(db.Date)
    project_lead_days   = db.Column(db.Integer)            # Lead time in days
    project_end_date    = db.Column(db.Date)
    client_coordinator  = db.Column(db.String(200))        # Client side coordinator

    # NPD-specific fields
    npd_fee_paid    = db.Column(db.Boolean, default=False)
    npd_fee_amount  = db.Column(db.Numeric(10, 2), default=10000)
    npd_fee_receipt = db.Column(db.String(300))   # uploaded receipt filename
    reference_product = db.Column(db.String(300))
    custom_formulation= db.Column(db.Boolean, default=False)
    requirement_spec  = db.Column(db.Text)
    order_quantity  = db.Column(db.String(100))

    assigned_members    = db.Column(db.String(500))   # comma-separated employee IDs
    assigned_rd_members = db.Column(db.String(500))   # comma-separated R&D employee IDs
    client_id           = db.Column(db.Integer, db.ForeignKey('client_masters.id'), nullable=True)
    assigned_sc     = db.Column(db.Integer, db.ForeignKey('users.id'))     # Sales Coordinator
    assigned_rd     = db.Column(db.Integer, db.ForeignKey('users.id'))     # R&D person
    npd_poc         = db.Column(db.Integer, db.ForeignKey('users.id'))     # NPD POC (Shital/Dipika)

    # Conversion
    converted_to_commercial = db.Column(db.Boolean, default=False)
    commercial_converted_at = db.Column(db.DateTime)

    # Advance payment (₹2k for Existing→NPD conversion)
    advance_paid    = db.Column(db.Boolean, default=False)
    advance_amount  = db.Column(db.Numeric(10, 2), default=2000)
    advance_receipt = db.Column(db.String(300))

    # Milestone Master created?
    milestone_master_created = db.Column(db.Boolean, default=False)

    # TAT tracking
    target_sample_date   = db.Column(db.Date)
    last_connected       = db.Column(db.DateTime)   # last activity/contact date
    delay_reason         = db.Column(db.Text)
    last_delay_update    = db.Column(db.DateTime)

    # Cancellation
    cancel_reason   = db.Column(db.Text)
    cancelled_at    = db.Column(db.DateTime)

    # Started
    started_at      = db.Column(db.DateTime)

    # Finished
    finished_at     = db.Column(db.DateTime)

    # Total duration in seconds (started_at to finished_at)
    total_duration_seconds = db.Column(db.Integer, nullable=True)

    # Completion
    completed_at    = db.Column(db.DateTime)

    # R&D pre-defined parameter defaults per project (stored as JSON)
    rd_param_defaults = db.Column(db.Text, nullable=True)
    npd_milestone_data = db.Column(db.Text, nullable=True)  # JSON: {ms_1:{status,date}, ...}

    # Soft delete
    is_deleted      = db.Column(db.Boolean, default=False, nullable=False, server_default='0')
    deleted_at      = db.Column(db.DateTime, nullable=True)
    deleted_by      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Audit
    created_by      = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at      = db.Column(db.DateTime, default=datetime.now)
    updated_by      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_at      = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.utcnow)

    # Relationships
    lead            = db.relationship('Lead', backref='npd_projects', lazy=True, foreign_keys=[lead_id])
    sc_user         = db.relationship('User', backref='npd_sc_projects', lazy=True, foreign_keys=[assigned_sc])
    rd_user         = db.relationship('User', backref='npd_rd_projects', lazy=True, foreign_keys=[assigned_rd])
    poc_user        = db.relationship('User', backref='npd_poc_projects', lazy=True, foreign_keys=[npd_poc])
    creator         = db.relationship('User', backref='npd_created', lazy=True, foreign_keys=[created_by])

    milestones      = db.relationship('MilestoneMaster', backref='project', lazy=True,
                                      cascade='all, delete-orphan',
                                      order_by='MilestoneMaster.sort_order')
    formulations    = db.relationship('NPDFormulation', backref='project', lazy=True,
                                      cascade='all, delete-orphan',
                                      order_by='NPDFormulation.created_at')
    packing_materials = db.relationship('NPDPackingMaterial', backref='project', lazy=True,
                                        cascade='all, delete-orphan')
    artworks        = db.relationship('NPDArtwork', backref='project', lazy=True,
                                      cascade='all, delete-orphan')
    activity_logs   = db.relationship('NPDActivityLog', backref='project', lazy=True,
                                      cascade='all, delete-orphan',
                                      order_by='NPDActivityLog.created_at.desc()')
    comments        = db.relationship('NPDComment', backref='project', lazy=True,
                                      cascade='all, delete-orphan',
                                      order_by='NPDComment.created_at.desc()')

    @property
    def status_label(self):
        try:
            from models.master import NPDStatus
            s = NPDStatus.query.filter_by(slug=self.status).first()
            if s: return s.name
        except: pass
        # fallback
        return self.status.replace('_', ' ').title() if self.status else '—'

    @property
    def status_color(self):
        try:
            from models.master import NPDStatus
            s = NPDStatus.query.filter_by(slug=self.status).first()
            if s: return s.color
        except: pass
        return '#6b7280'

    @property
    def status_icon(self):
        try:
            from models.master import NPDStatus
            s = NPDStatus.query.filter_by(slug=self.status).first()
            if s: return s.icon
        except: pass
        return '🔵'

    @property
    def project_age(self):
        delta = datetime.now() - (self.created_at or datetime.now())
        return delta.days

    @property
    def rejection_ratio(self):
        """Calculate sample rejection ratio for this project."""
        total = len(self.formulations)
        if total == 0:
            return 0
        rejected = sum(1 for f in self.formulations if f.status == 'rejected')
        return round((rejected / total) * 100, 1)

    def __repr__(self):
        return f'<NPDProject {self.code} — {self.product_name}>'


# ─────────────────────────────────────────────────────────────
# Milestone Master (per project)
# ─────────────────────────────────────────────────────────────

class MilestoneMaster(db.Model):
    __tablename__ = 'milestone_masters'

    id          = db.Column(db.Integer, primary_key=True)
    project_id  = db.Column(db.Integer, db.ForeignKey('npd_projects.id'), nullable=False)

    # Milestone type
    milestone_type = db.Column(db.String(50), nullable=False)
    # Types: ingredients, quotation, packing_material, filling_trial, artwork,
    #        kld_mockup, qc_fda, barcode, po_draft, pi_po, documents, po_processing, handover

    title       = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    is_selected = db.Column(db.Boolean, default=True)  # only selected milestones are followed

    # Status: pending / in_progress / approved / rejected / skipped
    status      = db.Column(db.String(20), default='pending')

    sort_order  = db.Column(db.Integer, default=0)

    # Dates
    target_date = db.Column(db.Date)
    completed_at= db.Column(db.DateTime)

    # Assignments
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at = db.Column(db.DateTime)

    # Files / attachments (comma-sep filenames)
    attachments = db.Column(db.Text)

    # Notes
    notes       = db.Column(db.Text)
    reject_reason = db.Column(db.Text)

    created_by  = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at  = db.Column(db.DateTime, default=datetime.now)
    updated_at  = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.utcnow)

    assignee    = db.relationship('User', backref='assigned_milestones', lazy=True, foreign_keys=[assigned_to])
    approver    = db.relationship('User', backref='approved_milestones', lazy=True, foreign_keys=[approved_by])

    logs        = db.relationship('MilestoneLog', backref='milestone', lazy=True,
                                  cascade='all, delete-orphan',
                                  order_by='MilestoneLog.created_at.desc()')

    @property
    def status_color(self):
        return {'pending':'#6b7280','in_progress':'#f59e0b','approved':'#22c55e',
                'rejected':'#ef4444','skipped':'#9ca3af'}.get(self.status,'#6b7280')

    @property
    def status_icon(self):
        return {'pending':'⏳','in_progress':'🔄','approved':'✅',
                'rejected':'❌','skipped':'⏭️'}.get(self.status,'⏳')

    def __repr__(self):
        return f'<Milestone {self.title} [{self.status}]>'


class MilestoneLog(db.Model):
    __tablename__ = 'milestone_logs'

    id           = db.Column(db.Integer, primary_key=True)
    milestone_id = db.Column(db.Integer, db.ForeignKey('milestone_masters.id'), nullable=False)
    action       = db.Column(db.String(500), nullable=False)
    old_status   = db.Column(db.String(20))
    new_status   = db.Column(db.String(20))
    note         = db.Column(db.Text)
    created_by   = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at   = db.Column(db.DateTime, default=datetime.now)

    user         = db.relationship('User', backref='milestone_logs', lazy=True)

    def __repr__(self):
        return f'<MilestoneLog {self.action}>'


# ─────────────────────────────────────────────────────────────
# NPD Formulation / Sampling Loop
# ─────────────────────────────────────────────────────────────

class NPDFormulation(db.Model):
    __tablename__ = 'npd_formulations'

    id          = db.Column(db.Integer, primary_key=True)
    project_id  = db.Column(db.Integer, db.ForeignKey('npd_projects.id'), nullable=False)

    iteration   = db.Column(db.Integer, default=1)   # loop count
    formulation_name = db.Column(db.String(200))
    formulation_desc = db.Column(db.Text)

    # R&D
    rd_person   = db.Column(db.Integer, db.ForeignKey('users.id'))
    rd_notes    = db.Column(db.Text)
    rd_submitted_at = db.Column(db.DateTime)

    # SC Review
    sc_reviewed_by  = db.Column(db.Integer, db.ForeignKey('users.id'))
    sc_review_status= db.Column(db.String(20), default='pending')  # pending/approved/rejected
    sc_review_notes = db.Column(db.Text)
    sc_reviewed_at  = db.Column(db.DateTime)

    # Sample creation & dispatch
    sample_created  = db.Column(db.Boolean, default=False)
    sample_sent_at  = db.Column(db.DateTime)
    sample_sent_to  = db.Column(db.String(200))  # HO / Client

    # Client feedback
    client_status   = db.Column(db.String(20), default='pending')  # pending/approved/rejected
    client_feedback = db.Column(db.Text)
    client_responded_at = db.Column(db.DateTime)
    feedback_due_date   = db.Column(db.Date)  # usually 7 days

    # Overall status: pending / sc_approved / sc_rejected / client_approved / client_rejected
    status          = db.Column(db.String(30), default='pending')

    # File attachments
    attachments     = db.Column(db.Text)  # comma-sep filenames

    created_by      = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at      = db.Column(db.DateTime, default=datetime.now)
    updated_at      = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.utcnow)

    rd_user         = db.relationship('User', backref='rd_formulations', lazy=True, foreign_keys=[rd_person])
    sc_user         = db.relationship('User', backref='sc_formulations', lazy=True, foreign_keys=[sc_reviewed_by])
    creator         = db.relationship('User', backref='created_formulations', lazy=True, foreign_keys=[created_by])

    def __repr__(self):
        return f'<NPDFormulation project={self.project_id} iter={self.iteration} status={self.status}>'


# ─────────────────────────────────────────────────────────────
# Packing Material
# ─────────────────────────────────────────────────────────────

class NPDPackingMaterial(db.Model):
    __tablename__ = 'npd_packing_materials'

    id          = db.Column(db.Integer, primary_key=True)
    project_id  = db.Column(db.Integer, db.ForeignKey('npd_projects.id'), nullable=False)

    # Type: bottle / label / mono_carton / other
    pm_type     = db.Column(db.String(50))
    description = db.Column(db.Text)

    # Source: client_provided / company_sourced
    source      = db.Column(db.String(30), default='company_sourced')
    supplier    = db.Column(db.String(200))

    # Status: pending / sample_sent / client_approved / client_rejected / filling_trial / approved
    status      = db.Column(db.String(30), default='pending')

    sample_sent_at      = db.Column(db.DateTime)
    filling_trial_done  = db.Column(db.Boolean, default=False)
    filling_trial_at    = db.Column(db.DateTime)
    client_approved_at  = db.Column(db.DateTime)
    reject_reason       = db.Column(db.Text)

    notes       = db.Column(db.Text)
    attachments = db.Column(db.Text)
    cost        = db.Column(db.String(100), default='')
    is_deleted  = db.Column(db.Boolean, default=False)

    created_by  = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at  = db.Column(db.DateTime, default=datetime.now)
    updated_at  = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.utcnow)

    creator     = db.relationship('User', backref='packing_materials', lazy=True, foreign_keys=[created_by])

    def __repr__(self):
        return f'<NPDPackingMaterial {self.pm_type} [{self.status}]>'


# ─────────────────────────────────────────────────────────────
# Artwork & Design
# ─────────────────────────────────────────────────────────────

class NPDArtwork(db.Model):
    __tablename__ = 'npd_artworks'

    id          = db.Column(db.Integer, primary_key=True)
    project_id  = db.Column(db.Integer, db.ForeignKey('npd_projects.id'), nullable=False)

    iteration   = db.Column(db.Integer, default=1)
    title       = db.Column(db.String(200))
    description = db.Column(db.Text)

    designer    = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Artwork details
    ingredients_included  = db.Column(db.Boolean, default=False)
    content_included      = db.Column(db.Boolean, default=False)
    packaging_details     = db.Column(db.Boolean, default=False)

    # File
    artwork_file = db.Column(db.String(300))
    final_file   = db.Column(db.String(300))
    barcode_file = db.Column(db.String(300))

    # Status flow: draft / uploaded / sc_review / client_review / qc_review / approved / rejected
    status      = db.Column(db.String(30), default='draft')

    # SC review
    sc_status   = db.Column(db.String(20), default='pending')
    sc_notes    = db.Column(db.Text)
    sc_reviewed_by  = db.Column(db.Integer, db.ForeignKey('users.id'))
    sc_reviewed_at  = db.Column(db.DateTime)

    # Client review
    client_status   = db.Column(db.String(20), default='pending')
    client_feedback = db.Column(db.Text)
    client_approved_at = db.Column(db.DateTime)

    # QC review
    qc_status       = db.Column(db.String(20), default='pending')
    qc_notes        = db.Column(db.Text)
    qc_reviewed_by  = db.Column(db.Integer, db.ForeignKey('users.id'))
    qc_reviewed_at  = db.Column(db.DateTime)

    # Final approval (from DindaStrad / ops)
    final_approved  = db.Column(db.Boolean, default=False)
    final_approved_at = db.Column(db.DateTime)
    final_approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Barcode
    barcode_required = db.Column(db.Boolean, default=False)
    barcode_paid     = db.Column(db.Boolean, default=False)
    barcode_pi       = db.Column(db.String(200))
    barcode_received = db.Column(db.Boolean, default=False)
    barcode_received_at = db.Column(db.DateTime)

    notes       = db.Column(db.Text)

    created_by  = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at  = db.Column(db.DateTime, default=datetime.now)
    updated_at  = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.utcnow)

    designer_user   = db.relationship('User', backref='npd_artworks', lazy=True, foreign_keys=[designer])
    sc_reviewer     = db.relationship('User', backref='artwork_sc_reviews', lazy=True, foreign_keys=[sc_reviewed_by])
    qc_reviewer     = db.relationship('User', backref='artwork_qc_reviews', lazy=True, foreign_keys=[qc_reviewed_by])
    final_approver  = db.relationship('User', backref='artwork_final_approvals', lazy=True, foreign_keys=[final_approved_by])
    creator         = db.relationship('User', backref='created_artworks', lazy=True, foreign_keys=[created_by])

    def __repr__(self):
        return f'<NPDArtwork project={self.project_id} iter={self.iteration} [{self.status}]>'


# ─────────────────────────────────────────────────────────────
# NPD Activity Log
# ─────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
# NPD Comment (Discussion Board & Internal Discussion Board)
# ─────────────────────────────────────────────────────────────

class NPDComment(db.Model):
    __tablename__ = 'npd_comments'

    id          = db.Column(db.Integer, primary_key=True)
    project_id  = db.Column(db.Integer, db.ForeignKey('npd_projects.id'), nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    comment     = db.Column(db.Text, nullable=False)
    is_internal = db.Column(db.Boolean, default=False)
    milestone_key = db.Column(db.String(20), nullable=True)   # e.g. 'ms_1', 'ms_2'
    attachment  = db.Column(db.String(300), nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.now)

    user        = db.relationship('User', backref='npd_comments', lazy=True)


# ─────────────────────────────────────────────────────────────
# NPD Note (Rich text note per project)
# ─────────────────────────────────────────────────────────────

class NPDNote(db.Model):
    __tablename__ = 'npd_notes'

    id          = db.Column(db.Integer, primary_key=True)
    project_id  = db.Column(db.Integer, db.ForeignKey('npd_projects.id'), nullable=False, unique=True)
    content     = db.Column(db.Text)
    updated_by  = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_at  = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    editor      = db.relationship('User', backref='npd_notes', lazy=True)


class NPDActivityLog(db.Model):
    __tablename__ = 'npd_activity_logs'

    id          = db.Column(db.Integer, primary_key=True)
    project_id  = db.Column(db.Integer, db.ForeignKey('npd_projects.id'), nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'))
    action      = db.Column(db.String(500), nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.now)

    user        = db.relationship('User', backref='npd_activity_logs', lazy=True)

    def __repr__(self):
        return f'<NPDActivityLog project={self.project_id} — {self.action[:40]}>'


# ─────────────────────────────────────────────────────────────
# NPD Milestone Template Master (Admin configurable)
# ─────────────────────────────────────────────────────────────

class NPDMilestoneTemplate(db.Model):
    """
    Admin-managed master list of milestone types.
    When a new NPD/EPD project is created, these templates are
    used to generate the project's MilestoneMaster records.
    Admin can add / edit / reorder / toggle these from NPD Masters page.
    """
    __tablename__ = 'npd_milestone_templates'

    id              = db.Column(db.Integer, primary_key=True)
    milestone_type  = db.Column(db.String(50), nullable=False, unique=True)
    title           = db.Column(db.String(200), nullable=False)
    description     = db.Column(db.Text)
    icon            = db.Column(db.String(10), default='📌')

    # Which project paths this applies to: 'both' / 'npd' / 'existing'
    applies_to      = db.Column(db.String(20), default='both')

    # Whether selected by default when creating a new project
    default_selected= db.Column(db.Boolean, default=True)

    # Mandatory = cannot be deselected during project creation
    is_mandatory    = db.Column(db.Boolean, default=False)

    sort_order      = db.Column(db.Integer, default=0)
    is_active       = db.Column(db.Boolean, default=True)

    created_at      = db.Column(db.DateTime, default=datetime.now)
    created_by      = db.Column(db.Integer, nullable=True)
    modified_at     = db.Column(db.DateTime, nullable=True)
    modified_by     = db.Column(db.Integer, nullable=True)

    def __repr__(self):
        return f'<NPDMilestoneTemplate {self.milestone_type} — {self.title}>'


# ─────────────────────────────────────────────────────────────
# Office Dispatch Token  (Sample Ready → Send to Office)
# ─────────────────────────────────────────────────────────────

class OfficeDispatchToken(db.Model):
    __tablename__ = 'office_dispatch_tokens'

    id          = db.Column(db.Integer, primary_key=True)
    token_no    = db.Column(db.String(30), unique=True, nullable=False)  # ODT-0001
    dispatched_by   = db.Column(db.Integer, db.ForeignKey('users.id'))
    dispatched_at   = db.Column(db.DateTime, default=datetime.now)
    notes       = db.Column(db.Text)

    dispatcher  = db.relationship('User', backref='dispatch_tokens', lazy=True)
    items       = db.relationship('OfficeDispatchItem', backref='token', lazy=True,
                                  cascade='all, delete-orphan',
                                  order_by='OfficeDispatchItem.id')

    def __repr__(self):
        return f'<OfficeDispatchToken {self.token_no}>'


class OfficeDispatchItem(db.Model):
    __tablename__ = 'office_dispatch_items'

    id           = db.Column(db.Integer, primary_key=True)
    token_id     = db.Column(db.Integer, db.ForeignKey('office_dispatch_tokens.id'), nullable=False)
    project_id   = db.Column(db.Integer, db.ForeignKey('npd_projects.id'), nullable=False)
    sample_code  = db.Column(db.String(500), nullable=True)   # comma-sep e.g. SC-001, SC-002
    handover_to  = db.Column(db.String(200), nullable=True)   # free text — person name
    submitted_by = db.Column(db.String(200), nullable=True)   # free text — person name

    # ── Link back to the R&D sub-assignment (when dispatched from R&D Sample Log)
    # Nullable because NPD dispatches don't set this.
    rd_sub_assignment_id = db.Column(db.Integer,
                                     db.ForeignKey('rd_sub_assignments.id', ondelete='SET NULL'),
                                     nullable=True)

    # ── Sample Approval (post-dispatch review)
    # approval_status: 'pending' (default), 'approved', 'rejected'
    approval_status = db.Column(db.String(20), default='pending', nullable=False)
    reject_reason   = db.Column(db.Text,    nullable=True)       # only set when rejected
    actioned_by     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    actioned_at     = db.Column(db.DateTime, nullable=True)

    # ── Client Dispatch (post-approval — sent to client)
    # When operator selects approved items and dispatches to client,
    # these get stamped with the ClientDispatch batch reference.
    client_dispatch_id = db.Column(db.Integer,
                                   db.ForeignKey('client_dispatch.id', ondelete='SET NULL'),
                                   nullable=True)
    sent_to_client_at  = db.Column(db.DateTime, nullable=True)

    project         = db.relationship('NPDProject', backref='dispatch_items', lazy=True)
    rd_sub_assignment = db.relationship('RDSubAssignment', backref='dispatch_items', lazy=True)
    actioner        = db.relationship('User', foreign_keys=[actioned_by], lazy=True)
    client_dispatch = db.relationship('ClientDispatch',
                                      backref='items', lazy=True,
                                      foreign_keys=[client_dispatch_id])

    def __repr__(self):
        return f'<OfficeDispatchItem token={self.token_id} project={self.project_id}>'


# ─────────────────────────────────────────────────────────────
# R&D Project Log  — project-wise start/stop/assign events
# ─────────────────────────────────────────────────────────────
class RDProjectLog(db.Model):
    __tablename__ = 'rd_project_logs'

    id          = db.Column(db.Integer, primary_key=True)
    project_id  = db.Column(db.Integer, db.ForeignKey('npd_projects.id'), nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    event       = db.Column(db.String(50),  nullable=False)   # 'assigned','started','stopped','finished'
    detail      = db.Column(db.String(500), nullable=True)    # extra info e.g. member names
    created_at  = db.Column(db.DateTime,    default=datetime.now)

    project     = db.relationship('NPDProject', backref='rd_logs', lazy=True)
    user        = db.relationship('User',       backref='rd_project_logs', lazy=True)

    def __repr__(self):
        return f'<RDProjectLog project={self.project_id} event={self.event}>'


# ─────────────────────────────────────────────────────────────
# RD Sub Assignment — 1 project → multiple executives, each independent
# ─────────────────────────────────────────────────────────────
class RDSubAssignment(db.Model):
    __tablename__ = 'rd_sub_assignments'

    id            = db.Column(db.Integer, primary_key=True)
    project_id    = db.Column(db.Integer, db.ForeignKey('npd_projects.id', ondelete='CASCADE'), nullable=False)
    user_id       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)   # R&D Executive User
    variant_code  = db.Column(db.String(100), nullable=True)   # Manager ka custom code/variant
    sample_code   = db.Column(db.String(500), nullable=True)   # Comma-separated sample codes, e.g. "SMP001,SMP002,SMP003"
    notes         = db.Column(db.String(500), nullable=True)   # Extra info
    assigned_by   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    assigned_at   = db.Column(db.DateTime, default=datetime.now)

    # Independent timer per executive
    started_at    = db.Column(db.DateTime, nullable=True)
    finished_at   = db.Column(db.DateTime, nullable=True)
    status        = db.Column(db.String(20), default='not_started')  # not_started / in_progress / finished
    total_seconds = db.Column(db.Integer, default=0)

    is_active     = db.Column(db.Boolean, default=True)

    # ── Send-to-Office workflow (added) ─────────────────────────────
    # `status` can additionally take: 'sent_to_office'
    # Lifecycle: not_started → in_progress → finished → sent_to_office
    #                                          ↑  (revert returns here)
    send_to_office_date = db.Column(db.DateTime, nullable=True)
    sent_to_office_by   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    project       = db.relationship('NPDProject', backref='sub_assignments', lazy=True, foreign_keys=[project_id])
    executive     = db.relationship('User', backref='rd_sub_assignments', lazy=True, foreign_keys=[user_id])
    assigner      = db.relationship('User', backref='rd_assigned_by', lazy=True, foreign_keys=[assigned_by])
    sent_by_user  = db.relationship('User', backref='rd_sent_to_office', lazy=True, foreign_keys=[sent_to_office_by])

    def __repr__(self):
        return f'<RDSubAssignment proj={self.project_id} user={self.user_id} code={self.variant_code}>'


# ─────────────────────────────────────────────────────────────
# RD Trial Log — purpose-built table for R&D trial logging
# ─────────────────────────────────────────────────────────────
# Each row represents one trial / sample iteration logged by an
# R&D executive against a project. We keep this DELIBERATELY simple:
# project + sample_code + user + parameters + notes — no status
# workflow, no client review fields, no dispatch tracking.
#
# Why a separate table from NPDFormulation?
#   NPDFormulation has grown to 20+ columns covering the entire
#   sample-dispatch-and-review workflow (SC review, sample creation,
#   client feedback, etc.). The R&D trial-logging UI only needs the
#   five fields below; mixing the two concerns made the schema hard
#   to reason about and required us to drop columns the NPD module
#   was still relying on. Keep them separate.
#
# Stable name reference:
#   `rd_user_id` is the live FK to users — query/filter by this.
#   `rd_user_name` is the snapshot at insert time — display this so
#   the UI doesn't shift when users.full_name is later edited.
class RDTrialLog(db.Model):
    __tablename__ = 'rd_trial_logs'

    id              = db.Column(db.Integer, primary_key=True)

    project_id      = db.Column(db.Integer,
                                db.ForeignKey('npd_projects.id', ondelete='CASCADE'),
                                nullable=False, index=True)

    sample_code     = db.Column(db.String(100), nullable=False)

    rd_user_id      = db.Column(db.Integer,
                                db.ForeignKey('users.id'),
                                nullable=False, index=True)
    rd_user_name    = db.Column(db.String(200))

    parameters_json = db.Column(db.Text)
    observations    = db.Column(db.Text)

    created_at      = db.Column(db.DateTime, default=datetime.now)
    updated_at      = db.Column(db.DateTime, default=datetime.now,
                                onupdate=datetime.now)

    # Relationships — eager loading off, opt in via .options(joinedload(...))
    project = db.relationship('NPDProject', backref='rd_trial_logs',
                              lazy=True, foreign_keys=[project_id])
    rd_user = db.relationship('User', backref='rd_trial_logs',
                              lazy=True, foreign_keys=[rd_user_id])

    def __repr__(self):
        return f'<RDTrialLog proj={self.project_id} sample={self.sample_code} user={self.rd_user_id}>'


# ─────────────────────────────────────────────────────────────
# Sample Approval Log — audit trail for approve/reject/reset
# ─────────────────────────────────────────────────────────────
class SampleApprovalLog(db.Model):
    __tablename__ = 'sample_approval_logs'

    id              = db.Column(db.Integer, primary_key=True)
    item_id         = db.Column(db.Integer, db.ForeignKey('office_dispatch_items.id', ondelete='SET NULL'), nullable=True)
    project_id      = db.Column(db.Integer, db.ForeignKey('npd_projects.id'), nullable=True)
    action          = db.Column(db.String(20), nullable=False)    # approve / reject / reset
    reason          = db.Column(db.Text, nullable=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    whatsapp_sent   = db.Column(db.Boolean, default=False, nullable=False)
    created_at      = db.Column(db.DateTime, default=datetime.now, nullable=False)

    # Snapshot of what the project looked like before reject, so we can undo if needed
    prev_project_status = db.Column(db.String(50), nullable=True)
    prev_assigned_rd    = db.Column(db.Integer, nullable=True)

    item    = db.relationship('OfficeDispatchItem',
                              foreign_keys=[item_id],
                              backref=db.backref('approval_logs', lazy=True),
                              lazy=True)
    project = db.relationship('NPDProject', foreign_keys=[project_id], lazy=True)
    user    = db.relationship('User', foreign_keys=[user_id], lazy=True)

    def __repr__(self):
        return f'<SampleApprovalLog item={self.item_id} action={self.action}>'


# ──────────────────────────────────────────────────────────────────────
# ClientDispatch — "Send Approved Samples to Client" workflow
# ──────────────────────────────────────────────────────────────────────
# Once OfficeDispatchItem.approval_status='approved', operator can batch
# selected items and send to client. Each batch creates one ClientDispatch
# row (token + tracking + email/whatsapp flags) and stamps every item
# with client_dispatch_id + sent_to_client_at.
#
# Companion DB columns on office_dispatch_items added by SQL migration:
#   - client_dispatch_id (FK to client_dispatch.id, nullable)
#   - sent_to_client_at  (datetime, nullable)
# ──────────────────────────────────────────────────────────────────────
class ClientDispatch(db.Model):
    __tablename__ = 'client_dispatch'

    id            = db.Column(db.Integer, primary_key=True)
    token_no      = db.Column(db.String(50), nullable=False)
    project_id    = db.Column(db.Integer,
                              db.ForeignKey('npd_projects.id'),
                              nullable=False)
    courier_name  = db.Column(db.String(100))
    tracking_no   = db.Column(db.String(150))
    extra_notes   = db.Column(db.Text)
    email_sent_to = db.Column(db.String(200))
    email_sent_at = db.Column(db.DateTime)
    whatsapp_sent = db.Column(db.Boolean, default=False, nullable=False)
    dispatched_by = db.Column(db.Integer,
                              db.ForeignKey('users.id'), nullable=False)
    dispatched_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    project    = db.relationship('NPDProject',
                                 backref='client_dispatches', lazy=True)
    dispatcher = db.relationship('User',
                                 foreign_keys=[dispatched_by], lazy=True)

    def __repr__(self):
        return f'<ClientDispatch {self.token_no} project={self.project_id}>'
