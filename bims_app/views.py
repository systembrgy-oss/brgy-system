from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.http import HttpResponse, HttpResponseForbidden
from django.contrib.auth.hashers import make_password
import csv
import io
import json
from datetime import datetime

from .models import (
    Role, Purok, Household, Resident, Sector, ResidentSector,
    User, DocumentType, Payment, DocumentRequest,
    Incident, IncidentHearing, AssistanceProgram, AssistanceBeneficiary,
    HealthRecord, Medicine, MedicineDistribution, Announcement, AuditLog,
    BarangaySetting, CitizenRegistration, Notification
)
from .utils import log_action, generate_qr_base64, role_required


def create_notification(title, message, notif_type='system', target_role='All', recipient_user=None, link_url=None):
    """
    Creates a persistent role-based notification:
    - Admin: Automatically receives all notifications.
    - Staff: Receives 'Staff' and 'All' notifications (registrations, blotters, announcements).
    - People: Receives 'People' and 'All' notifications (announcements, their approval/clearance status).
    """
    try:
        return Notification.objects.create(
            Title=title,
            Message=message,
            NotificationType=notif_type,
            TargetRole=target_role,
            RecipientUser=recipient_user,
            LinkURL=link_url
        )
    except Exception:
        return None


# --- PUBLIC LANDING PAGE ---
def landing_page_view(request):
    announcements = Announcement.objects.all().order_by('-IsEmergency', '-PublishDate')[:4]
    doc_types = DocumentType.objects.all()
    puroks = Purok.objects.all().order_by('ZoneNo', 'PurokName')
    emergency_alerts = Announcement.objects.filter(IsEmergency=True).order_by('-PublishDate')[:2]
    context = {
        'announcements': announcements,
        'doc_types': doc_types,
        'puroks': puroks,
        'emergency_alerts': emergency_alerts,
    }
    return render(request, 'bims/landing_page.html', context)


# --- AUTHENTICATION & PORTAL ---
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')


    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        user = authenticate(request, username=u, password=p)
        if user is not None:
            login(request, user)
            log_action(request, f"User logged in ({user.username})", "Authentication")
            messages.success(request, f"Welcome back, {user.first_name or user.username}!")
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, 'bims/login.html')

def logout_view(request):
    if request.user.is_authenticated:
        log_action(request, f"User logged out ({request.user.username})", "Authentication")
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('login')


# --- DASHBOARD (ROLE-AWARE) ---
@login_required
def dashboard_view(request):
    user = request.user
    role_name = user.RoleID.RoleName if user.RoleID else ("Admin" if user.is_superuser else "Staff")

    # Announcements (visible to all, emergency first)
    announcements = Announcement.objects.all().order_by('-IsEmergency', '-PublishDate')[:5]
    emergency_alerts = Announcement.objects.filter(IsEmergency=True).order_by('-PublishDate')[:2]

    context = {
        'role_name': role_name,
        'announcements': announcements,
        'emergency_alerts': emergency_alerts,
    }

    if role_name in ['Admin', 'Staff']:
        total_residents = Resident.objects.count()
        total_voters = Resident.objects.filter(IsVoter=True).count()
        senior_count = ResidentSector.objects.filter(SectorID__SectorName='Senior Citizen').count()
        pwd_count = ResidentSector.objects.filter(SectorID__SectorName='PWD').count()
        solo_parent_count = ResidentSector.objects.filter(SectorID__SectorName='Solo Parent').count()
        four_ps_count = ResidentSector.objects.filter(SectorID__SectorName='4Ps Beneficiary').count()

        # Dynamic Chart Analytics Data
        purok_query = Purok.objects.annotate(pop=Count('households__residents')).order_by('ZoneNo', 'PurokName')
        purok_labels = [p.PurokName for p in purok_query]
        purok_data = [p.pop for p in purok_query]

        doc_type_stats = DocumentType.objects.annotate(
            issued_count=Count('requests', filter=Q(requests__RequestStatus__in=['Approved', 'Released']))
        ).order_by('-issued_count')
        doc_labels = [dt.DocumentTypeName for dt in doc_type_stats]
        doc_data = [dt.issued_count for dt in doc_type_stats]

        total_collected = Payment.objects.aggregate(total=Sum('AmountPaid'))['total'] or 0.00

        pending_attention_requests = DocumentRequest.objects.filter(RequestStatus='Pending').select_related('ResidentID', 'DocumentTypeID').order_by('-RequestDate')[:3]
        active_attention_incidents = Incident.objects.filter(CaseStatus__in=['Filed', 'Under Mediation']).select_related('ComplainantResidentID').order_by('-IncidentDate')[:3]

        context.update({
            'total_residents': total_residents,
            'total_households': Household.objects.count(),
            'pending_requests': DocumentRequest.objects.filter(RequestStatus='Pending').count(),
            'active_incidents': Incident.objects.filter(CaseStatus__in=['Filed', 'Under Mediation']).count(),
            'total_voters': total_voters,
            'senior_count': senior_count,
            'pwd_count': pwd_count,
            'solo_parent_count': solo_parent_count,
            'four_ps_count': four_ps_count,
            'purok_list': purok_query,
            'pending_attention_requests': pending_attention_requests,
            'active_attention_incidents': active_attention_incidents,
            'recent_requests': DocumentRequest.objects.select_related('ResidentID', 'DocumentTypeID').order_by('-RequestDate')[:5],
            'recent_incidents': Incident.objects.select_related('ComplainantResidentID').order_by('-IncidentDate')[:5],
            'recent_audits': AuditLog.objects.select_related('UserID').order_by('-Timestamp')[:6] if role_name == 'Admin' else [],
            # Charts
            'chart_purok_labels': json.dumps(purok_labels),
            'chart_purok_data': json.dumps(purok_data),
            'chart_sector_labels': json.dumps(['Senior Citizens', 'PWD Registered', 'Solo Parents', '4Ps Beneficiaries']),
            'chart_sector_data': json.dumps([senior_count, pwd_count, solo_parent_count, four_ps_count]),
            'chart_voter_labels': json.dumps(['Registered Voters', 'Non-Voters']),
            'chart_voter_data': json.dumps([total_voters, max(0, total_residents - total_voters)]),
            'chart_doc_labels': json.dumps(doc_labels),
            'chart_doc_data': json.dumps(doc_data),
            'total_revenue_collected': total_collected,
        })
    else:

        # Resident / People Role View
        resident = user.ResidentID
        if resident:
            my_requests = DocumentRequest.objects.filter(ResidentID=resident).order_by('-RequestDate')
            my_incidents = Incident.objects.filter(ComplainantResidentID=resident).order_by('-IncidentDate')
            my_health = HealthRecord.objects.filter(ResidentID=resident).order_by('-RecordDate')[:5]
            my_aid = AssistanceBeneficiary.objects.filter(ResidentID=resident).select_related('ProgramID').order_by('-ReceivedDate')
            context.update({
                'resident': resident,
                'my_requests': my_requests,
                'my_incidents': my_incidents,
                'my_health': my_health,
                'my_aid': my_aid,
            })

    return render(request, 'bims/dashboard.html', context)


# --- 1. RESIDENT PROFILING & HOUSEHOLD MANAGEMENT ---
@login_required
def residents_list(request):
    user = request.user
    role_name = user.RoleID.RoleName if user.RoleID else "Admin"

    if role_name == 'People':
        # Residents only see their own profile
        if user.ResidentID:
            return redirect('resident_detail', pk=user.ResidentID.ResidentID)
        messages.error(request, "No resident record linked to your account.")
        return redirect('dashboard')

    query = request.GET.get('q', '').strip()
    purok_id = request.GET.get('purok')
    sector_id = request.GET.get('sector')
    voter_status = request.GET.get('voter')

    residents = Resident.objects.select_related('HouseholdID', 'HouseholdID__PurokID').prefetch_related('resident_sectors__SectorID').all()

    if query:
        residents = residents.filter(
            Q(FirstName__icontains=query) |
            Q(LastName__icontains=query) |
            Q(HouseholdID__HouseholdNumber__icontains=query)
        )

    if purok_id:
        residents = residents.filter(HouseholdID__PurokID_id=purok_id)

    if sector_id:
        residents = residents.filter(resident_sectors__SectorID_id=sector_id)

    if voter_status in ['0', '1']:
        residents = residents.filter(IsVoter=(voter_status == '1'))

    puroks = Purok.objects.all().order_by('ZoneNo', 'PurokName')
    sectors = Sector.objects.all()

    context = {
        'residents': residents,
        'puroks': puroks,
        'sectors': sectors,
        'query': query,
        'selected_purok': purok_id,
        'selected_sector': sector_id,
        'selected_voter': voter_status,
    }
    return render(request, 'bims/residents_list.html', context)


@login_required
def resident_detail(request, pk):
    resident = get_object_or_404(Resident.objects.select_related('HouseholdID', 'HouseholdID__PurokID'), pk=pk)

    # Permission check for People role: can only view own profile
    if request.user.RoleID and request.user.RoleID.RoleName == 'People':
        if not request.user.ResidentID or request.user.ResidentID.ResidentID != resident.ResidentID:
            messages.error(request, "Access Denied: You can only view your own profile.")
            return redirect('dashboard')

    sectors = resident.resident_sectors.select_related('SectorID').all()
    requests = resident.document_requests.select_related('DocumentTypeID').order_by('-RequestDate')
    incidents = resident.filed_incidents.order_by('-IncidentDate')
    health_records = resident.health_records.order_by('-RecordDate')
    assistances = resident.assistances_received.select_related('ProgramID').order_by('-ReceivedDate')
    medicines = resident.medicine_received.select_related('MedicineID').order_by('-DistributionDate')

    context = {
        'resident': resident,
        'sectors': sectors,
        'requests': requests,
        'incidents': incidents,
        'health_records': health_records,
        'assistances': assistances,
        'medicines': medicines,
    }
    return render(request, 'bims/resident_detail.html', context)


@login_required
@role_required(['Admin', 'Staff'])
def resident_create(request):
    if request.method == 'POST':
        first_name = request.POST.get('FirstName')
        last_name = request.POST.get('LastName')
        middle_name = request.POST.get('MiddleName', '')
        sex = request.POST.get('Sex')
        birth_date = request.POST.get('BirthDate')
        civil_status = request.POST.get('CivilStatus')
        is_voter = request.POST.get('IsVoter') == '1'
        employment = request.POST.get('EmploymentStatus')
        contact_no = request.POST.get('ContactNo', '').strip()
        if contact_no:
            import re
            clean_digits = re.sub(r'\D', '', contact_no)
            if len(clean_digits) != 11 or not clean_digits.startswith('09'):
                messages.error(request, "Contact number must be exactly 11 digits starting with 09 (e.g. 09171234567).")
                households = Household.objects.select_related('PurokID').all().order_by('HouseholdNumber')
                sectors = Sector.objects.all()
                return render(request, 'bims/resident_form.html', {'households': households, 'sectors': sectors})
            contact_no = clean_digits

        household_id = request.POST.get('HouseholdID')
        rel_head = request.POST.get('RelationshipToHead')
        selected_sectors = request.POST.getlist('sectors')

        household = get_object_or_404(Household, pk=household_id)

        resident = Resident.objects.create(
            FirstName=first_name,
            LastName=last_name,
            MiddleName=middle_name,
            Sex=sex,
            BirthDate=birth_date,
            CivilStatus=civil_status,
            IsVoter=is_voter,
            EmploymentStatus=employment,
            ContactNo=contact_no,
            HouseholdID=household,
            RelationshipToHead=rel_head
        )

        for sec_id in selected_sectors:
            ResidentSector.objects.create(ResidentID=resident, SectorID_id=sec_id)

        log_action(request, f"Created Resident record: {resident.full_name}", "Resident Management")
        messages.success(request, f"Resident {resident.full_name} registered successfully.")
        return redirect('resident_detail', pk=resident.ResidentID)

    households = Household.objects.select_related('PurokID').all().order_by('HouseholdNumber')
    sectors = Sector.objects.all()
    return render(request, 'bims/resident_form.html', {'households': households, 'sectors': sectors})


@login_required
@role_required(['Admin', 'Staff'])
def resident_edit(request, pk):
    resident = get_object_or_404(Resident, pk=pk)
    households = Household.objects.select_related('PurokID').all().order_by('HouseholdNumber')
    sectors = Sector.objects.all()

    if request.method == 'POST':
        first_name = request.POST.get('FirstName')
        last_name = request.POST.get('LastName')
        middle_name = request.POST.get('MiddleName', '')
        sex = request.POST.get('Sex')
        birth_date = request.POST.get('BirthDate')
        civil_status = request.POST.get('CivilStatus')
        is_voter = request.POST.get('IsVoter') == '1'
        employment = request.POST.get('EmploymentStatus')
        contact_no = request.POST.get('ContactNo', '').strip()
        household_id = request.POST.get('HouseholdID')
        rel_head = request.POST.get('RelationshipToHead')
        selected_sectors = request.POST.getlist('sectors')

        if contact_no:
            import re
            clean_digits = re.sub(r'\D', '', contact_no)
            if len(clean_digits) != 11 or not clean_digits.startswith('09'):
                messages.error(request, "Contact number must be exactly 11 digits starting with 09 (e.g. 09171234567).")
                assigned_sector_ids = list(resident.resident_sectors.values_list('SectorID_id', flat=True))
                return render(request, 'bims/resident_form.html', {
                    'resident': resident,
                    'households': households,
                    'sectors': sectors,
                    'assigned_sector_ids': assigned_sector_ids,
                    'is_edit': True
                })
            contact_no = clean_digits

        household = get_object_or_404(Household, pk=household_id)

        resident.FirstName = first_name
        resident.LastName = last_name
        resident.MiddleName = middle_name
        resident.Sex = sex
        resident.BirthDate = birth_date
        resident.CivilStatus = civil_status
        resident.IsVoter = is_voter
        resident.EmploymentStatus = employment
        resident.ContactNo = contact_no
        resident.HouseholdID = household
        resident.RelationshipToHead = rel_head
        resident.save()

        # Update Sectors
        resident.resident_sectors.all().delete()
        for sec_id in selected_sectors:
            ResidentSector.objects.create(ResidentID=resident, SectorID_id=sec_id)

        log_action(request, f"Updated Citizen profile: {resident.full_name}", "Resident Management")
        messages.success(request, f"Citizen record for {resident.full_name} updated successfully.")
        return redirect('resident_detail', pk=resident.ResidentID)

    assigned_sector_ids = list(resident.resident_sectors.values_list('SectorID_id', flat=True))
    return render(request, 'bims/resident_form.html', {
        'resident': resident,
        'households': households,
        'sectors': sectors,
        'assigned_sector_ids': assigned_sector_ids,
        'is_edit': True
    })


def generate_next_household_number():
    year = timezone.now().year
    existing = Household.objects.values_list('HouseholdNumber', flat=True)
    max_num = 0
    import re
    for num_str in existing:
        if not num_str:
            continue
        match = re.search(r'(\d+)$', str(num_str))
        if match:
            try:
                val = int(match.group(1))
                if val > max_num:
                    max_num = val
            except ValueError:
                pass
    next_num = max_num + 1
    return f"HH-{year}-{next_num:03d}"


@login_required
@role_required(['Admin', 'Staff'])
def households_list(request):
    if request.method == 'POST':
        action_type = request.POST.get('action_type', 'create_household')

        if action_type == 'create_purok':
            purok_name = request.POST.get('PurokName', '').strip()
            zone_no = request.POST.get('ZoneNo', '').strip() or '1'
            if not purok_name:
                messages.error(request, "Purok name is required.")
            else:
                purok_obj, created = Purok.objects.get_or_create(
                    PurokName=purok_name,
                    defaults={'ZoneNo': zone_no}
                )
                if created:
                    log_action(request, f"Created Purok: {purok_name} (Zone {zone_no})", "Purok Management")
                    messages.success(request, f"Purok '{purok_name}' (Zone {zone_no}) created successfully.")
                else:
                    messages.info(request, f"Purok '{purok_name}' already exists.")
            return redirect('households_list')

        elif action_type == 'edit_purok':
            purok_id = request.POST.get('PurokID')
            purok = get_object_or_404(Purok, pk=purok_id)
            purok_name = request.POST.get('PurokName', '').strip()
            zone_no = request.POST.get('ZoneNo', '').strip()
            if not purok_name:
                messages.error(request, "Purok name is required.")
            else:
                purok.PurokName = purok_name
                if zone_no:
                    try:
                        purok.ZoneNo = int(zone_no)
                    except ValueError:
                        pass
                purok.save()
                log_action(request, f"Updated Purok #{purok.PurokID}: {purok.PurokName} (Zone {purok.ZoneNo})", "Purok Management")
                messages.success(request, f"Purok '{purok.PurokName}' updated successfully.")
            return redirect('households_list')

        # create_household
        hh_num = request.POST.get('HouseholdNumber', '').strip()
        purok_id = request.POST.get('PurokID')
        address = request.POST.get('StreetAddress')

        if not hh_num:
            hh_num = generate_next_household_number()

        purok = get_object_or_404(Purok, pk=purok_id)
        hh = Household.objects.create(HouseholdNumber=hh_num, PurokID=purok, StreetAddress=address)
        log_action(request, f"Created Household #{hh.HouseholdNumber}", "Household Management")
        messages.success(request, f"Household {hh.HouseholdNumber} created successfully in {purok.PurokName}.")
        return redirect('households_list')

    households = Household.objects.select_related('PurokID').annotate(resident_count=Count('residents')).order_by('HouseholdNumber')
    puroks = Purok.objects.all().order_by('ZoneNo', 'PurokName')
    next_hh_no = generate_next_household_number()
    return render(request, 'bims/households_list.html', {
        'households': households,
        'puroks': puroks,
        'next_hh_no': next_hh_no
    })


# --- 2. PAPERLESS DOCUMENT REQUEST & ISSUANCE ---
@login_required
def documents_list(request):
    user = request.user
    role_name = user.RoleID.RoleName if user.RoleID else "Admin"

    if role_name == 'People':
        requests = DocumentRequest.objects.filter(ResidentID=user.ResidentID).select_related('DocumentTypeID', 'PaymentID')
    else:
        status_filter = request.GET.get('status')
        requests = DocumentRequest.objects.select_related('ResidentID', 'DocumentTypeID', 'PaymentID', 'ProcessedByUserID').all().order_by('-RequestDate')
        if status_filter:
            requests = requests.filter(RequestStatus=status_filter)

    doc_types = DocumentType.objects.all()
    return render(request, 'bims/documents_list.html', {'requests': requests, 'doc_types': doc_types, 'role_name': role_name})


@login_required
def document_request_create(request):
    user = request.user
    role_name = user.RoleID.RoleName if user.RoleID else "Admin"

    if request.method == 'POST':
        if role_name == 'People':
            resident = user.ResidentID
            if not resident:
                messages.error(request, "Your account is not linked to a resident record.")
                return redirect('documents_list')
        else:
            resident_id = request.POST.get('ResidentID')
            resident = get_object_or_404(Resident, pk=resident_id)

        doc_type_id = request.POST.get('DocumentTypeID')
        purpose = request.POST.get('Purpose')
        attachment = request.FILES.get('AttachmentFile')
        doc_type = get_object_or_404(DocumentType, pk=doc_type_id)

        doc_req = DocumentRequest.objects.create(
            ResidentID=resident,
            DocumentTypeID=doc_type,
            Purpose=purpose,
            AttachmentFile=attachment,
            RequestStatus='Pending'
        )

        create_notification(
            title=f"New Document Request: {doc_type.DocumentTypeName}",
            message=f"{resident.full_name} submitted a request for {doc_type.DocumentTypeName} (Purpose: {purpose}).",
            notif_type='document',
            target_role='Staff',
            link_url=f"/documents/?highlight={doc_req.RequestID}#req-{doc_req.RequestID}"
        )

        log_action(request, f"Submitted document request #{doc_req.RequestID} for {doc_type.DocumentTypeName}", "Document Requests")
        messages.success(request, f"Document request for {doc_type.DocumentTypeName} submitted successfully.")
        return redirect('documents_list')

    doc_types = DocumentType.objects.all()
    residents = Resident.objects.all().order_by('LastName') if role_name in ['Admin', 'Staff'] else None
    return render(request, 'bims/document_request_form.html', {'doc_types': doc_types, 'residents': residents, 'role_name': role_name})


def build_default_letter_paragraphs(doc_req, barangay_name="Barangay Baan"):
    resident = doc_req.ResidentID
    full_name = resident.full_name.upper()
    age = resident.age
    sex = resident.Sex.lower() if resident.Sex else "citizen"
    civil_status = resident.CivilStatus.lower() if resident.CivilStatus else "single"
    street = resident.HouseholdID.StreetAddress if resident.HouseholdID else ""
    purok = resident.HouseholdID.PurokID.PurokName if (resident.HouseholdID and resident.HouseholdID.PurokID) else ""
    address = f"{street}, {purok}" if street and purok else (street or purok or "Barangay jurisdiction")
    doc_name = (doc_req.DocumentTypeID.DocumentTypeName or "").lower()

    if "first-time" in doc_name or "job seeker" in doc_name:
        return [
            f"This is to certify that {full_name}, {age} years old, {sex}, {civil_status}, Filipino citizen, is a bonafide resident of {address}, {barangay_name}.",
            "This is to further certify that the above-named person is a qualified beneficiary of Republic Act No. 11261, otherwise known as the 'First Time Jobseekers Assistance Act' of 2019, actively seeking employment for the first time and is entitled to government fee waivers and incentives under the law.",
            "Records of this office further show that the subject person has NO DEROGATORY RECORD nor any pending complaint or criminal case filed against him/her in the Katarungang Pambarangay (Barangay Justice System) to date. He/she is known to be an upright citizen with good moral character and a law-abiding member of this community.",
        ]
    elif "residency" in doc_name:
        return [
            f"This is to certify that {full_name}, {age} years old, {sex}, {civil_status}, Filipino citizen, is a bonafide and continuous resident of {address}, {barangay_name}.",
            "Based on the official records and demographic registry of this barangay, the subject person is an established and verified resident of good moral character and reputable standing in this community.",
            "This certification of residency is issued to verify the permanent domicile and actual residence of the above-named person.",
        ]
    elif "indigency" in doc_name:
        return [
            f"This is to certify that {full_name}, {age} years old, {sex}, {civil_status}, Filipino citizen, is a bonafide resident of {address}, {barangay_name}.",
            "This is to further certify that the above-named individual and their household belong to the low-income / indigent sector of this barangay whose monthly household income is below the subsistence threshold.",
            "This certification of indigency is issued to attest to the indigent financial standing of the applicant and to qualify them for medical, financial, funeral, or legal aid.",
        ]
    elif "good moral" in doc_name:
        return [
            f"This is to certify that {full_name}, {age} years old, {sex}, {civil_status}, Filipino citizen, is a bonafide resident of {address}, {barangay_name}.",
            "This certifies that the subject individual has maintained good standing in this barangay, has exemplified moral integrity, and has NO DEROGATORY RECORD or adverse case on file in this office.",
            "He/she is known in this community as a law-abiding citizen with high regard for peace, order, and civic cooperation.",
        ]
    else: # Standard Barangay Clearance
        return [
            f"This is to certify that {full_name}, {age} years old, {sex}, {civil_status}, Filipino citizen, is a bonafide resident of {address}, {barangay_name}.",
            "Records of this office further show that the subject person has NO DEROGATORY RECORD nor any pending complaint or criminal case filed against him/her in the Katarungang Pambarangay (Barangay Justice System) to date. He/she is known to be an upright citizen with good moral character and a law-abiding member of this community.",
        ]


@login_required
@role_required(['Admin', 'Staff'])
def document_process(request, pk):
    doc_req = get_object_or_404(DocumentRequest.objects.select_related('DocumentTypeID', 'ResidentID', 'ResidentID__HouseholdID', 'ResidentID__HouseholdID__PurokID'), pk=pk)

    if request.method == 'POST':
        action = request.POST.get('action') # 'approve', 'release', 'reject', 'update_details'
        or_no = request.POST.get('OfficialReceiptNo')
        amount = request.POST.get('AmountPaid', doc_req.DocumentTypeID.StandardFee)

        if action == 'approve':
            doc_req.RequestStatus = 'Approved'
            doc_req.ProcessedByUserID = request.user
            doc_req.DigitalSignaturePath = "signatures/punong_barangay_signed.png"

            # Record Payment if fee > 0 and OR provided
            if float(amount or 0) > 0 and or_no:
                payment, _ = Payment.objects.get_or_create(
                    OfficialReceiptNo=or_no,
                    defaults={'AmountPaid': amount}
                )
                doc_req.PaymentID = payment

            doc_req.save()

            # Email notification if resident has linked user account with email
            try:
                user_acct = User.objects.filter(ResidentID=doc_req.ResidentID).first()
                if user_acct and user_acct.email:
                    from django.core.mail import send_mail
                    send_mail(
                        subject=f"Document Ready - {doc_req.DocumentTypeID.DocumentTypeName} (#{doc_req.RequestID})",
                        message=(
                            f"Magandang araw, {doc_req.ResidentID.full_name}!\n\n"
                            f"Your request for {doc_req.DocumentTypeID.DocumentTypeName} has been APPROVED and digitally signed.\n"
                            f"Tracking QR Code: {doc_req.QRCodeHash}\n\n"
                            f"You may pick up your printed document at the Barangay Hall or view it online via your portal:\n"
                            f"http://127.0.0.1:8000/documents/{doc_req.RequestID}/print/\n\n"
                            f"Maraming salamat,\n"
                            f"Barangay Baan"
                        ),
                        from_email='notifications@barangaysanroque.gov.ph',
                        recipient_list=[user_acct.email],
                        fail_silently=True
                    )
            except Exception:
                pass

            # Create in-app notification for resident
            user_acct = User.objects.filter(ResidentID=doc_req.ResidentID).first()
            if user_acct:
                create_notification(
                    title=f"Document Request Approved: {doc_req.DocumentTypeID.DocumentTypeName}",
                    message=f"Your {doc_req.DocumentTypeID.DocumentTypeName} has been approved and digitally signed. You may now view or print it.",
                    notif_type='document',
                    target_role='People',
                    recipient_user=user_acct,
                    link_url=f"/documents/{doc_req.RequestID}/print/"
                )

            log_action(request, f"Approved Document Request #{doc_req.RequestID} for {doc_req.ResidentID.full_name}", "Document Requests")
            messages.success(request, f"Request #{doc_req.RequestID} approved and digitally stamped.")

        elif action == 'update_details':
            doc_type_id = request.POST.get('DocumentTypeID')
            purpose = request.POST.get('Purpose', '').strip()
            custom_body = request.POST.get('CustomLetterBody', '').strip()
            if doc_type_id:
                doc_req.DocumentTypeID = get_object_or_404(DocumentType, pk=doc_type_id)
            if purpose:
                doc_req.Purpose = purpose
            doc_req.CustomLetterBody = custom_body if custom_body else None
            doc_req.save()
            log_action(request, f"Updated Application details for Request #{doc_req.RequestID}", "Document Requests")
            messages.success(request, f"Application details for Request #{doc_req.RequestID} updated successfully.")
            return redirect('document_process', pk=doc_req.RequestID)

        elif action == 'release':
            doc_req.RequestStatus = 'Released'
            doc_req.save()
            log_action(request, f"Released Document Request #{doc_req.RequestID}", "Document Requests")
            messages.success(request, f"Request #{doc_req.RequestID} marked as Released.")

        elif action == 'reject':
            doc_req.RequestStatus = 'Rejected'
            doc_req.ProcessedByUserID = request.user
            doc_req.save()
            log_action(request, f"Rejected Document Request #{doc_req.RequestID}", "Document Requests")
            messages.warning(request, f"Request #{doc_req.RequestID} rejected.")

        return redirect('documents_list')

    doc_types = DocumentType.objects.all()
    barangay_setting = BarangaySetting.objects.first()
    b_name = barangay_setting.BarangayName if barangay_setting else "Barangay Baan"
    default_body = "\n\n".join(build_default_letter_paragraphs(doc_req, b_name))

    return render(request, 'bims/document_process_modal.html', {
        'doc_req': doc_req,
        'doc_types': doc_types,
        'current_letter_body': doc_req.CustomLetterBody or default_body,
    })


@login_required
def document_view(request, pk):
    doc_req = get_object_or_404(
        DocumentRequest.objects.select_related('DocumentTypeID', 'ResidentID', 'ResidentID__HouseholdID', 'ResidentID__HouseholdID__PurokID', 'PaymentID', 'ProcessedByUserID'),
        pk=pk
    )

    # Allow staff or admin to update the letter body directly from the print preview
    if request.method == 'POST' and (request.user.RoleID and request.user.RoleID.RoleName in ['Admin', 'Staff'] or request.user.is_superuser):
        action = request.POST.get('action')
        if action == 'update_letter_body':
            custom_body = request.POST.get('CustomLetterBody', '').strip()
            purpose = request.POST.get('Purpose', '').strip()
            if purpose:
                doc_req.Purpose = purpose
            doc_req.CustomLetterBody = custom_body if custom_body else None
            doc_req.save()
            log_action(request, f"Updated Letter Body for Certificate #{doc_req.RequestID}", "Document Requests")
            messages.success(request, "Certificate letter context updated successfully.")
            return redirect('document_view', pk=pk)

    # Permission: People can only view their own approved/released documents
    if request.user.RoleID and request.user.RoleID.RoleName == 'People':
        if not request.user.ResidentID or request.user.ResidentID.ResidentID != doc_req.ResidentID.ResidentID:
            messages.error(request, "Access Denied.")
            return redirect('dashboard')
        if doc_req.RequestStatus not in ['Approved', 'Released']:
            messages.warning(request, "This document has not yet been approved or released.")
            return redirect('documents_list')

    # Generate QR Code verification url
    verify_url = request.build_absolute_uri(f"/verify/{doc_req.QRCodeHash}/")
    qr_b64 = generate_qr_base64(verify_url)

    barangay_setting = BarangaySetting.objects.first()
    b_name = barangay_setting.BarangayName if barangay_setting else "Barangay Baan"

    if doc_req.CustomLetterBody:
        letter_paragraphs = [p.strip() for p in doc_req.CustomLetterBody.split("\n\n") if p.strip()]
        if not letter_paragraphs:
            letter_paragraphs = [doc_req.CustomLetterBody]
    else:
        letter_paragraphs = build_default_letter_paragraphs(doc_req, b_name)

    context = {
        'doc': doc_req,
        'resident': doc_req.ResidentID,
        'doc_type': doc_req.DocumentTypeID,
        'qr_b64': qr_b64,
        'verify_url': verify_url,
        'issue_date': timezone.now().strftime("%B %d, %Y"),
        'letter_paragraphs': letter_paragraphs,
        'current_letter_body': doc_req.CustomLetterBody or "\n\n".join(letter_paragraphs),
    }
    return render(request, 'bims/document_print_template.html', context)


# Public verification endpoint (for QR Code scanning on printed certificates)
def document_verify(request, qr_hash):
    doc_req = DocumentRequest.objects.filter(QRCodeHash=qr_hash).select_related('ResidentID', 'DocumentTypeID', 'PaymentID').first()
    return render(request, 'bims/document_verification.html', {'doc': doc_req, 'qr_hash': qr_hash})


# --- 3. BLOTTER & INCIDENT MANAGEMENT (KATARUNGANG PAMBARANGAY) ---
@login_required
def incidents_list(request):
    user = request.user
    role_name = user.RoleID.RoleName if user.RoleID else "Admin"

    if role_name == 'People':
        # Residents only see cases they filed
        incidents = Incident.objects.filter(ComplainantResidentID=user.ResidentID).order_by('-IncidentDate')
    else:
        # Admin / Staff see all, but handle confidential
        incidents = Incident.objects.select_related('ComplainantResidentID').prefetch_related('hearings').order_by('-IncidentDate')

    return render(request, 'bims/incidents_list.html', {'incidents': incidents, 'role_name': role_name})


@login_required
def incident_create(request):
    user = request.user
    role_name = user.RoleID.RoleName if user.RoleID else "Admin"

    if request.method == 'POST':
        if role_name == 'People':
            complainant = user.ResidentID
            if not complainant:
                messages.error(request, "No resident record associated with this account.")
                return redirect('incidents_list')
        else:
            complainant_id = request.POST.get('ComplainantResidentID')
            complainant = get_object_or_404(Resident, pk=complainant_id)

        respondent = request.POST.get('RespondentName')
        details = request.POST.get('IncidentDetails')
        incident_date = request.POST.get('IncidentDate') or timezone.now()
        is_confidential = request.POST.get('IsConfidential') == '1'

        incident = Incident.objects.create(
            IncidentDate=incident_date,
            ComplainantResidentID=complainant,
            RespondentName=respondent,
            IncidentDetails=details,
            CaseStatus='Filed',
            IsConfidential=is_confidential
        )

        create_notification(
            title=f"New Blotter Incident Filed: Case #{incident.IncidentID}",
            message=f"New incident filed vs {incident.RespondentName} (Complainant: {complainant.full_name if complainant else 'Resident'}).",
            notif_type='incident',
            target_role='Staff',
            link_url=f"/incidents/{incident.IncidentID}/"
        )

        log_action(request, f"Filed Blotter Case #{incident.IncidentID}: vs {incident.RespondentName}", "Blotter Management")
        messages.success(request, f"Blotter Case #{incident.IncidentID} recorded successfully.")
        return redirect('incident_detail', pk=incident.IncidentID)

    residents = Resident.objects.all().order_by('LastName') if role_name in ['Admin', 'Staff'] else None
    return render(request, 'bims/incident_form.html', {'residents': residents, 'role_name': role_name})


@login_required
def incident_detail(request, pk):
    incident = get_object_or_404(Incident.objects.select_related('ComplainantResidentID'), pk=pk)
    user = request.user
    role_name = user.RoleID.RoleName if user.RoleID else "Admin"

    if role_name == 'People':
        if not user.ResidentID or user.ResidentID.ResidentID != incident.ComplainantResidentID.ResidentID:
            messages.error(request, "Access Denied.")
            return redirect('dashboard')

    if request.method == 'POST' and role_name in ['Admin', 'Staff']:
        new_status = request.POST.get('CaseStatus')
        if new_status in dict(Incident.CASE_STATUS_CHOICES):
            incident.CaseStatus = new_status
            incident.save()
            log_action(request, f"Updated Case #{incident.IncidentID} status to {new_status}", "Blotter Management")
            messages.success(request, f"Case status updated to {new_status}.")
            return redirect('incident_detail', pk=incident.IncidentID)

    hearings = incident.hearings.all().order_by('HearingDate')
    return render(request, 'bims/incident_detail.html', {'incident': incident, 'hearings': hearings, 'role_name': role_name})


@login_required
@role_required(['Admin', 'Staff'])
def hearing_create(request, incident_id):
    incident = get_object_or_404(Incident, pk=incident_id)

    if request.method == 'POST':
        hearing_date = request.POST.get('HearingDate')
        summons = request.POST.get('SummonsDetails')
        remarks = request.POST.get('Remarks', '')

        hearing = IncidentHearing.objects.create(
            IncidentID=incident,
            HearingDate=hearing_date,
            SummonsDetails=summons,
            Remarks=remarks
        )

        if incident.CaseStatus == 'Filed':
            incident.CaseStatus = 'Under Mediation'
            incident.save()

        log_action(request, f"Scheduled Hearing for Case #{incident.IncidentID} on {hearing_date}", "Blotter Management")
        messages.success(request, "Conciliation hearing scheduled.")
        return redirect('incident_detail', pk=incident.IncidentID)

    return render(request, 'bims/hearing_form.html', {'incident': incident})


# --- 4. HEALTH, WELFARE & FINANCIAL ASSISTANCE ---
@login_required
@role_required(['Admin', 'Staff'])
def assistance_programs_list(request):
    if request.method == 'POST':
        pname = request.POST.get('ProgramName')
        desc = request.POST.get('Description')
        dist_date = request.POST.get('DistributionDate')

        prog = AssistanceProgram.objects.create(ProgramName=pname, Description=desc, DistributionDate=dist_date)
        log_action(request, f"Created Assistance Program: {prog.ProgramName}", "Assistance Programs")
        messages.success(request, f"Program '{prog.ProgramName}' created.")
        return redirect('assistance_programs_list')

    programs = AssistanceProgram.objects.annotate(beneficiary_count=Count('beneficiaries')).order_by('-DistributionDate')
    return render(request, 'bims/assistance_programs.html', {'programs': programs})


@login_required
@role_required(['Admin', 'Staff'])
def assistance_program_detail(request, pk):
    program = get_object_or_404(AssistanceProgram, pk=pk)

    if request.method == 'POST':
        resident_id = request.POST.get('ResidentID')
        quantity_or_amount = request.POST.get('QuantityOrAmountGiven')

        resident = get_object_or_404(Resident, pk=resident_id)

        # Check duplicate claim protection
        existing = AssistanceBeneficiary.objects.filter(ProgramID=program, ResidentID=resident).first()
        if existing:
            messages.error(request, f"Duplicate Claim Blocked! Resident {resident.full_name} has already received this assistance.")
        else:
            AssistanceBeneficiary.objects.create(
                ProgramID=program,
                ResidentID=resident,
                QuantityOrAmountGiven=quantity_or_amount
            )
            log_action(request, f"Disbursed aid to {resident.full_name} for {program.ProgramName}", "Assistance Programs")
            messages.success(request, f"Aid recorded for {resident.full_name}.")
        return redirect('assistance_program_detail', pk=program.ProgramID)

    beneficiaries = program.beneficiaries.select_related('ResidentID', 'ResidentID__HouseholdID').order_by('-ReceivedDate')
    residents = Resident.objects.all().order_by('LastName')
    return render(request, 'bims/assistance_detail.html', {'program': program, 'beneficiaries': beneficiaries, 'residents': residents})


@login_required
@role_required(['Admin', 'Staff'])
def health_records_list(request):
    if request.method == 'POST':
        action = request.POST.get('action', 'create')

        if action == 'edit':
            record_id = request.POST.get('RecordID')
            rec = get_object_or_404(HealthRecord, pk=record_id)
            rec_type = request.POST.get('RecordType', '').strip()
            custom_type = request.POST.get('CustomRecordType', '').strip()
            if rec_type == 'Other' and custom_type:
                rec_type = custom_type
            if rec_type:
                rec.RecordType = rec_type
            rec.Details = request.POST.get('Details', rec.Details).strip()
            rec_date = request.POST.get('RecordDate')
            if rec_date:
                rec.RecordDate = rec_date
            rec.save()
            log_action(request, f"Updated Health Record #{rec.RecordID} ({rec.RecordType}) for {rec.ResidentID.full_name}", "Health Center")
            messages.success(request, f"Health record updated to '{rec.RecordType}'.")
            return redirect('health_records_list')

        elif action == 'delete':
            record_id = request.POST.get('RecordID')
            rec = get_object_or_404(HealthRecord, pk=record_id)
            patient_name = rec.ResidentID.full_name
            rec.delete()
            log_action(request, f"Deleted Health Record #{record_id} of {patient_name}", "Health Center")
            messages.success(request, f"Health consultation record deleted.")
            return redirect('health_records_list')

        # Create Record
        resident_id = request.POST.get('ResidentID')
        rec_type = request.POST.get('RecordType', '').strip()
        custom_type = request.POST.get('CustomRecordType', '').strip()
        if rec_type == 'Other' and custom_type:
            rec_type = custom_type
        details = request.POST.get('Details')
        rec_date = request.POST.get('RecordDate') or timezone.localdate()

        resident = get_object_or_404(Resident, pk=resident_id)
        HealthRecord.objects.create(
            ResidentID=resident,
            RecordType=rec_type,
            Details=details,
            RecordDate=rec_date
        )
        log_action(request, f"Recorded {rec_type} for {resident.full_name}", "Health Center")
        messages.success(request, f"Health consultation record '{rec_type}' logged.")
        return redirect('health_records_list')

    records = HealthRecord.objects.select_related('ResidentID', 'ResidentID__HouseholdID').order_by('-RecordDate')
    residents = Resident.objects.all().order_by('LastName')
    return render(request, 'bims/health_records.html', {'records': records, 'residents': residents})


@login_required
@role_required(['Admin', 'Staff'])
def medicines_inventory(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_medicine':
            name = request.POST.get('MedicineName')
            unit = request.POST.get('Unit')
            stock = int(request.POST.get('CurrentStock', 0))
            med = Medicine.objects.create(MedicineName=name, Unit=unit, CurrentStock=stock)
            log_action(request, f"Added Medicine: {med.MedicineName}", "Medicine Inventory")
            messages.success(request, f"Medicine {med.MedicineName} added.")

        elif action == 'distribute':
            med_id = request.POST.get('MedicineID')
            resident_id = request.POST.get('ResidentID')
            qty = int(request.POST.get('QuantityGiven', 1))

            med = get_object_or_404(Medicine, pk=med_id)
            resident = get_object_or_404(Resident, pk=resident_id)

            if med.CurrentStock < qty:
                messages.error(request, f"Insufficient stock! Available: {med.CurrentStock} {med.Unit}")
            else:
                med.CurrentStock -= qty
                med.save()
                MedicineDistribution.objects.create(
                    MedicineID=med,
                    ResidentID=resident,
                    QuantityGiven=qty
                )
                log_action(request, f"Dispensed {qty} {med.Unit} {med.MedicineName} to {resident.full_name}", "Medicine Inventory")
                messages.success(request, f"Dispensed {qty} {med.Unit} to {resident.full_name}.")

        return redirect('medicines_inventory')

    medicines = Medicine.objects.all().order_by('MedicineName')
    distributions = MedicineDistribution.objects.select_related('MedicineID', 'ResidentID').order_by('-DistributionDate')[:20]
    residents = Resident.objects.all().order_by('LastName')
    return render(request, 'bims/medicines.html', {'medicines': medicines, 'distributions': distributions, 'residents': residents})


# --- 5. COMMUNITY ANNOUNCEMENTS & NOTICE BOARD ---
@login_required
def announcements_list(request):
    user = request.user
    role_name = user.RoleID.RoleName if user.RoleID else "Admin"

    if request.method == 'POST' and role_name in ['Admin', 'Staff']:
        action = request.POST.get('action', 'create')

        if action == 'pin':
            ann_id = request.POST.get('AnnouncementID')
            ann = get_object_or_404(Announcement, pk=ann_id)
            ann.IsPinned = not ann.IsPinned
            ann.save()
            state = "pinned to top" if ann.IsPinned else "unpinned"
            log_action(request, f"{'Pinned' if ann.IsPinned else 'Unpinned'} Announcement: {ann.Title}", "Announcements")
            messages.success(request, f"Bulletin '{ann.Title}' is now {state}.")
            return redirect('announcements_list')

        elif action == 'edit':
            ann_id = request.POST.get('AnnouncementID')
            ann = get_object_or_404(Announcement, pk=ann_id)
            ann.Title = request.POST.get('Title', ann.Title).strip()
            ann.Content = request.POST.get('Content', ann.Content).strip()
            ann.Category = request.POST.get('Category', ann.Category)
            ann.IsEmergency = request.POST.get('IsEmergency') == '1'
            ann.IsPinned = request.POST.get('IsPinned') == '1'
            ann.save()
            log_action(request, f"Updated Announcement: {ann.Title}", "Announcements")
            messages.success(request, f"Announcement '{ann.Title}' updated.")
            return redirect('announcements_list')

        elif action == 'delete':
            ann_id = request.POST.get('AnnouncementID')
            ann = get_object_or_404(Announcement, pk=ann_id)
            title = ann.Title
            ann.delete()
            log_action(request, f"Deleted Announcement: {title}", "Announcements")
            messages.success(request, f"Announcement '{title}' deleted.")
            return redirect('announcements_list')

        # create
        title = request.POST.get('Title')
        content = request.POST.get('Content')
        category = request.POST.get('Category')
        is_emergency = request.POST.get('IsEmergency') == '1'
        is_pinned = request.POST.get('IsPinned') == '1'

        ann = Announcement.objects.create(
            Title=title,
            Content=content,
            Category=category,
            IsEmergency=is_emergency,
            IsPinned=is_pinned,
            CreatedByUserID=user
        )

        create_notification(
            title=f"{'🚨 EMERGENCY ADVISORY' if is_emergency else '📢 Barangay Announcement'}: {ann.Title}",
            message=content[:180] + ("..." if len(content) > 180 else ""),
            notif_type='announcement',
            target_role='All',
            link_url='/announcements/'
        )

        log_action(request, f"Published Announcement: {ann.Title} (Emergency={is_emergency})", "Announcements")
        messages.success(request, "Announcement posted successfully.")
        return redirect('announcements_list')

    announcements = Announcement.objects.select_related('CreatedByUserID').order_by('-IsPinned', '-IsEmergency', '-PublishDate')
    return render(request, 'bims/announcements.html', {'announcements': announcements, 'role_name': role_name})


# --- 6. UNIFIED SYSTEM HUB (BARANGAY PROFILE, USER ACCOUNTS & RBAC, AUDIT TRAIL LOGS) ---
@login_required
@role_required(['Admin'])
def audit_logs_list(request):
    req_copy = request.GET.copy()
    req_copy['tab'] = 'audit'
    request.GET = req_copy
    return barangay_settings_view(request)


@login_required
@role_required(['Admin'])
def users_list(request):
    req_copy = request.GET.copy()
    req_copy['tab'] = 'users'
    request.GET = req_copy
    return barangay_settings_view(request)


@login_required
@role_required(['Admin'])
def barangay_settings_view(request):
    settings = BarangaySetting.get_settings()
    active_tab = request.GET.get('tab', 'profile')

    if request.method == 'POST':
        action = request.POST.get('action', 'update_settings')

        if action == 'toggle_status':
            user_id = request.POST.get('user_id')
            target_user = get_object_or_404(User, pk=user_id)
            if target_user.id == request.user.id:
                messages.error(request, "You cannot deactivate your own current administrative session.")
                return redirect('/settings/?tab=users')
            target_user.is_active = not target_user.is_active
            target_user.save()
            status_label = "activated" if target_user.is_active else "disabled / deactivated"
            log_action(request, f"{'Activated' if target_user.is_active else 'Deactivated'} User: {target_user.username}", "User Management")
            messages.success(request, f"User account '{target_user.username}' is now {status_label}.")
            return redirect('/settings/?tab=users')

        elif action == 'edit_user':
            user_id = request.POST.get('user_id')
            target_user = get_object_or_404(User, pk=user_id)
            role_id = request.POST.get('RoleID')
            email = request.POST.get('email', '').strip()
            new_password = request.POST.get('new_password', '').strip()

            if role_id:
                role = get_object_or_404(Role, pk=role_id)
                target_user.RoleID = role
                target_user.is_staff = (role.RoleName in ['Admin', 'Staff'])
            if email:
                target_user.email = email
            if new_password:
                target_user.set_password(new_password)
            target_user.save()
            log_action(request, f"Updated User privileges for {target_user.username} (Role: {target_user.RoleID.RoleName})", "User Management")
            messages.success(request, f"User account '{target_user.username}' privileges updated successfully.")
            return redirect('/settings/?tab=users')

        elif action == 'delete_user':
            user_id = request.POST.get('user_id')
            target_user = get_object_or_404(User, pk=user_id)
            if target_user.id == request.user.id:
                messages.error(request, "You cannot delete your own administrative account.")
                return redirect('/settings/?tab=users')
            u_name = target_user.username
            target_user.delete()
            log_action(request, f"Deleted User account: {u_name}", "User Management")
            messages.success(request, f"User account '{u_name}' deleted permanently.")
            return redirect('/settings/?tab=users')

        elif action == 'create_user':
            username = request.POST.get('username')
            password = request.POST.get('password')
            role_id = request.POST.get('RoleID')
            resident_id = request.POST.get('ResidentID') or None

            role = get_object_or_404(Role, pk=role_id)
            resident = Resident.objects.get(pk=resident_id) if resident_id else None

            new_user = User.objects.create_user(
                username=username,
                password=password,
                RoleID=role,
                ResidentID=resident,
                is_staff=(role.RoleName in ['Admin', 'Staff'])
            )
            log_action(request, f"Created User account: {new_user.username} (Role: {role.RoleName})", "User Management")
            messages.success(request, f"User {new_user.username} created.")
            return redirect('/settings/?tab=users')

        else:
            # Update Settings
            settings.BarangayName = request.POST.get('BarangayName', settings.BarangayName)
            settings.CityOrMunicipality = request.POST.get('CityOrMunicipality', settings.CityOrMunicipality)
            settings.Province = request.POST.get('Province', settings.Province)
            settings.Region = request.POST.get('Region', settings.Region)
            settings.PunongBarangay = request.POST.get('PunongBarangay', settings.PunongBarangay)
            settings.BarangaySecretary = request.POST.get('BarangaySecretary', settings.BarangaySecretary)
            settings.BarangayTreasurer = request.POST.get('BarangayTreasurer', settings.BarangayTreasurer)
            settings.ContactNumber = request.POST.get('ContactNumber', settings.ContactNumber)
            settings.EmailAddress = request.POST.get('EmailAddress', settings.EmailAddress)
            settings.BarangayHallAddress = request.POST.get('BarangayHallAddress', settings.BarangayHallAddress)
            settings.save()

            log_action(request, f"Updated Barangay Profile & Signatories for {settings.BarangayName}", "System Settings")
            messages.success(request, "Barangay Profile and Signatories updated successfully! All certificates and layouts now reflect these changes.")
            return redirect('/settings/?tab=profile')

    users = User.objects.select_related('RoleID', 'ResidentID').all().order_by('username')
    roles = Role.objects.all()
    residents = Resident.objects.filter(user_account__isnull=True).order_by('LastName')
    logs = AuditLog.objects.select_related('UserID').order_by('-Timestamp')[:100]

    return render(request, 'bims/barangay_settings.html', {
        'settings': settings,
        'users': users,
        'roles': roles,
        'residents': residents,
        'logs': logs,
        'active_tab': active_tab
    })


@login_required
@role_required(['Admin', 'Staff'])
def census_import_view(request):
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        if not csv_file.name.endswith('.csv'):
            messages.error(request, "Invalid file format. Please upload a standard .CSV file.")
            return redirect('census_import')

        try:
            decoded_file = csv_file.read().decode('utf-8-sig')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)

            created_residents = 0
            created_households = 0
            errors = []

            for row_idx, row in enumerate(reader, start=2):
                row = {k.strip(): (v.strip() if v else "") for k, v in row.items() if k}
                try:
                    hh_num = row.get('HouseholdNumber')
                    purok_name = row.get('PurokName', 'Purok 1')
                    zone_no_str = row.get('ZoneNo', '1')
                    try:
                        zone_no = int(zone_no_str)
                    except ValueError:
                        zone_no = 1

                    street = row.get('StreetAddress', 'Barangay Proper')
                    first_name = row.get('FirstName')
                    last_name = row.get('LastName')
                    middle_name = row.get('MiddleName', '')
                    sex = row.get('Sex', 'Male')
                    birth_date_str = row.get('BirthDate')
                    civil_status = row.get('CivilStatus', 'Single')
                    is_voter_val = str(row.get('IsVoter', '0')).lower() in ['1', 'true', 'yes', 'y']
                    employment = row.get('EmploymentStatus', 'Employed')
                    contact = row.get('ContactNo', '')
                    rel_head = row.get('RelationshipToHead', 'Head')
                    sectors_str = row.get('Sectors', '')

                    if not (first_name and last_name and hh_num and birth_date_str):
                        errors.append(f"Row {row_idx}: Missing required demographics (First Name, Last Name, Household #, or BirthDate).")
                        continue

                    # Parse BirthDate safely
                    try:
                        birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
                    except ValueError:
                        errors.append(f"Row {row_idx} ({first_name} {last_name}): Invalid date format '{birth_date_str}'. Expected YYYY-MM-DD.")
                        continue

                    # 1. Ensure Purok
                    purok, _ = Purok.objects.get_or_create(
                        PurokName=purok_name,
                        defaults={'ZoneNo': zone_no}
                    )

                    # 2. Ensure Household
                    household, hh_created = Household.objects.get_or_create(
                        HouseholdNumber=hh_num,
                        defaults={'PurokID': purok, 'StreetAddress': street}
                    )
                    if hh_created:
                        created_households += 1

                    # 3. Create or Get Resident
                    resident, res_created = Resident.objects.get_or_create(
                        FirstName=first_name,
                        LastName=last_name,
                        BirthDate=birth_date,
                        HouseholdID=household,
                        defaults={
                            'MiddleName': middle_name,
                            'Sex': sex,
                            'CivilStatus': civil_status,
                            'IsVoter': is_voter_val,
                            'EmploymentStatus': employment,
                            'ContactNo': contact,
                            'RelationshipToHead': rel_head
                        }
                    )
                    if res_created:
                        created_residents += 1

                    # 4. Map Sectors
                    if sectors_str:
                        sec_items = [s.strip() for s in sectors_str.replace(',', ';').split(';') if s.strip()]
                        for sname in sec_items:
                            sec_obj, _ = Sector.objects.get_or_create(SectorName=sname)
                            ResidentSector.objects.get_or_create(ResidentID=resident, SectorID=sec_obj)

                except Exception as ex:
                    errors.append(f"Row {row_idx}: {str(ex)}")

            log_action(request, f"Bulk Census Ingestion: Added {created_residents} residents, {created_households} households", "Census Ingestion")
            if created_residents > 0:
                messages.success(request, f"Bulk Ingestion Success! Successfully imported {created_residents} residents across {created_households} new households.")
            if errors:
                messages.warning(request, f"{len(errors)} row(s) had formatting errors and were skipped. Details: " + "; ".join(errors[:4]))

            return redirect('residents_list')

        except Exception as e:
            messages.error(request, f"Failed to parse CSV file: {str(e)}")
            return redirect('census_import')

    return render(request, 'bims/census_import.html')


@login_required
@role_required(['Admin', 'Staff'])
def census_sample_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="bims_census_template.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'HouseholdNumber', 'PurokName', 'ZoneNo', 'StreetAddress',
        'FirstName', 'LastName', 'MiddleName', 'Sex', 'BirthDate',
        'CivilStatus', 'IsVoter', 'EmploymentStatus', 'ContactNo',
        'RelationshipToHead', 'Sectors'
    ])
    writer.writerow([
        'HH-2026-050', 'Purok 1 - Sampaguita', '1', 'Block 12 Lot 4, Mabini St.',
        'Ricardo', 'Dalisay', 'Gomez', 'Male', '1982-05-14',
        'Married', '1', 'Employed', '09171234567',
        'Head', 'Senior Citizen'
    ])
    writer.writerow([
        'HH-2026-050', 'Purok 1 - Sampaguita', '1', 'Block 12 Lot 4, Mabini St.',
        'Alyana', 'Dalisay', 'Arevalo', 'Female', '1985-08-20',
        'Married', '1', 'Self-Employed', '09187654321',
        'Spouse', '4Ps Beneficiary'
    ])
    writer.writerow([
        'HH-2026-051', 'Purok 2 - Rosal', '1', '108 Rizal Avenue',
        'Mateo', 'Guidicelli', 'Fernandez', 'Male', '2001-03-10',
        'Single', '0', 'Student', '09201112233',
        'Son', 'PWD'
    ])
    return response


# --- CITIZEN ONLINE REGISTRATION & ADMIN APPROVAL GATEWAY ---
def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password')
        first_name = request.POST.get('FirstName', '').strip()
        last_name = request.POST.get('LastName', '').strip()
        middle_name = request.POST.get('MiddleName', '').strip()
        sex = request.POST.get('Sex')
        birth_date_str = request.POST.get('BirthDate')
        civil_status = request.POST.get('CivilStatus')
        employment = request.POST.get('EmploymentStatus')
        contact_no = request.POST.get('ContactNo', '').strip()
        email = request.POST.get('Email', '').strip()
        purok_id = request.POST.get('PurokID')
        street = request.POST.get('StreetAddress', '').strip()
        hh_num = request.POST.get('HouseholdNumber', '').strip()
        rel_head = request.POST.get('RelationshipToHead', '').strip()
        sectors_list = request.POST.getlist('sectors')
        proof_file = request.FILES.get('ProofOfResidencyImage')

        # Auto-generate clean unique username if not provided
        if not username:
            import re
            clean_first = re.sub(r'[^a-zA-Z0-9]', '', first_name).lower()
            clean_last = re.sub(r'[^a-zA-Z0-9]', '', last_name).lower()
            base_u = f"{clean_first[:1]}{clean_last}" if clean_first and clean_last else "resident"
            candidate = base_u
            counter = 1
            while User.objects.filter(username__iexact=candidate).exists() or CitizenRegistration.objects.filter(Username__iexact=candidate, Status='Pending').exists():
                candidate = f"{base_u}{counter}"
                counter += 1
            username = candidate
        else:
            if User.objects.filter(username__iexact=username).exists() or CitizenRegistration.objects.filter(Username__iexact=username, Status='Pending').exists():
                messages.error(request, f"The username '{username}' is already in use. Please select a different username.")
                puroks = Purok.objects.all().order_by('ZoneNo')
                sectors = Sector.objects.all()
                return render(request, 'bims/register.html', {'puroks': puroks, 'sectors': sectors})

        # Password handling: if citizen omitted password, assign unusable placeholder until approved
        password_hash = make_password(password) if password else make_password(None)

        if not email:
            messages.error(request, "Email (Gmail) is required. Please provide a valid email to receive your account activation notices.")
            puroks = Purok.objects.all().order_by('ZoneNo')
            sectors = Sector.objects.all()
            return render(request, 'bims/register.html', {'puroks': puroks, 'sectors': sectors})

        try:
            birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, "Invalid birth date format. Please select a valid date.")
            puroks = Purok.objects.all().order_by('ZoneNo')
            sectors = Sector.objects.all()
            return render(request, 'bims/register.html', {'puroks': puroks, 'sectors': sectors})

        purok = Purok.objects.filter(pk=purok_id).first()

        # Automated Census Cross-Check to see if person is already in Residents registry
        census_match = Resident.objects.filter(
            FirstName__iexact=first_name,
            LastName__iexact=last_name,
            BirthDate=birth_date
        ).first()

        app = CitizenRegistration.objects.create(
            Username=username,
            PasswordHash=password_hash,
            FirstName=first_name,
            LastName=last_name,
            MiddleName=middle_name,
            Sex=sex,
            BirthDate=birth_date,
            CivilStatus=civil_status,
            EmploymentStatus=employment,
            ContactNo=contact_no,
            Email=email if email else None,
            PurokID=purok,
            StreetAddress=street,
            HouseholdNumber=hh_num,
            RelationshipToHead=rel_head,
            Sectors=", ".join(sectors_list) if sectors_list else "",
            ProofOfResidencyImage=proof_file,
            ExistingResidentMatch=census_match,
            Status='Pending'
        )

        create_notification(
            title="New Resident Registration Pending Review",
            message=f"{first_name} {last_name} submitted registration #{app.ReferenceNumber} ({purok.PurokName if purok else 'Purok'}).",
            notif_type='registration',
            target_role='Staff',
            link_url=f"/citizen-applications/?highlight={app.RegistrationID}#reg-{app.RegistrationID}"
        )

        log_action(request, f"Submitted Citizen Registration: {app.ReferenceNumber} ({first_name} {last_name})", "Citizen Registration")
        return render(request, 'bims/registration_success.html', {'app': app})

    puroks = Purok.objects.all().order_by('ZoneNo')
    sectors = Sector.objects.all()
    return render(request, 'bims/register.html', {'puroks': puroks, 'sectors': sectors})


def registration_status_check(request):
    query = request.GET.get('ref', '').strip()
    result = None
    if query:
        result = CitizenRegistration.objects.filter(
            Q(ReferenceNumber__iexact=query) | Q(ContactNo=query)
        ).first()
    return render(request, 'bims/registration_status.html', {'result': result, 'query': query})


@login_required
@role_required(['Admin', 'Staff'])
def admin_registrations_list(request):
    status_filter = request.GET.get('status', 'Pending')
    registrations = CitizenRegistration.objects.select_related('PurokID', 'ExistingResidentMatch').all()
    if status_filter:
        registrations = registrations.filter(Status=status_filter)

    pending_count = CitizenRegistration.objects.filter(Status='Pending').count()
    return render(request, 'bims/admin_registrations.html', {
        'registrations': registrations,
        'status_filter': status_filter,
        'pending_count': pending_count
    })


@login_required
@role_required(['Admin', 'Staff'])
def admin_registration_process(request, pk):
    app = get_object_or_404(CitizenRegistration.objects.select_related('PurokID', 'ExistingResidentMatch'), pk=pk)

    if request.method == 'POST':
        action = request.POST.get('action') # 'approve', 'reject', or 'update_applicant_demographics'
        remarks = request.POST.get('AdminRemarks', '').strip()

        if action == 'update_applicant_demographics':
            app.FirstName = request.POST.get('FirstName', app.FirstName).strip()
            app.MiddleName = request.POST.get('MiddleName', app.MiddleName).strip()
            app.LastName = request.POST.get('LastName', app.LastName).strip()
            app.Sex = request.POST.get('Sex', app.Sex)
            birth_date_str = request.POST.get('BirthDate')
            if birth_date_str:
                try:
                    app.BirthDate = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    pass
            app.CivilStatus = request.POST.get('CivilStatus', app.CivilStatus)
            app.EmploymentStatus = request.POST.get('EmploymentStatus', app.EmploymentStatus)
            app.ContactNo = request.POST.get('ContactNo', app.ContactNo).strip()
            app.Email = request.POST.get('Email', app.Email).strip() or None
            purok_id = request.POST.get('PurokID')
            if purok_id:
                app.PurokID = Purok.objects.filter(pk=purok_id).first()
            app.StreetAddress = request.POST.get('StreetAddress', app.StreetAddress).strip()
            app.HouseholdNumber = request.POST.get('HouseholdNumber', app.HouseholdNumber).strip()
            app.RelationshipToHead = request.POST.get('RelationshipToHead', app.RelationshipToHead).strip()
            sectors_list = request.POST.getlist('sectors')
            if sectors_list:
                app.Sectors = ", ".join(sectors_list)

            # Recalculate census match in case name or birthdate was modified
            app.ExistingResidentMatch = Resident.objects.filter(
                FirstName__iexact=app.FirstName,
                LastName__iexact=app.LastName,
                BirthDate=app.BirthDate
            ).first()

            app.save()
            log_action(request, f"Updated Demographics for Registration #{app.ReferenceNumber} ({app.FirstName} {app.LastName})", "Citizen Registration")
            messages.success(request, f"Applicant Demographics & Residency Profile for #{app.ReferenceNumber} updated successfully.")
            return redirect('admin_registration_process', pk=app.RegistrationID)

        app.AdminRemarks = remarks
        app.ReviewedAt = timezone.now()
        app.ReviewedByUserID = request.user

        if action == 'approve':
            # 1. Resolve Household (Ensure sequential household number in order)
            hh_no = (app.HouseholdNumber or '').strip()
            if not hh_no:
                hh_no = generate_next_household_number()
            household, _ = Household.objects.get_or_create(
                HouseholdNumber=hh_no,
                defaults={'PurokID': app.PurokID, 'StreetAddress': app.StreetAddress}
            )

            # 2. Resolve or Create Resident Record (With Namesake Disambiguation Protection)
            treat_as_distinct_citizen = request.POST.get('treat_as_distinct_citizen') == '1'
            explicit_link_id = request.POST.get('link_to_resident_id')

            resident = None
            if not treat_as_distinct_citizen:
                if explicit_link_id:
                    resident = Resident.objects.filter(pk=explicit_link_id).first()
                else:
                    resident = app.ExistingResidentMatch

            if not resident:
                # Create a fresh, distinct Resident record (guarantees a separate unique ResidentID)
                resident = Resident.objects.create(
                    FirstName=app.FirstName,
                    LastName=app.LastName,
                    MiddleName=app.MiddleName,
                    Sex=app.Sex,
                    BirthDate=app.BirthDate,
                    CivilStatus=app.CivilStatus,
                    IsVoter=False,
                    EmploymentStatus=app.EmploymentStatus,
                    ContactNo=app.ContactNo,
                    HouseholdID=household,
                    RelationshipToHead=app.RelationshipToHead
                )
                if app.Sectors:
                    for sname in [s.strip() for s in app.Sectors.split(',') if s.strip()]:
                        sec_obj = Sector.objects.filter(SectorName=sname).first()
                        if sec_obj:
                            ResidentSector.objects.get_or_create(ResidentID=resident, SectorID=sec_obj)

            # 3. Create active User Account with role People
            people_role = Role.objects.get(RoleName='People')
            temp_pass_input = request.POST.get('temporary_password', '').strip()

            import secrets, string
            if temp_pass_input:
                final_password = temp_pass_input
            elif not app.PasswordHash or app.PasswordHash.startswith('!'):
                # Resident registered without password; generate random 6-digit temporary password
                digits = ''.join(secrets.choice(string.digits) for _ in range(6))
                final_password = f"Bims-{digits}!"
            else:
                final_password = None

            user = User.objects.create(
                username=app.Username,
                password=app.PasswordHash if not final_password else make_password(final_password),
                first_name=app.FirstName,
                last_name=app.LastName,
                email=app.Email or "",
                RoleID=people_role,
                ResidentID=resident,
                is_active=True
            )

            if final_password:
                user.set_password(final_password)
                user.save()
                password_in_email = final_password
            else:
                password_in_email = "The secure password you provided during registration"

            app.Status = 'Approved'
            app.save()

            # 4. Dispatch Email with Username and Password
            if app.Email:
                from django.core.mail import send_mail
                email_subject = f"Barangay Baan - Citizen Account Approved ({app.ReferenceNumber})"
                email_body = (
                    f"Magandang araw, {app.FirstName} {app.LastName}!\n\n"
                    f"Your registration application has been reviewed and APPROVED by the Barangay Council!\n\n"
                    f"Here are your login credentials:\n"
                    f"Citizen Portal: http://127.0.0.1:8000/login/\n"
                    f"Username: {user.username}\n"
                    f"Password: {password_in_email}\n"
                    f"Reference Code: {app.ReferenceNumber}\n\n"
                    f"You may now request clearances, view community advisories, and track status online.\n\n"
                    f"Maraming salamat,\n"
                    f"Office of the Barangay Secretary\n"
                    f"Barangay Baan"
                )
                try:
                    send_mail(
                        subject=email_subject,
                        message=email_body,
                        from_email='notifications@barangaysanroque.gov.ph',
                        recipient_list=[app.Email],
                        fail_silently=True
                    )
                except Exception:
                    pass

            # Create in-app notification for resident
            create_notification(
                title="Resident Account Approved & Activated",
                message=f"Welcome {app.FirstName}! Your resident account has been reviewed, approved, and activated by the Barangay Council.",
                notif_type="registration",
                target_role="People",
                recipient_user=user,
                link_url="/dashboard/"
            )

            log_action(request, f"Approved Citizen Registration {app.ReferenceNumber} for {resident.full_name} (Account: {user.username})", "Citizen Registration")
            messages.success(request, f"Citizen Registration {app.ReferenceNumber} approved! Account '{user.username}' activated and email sent to {app.Email}.")

        elif action == 'reject':
            app.Status = 'Rejected'
            app.save()
            log_action(request, f"Rejected Citizen Registration {app.ReferenceNumber} (Reason: {remarks})", "Citizen Registration")
            messages.warning(request, f"Citizen Registration {app.ReferenceNumber} marked as Rejected.")

        return redirect('admin_registrations')

    # Look up namesake residents with identical name (First & Last)
    namesake_residents = Resident.objects.filter(
        FirstName__iexact=app.FirstName,
        LastName__iexact=app.LastName
    ).select_related('HouseholdID', 'HouseholdID__PurokID')

    matching_resident_ids = list(namesake_residents.values_list('ResidentID', flat=True))
    if app.ExistingResidentMatch and app.ExistingResidentMatch.ResidentID not in matching_resident_ids:
        matching_resident_ids.append(app.ExistingResidentMatch.ResidentID)

    # Fetch any existing document requests associated with those resident IDs
    matched_document_requests = DocumentRequest.objects.filter(
        ResidentID__in=matching_resident_ids
    ).select_related('DocumentTypeID', 'ResidentID', 'PaymentID').order_by('-RequestDate')

    puroks = Purok.objects.all().order_by('ZoneNo')
    sectors = Sector.objects.all()

    return render(request, 'bims/admin_registration_detail.html', {
        'app': app,
        'puroks': puroks,
        'sectors': sectors,
        'namesake_residents': namesake_residents,
        'matched_document_requests': matched_document_requests,
        'has_matching_documents': matched_document_requests.exists(),
    })


@login_required
def notification_mark_read(request, pk):
    notif = get_object_or_404(Notification, pk=pk)
    notif.IsRead = True
    notif.save()
    if request.headers.get('HX-Request') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return HttpResponse("")
    return redirect(notif.LinkURL or 'dashboard')


@login_required
def notification_mark_all_read(request):
    user = request.user
    role_name = user.RoleID.RoleName if user.RoleID else "Admin"
    if role_name == 'Admin' or user.is_superuser:
        Notification.objects.filter(Q(RecipientUser=user) | Q(TargetRole__in=['Admin', 'Staff', 'All'])).update(IsRead=True)
    elif role_name == 'Staff':
        Notification.objects.filter(Q(RecipientUser=user) | Q(TargetRole__in=['Staff', 'All'])).update(IsRead=True)
    else:
        Notification.objects.filter(Q(RecipientUser=user) | Q(TargetRole__in=['People', 'All'])).update(IsRead=True)
    messages.success(request, "All notifications marked as read.")
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))



