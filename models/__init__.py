from .base       import db
from .supplier   import Supplier
from .audit      import AuditLog
from .user       import User, LoginLog
from .client     import ClientMaster, ClientBrand, ClientAddress
from .lead       import (Lead, LeadDiscussion, LeadAttachment,
                         LeadReminder, LeadNote, LeadActivityLog,
                         SampleOrder, Quotation, EmailTemplate, LeadContribution, ContributionConfig)
from .legacy     import Customer, CustomerAddress
from .master     import LeadStatus, LeadSource, LeadCategory, ProductRange, CategoryMaster, UOMMaster, HSNCode, NPDStatus, MilestoneStatus, QCParamOption
from .employee   import Employee, Contractor, WishLog, SalaryConfig, SalaryComponent, EmployeeTypeMaster, EmployeeLocationMaster, DepartmentMaster, DesignationMaster, CountryMaster, StateMaster, NationalityMaster, QualificationMaster, GradeMaster
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
from .material  import MaterialType, MaterialGroup, Material, ItemCategory
from .formulation import Formulation, FormulationIngredient
from .packing_bom import PackingBOM, PackingBOMItem
from .raw_material_sample import (RawMaterialSampleRequest, RMSActivityLog,
                                   RMSNotification, RMSDailyAck,
                                   RMS_STATUSES, RMS_STATUS_LABELS, RMS_STATUS_COLORS)

__all__ = [
    'db',
    'User', 'LoginLog',
    'ClientMaster', 'ClientBrand', 'ClientAddress',
    'Lead', 'LeadDiscussion', 'LeadAttachment',
    'LeadReminder', 'LeadNote', 'LeadActivityLog',
    'SampleOrder', 'Quotation', 'EmailTemplate', 'LeadContribution', 'ContributionConfig',
    'Customer', 'CustomerAddress',
    'LeadStatus', 'LeadSource', 'LeadCategory', 'ProductRange', 'NPDStatus', 'MilestoneStatus',
    'CategoryMaster', 'UOMMaster', 'HSNCode', 'QCParamOption',
    'Employee', 'Contractor', 'WishLog', 'SalaryConfig', 'SalaryComponent',
    'EmployeeTypeMaster', 'EmployeeLocationMaster',
    'NationalityMaster',
    'QualificationMaster',
    'GradeMaster',
    'CountryMaster', 'StateMaster',
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
    'MaterialType', 'MaterialGroup', 'Material', 'ItemCategory',
    'Formulation', 'FormulationIngredient',
    'PackingBOM', 'PackingBOMItem',
    'Supplier',
    # Raw Material Sample Request module
    'RawMaterialSampleRequest', 'RMSActivityLog', 'RMSNotification', 'RMSDailyAck',
]
