from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    Role, Purok, Household, Resident, Sector, ResidentSector,
    User, DocumentType, Payment, DocumentRequest,
    Incident, IncidentHearing, AssistanceProgram, AssistanceBeneficiary,
    HealthRecord, Medicine, MedicineDistribution, Announcement, AuditLog,
    BarangaySetting, CitizenRegistration
)

class CustomUserAdmin(UserAdmin):
    model = User
    fieldsets = UserAdmin.fieldsets + (
        ('BIMS Roles & Resident Link', {'fields': ('RoleID', 'ResidentID')}),
    )
    list_display = ['username', 'email', 'RoleID', 'ResidentID', 'is_staff']

admin.site.register(User, CustomUserAdmin)
admin.site.register(BarangaySetting)
admin.site.register(CitizenRegistration)
admin.site.register(Role)


admin.site.register(Purok)
admin.site.register(Household)
admin.site.register(Resident)
admin.site.register(Sector)
admin.site.register(ResidentSector)
admin.site.register(DocumentType)
admin.site.register(Payment)
admin.site.register(DocumentRequest)
admin.site.register(Incident)
admin.site.register(IncidentHearing)
admin.site.register(AssistanceProgram)
admin.site.register(AssistanceBeneficiary)
admin.site.register(HealthRecord)
admin.site.register(Medicine)
admin.site.register(MedicineDistribution)
admin.site.register(Announcement)
admin.site.register(AuditLog)
