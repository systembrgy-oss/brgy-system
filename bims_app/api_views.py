import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Sum, Q
from .models import (
    Resident, Household, Sector, ResidentSector,
    DocumentType, DocumentRequest, Payment, BarangaySetting
)

# --------------------------------------------------------------------------
# 1. API System Health Check
# --------------------------------------------------------------------------
@require_GET
def api_health(request):
    """
    Public Health & Meta endpoint for API heartbeat and version info.
    """
    settings = BarangaySetting.get_settings()
    return JsonResponse({
        "status": "online",
        "timestamp": timezone.now().isoformat(),
        "api_version": "v1.0.0",
        "service": "BIMS Core REST API",
        "jurisdiction": {
            "barangay": settings.BarangayName,
            "municipality": settings.CityOrMunicipality,
            "province": settings.Province
        }
    }, status=200)


# --------------------------------------------------------------------------
# 2. Public Document Verification API (Anti-Tamper QR Verification)
# --------------------------------------------------------------------------
@require_GET
def api_document_verify(request, qr_hash):
    """
    Public REST endpoint for verifying physical/digital document authenticity.
    Used by employers, banks, and external agencies scanning the document's QR code.
    """
    doc_req = DocumentRequest.objects.filter(QRCodeHash=qr_hash).select_related(
        'ResidentID', 'DocumentTypeID', 'PaymentID'
    ).first()

    if not doc_req:
        return JsonResponse({
            "success": False,
            "verification_status": "INVALID_OR_NOT_FOUND",
            "message": "No document record found matching this QR verification hash.",
            "qr_hash": qr_hash
        }, status=404)

    settings = BarangaySetting.get_settings()
    res = doc_req.ResidentID
    payment = doc_req.PaymentID

    return JsonResponse({
        "success": True,
        "verification_status": "AUTHENTIC_AND_VERIFIED",
        "data": {
            "request_id": doc_req.RequestID,
            "qr_code_hash": doc_req.QRCodeHash,
            "document_type": doc_req.DocumentTypeID.DocumentTypeName,
            "purpose": doc_req.Purpose,
            "status": doc_req.RequestStatus,
            "request_date": doc_req.RequestDate.strftime('%Y-%m-%d %H:%M:%S'),
            "recipient": {
                "resident_id": res.ResidentID,
                "full_name": res.full_name,
                "civil_status": res.CivilStatus,
                "voter": res.IsVoter
            },
            "payment": {
                "official_receipt_no": payment.OfficialReceiptNo if payment else None,
                "amount_paid": str(payment.AmountPaid) if payment else "0.00",
                "payment_date": payment.PaymentDate.strftime('%Y-%m-%d') if payment else None
            },
            "issuing_authority": {
                "barangay": settings.BarangayName,
                "city_municipality": settings.CityOrMunicipality,
                "province": settings.Province,
                "punong_barangay": settings.PunongBarangay
            }
        }
    }, status=200)


# --------------------------------------------------------------------------
# 3. Demographic & Governance Statistics API
# --------------------------------------------------------------------------
@require_GET
def api_statistics_summary(request):
    """
    Live demographics, priority sectors, and treasury performance metrics.
    Can be ingested by external City/Municipal dashboards or open data portals.
    """
    total_residents = Resident.objects.count()
    total_households = Household.objects.count()

    male_count = Resident.objects.filter(Sex='Male').count()
    female_count = Resident.objects.filter(Sex='Female').count()
    voters_count = Resident.objects.filter(IsVoter=True).count()

    # Sector breakdown
    senior_count = ResidentSector.objects.filter(SectorID__SectorName__icontains='Senior').count()
    pwd_count = ResidentSector.objects.filter(SectorID__SectorName__icontains='PWD').count()
    solo_parent_count = ResidentSector.objects.filter(SectorID__SectorName__icontains='Solo Parent').count()
    four_ps_count = ResidentSector.objects.filter(SectorID__SectorName__icontains='4Ps').count()

    # Document & revenue metrics
    total_docs = DocumentRequest.objects.count()
    pending_docs = DocumentRequest.objects.filter(RequestStatus='Pending').count()
    approved_docs = DocumentRequest.objects.filter(RequestStatus='Approved').count()
    total_revenue = Payment.objects.aggregate(total=Sum('AmountPaid'))['total'] or 0.00

    settings = BarangaySetting.get_settings()

    return JsonResponse({
        "success": True,
        "barangay_profile": {
            "name": settings.BarangayName,
            "city_municipality": settings.CityOrMunicipality,
            "province": settings.Province
        },
        "demographics": {
            "total_residents": total_residents,
            "total_households": total_households,
            "male_count": male_count,
            "female_count": female_count,
            "voters": voters_count,
            "non_voters": total_residents - voters_count
        },
        "priority_sectors": {
            "senior_citizens": senior_count,
            "persons_with_disability": pwd_count,
            "solo_parents": solo_parent_count,
            "four_ps_beneficiaries": four_ps_count
        },
        "treasury_and_services": {
            "total_requests": total_docs,
            "pending_requests": pending_docs,
            "approved_requests": approved_docs,
            "total_revenue_collected_php": float(total_revenue)
        }
    }, status=200)


# --------------------------------------------------------------------------
# 4. Document Types Catalog API
# --------------------------------------------------------------------------
@require_GET
def api_document_types(request):
    """
    Returns all standard certifications/clearances available in the barangay.
    """
    doc_types = DocumentType.objects.all().order_by('DocumentTypeID')
    results = []
    for dt in doc_types:
        results.append({
            "id": dt.DocumentTypeID,
            "name": dt.DocumentTypeName,
            "fee": float(dt.StandardFee)
        })

    return JsonResponse({
        "success": True,
        "count": len(results),
        "document_types": results
    }, status=200)


# --------------------------------------------------------------------------
# 5. Resident Lookup & Search API
# --------------------------------------------------------------------------
@require_GET
def api_residents_search(request):
    """
    Search resident profiles by name, contact, or household number.
    Accepts query param: ?q=query_string&limit=15
    """
    query = request.GET.get('q', '').strip()
    limit = int(request.GET.get('limit', 15))
    limit = min(limit, 50)

    qs = Resident.objects.select_related('HouseholdID__PurokID').all()

    if query:
        qs = qs.filter(
            Q(FirstName__icontains=query) |
            Q(LastName__icontains=query) |
            Q(ContactNo__icontains=query) |
            Q(HouseholdID__HouseholdNumber__icontains=query)
        )

    results = []
    for r in qs[:limit]:
        results.append({
            "id": r.ResidentID,
            "full_name": r.full_name,
            "sex": r.Sex,
            "age": r.age,
            "civil_status": r.CivilStatus,
            "is_voter": r.IsVoter,
            "contact_no": r.ContactNo or "N/A",
            "purok": r.HouseholdID.PurokID.PurokName if r.HouseholdID and r.HouseholdID.PurokID else "Unassigned",
            "household_number": r.HouseholdID.HouseholdNumber if r.HouseholdID else "N/A"
        })

    return JsonResponse({
        "success": True,
        "query": query,
        "count": len(results),
        "residents": results
    }, status=200)


# --------------------------------------------------------------------------
# 6. Document Request Submission API
# --------------------------------------------------------------------------
@csrf_exempt
@require_POST
def api_document_request_submit(request):
    """
    Submits a new document request programmatically via JSON payload.
    Expected Payload:
    {
        "resident_id": 1,
        "document_type_id": 1,
        "purpose": "Employment requirement"
    }
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({
            "success": False,
            "error": "Invalid JSON format in request body."
        }, status=400)

    resident_id = data.get('resident_id')
    doc_type_id = data.get('document_type_id')
    purpose = data.get('purpose', '').strip()

    if not resident_id or not doc_type_id or not purpose:
        return JsonResponse({
            "success": False,
            "error": "Missing required fields: 'resident_id', 'document_type_id', and 'purpose' are mandatory."
        }, status=400)

    resident = Resident.objects.filter(pk=resident_id).first()
    if not resident:
        return JsonResponse({
            "success": False,
            "error": f"Resident with ID {resident_id} does not exist."
        }, status=404)

    doc_type = DocumentType.objects.filter(pk=doc_type_id).first()
    if not doc_type:
        return JsonResponse({
            "success": False,
            "error": f"DocumentType with ID {doc_type_id} does not exist."
        }, status=404)

    new_request = DocumentRequest.objects.create(
        ResidentID=resident,
        DocumentTypeID=doc_type,
        Purpose=purpose,
        RequestStatus='Pending'
    )

    return JsonResponse({
        "success": True,
        "message": "Document request created successfully via API.",
        "data": {
            "request_id": new_request.RequestID,
            "qr_code_hash": new_request.QRCodeHash,
            "document_type": doc_type.DocumentTypeName,
            "resident_name": resident.full_name,
            "purpose": new_request.Purpose,
            "status": new_request.RequestStatus,
            "standard_fee": float(doc_type.StandardFee),
            "created_at": new_request.RequestDate.strftime('%Y-%m-%d %H:%M:%S')
        }
    }, status=201)
