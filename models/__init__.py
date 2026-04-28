from .base       import db
from .audit      import AuditLog
from .user       import User, LoginLog
from .client     import ClientMaster, ClientBrand, ClientAddress
from .lead       import (Lead, LeadDiscussion, LeadAttachment,
                         LeadReminder, LeadNote, LeadActivityLog,
                         SampleOrder, Quotation, EmailTemplate, LeadContribution, ContributionConfig)
from .legacy     import Customer, CustomerAddress
from .master     import LeadStatus, LeadSource, LeadCategory, ProductRange, CategoryMaster, UOMMaster, HSNCode, NPDStatus, MilestoneStatus
from .employee   import Employee, Contractor, WishLog, SalaryConfig, SalaryComponent, EmployeeTypeMaster, EmployeeLocationMaster, DepartmentMaster, DesignationMaster
from .permission import Module, RolePermission, UserGridConfig, UserPermission
from .approval   import ApprovalRequest, ApprovalLevel
from .attendance import RawPunchLog, Attendance, HolidayMaster, LateShiftRule, LatePenaltyRule, EarlyComingRule
from .hr_rules import (HRShift, HRLocation, HRLateRule, HRLatePenaltySlab,
                       HREarlyGoingRule, HROvertimeRule, HRLeavePolicy, HRLeaveType,
                       HRLOPRule, HRAbsentRule, HRCompOffRule)
from .npd        import (NPDProject, MilestoneMaster, MilestoneLog, NPDMilestoneTemplate,
                         NPDFormulation, NPDPackingMaterial, NPDArtwork, NPDActivityLog,
                         NPDComment, NPDNote,
                         OfficeDispatchToken, OfficeDispatchItem,
                         SampleApprovalLog,
                         RDTrialLog)
from .packing    import PackingEntry
from .material  import MaterialType, MaterialGroup, Material

__all__ = [
    'db',
    'User', 'LoginLog',
    'ClientMaster', 'ClientBrand', 'ClientAddress',
    'Lead', 'LeadDiscussion', 'LeadAttachment',
    'LeadReminder', 'LeadNote', 'LeadActivityLog',
    'SampleOrder', 'Quotation', 'EmailTemplate', 'LeadContribution', 'ContributionConfig',
    'Customer', 'CustomerAddress',
    'LeadStatus', 'LeadSource', 'LeadCategory', 'ProductRange', 'NPDStatus', 'MilestoneStatus',
    'CategoryMaster', 'UOMMaster', 'HSNCode',
    'Employee', 'Contractor', 'WishLog', 'SalaryConfig', 'SalaryComponent',
    'EmployeeTypeMaster', 'EmployeeLocationMaster',
    'Module', 'RolePermission', 'UserGridConfig', 'UserPermission',
    'AuditLog',
    'ApprovalRequest', 'ApprovalLevel',
    'RawPunchLog', 'Attendance', 'HolidayMaster', 'LateShiftRule', 'LatePenaltyRule', 'EarlyComingRule',
    'DepartmentMaster', 'DesignationMaster',
    'HRShift', 'HRLocation', 'HRLateRule', 'HRLatePenaltySlab',
    'HREarlyGoingRule', 'HROvertimeRule', 'HRLeavePolicy', 'HRLeaveType',
    'HRLOPRule', 'HRAbsentRule', 'HRCompOffRule',
    # NPD / Product Development
    'NPDProject', 'MilestoneMaster', 'MilestoneLog', 'NPDMilestoneTemplate',
    'NPDFormulation', 'NPDPackingMaterial', 'NPDArtwork', 'NPDActivityLog', 'NPDComment', 'NPDNote',
    'OfficeDispatchToken', 'OfficeDispatchItem',
    'RDTrialLog',
    # Packing Department
    'PackingEntry',
    'MaterialType', 'MaterialGroup', 'Material',
]
