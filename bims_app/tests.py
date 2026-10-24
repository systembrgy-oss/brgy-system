from django.test import TestCase, Client
from django.urls import reverse
from bims_app.models import (
    Role, Purok, Household, Resident, Sector, ResidentSector,
    User, DocumentType, DocumentRequest, AssistanceProgram, AssistanceBeneficiary
)
import datetime

class BIMSSystemTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Roles
        self.role_admin = Role.objects.create(RoleName='Admin')
        self.role_staff = Role.objects.create(RoleName='Staff')
        self.role_people = Role.objects.create(RoleName='People')

        # Sectors
        self.sector_pwd = Sector.objects.create(SectorName='PWD')

        # Purok & Household
        self.purok = Purok.objects.create(PurokName='Purok 1', ZoneNo=1)
        self.household = Household.objects.create(HouseholdNumber='HH-001', PurokID=self.purok, StreetAddress='Main St.')

        # Resident
        self.resident = Resident.objects.create(
            FirstName='Juan',
            LastName='Dela Cruz',
            Sex='Male',
            BirthDate=datetime.date(1990, 1, 1),
            CivilStatus='Single',
            IsVoter=True,
            EmploymentStatus='Employed',
            HouseholdID=self.household,
            RelationshipToHead='Head'
        )
        ResidentSector.objects.create(ResidentID=self.resident, SectorID=self.sector_pwd)

        # Users
        self.admin_user = User.objects.create_user(
            username='admin_test',
            password='password123',
            RoleID=self.role_admin,
            is_staff=True,
            is_superuser=True
        )
        self.resident_user = User.objects.create_user(
            username='resident_test',
            password='password123',
            RoleID=self.role_people,
            ResidentID=self.resident
        )

        # Document Type
        self.doc_type = DocumentType.objects.create(DocumentTypeName='Barangay Clearance', StandardFee=50.00)

    def test_resident_creation_and_age(self):
        self.assertEqual(self.resident.full_name, "Juan Dela Cruz")
        self.assertGreaterEqual(self.resident.age, 30)
        self.assertEqual(self.resident.resident_sectors.count(), 1)

    def test_rbac_security_admin_only_routes(self):
        # Resident user should be forbidden / redirected from audit logs
        self.client.login(username='resident_test', password='password123')
        response = self.client.get(reverse('audit_logs_list'))
        self.assertEqual(response.status_code, 302) # Redirected to dashboard

        # Admin user can access audit logs
        self.client.login(username='admin_test', password='password123')
        response = self.client.get(reverse('audit_logs_list'))
        self.assertEqual(response.status_code, 200)

    def test_document_request_qr_generation(self):
        doc_req = DocumentRequest.objects.create(
            ResidentID=self.resident,
            DocumentTypeID=self.doc_type,
            Purpose='Job Requirement'
        )
        self.assertTrue(doc_req.QRCodeHash.startswith('BIMS-'))
        self.assertEqual(doc_req.RequestStatus, 'Pending')

    def test_assistance_anti_duplicate_claim(self):
        prog = AssistanceProgram.objects.create(
            ProgramName='Relief Ayuda',
            DistributionDate=datetime.date.today()
        )
        AssistanceBeneficiary.objects.create(
            ProgramID=prog,
            ResidentID=self.resident,
            QuantityOrAmountGiven='PHP 1,000'
        )
        # Verify duplicate creation raises integrity error
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            AssistanceBeneficiary.objects.create(
                ProgramID=prog,
                ResidentID=self.resident,
                QuantityOrAmountGiven='Duplicate claim attempt'
            )

    def test_census_sample_csv_download(self):
        self.client.login(username='admin_test', password='password123')
        resp = self.client.get(reverse('census_sample_csv'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv')
        self.assertIn(b'HouseholdNumber', resp.content)

    def test_census_bulk_import_csv(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.login(username='admin_test', password='password123')

        csv_content = (
            "HouseholdNumber,PurokName,ZoneNo,StreetAddress,FirstName,LastName,MiddleName,Sex,BirthDate,CivilStatus,IsVoter,EmploymentStatus,ContactNo,RelationshipToHead,Sectors\n"
            "HH-BULK-01,Purok 5 - Gumamela,3,Acacia St.,Fernando,Poe,Jr,Male,1970-08-20,Married,1,Employed,09170001111,Head,Senior Citizen\n"
            "HH-BULK-01,Purok 5 - Gumamela,3,Acacia St.,Susan,Roces,Sonora,Female,1972-11-15,Married,1,Employed,09170002222,Spouse,4Ps Beneficiary\n"
        )
        csv_file = SimpleUploadedFile("census_test.csv", csv_content.encode('utf-8'), content_type="text/csv")

        resp = self.client.post(reverse('census_import'), {'csv_file': csv_file}, follow=True)
        self.assertEqual(resp.status_code, 200)

        # Verify database entities created
        self.assertTrue(Household.objects.filter(HouseholdNumber="HH-BULK-01").exists())
        self.assertTrue(Resident.objects.filter(FirstName="Fernando", LastName="Poe").exists())
        self.assertTrue(Resident.objects.filter(FirstName="Susan", LastName="Roces").exists())

    def test_dashboard_analytics_charts(self):
        self.client.login(username='admin_test', password='password123')
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('chart_purok_labels', resp.context)
        self.assertIn('chart_sector_labels', resp.context)
        self.assertIn('chart_voter_labels', resp.context)
        self.assertIn('chart_doc_labels', resp.context)

    def test_public_landing_page(self):
        resp = self.client.get(reverse('landing_page'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Citizen Services', resp.content)

    def test_citizen_registration_and_admin_approval_workflow(self):
        from bims_app.models import CitizenRegistration

        # 1. Citizen registers
        reg_data = {
            'username': 'newcitizen',
            'password': 'securepassword123',
            'FirstName': 'Carlos',
            'LastName': 'Yulo',
            'MiddleName': 'Edriel',
            'Sex': 'Male',
            'BirthDate': '2000-02-16',
            'CivilStatus': 'Single',
            'EmploymentStatus': 'Employed',
            'ContactNo': '09175558888',
            'Email': 'carlos.yulo@gmail.com',
            'PurokID': self.purok.PurokID,
            'StreetAddress': 'Golden Lane, Block 1',
            'HouseholdNumber': 'HH-2026-GOLD',
            'RelationshipToHead': 'Head',
            'sectors': ['Senior Citizen']
        }
        resp = self.client.post(reverse('register'), reg_data)
        self.assertEqual(resp.status_code, 200)

        app = CitizenRegistration.objects.get(Username='newcitizen')
        self.assertEqual(app.Status, 'Pending')
        self.assertTrue(app.ReferenceNumber.startswith('REG-'))

        # Verify applicant cannot log in while pending
        login_success = self.client.login(username='newcitizen', password='securepassword123')
        self.assertFalse(login_success, "Pending registration should NOT be able to log in!")

        # 2. Admin reviews and approves
        self.client.login(username='admin_test', password='password123')
        process_resp = self.client.post(reverse('admin_registration_process', args=[app.RegistrationID]), {
            'action': 'approve',
            'AdminRemarks': 'Verified with Barangay Council'
        }, follow=True)
        self.assertEqual(process_resp.status_code, 200)

        app.refresh_from_db()
        self.assertEqual(app.Status, 'Approved')

        # 3. Verify citizen can now log in successfully!
        self.client.logout()
        login_after_approval = self.client.login(username='newcitizen', password='securepassword123')
        self.assertTrue(login_after_approval, "Citizen should be able to log in after admin approval!")

    def test_registration_without_password_generates_temp_password_on_approval(self):
        from bims_app.models import CitizenRegistration, User

        # Citizen submits form WITHOUT username or password (new streamlined intake)
        reg_data = {
            'FirstName': 'Lydia',
            'LastName': 'DeVega',
            'MiddleName': 'Mercado',
            'Sex': 'Female',
            'BirthDate': '1995-12-12',
            'CivilStatus': 'Single',
            'EmploymentStatus': 'Employed',
            'ContactNo': '09181234567',
            'Email': 'lydia.devega@gmail.com',
            'PurokID': self.purok.PurokID,
            'StreetAddress': 'Olympic Village, Block 4',
            'HouseholdNumber': 'HH-2026-LYD',
            'RelationshipToHead': 'Head'
        }
        resp = self.client.post(reverse('register'), reg_data)
        self.assertEqual(resp.status_code, 200)

        app = CitizenRegistration.objects.get(Email='lydia.devega@gmail.com')
        self.assertEqual(app.Status, 'Pending')
        self.assertTrue(len(app.Username) > 0, "Username should be auto-generated from name")

        # Admin approves and issues a temporary password
        self.client.login(username='admin_test', password='password123')
        process_resp = self.client.post(reverse('admin_registration_process', args=[app.RegistrationID]), {
            'action': 'approve',
            'temporary_password': 'Bims-TempPass123!',
            'AdminRemarks': 'Resident identity verified'
        }, follow=True)
        self.assertEqual(process_resp.status_code, 200)

        # Verify resident can log in with auto-assigned username and the temporary password
        self.client.logout()
        login_ok = self.client.login(username=app.Username, password='Bims-TempPass123!')
        self.assertTrue(login_ok, "Resident should log in with auto-generated username and temporary password!")

    def test_api_health_endpoint(self):
        resp = self.client.get(reverse('api_health'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'online')
        self.assertEqual(data['api_version'], 'v1.0.0')

    def test_api_statistics_summary(self):
        resp = self.client.get(reverse('api_statistics_summary'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertIn('demographics', data)
        self.assertIn('total_residents', data['demographics'])
        self.assertIn('treasury_and_services', data)

    def test_api_document_types(self):
        resp = self.client.get(reverse('api_document_types'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertGreaterEqual(data['count'], 1)

    def test_api_residents_search(self):
        resp = self.client.get(reverse('api_residents_search'), {'q': 'Juan'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertGreaterEqual(data['count'], 1)
        self.assertEqual(data['residents'][0]['full_name'], 'Juan Dela Cruz')

    def test_api_document_verification_and_request_submission(self):
        # 1. Programmatic creation via POST /api/v1/documents/request/
        import json
        payload = {
            'resident_id': self.resident.ResidentID,
            'document_type_id': self.doc_type.DocumentTypeID,
            'purpose': 'Bank Account Opening via API'
        }
        create_resp = self.client.post(
            reverse('api_document_request_submit'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(create_resp.status_code, 201)
        res_data = create_resp.json()
        self.assertTrue(res_data['success'])
        qr_hash = res_data['data']['qr_code_hash']
        self.assertTrue(qr_hash.startswith('BIMS-'))

        # 2. Verification via GET /api/v1/verify/<qr_hash>/
        verify_resp = self.client.get(reverse('api_document_verify', args=[qr_hash]))
        self.assertEqual(verify_resp.status_code, 200)
        verify_data = verify_resp.json()
        self.assertEqual(verify_data['verification_status'], 'AUTHENTIC_AND_VERIFIED')
        self.assertEqual(verify_data['data']['purpose'], 'Bank Account Opening via API')

        # 3. Invalid QR hash check
        fake_verify = self.client.get(reverse('api_document_verify', args=['BIMS-NON-EXISTENT']))
        self.assertEqual(fake_verify.status_code, 404)



