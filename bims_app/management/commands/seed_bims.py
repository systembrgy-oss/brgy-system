import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from bims_app.models import (
    Role, Sector, Purok, Household, Resident, ResidentSector,
    User, DocumentType, Payment, DocumentRequest,
    Incident, IncidentHearing, AssistanceProgram, AssistanceBeneficiary,
    HealthRecord, Medicine, MedicineDistribution, Announcement, AuditLog
)

class Command(BaseCommand):
    help = 'Seeds initial BIMS roles, sectors, document types, demo users, and operational data.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding BIMS Data...")

        # 1. Roles
        roles_data = ['Admin', 'Staff', 'People']
        role_objs = {}
        for rname in roles_data:
            role, _ = Role.objects.get_or_create(RoleName=rname)
            role_objs[rname] = role
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(role_objs)} Roles."))

        # 2. Sectors
        sectors_data = ['Senior Citizen', 'PWD', 'Solo Parent', '4Ps Beneficiary']
        sector_objs = {}
        for sname in sectors_data:
            sec, _ = Sector.objects.get_or_create(SectorName=sname)
            sector_objs[sname] = sec
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(sector_objs)} Sectors."))

        # 3. Document Types
        doc_types = [
            ('Barangay Clearance', 50.00),
            ('Certificate of Indigency', 0.00),
            ('Certificate of Residency', 50.00),
            ('Business Permit Clearance', 150.00),
            ('First-Time Job Seeker Certificate', 0.00),
        ]
        doc_type_objs = {}
        for dname, fee in doc_types:
            dt, _ = DocumentType.objects.get_or_create(DocumentTypeName=dname, defaults={'StandardFee': fee})
            doc_type_objs[dname] = dt
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(doc_type_objs)} Document Types."))

        # 4. Puroks
        puroks = [
            ('Purok 1 - Sampaguita', 1),
            ('Purok 2 - Rosal', 1),
            ('Purok 3 - Ilang-Ilang', 2),
            ('Purok 4 - Camia', 2),
        ]
        purok_objs = []
        for pname, zno in puroks:
            p, _ = Purok.objects.get_or_create(PurokName=pname, ZoneNo=zno)
            purok_objs.append(p)

        # 5. Households
        hh1, _ = Household.objects.get_or_create(
            HouseholdNumber="HH-2026-001",
            defaults={"PurokID": purok_objs[0], "StreetAddress": "Block 2 Lot 14, Mabini St."}
        )
        hh2, _ = Household.objects.get_or_create(
            HouseholdNumber="HH-2026-002",
            defaults={"PurokID": purok_objs[1], "StreetAddress": "105 Rizal Avenue"}
        )
        hh3, _ = Household.objects.get_or_create(
            HouseholdNumber="HH-2026-003",
            defaults={"PurokID": purok_objs[2], "StreetAddress": "77 Bonifacio Extension"}
        )

        # 6. Residents
        res1, _ = Resident.objects.get_or_create(
            FirstName="Juan",
            LastName="Dela Cruz",
            MiddleName="Santos",
            defaults={
                "Sex": "Male",
                "BirthDate": datetime.date(1985, 6, 12),
                "CivilStatus": "Married",
                "IsVoter": True,
                "EmploymentStatus": "Employed",
                "ContactNo": "09171234567",
                "HouseholdID": hh1,
                "RelationshipToHead": "Head"
            }
        )

        res2, _ = Resident.objects.get_or_create(
            FirstName="Maria",
            LastName="Dela Cruz",
            MiddleName="Reyes",
            defaults={
                "Sex": "Female",
                "BirthDate": datetime.date(1988, 9, 21),
                "CivilStatus": "Married",
                "IsVoter": True,
                "EmploymentStatus": "Self-Employed",
                "ContactNo": "09189876543",
                "HouseholdID": hh1,
                "RelationshipToHead": "Spouse"
            }
        )

        res3, _ = Resident.objects.get_or_create(
            FirstName="Rosa",
            LastName="Magtanggol",
            MiddleName="Aquino",
            defaults={
                "Sex": "Female",
                "BirthDate": datetime.date(1955, 3, 10),
                "CivilStatus": "Widowed",
                "IsVoter": True,
                "EmploymentStatus": "Retired",
                "ContactNo": "09205551234",
                "HouseholdID": hh2,
                "RelationshipToHead": "Head"
            }
        )

        res4, _ = Resident.objects.get_or_create(
            FirstName="Pedro",
            LastName="Penduko",
            MiddleName="Lopez",
            defaults={
                "Sex": "Male",
                "BirthDate": datetime.date(2003, 11, 5),
                "CivilStatus": "Single",
                "IsVoter": False,
                "EmploymentStatus": "Student",
                "ContactNo": "09193334444",
                "HouseholdID": hh3,
                "RelationshipToHead": "Son"
            }
        )

        # Assign Sectors
        ResidentSector.objects.get_or_create(ResidentID=res3, SectorID=sector_objs['Senior Citizen'])
        ResidentSector.objects.get_or_create(ResidentID=res2, SectorID=sector_objs['4Ps Beneficiary'])

        # 7. System Users
        # Admin User
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@barangay.gov.ph',
                'first_name': 'Barangay',
                'last_name': 'Captain',
                'RoleID': role_objs['Admin'],
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()

        # Staff User
        staff_user, created = User.objects.get_or_create(
            username='staff',
            defaults={
                'email': 'secretary@barangay.gov.ph',
                'first_name': 'Barangay',
                'last_name': 'Secretary',
                'RoleID': role_objs['Staff'],
                'is_staff': True
            }
        )
        if created:
            staff_user.set_password('staff123')
            staff_user.save()

        # People User (Resident Juan Dela Cruz)
        resident_user, created = User.objects.get_or_create(
            username='resident',
            defaults={
                'email': 'juan.delacruz@email.com',
                'first_name': 'Juan',
                'last_name': 'Dela Cruz',
                'RoleID': role_objs['People'],
                'ResidentID': res1
            }
        )
        if created:
            resident_user.set_password('resident123')
            resident_user.save()

        self.stdout.write(self.style.SUCCESS("Seeded Users: admin/admin123, staff/staff123, resident/resident123"))

        # 8. Sample Payment & Document Request
        pay1, _ = Payment.objects.get_or_create(
            OfficialReceiptNo="OR-2026-0891",
            defaults={"AmountPaid": 50.00}
        )
        DocumentRequest.objects.get_or_create(
            ResidentID=res1,
            DocumentTypeID=doc_type_objs['Barangay Clearance'],
            defaults={
                "Purpose": "Local Employment Requirement at SM City",
                "ProcessedByUserID": staff_user,
                "PaymentID": pay1,
                "RequestStatus": "Approved",
                "QRCodeHash": "BIMS-BC-20260401-001",
                "DigitalSignaturePath": "signatures/captain_signed.png"
            }
        )
        DocumentRequest.objects.get_or_create(
            ResidentID=res3,
            DocumentTypeID=doc_type_objs['Certificate of Indigency'],
            defaults={
                "Purpose": "DSWD Medical Assistance for maintenance medication",
                "RequestStatus": "Pending",
                "QRCodeHash": "BIMS-IND-20260402-002"
            }
        )

        # 9. Blotter / Incident & Hearing
        incident1, _ = Incident.objects.get_or_create(
            ComplainantResidentID=res1,
            RespondentName="Mark Anthony Gil",
            defaults={
                "IncidentDate": timezone.now() - datetime.timedelta(days=3),
                "IncidentDetails": "Property boundary encroachment and late-night karaoke disturbance after 10:00 PM.",
                "CaseStatus": "Under Mediation",
                "IsConfidential": False
            }
        )
        IncidentHearing.objects.get_or_create(
            IncidentID=incident1,
            HearingDate=timezone.now() + datetime.timedelta(days=2, hours=10),
            defaults={
                "SummonsDetails": "1st Barangay Conciliation Hearing (Lupon Tagapamayapa)",
                "Remarks": "Both parties served summons letter on yesterday."
            }
        )

        # 10. Assistance Program & Beneficiary
        prog1, _ = AssistanceProgram.objects.get_or_create(
            ProgramName="Senior Citizen Wellness & Nutritional Pack Distribution",
            defaults={
                "Description": "Quarterly health supplement and essential food provisions for registered elders.",
                "DistributionDate": timezone.localdate()
            }
        )
        AssistanceBeneficiary.objects.get_or_create(
            ProgramID=prog1,
            ResidentID=res3,
            defaults={"QuantityOrAmountGiven": "1 Wellness Pack + PHP 1,000 Cash Assistance"}
        )

        # 11. Health Record
        HealthRecord.objects.get_or_create(
            ResidentID=res3,
            RecordType="General Checkup",
            defaults={
                "Details": "Blood pressure reading: 130/80 mmHg. Blood glucose within normal limits.",
                "RecordDate": timezone.localdate() - datetime.timedelta(days=10)
            }
        )

        # 12. Medicines & Distribution
        med1, _ = Medicine.objects.get_or_create(
            MedicineName="Paracetamol 500mg",
            defaults={"Unit": "tablets", "CurrentStock": 450}
        )
        med2, _ = Medicine.objects.get_or_create(
            MedicineName="Amlodipine 5mg",
            defaults={"Unit": "tablets", "CurrentStock": 280}
        )
        med3, _ = Medicine.objects.get_or_create(
            MedicineName="Amoxicillin 500mg",
            defaults={"Unit": "capsules", "CurrentStock": 120}
        )
        MedicineDistribution.objects.get_or_create(
            MedicineID=med2,
            ResidentID=res3,
            defaults={"QuantityGiven": 30}
        )

        # 13. Announcements
        Announcement.objects.get_or_create(
            Title="Barangay Clean-Up Drive & Anti-Dengue Operation",
            defaults={
                "Content": "Join the synchronous clean-up drive this Saturday across all Puroks. Barangay tanods and health workers will distribute larvicides.",
                "Category": "Community Event",
                "IsEmergency": False,
                "CreatedByUserID": admin_user
            }
        )
        Announcement.objects.get_or_create(
            Title="Typhoon Alert: Disaster Preparedness Advisory",
            defaults={
                "Content": "Evacuation centers at Barangay Multipurpose Hall are open. Keep emergency hotlines ready: 0917-888-BIMS.",
                "Category": "Emergency",
                "IsEmergency": True,
                "CreatedByUserID": admin_user
            }
        )

        # 14. Audit Log
        AuditLog.objects.get_or_create(
            UserID=admin_user,
            Action="System Initialized and Seed Data Loaded",
            Module="System Administration",
            IPAddress="127.0.0.1"
        )

        self.stdout.write(self.style.SUCCESS("All BIMS seed data loaded successfully!"))
