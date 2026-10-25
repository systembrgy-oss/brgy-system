from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid

# ==============================================================================
# AUDIT & SOFT DELETE ARCHITECTURE
# Prevents physical deletion of records from the database. Deleted records
# remain permanently archived for legal registry, compliance, and auditing.
# ==============================================================================
class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class SoftDeleteModel(models.Model):
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save()


# 1. ROLES (RBAC)
class Role(models.Model):
    RoleID = models.AutoField(primary_key=True)
    RoleName = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = 'Roles'
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'

    def __str__(self):
        return self.RoleName


# 2. PUROKS
class Purok(models.Model):
    PurokID = models.AutoField(primary_key=True)
    PurokName = models.CharField(max_length=100)
    ZoneNo = models.IntegerField()

    class Meta:
        db_table = 'Puroks'
        verbose_name = 'Purok'
        verbose_name_plural = 'Puroks'

    def __str__(self):
        return f"{self.PurokName} (Zone {self.ZoneNo})"


# 3. HOUSEHOLDS
class Household(SoftDeleteModel):
    HouseholdID = models.AutoField(primary_key=True)
    HouseholdNumber = models.CharField(max_length=50, unique=True)
    PurokID = models.ForeignKey(Purok, on_delete=models.CASCADE, db_column='PurokID', related_name='households')
    StreetAddress = models.CharField(max_length=255)

    class Meta:
        db_table = 'Households'
        verbose_name = 'Household'
        verbose_name_plural = 'Households'

    def __str__(self):
        return f"HH #{self.HouseholdNumber} - {self.StreetAddress}"


# 4. RESIDENTS
class Resident(SoftDeleteModel):
    SEX_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
    ]
    CIVIL_STATUS_CHOICES = [
        ('Single', 'Single'),
        ('Married', 'Married'),
        ('Widowed', 'Widowed'),
        ('Separated', 'Separated'),
        ('Divorced', 'Divorced'),
    ]
    EMPLOYMENT_CHOICES = [
        ('Employed', 'Employed'),
        ('Unemployed', 'Unemployed'),
        ('Self-Employed', 'Self-Employed'),
        ('Student', 'Student'),
        ('Retired', 'Retired'),
    ]

    ResidentID = models.AutoField(primary_key=True)
    FirstName = models.CharField(max_length=100)
    LastName = models.CharField(max_length=100)
    MiddleName = models.CharField(max_length=100, blank=True, null=True)
    Sex = models.CharField(max_length=10, choices=SEX_CHOICES)
    BirthDate = models.DateField()
    CivilStatus = models.CharField(max_length=50, choices=CIVIL_STATUS_CHOICES)
    IsVoter = models.BooleanField(default=False)
    EmploymentStatus = models.CharField(max_length=50, choices=EMPLOYMENT_CHOICES)
    ContactNo = models.CharField(max_length=20, blank=True, null=True)
    HouseholdID = models.ForeignKey(Household, on_delete=models.CASCADE, db_column='HouseholdID', related_name='residents')
    RelationshipToHead = models.CharField(max_length=50)

    class Meta:
        db_table = 'Residents'
        verbose_name = 'Resident'
        verbose_name_plural = 'Residents'

    def __str__(self):
        middle = f" {self.MiddleName[0]}." if self.MiddleName else ""
        return f"{self.LastName}, {self.FirstName}{middle}"

    @property
    def full_name(self):
        middle = f" {self.MiddleName}" if self.MiddleName else ""
        return f"{self.FirstName}{middle} {self.LastName}"

    @property
    def age(self):
        today = timezone.localdate()
        return today.year - self.BirthDate.year - ((today.month, today.day) < (self.BirthDate.month, self.BirthDate.day))


# 5. SECTORS
class Sector(models.Model):
    SectorID = models.AutoField(primary_key=True)
    SectorName = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = 'Sectors'
        verbose_name = 'Sector'
        verbose_name_plural = 'Sectors'

    def __str__(self):
        return self.SectorName


# 6. RESIDENT SECTORS (JUNCTION TABLE)
class ResidentSector(models.Model):
    ResidentID = models.ForeignKey(Resident, on_delete=models.CASCADE, db_column='ResidentID', related_name='resident_sectors')
    SectorID = models.ForeignKey(Sector, on_delete=models.CASCADE, db_column='SectorID', related_name='sector_residents')

    class Meta:
        db_table = 'ResidentSectors'
        unique_together = ('ResidentID', 'SectorID')
        verbose_name = 'Resident Sector'
        verbose_name_plural = 'Resident Sectors'

    def __str__(self):
        return f"{self.ResidentID} - {self.SectorID}"


# 7. SYSTEM USERS (RBAC AUTH)
class User(AbstractUser):
    RoleID = models.ForeignKey(Role, on_delete=models.PROTECT, null=True, blank=True, db_column='RoleID', related_name='users')
    ResidentID = models.OneToOneField(Resident, on_delete=models.SET_NULL, null=True, blank=True, db_column='ResidentID', related_name='user_account')
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def soft_delete(self):
        self.is_active = False
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()

    def restore(self):
        self.is_active = True
        self.is_deleted = False
        self.deleted_at = None
        self.save()

    @property
    def perm(self):
        return UserPermission.get_for_user(self)

    class Meta:
        db_table = 'Users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    @property
    def is_admin_role(self):
        return self.is_superuser or (self.RoleID and self.RoleID.RoleName == 'Admin')

    @property
    def is_staff_role(self):
        return self.is_admin_role or (self.RoleID and self.RoleID.RoleName == 'Staff')

    @property
    def is_people_role(self):
        return self.RoleID and self.RoleID.RoleName == 'People'


# 8. DOCUMENT TYPES
class DocumentType(models.Model):
    DocumentTypeID = models.AutoField(primary_key=True)
    DocumentTypeName = models.CharField(max_length=100)
    StandardFee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    TemplateBody = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'DocumentTypes'
        verbose_name = 'Document Type'
        verbose_name_plural = 'Document Types'

    def __str__(self):
        return f"{self.DocumentTypeName} (PHP {self.StandardFee:.2f})"


# 9. PAYMENTS
class Payment(models.Model):
    PaymentID = models.AutoField(primary_key=True)
    PaymentDate = models.DateTimeField(default=timezone.now)
    AmountPaid = models.DecimalField(max_digits=10, decimal_places=2)
    OfficialReceiptNo = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = 'Payments'
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'

    def __str__(self):
        return f"OR #{self.OfficialReceiptNo} - PHP {self.AmountPaid:.2f}"


# 10. DOCUMENT REQUESTS
class DocumentRequest(SoftDeleteModel):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Released', 'Released'),
        ('Rejected', 'Rejected'),
    ]

    RequestID = models.AutoField(primary_key=True)
    RequestDate = models.DateTimeField(default=timezone.now)
    Purpose = models.TextField()
    ResidentID = models.ForeignKey(Resident, on_delete=models.CASCADE, db_column='ResidentID', related_name='document_requests')
    DocumentTypeID = models.ForeignKey(DocumentType, on_delete=models.CASCADE, db_column='DocumentTypeID', related_name='requests')
    ProcessedByUserID = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_column='ProcessedByUserID', related_name='processed_documents')
    PaymentID = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True, db_column='PaymentID', related_name='document_requests')
    RequestStatus = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    QRCodeHash = models.CharField(max_length=100, unique=True, null=True, blank=True)
    DigitalSignaturePath = models.CharField(max_length=255, null=True, blank=True)
    AttachmentFile = models.FileField(upload_to='doc_attachments/', null=True, blank=True)
    IsDigitallyStamped = models.BooleanField(default=False)
    CustomLetterBody = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'DocumentRequests'
        verbose_name = 'Document Request'
        verbose_name_plural = 'Document Requests'

    def __str__(self):
        return f"Req #{self.RequestID} - {self.DocumentTypeID.DocumentTypeName} ({self.ResidentID})"

    def save(self, *args, **kwargs):
        if not self.QRCodeHash:
            self.QRCodeHash = f"BIMS-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)


# 11. BLOTTER / INCIDENTS
class Incident(SoftDeleteModel):
    CASE_STATUS_CHOICES = [
        ('Filed', 'Filed'),
        ('Under Mediation', 'Under Mediation'),
        ('Resolved', 'Resolved'),
        ('Escalated', 'Escalated'),
    ]

    IncidentID = models.AutoField(primary_key=True)
    IncidentDate = models.DateTimeField()
    ComplainantResidentID = models.ForeignKey(Resident, on_delete=models.CASCADE, db_column='ComplainantResidentID', related_name='filed_incidents')
    RespondentName = models.CharField(max_length=150)
    IncidentDetails = models.TextField()
    CaseStatus = models.CharField(max_length=30, choices=CASE_STATUS_CHOICES, default='Filed')
    IsConfidential = models.BooleanField(default=False)

    class Meta:
        db_table = 'Incidents'
        verbose_name = 'Incident / Blotter'
        verbose_name_plural = 'Incidents / Blotters'

    def __str__(self):
        return f"Case #{self.IncidentID}: vs {self.RespondentName} ({self.CaseStatus})"


# 12. INCIDENT HEARINGS
class IncidentHearing(models.Model):
    HearingID = models.AutoField(primary_key=True)
    IncidentID = models.ForeignKey(Incident, on_delete=models.CASCADE, db_column='IncidentID', related_name='hearings')
    HearingDate = models.DateTimeField()
    SummonsDetails = models.TextField(blank=True, null=True)
    Remarks = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'IncidentHearings'
        verbose_name = 'Incident Hearing'
        verbose_name_plural = 'Incident Hearings'

    def __str__(self):
        return f"Hearing for Case #{self.IncidentID_id} on {self.HearingDate}"


# 13. ASSISTANCE PROGRAMS
class AssistanceProgram(models.Model):
    ProgramID = models.AutoField(primary_key=True)
    ProgramName = models.CharField(max_length=150)
    Description = models.TextField(blank=True, null=True)
    DistributionDate = models.DateField()

    class Meta:
        db_table = 'AssistancePrograms'
        verbose_name = 'Assistance Program'
        verbose_name_plural = 'Assistance Programs'

    def __str__(self):
        return f"{self.ProgramName} ({self.DistributionDate})"


# 14. ASSISTANCE BENEFICIARIES
class AssistanceBeneficiary(models.Model):
    BeneficiaryLogID = models.AutoField(primary_key=True)
    ProgramID = models.ForeignKey(AssistanceProgram, on_delete=models.CASCADE, db_column='ProgramID', related_name='beneficiaries')
    ResidentID = models.ForeignKey(Resident, on_delete=models.CASCADE, db_column='ResidentID', related_name='assistances_received')
    QuantityOrAmountGiven = models.CharField(max_length=100)
    ReceivedDate = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'AssistanceBeneficiaries'
        unique_together = ('ProgramID', 'ResidentID')
        verbose_name = 'Assistance Beneficiary'
        verbose_name_plural = 'Assistance Beneficiaries'

    def __str__(self):
        return f"{self.ResidentID} - {self.ProgramID.ProgramName}"


# 15. HEALTH RECORDS
class HealthRecord(SoftDeleteModel):
    RECORD_TYPE_CHOICES = [
        ('Vaccination', 'Vaccination'),
        ('Maternal Care', 'Maternal Care'),
        ('General Checkup', 'General Checkup'),
    ]

    RecordID = models.AutoField(primary_key=True)
    ResidentID = models.ForeignKey(Resident, on_delete=models.CASCADE, db_column='ResidentID', related_name='health_records')
    RecordType = models.CharField(max_length=100)
    Details = models.TextField()
    RecordDate = models.DateField()

    class Meta:
        db_table = 'HealthRecords'
        verbose_name = 'Health Record'
        verbose_name_plural = 'Health Records'

    def __str__(self):
        return f"{self.RecordType} - {self.ResidentID} ({self.RecordDate})"


# 16. MEDICINE INVENTORY
class Medicine(SoftDeleteModel):
    MedicineID = models.AutoField(primary_key=True)
    MedicineName = models.CharField(max_length=100)
    Unit = models.CharField(max_length=50)
    CurrentStock = models.IntegerField(default=0)

    class Meta:
        db_table = 'Medicines'
        verbose_name = 'Medicine'
        verbose_name_plural = 'Medicines'

    def __str__(self):
        return f"{self.MedicineName} ({self.CurrentStock} {self.Unit})"


# 17. MEDICINE DISTRIBUTIONS
class MedicineDistribution(models.Model):
    DistributionID = models.AutoField(primary_key=True)
    MedicineID = models.ForeignKey(Medicine, on_delete=models.CASCADE, db_column='MedicineID', related_name='distributions')
    ResidentID = models.ForeignKey(Resident, on_delete=models.CASCADE, db_column='ResidentID', related_name='medicine_received')
    QuantityGiven = models.IntegerField()
    DistributionDate = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'MedicineDistributions'
        verbose_name = 'Medicine Distribution'
        verbose_name_plural = 'Medicine Distributions'

    def __str__(self):
        return f"{self.QuantityGiven} {self.MedicineID.Unit} {self.MedicineID.MedicineName} to {self.ResidentID}"


# 18. ANNOUNCEMENTS
class Announcement(SoftDeleteModel):
    AnnouncementID = models.AutoField(primary_key=True)
    Title = models.CharField(max_length=200)
    Content = models.TextField()
    Category = models.CharField(max_length=50)
    IsEmergency = models.BooleanField(default=False)
    IsPinned = models.BooleanField(default=False)
    PublishDate = models.DateTimeField(default=timezone.now)
    CreatedByUserID = models.ForeignKey(User, on_delete=models.CASCADE, db_column='CreatedByUserID', related_name='announcements')

    class Meta:
        db_table = 'Announcements'
        ordering = ['-IsPinned', '-IsEmergency', '-PublishDate']
        verbose_name = 'Announcement'
        verbose_name_plural = 'Announcements'

    def __str__(self):
        emergency_tag = "[EMERGENCY] " if self.IsEmergency else ""
        return f"{emergency_tag}{self.Title}"


# 19. AUDIT LOG (Security & Compliance)
class AuditLog(models.Model):
    LogID = models.AutoField(primary_key=True)
    UserID = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    Action = models.CharField(max_length=255)
    Module = models.CharField(max_length=100)
    IPAddress = models.CharField(max_length=50, blank=True, null=True)
    Timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'AuditLogs'
        ordering = ['-Timestamp']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'

    def __str__(self):
        user_name = self.UserID.username if self.UserID else "Anonymous/System"
        return f"[{self.Timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {user_name} - {self.Action} ({self.Module})"


# 20. BARANGAY SETTINGS (Dynamic LGU Branding & Signatories)
class BarangaySetting(models.Model):
    SettingID = models.AutoField(primary_key=True)
    BarangayName = models.CharField(max_length=150, default="Barangay San Roque")
    CityOrMunicipality = models.CharField(max_length=150, default="City Center")
    Province = models.CharField(max_length=150, default="Metro Manila")
    Region = models.CharField(max_length=150, default="National Capital Region")
    PunongBarangay = models.CharField(max_length=150, default="Hon. Ferdinand D. Morales")
    BarangaySecretary = models.CharField(max_length=150, default="Maria Clara Santos")
    BarangayTreasurer = models.CharField(max_length=150, default="Juanita Perez")
    ContactNumber = models.CharField(max_length=50, default="0917-888-BIMS")
    EmailAddress = models.EmailField(default="contact@barangaysanroque.gov.ph")
    BarangayHallAddress = models.CharField(max_length=255, default="Barangay Hall Complex, Mabini St.")
    # Official Seals and Letter Template Fields
    BarangayLogo = models.FileField(upload_to='seals/', null=True, blank=True)
    CityLogo = models.FileField(upload_to='seals/', null=True, blank=True)
    LetterOfficeHeader = models.CharField(max_length=200, default="OFFICE OF THE PUNONG BARANGAY")
    LetterSalutation = models.CharField(max_length=200, default="TO WHOM IT MAY CONCERN:")
    LetterBodyTemplate = models.TextField(blank=True, null=True)
    LetterClosing = models.CharField(max_length=255, default="Issued upon request of the above-named person for whatever legal intents and purposes it may serve.")
    LetterSignatoryTitle = models.CharField(max_length=150, default="Punong Barangay")
    ShowSealWatermark = models.BooleanField(default=True)

    class Meta:
        db_table = 'BarangaySettings'
        verbose_name = 'Barangay Setting'
        verbose_name_plural = 'Barangay Settings'

    def __str__(self):
        return f"{self.BarangayName}, {self.CityOrMunicipality}"

    @classmethod
    def get_settings(cls):
        obj, created = cls.objects.get_or_create(SettingID=1)
        return obj


# 21. CITIZEN REGISTRATIONS (Public Online Intake & Admin Review Gate)
class CitizenRegistration(SoftDeleteModel):
    STATUS_CHOICES = [
        ('Pending', 'Pending Review'),
        ('Approved', 'Approved & Activated'),
        ('Rejected', 'Rejected / Incomplete'),
    ]

    RegistrationID = models.AutoField(primary_key=True)
    ReferenceNumber = models.CharField(max_length=50, unique=True)
    Username = models.CharField(max_length=150, unique=True)
    PasswordHash = models.CharField(max_length=255)
    
    # Demographics
    FirstName = models.CharField(max_length=100)
    LastName = models.CharField(max_length=100)
    MiddleName = models.CharField(max_length=100, blank=True, null=True)
    Sex = models.CharField(max_length=10, choices=[('Male', 'Male'), ('Female', 'Female')])
    BirthDate = models.DateField()
    CivilStatus = models.CharField(max_length=50)
    EmploymentStatus = models.CharField(max_length=50)
    
    # Contact Info (Mobile is mandatory for notifications, Email optional)
    ContactNo = models.CharField(max_length=20)
    Email = models.EmailField(blank=True, null=True)
    
    # Residence Info
    PurokID = models.ForeignKey(Purok, on_delete=models.SET_NULL, null=True, db_column='PurokID')
    StreetAddress = models.CharField(max_length=255)
    HouseholdNumber = models.CharField(max_length=50)
    RelationshipToHead = models.CharField(max_length=50)
    Sectors = models.CharField(max_length=255, blank=True, null=True)
    
    # Verification Document (Valid ID or Utility Bill)
    ProofOfResidencyImage = models.FileField(upload_to='proof_of_residency/', blank=True, null=True)
    
    # Automated Census Match Flag
    ExistingResidentMatch = models.ForeignKey(Resident, on_delete=models.SET_NULL, null=True, blank=True, related_name='registration_applications')
    
    # Review Workflow
    Status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    AdminRemarks = models.TextField(blank=True, null=True)
    SubmittedAt = models.DateTimeField(default=timezone.now)
    ReviewedAt = models.DateTimeField(null=True, blank=True)
    ReviewedByUserID = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_registrations')

    class Meta:
        db_table = 'CitizenRegistrations'
        ordering = ['-SubmittedAt']
        verbose_name = 'Citizen Registration'
        verbose_name_plural = 'Citizen Registrations'

    def __str__(self):
        return f"{self.ReferenceNumber} - {self.FirstName} {self.LastName} ({self.Status})"

    def save(self, *args, **kwargs):
        if not self.ReferenceNumber:
            self.ReferenceNumber = f"REG-{timezone.now().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)


# 22. NOTIFICATIONS (Role-Based Notification System)
class Notification(models.Model):
    TYPE_CHOICES = [
        ('registration', 'Resident Registration'),
        ('document', 'Document Request'),
        ('incident', 'Blotter Incident'),
        ('announcement', 'Barangay Announcement'),
        ('system', 'System Alert'),
    ]

    NotificationID = models.AutoField(primary_key=True)
    RecipientUser = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    TargetRole = models.CharField(max_length=50, default='All')  # 'Admin', 'Staff', 'People', 'All'
    Title = models.CharField(max_length=200)
    Message = models.TextField()
    NotificationType = models.CharField(max_length=50, choices=TYPE_CHOICES, default='system')
    LinkURL = models.CharField(max_length=255, blank=True, null=True)
    IsRead = models.BooleanField(default=False)
    CreatedAt = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'Notifications'
        ordering = ['-CreatedAt']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        return f"[{self.NotificationType}] {self.Title} ({self.CreatedAt.strftime('%b %d, %H:%M')})"





# 23. USER PERMISSIONS (Granular Role-Based Action Privileges)
class UserPermission(models.Model):
    PermissionID = models.AutoField(primary_key=True)
    UserID = models.OneToOneField(User, on_delete=models.CASCADE, db_column='UserID', related_name='permissions')
    can_approve = models.BooleanField(default=False, help_text="Can approve citizen registrations and document requests")
    can_reject = models.BooleanField(default=False, help_text="Can reject citizen applications and clearance requests")
    can_add = models.BooleanField(default=False, help_text="Can add residents, households, blotter incidents, or inventory items")
    can_edit = models.BooleanField(default=False, help_text="Can edit records, citizen details, inventory, and blotter hearings")
    can_delete = models.BooleanField(default=False, help_text="Can delete records from system modules")
    can_distribute_medicine = models.BooleanField(default=False, help_text="Can dispense medicines and log health center pharmacy distributions")
    can_give_document = models.BooleanField(default=False, help_text="Can process, sign, and release official clearance documents")
    can_view_records = models.BooleanField(default=True, help_text="Can view system records and information")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'UserPermissions'
        verbose_name = 'User Permission'
        verbose_name_plural = 'User Permissions'

    def __str__(self):
        return f"Permissions for {self.UserID.username}"

    @classmethod
    def get_for_user(cls, user):
        if not user or not user.is_authenticated:
            return None
        role_name = user.RoleID.RoleName if user.RoleID else ''
        is_admin = user.is_superuser or role_name == 'Admin'
        is_staff = is_admin or role_name == 'Staff'
        perm, created = cls.objects.get_or_create(
            UserID=user,
            defaults={
                'can_approve': is_admin,
                'can_reject': is_admin,
                'can_add': is_staff,
                'can_edit': is_staff,
                'can_delete': is_admin,
                'can_distribute_medicine': is_staff,
                'can_give_document': is_staff,
                'can_view_records': True,
            }
        )
        return perm
