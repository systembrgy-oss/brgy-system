# Barangay Information Management System (BIMS)

A complete, 3NF-normalized web application built with **Python 3.12**, **Django 6**, **SQLite**, and modern frontend UI featuring **Lucide Icons** and **Role-Based Access Control (RBAC)**.

---

## 🏛️ System Features & Core Modules

### 1. Resident Profiling & Household Management
- **Demographics & Census**: First name, last name, middle name, birth date, computed age, sex, civil status, contact info, employment, and voter status.
- **Vulnerable Sectors Tracking**: Senior Citizen, PWD, Solo Parent, and 4Ps Beneficiary classifications.
- **Household Mapping**: Households mapped by Purok/Zone and street address with family head relationship hierarchy.

### 2. Paperless Document Request & Issuance
- **Applications**: Barangay Clearance, Certificate of Indigency, Certificate of Residency, Business Permit Clearance, and First-Time Job Seeker Certificate.
- **Digital Stamp & Signatures**: Official Punong Barangay signature line and stamp upon approval.
- **Instant QR Code Verification**: Every approved certificate embeds a tamper-proof QR code pointing to `/verify/<QRCodeHash>/` for instant smartphone verification.
- **Official Receipt & Fee Tracking**: Tracks OR numbers and fees.

### 3. Blotter & Incident Management (Katarungang Pambarangay)
- **Incident Intake**: Complainant, respondent, statement of facts, and confidential case toggle.
- **Conciliation Hearings**: Schedule 1st, 2nd, and 3rd summons and conciliation hearings with remarks.
- **Status Lifecycle**: `Filed` ➔ `Under Mediation` ➔ `Resolved` ➔ `Escalated` (Certificate to File Action).

### 4. Health, Welfare & Financial Assistance
- **Ayuda & Assistance Distribution**: Tracks relief packages, cash, or medical assistance.
- **Anti-Duplicate Claim Protection**: Database enforces `UNIQUE(ProgramID, ResidentID)` to prevent double claiming.
- **Health Center Consultation**: Vaccination logs, maternal care, and general checkups.
- **Medicine Dispensary**: Pharmacy inventory with real-time stock deductions upon dispensing.

### 5. Community Bulletins & Emergency Alerts
- High-visibility emergency alert banners across all pages.
- Category filters (Emergency, Community Event, Health, Ordinance, Welfare).

### 6. System Security & Audit Trail (RA 10173 Compliance)
- Full Audit Trail logging actor, action, timestamp, module, and client IP address.
- Role-Based Access Control (RBAC) protecting views and resident data.

### 7. Dynamic Barangay Profile & Signatories (Option 1)
- Accessible via `/settings/` for the Administrator.
- Dynamically configures Barangay Name, City/Municipality, Province, Region, Punong Barangay, Secretary, Treasurer, and Barangay Hall Address without hardcoding.
- Immediately updates all printable PDF certificates, official seals, and the public verification portal.

### 8. Bulk Census Ingestion via CSV / Excel (Option 2)
- Accessible via `/residents/import/`.
- Downloadable official sample template (`/residents/import/sample/`).
- Ingests hundreds of residents at once, automatically resolving or creating Puroks, Households, Resident demographics, and Sector classifications.

### 9. Visual Analytics & Executive Demographic Charts (Option 3)
- Powered by Chart.js on the main dashboard.
- **Population Distribution by Purok / Zone** (Vertical Bar Chart).
- **Priority Sectors Ratio** (Doughnut Chart: Senior Citizens, PWD, Solo Parents, 4Ps).
- **Voter Registration Status** (Pie Chart: Registered Voters vs Non-Voters).
- **Clearance Volume & Treasury Revenue Summary** (Horizontal Bar Chart + Total PHP collected badge).


---

## 👥 Demo User Credentials

The database is pre-seeded with 3 roles ready for testing:

| Role | Username | Password | Access Privileges |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin` | `admin123` | Full Access (SuperAdmin, Users, Audit Logs, Clearances, Blotter) |
| **Staff** | `staff` | `staff123` | Operations (Resident registration, process requests, blotter, clinics) |
| **People (Resident)** | `resident` | `resident123` | Citizen Portal (View own profile, apply for clearances, view status) |

*(Note: The login page also features 1-click demo switcher buttons for instant role switching during testing.)*

---

## 🎨 Icon Library Choice: Lucide Icons

- **Why Lucide Icons?** 
  - Standardized **24×24 pixel grid** with a consistent **2px stroke width**.
  - High legibility on both low-dpi monitors and mobile devices.
  - Zero layout shift and zero bloated font files.
  - Seamless semantic metaphors tailored for public sector dashboards (`users`, `file-check-2`, `scale`, `landmark`, `shield-check`, `hand-heart`, `pill`).

---

## 🚀 Running the Project

```bash
# 1. Activate Virtual Environment
.\venv\Scripts\activate

# 2. Run Database Migrations (already completed)
python manage.py migrate

# 3. Seed Sample Data (already completed)
python manage.py seed_bims

# 4. Start Development Server
python manage.py runserver 127.0.0.1:8000
```

Access the application in your browser:
- **Main Portal**: `http://127.0.0.1:8000/`
- **QR Certificate Verification Example**: `http://127.0.0.1:8000/verify/BIMS-BC-20260401-001/`
- **Django Admin**: `http://127.0.0.1:8000/admin/`
