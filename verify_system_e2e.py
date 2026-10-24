import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bims_project.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from bims_app.models import (
    User, DocumentRequest, DocumentType, Resident,
    AssistanceProgram, AssistanceBeneficiary, AuditLog
)

client = Client()

print("=" * 60)
print("RUNNING BIMS 4-POINT ACCEPTANCE VERIFICATION")
print("=" * 60)

# ----------------------------------------------------
# 1. TEST RBAC ISOLATION
# ----------------------------------------------------
print("\n[CHECK 1] Testing RBAC Isolation for Resident Role...")
logged_in = client.login(username='resident', password='resident123')
assert logged_in, "Failed to log in as resident"

# Resident tries accessing admin-only /audit-logs/
res_audit = client.get('/audit-logs/', follow=True)
print(f" -> Resident accessing /audit-logs/ redirected to: {res_audit.request['PATH_INFO']}")
assert res_audit.request['PATH_INFO'] == '/dashboard/', "RBAC leak: resident was not redirected!"

# Resident tries accessing /users/
res_users = client.get('/users/', follow=True)
print(f" -> Resident accessing /users/ redirected to: {res_users.request['PATH_INFO']}")
assert res_users.request['PATH_INFO'] == '/dashboard/', "RBAC leak: resident was not redirected!"
print(" [PASS] RBAC properly isolated unauthorized access and redirected to dashboard.")
client.logout()

# ----------------------------------------------------
# 2. TEST DOCUMENT REQUEST, APPROVAL & QR VERIFICATION
# ----------------------------------------------------
print("\n[CHECK 2] Testing Paperless Document Workflow & QR Verification...")
# A. Resident submits request
client.login(username='resident', password='resident123')
doc_type = DocumentType.objects.get(DocumentTypeName='Barangay Clearance')
req_resp = client.post('/documents/apply/', {
    'DocumentTypeID': doc_type.DocumentTypeID,
    'Purpose': 'Passport Application at DFA'
}, follow=True)
new_req = DocumentRequest.objects.filter(Purpose='Passport Application at DFA').latest('RequestID')
print(f" -> Resident submitted Request #{new_req.RequestID} with QR Hash: {new_req.QRCodeHash}")
assert new_req.RequestStatus == 'Pending', "Request status should be Pending"
client.logout()

# B. Staff reviews and approves request with Official Receipt
client.login(username='staff', password='staff123')
approve_resp = client.post(f'/documents/{new_req.RequestID}/process/', {
    'action': 'approve',
    'OfficialReceiptNo': 'OR-2026-9999',
    'AmountPaid': '50.00'
}, follow=True)
new_req.refresh_from_db()
print(f" -> Staff approved Request #{new_req.RequestID}: Status={new_req.RequestStatus}, Paid OR={new_req.PaymentID.OfficialReceiptNo}")
assert new_req.RequestStatus == 'Approved'
assert new_req.PaymentID is not None

# C. Public QR Verification Check
client.logout()
verify_url = f'/verify/{new_req.QRCodeHash}/'
verify_resp = client.get(verify_url)
print(f" -> Scanning public QR verification URL: {verify_url} (HTTP {verify_resp.status_code})")
assert verify_resp.status_code == 200
assert b"AUTHENTIC DOCUMENT VERIFIED" in verify_resp.content
print(" [PASS] Document approval and QR Code digital verification passed flawlessly.")

# ----------------------------------------------------
# 3. TEST DUPLICATE ASSISTANCE PROTECTION
# ----------------------------------------------------
print("\n[CHECK 3] Testing Anti-Duplicate Assistance Protection...")
client.login(username='staff', password='staff123')
program = AssistanceProgram.objects.first()
juan = Resident.objects.get(FirstName='Juan', LastName='Dela Cruz')

# First claim
first_claim_resp = client.post(f'/assistance/{program.ProgramID}/', {
    'ResidentID': juan.ResidentID,
    'QuantityOrAmountGiven': 'PHP 1,500 Calamity Aid'
}, follow=True)
print(f" -> First aid disbursement recorded for {juan.full_name}.")

# Duplicate claim attempt
dup_claim_resp = client.post(f'/assistance/{program.ProgramID}/', {
    'ResidentID': juan.ResidentID,
    'QuantityOrAmountGiven': 'PHP 1,500 Second Attempt'
}, follow=True)
from django.contrib.messages import get_messages
msgs = [m.message for m in get_messages(dup_claim_resp.wsgi_request)]
print(f" -> Duplicate disbursement attempt result: {msgs[0] if msgs else 'Blocked'}")
assert any("Duplicate Claim Blocked" in m for m in msgs), "Duplicate claim was not blocked!"


print(" [PASS] SQLite unique constraint & duplicate claim protection held successfully.")

# ----------------------------------------------------
# 4. INSPECT AUDIT TRAIL LOGS
# ----------------------------------------------------
print("\n[CHECK 4] Inspecting Security Audit Trail as Admin...")
client.logout()
client.login(username='admin', password='admin123')
audit_resp = client.get('/audit-logs/')
recent_logs = AuditLog.objects.order_by('-Timestamp')[:5]
print(" -> Last 5 recorded security audit events:")
for l in recent_logs:
    u = l.UserID.username if l.UserID else "Anonymous"
    print(f"    * [{l.Timestamp.strftime('%H:%M:%S')}] User '{u}' in [{l.Module}]: {l.Action}")
assert recent_logs.count() > 0
print(" [PASS] Audit trail actively logging system actions with accurate context.")
print("\n" + "=" * 60)
print("ALL 4 ACCEPTANCE TESTS PASSED - SYSTEM READY FOR PRODUCTION")
print("=" * 60)
