# BIMS FINAL PRESENTATION DEFENSE GUIDE & Q&A CHEAT SHEET
**SIA 2 – Systems Integration and Architecture 2 · Final Presentation Defense**  
**Date of Defense:** Tuesday, October 27, 2026  
**Target Score:** 100 / 100 in Part B (Presentation and Demo)

---

## ⚠️ 1. CRITICAL PRE-FLIGHT CHECKLIST (ZERO AI POLICY)
The instructor explicitly noted in the rules:
> *"Your instructor may check your open windows and taskbar before you start. Penalty: First offense = -20 pts; Second offense = presentation stops, Part B = 0."*

Before stepping up to present, perform this 60-second cleanup on the laptop:
* [ ] **Close AI Coding Apps:** Ensure Antigravity, Cursor, Windsurf, Claude Code, etc. are completely closed.
* [ ] **VS Code AI Check:** If using VS Code, click the Copilot icon in the status bar and select **Disable Globally** / Sign out.
* [ ] **Browser Tabs:** Close all ChatGPT, Claude, Gemini, Copilot, and AI search tabs.
* [ ] **Ready Only Permitted Tools:**
  1. Browser (Chrome/Edge/Firefox) opened to `http://127.0.0.1:8000/`.
  2. Terminal / PowerShell running `python manage.py runserver 127.0.0.1:8000`.
  3. Postman opened with your 4 saved API requests.
  4. PowerPoint / Google Slides opened in presentation mode.

---

## 2. TIMED PRESENTATION OUTLINE (10 MINUTES TOTAL)
*(Scores B1: Organization and Time - Ends on time with logical flow)*

| Timestamp | Phase | Presenter | Key Focus |
| :--- | :--- | :--- | :--- |
| **0:00 - 1:30** | Introduction & Problem Statement | Member 1 | Why BIMS was built (paper logbooks, fake clearances, ayuda fraud). |
| **1:30 - 3:30** | Technical Explanations (B3) | Member 2 & 3 | Architecture (MVT + REST), Database (3NF ERD), Security (RBAC & RA 10173). |
| **3:30 - 7:30** | Live System Walkthrough (B2) | All Members | 1. Public intake ➔ 2. Admin approval ➔ 3. Clearance OR & QR Print ➔ 4. Anti-Duplicate Ayuda. |
| **7:30 - 8:30** | Live Postman API Demo (A2) | Member 4 | Query `/api/v1/health/`, `/api/v1/verify/`, and `/api/v1/statistics/summary/` live. |
| **8:30 - 10:00**| Q&A Defense (B4) | All Members | Confidently explain design choices and database constraints. |

---

## 3. THE 4 TECHNICAL EXPLANATIONS (CRITERION B3 - 20 POINTS)
Every group member should memorize their assigned pillar:

### Pillar 1: System Architecture (MVT + Service-Oriented REST)
> *"Our system is built on Django's Model-View-Template (MVT) architecture augmented with a decoupled RESTful service layer. The Model handles data validation and 3NF database transactions; the View enforces role-based access control and business logic; and the Template serves responsive, accessible UI components. Simultaneously, our REST API layer under `/api/v1/` exposes stateless endpoints for external integrations and automated verification."*

### Pillar 2: Database Design & 3NF Normalization
> *"Our database consists of 22 normalized relational tables adhering strictly to Third Normal Form (3NF). We have eliminated transitive and partial dependencies. For instance, household demographics are separated from individual resident profiles, and priority sector tags are decoupled using a junction table (`ResidentSectors`). To prevent double claiming during financial aid distributions, we enforced a composite constraint: `UNIQUE(ProgramID, ResidentID)` directly in the database engine."*

### Pillar 3: API & System Integration
> *"Under the course competencies of Systems Integration, BIMS provides a live RESTful API. We have public endpoints like `/api/v1/health/` and `/api/v1/verify/<qr_hash>/` which allows external agencies, banks, and employers to authenticate printed barangay clearances without exposing our internal database. We also provide demographic summary APIs that can feed into higher-level Municipal or City LGU dashboards."*

### Pillar 4: Security Measures (RBAC & RA 10173 Compliance)
> *"Security is architected in accordance with the Data Privacy Act of 2012 (Republic Act 10173). Passwords are never stored in plaintext; they use salted PBKDF2 with SHA-256 encryption. We implement Role-Based Access Control dividing privileges between Admin, Staff, and Citizens. Furthermore, every data mutation is recorded in an immutable `AuditLogs` table capturing the actor, module, action timestamp, and client IP address."*

---

## 4. STEP-BY-STEP LIVE DEMO SCRIPT (CRITERION B2 - 20 POINTS)

### Step 1: Citizen Public Intake (Show citizen independence)
1. Open browser at `http://127.0.0.1:8000/`.
2. Say: *"Residents do not need to line up at the barangay hall. They register directly through our citizen portal."*
3. Show the **Register as Citizen** page with Purok and Household dropdowns.
4. Show how the applicant receives a Reference Number (`REG-YYYYMM-XXXXXX`) to track their application.

### Step 2: Admin Approval & RBAC Isolation
1. Log in as `admin` (use the 1-click demo switcher or enter `admin` / `admin123`).
2. Show the **Citizen Applications** queue (`/citizen-applications/`).
3. Click **Approve**. Say: *"The system validates the resident into the census database and activates their login credentials."*
4. Quick RBAC proof: Explain how citizens attempting to visit `/audit-logs/` are automatically blocked and redirected to dashboard.

### Step 3: Document Request, Receipt, & QR Code Generation
1. Switch to `resident` account (`resident` / `resident123`).
2. Apply for a **Barangay Clearance** with Purpose: *"Job Application"*.
3. Switch to `staff` account (`staff` / `staff123`).
4. Go to `/documents/`, find the request, and click **Process Request**.
5. Enter Official Receipt No: `OR-2026-8888` and Fee: `50.00`. Click **Approve**.
6. Click **Print Official Certificate**:
   * Show the dynamic barangay header, official dry seal, and the **tamper-proof QR Code**.
   * Open the QR code URL (`/verify/<QRCodeHash>/`) to demonstrate the live public verification badge.

### Step 4: Anti-Duplicate Ayuda Protection (The "Wow" Feature)
1. Go to `/assistance/` and open an active relief program (e.g., *Calamity Ayuda Relief*).
2. Record disbursement to resident **Juan Dela Cruz**. (Successful).
3. Immediately try recording **Juan Dela Cruz** again in the exact same program.
4. Show the alert banner: **"Duplicate Claim Blocked: This resident has already claimed assistance under this program."**
5. Say: *"This eliminates double claiming and ghost beneficiaries during aid distribution."*

### Step 5: Live Postman API Demo (Criterion A2 - 20 Points)
1. Switch to the **Postman** window.
2. **Request 1:** Send `GET http://127.0.0.1:8000/api/v1/health/` ➔ Show `200 OK` and `"status": "online"`.
3. **Request 2:** Send `GET http://127.0.0.1:8000/api/v1/statistics/summary/` ➔ Show live JSON demographics, senior citizen counts, and total revenue.
4. **Request 3:** Send `GET http://127.0.0.1:8000/api/v1/residents/search/?q=Juan` ➔ Show search results returning Juan Dela Cruz with household and purok details.
5. Say: *"External government systems can consume our live REST API endpoints without requiring direct database access."*

---

## 5. TOP 10 PROFESSOR Q&A QUESTIONS & MODEL ANSWERS (CRITERION B4)

### Q1: "Why did you choose Django instead of pure PHP or Express/Node.js?"
> **Answer:** *"Django provides enterprise-level security out of the box—specifically built-in CSRF token validation, SQL injection prevention via parameterized ORM queries, and PBKDF2 password hashing. In local governance systems handling sensitive citizen demographics under RA 10173, security and database integrity are paramount."*

### Q2: "How does your system enforce 3NF normalization in the database?"
> **Answer:** *"We eliminated partial dependencies by ensuring all attributes depend on the full primary key. We also removed transitive dependencies—for example, rather than storing Purok name and Zone inside the Residents table, we created a `Households` table linked to a `Puroks` table. Furthermore, multi-valued attributes like priority sectors (Senior, PWD, 4Ps) are normalized through the `ResidentSectors` junction table."*

### Q3: "What prevents someone from printing a fake Barangay Clearance with a fabricated QR code?"
> **Answer:** *"The QR code does not contain static resident text; it contains a unique cryptographic hash (`QRCodeHash`) generated on our server upon approval. When scanned, it queries our live verification endpoint (`/verify/<hash>/`). If someone alters the certificate or forges a QR code, our database will find no matching record and flag it as `INVALID_OR_NOT_FOUND`."*

### Q4: "How is your system integrated with external systems? (SIA 2 Core Competency)"
> **Answer:** *"We have a dedicated REST API service layer under `/api/v1/`. Any authorized external entity—such as a City Hall demographic aggregation system, law enforcement background check terminal, or employer verification portal—can query our `/api/v1/verify/` and `/api/v1/statistics/summary/` endpoints securely over HTTP."*

### Q5: "How did you prevent duplicate assistance claims in the database?"
> **Answer:** *"We enforce integrity at two levels: First, in the database schema, the `AssistanceBeneficiaries` table has a composite unique constraint: `UNIQUE(ProgramID, ResidentID)`. If a duplicate is attempted, SQLite raises an integrity exception. Second, in our Django view logic, we check for prior disbursement before attempting insertion, providing a clean user feedback banner."*

### Q6: "How do you handle Data Privacy Act (RA 10173) compliance?"
> **Answer:** *"We implement three key pillars: 
1. **Access Control (RBAC):** Residents only see their own records; staff only see operational data; only admins see system-wide logs.
2. **Confidentiality Toggles:** Blotter complaints involving domestic disputes or minors are marked confidential and hidden from unauthorized staff.
3. **Audit Trail:** Every addition, update, or login is recorded with timestamp and IP address in the `AuditLogs` table."*

### Q7: "What happens if a resident does not have internet access or a smartphone?"
> **Answer:** *"BIMS supports assisted front-desk encoding. Barangay staff can encode walk-in residents directly via `/residents/new/` or import bulk census data from surveys using our CSV ingestion tool (`/residents/import/`). The printed certificates they receive are physically valid and can be verified by any third party."*

### Q8: "How do you test your system to ensure it won't crash in production?"
> **Answer:** *"We authored 15 comprehensive automated test cases in `bims_app/tests.py` using Django's test framework. These test demographic calculations, RBAC isolation redirects, QR hash generation, anti-duplicate claim blocks, CSV imports, and REST API endpoints. Running `python manage.py test` executes all 15 tests with 100% success rate in 21 seconds."*

### Q9: "Why did you use SQLite instead of MySQL or PostgreSQL?"
> **Answer:** *"SQLite is serverless, zero-configuration, and has negligible memory overhead, making it ideal for standalone municipal deployments and rapid demonstration. Because we use Django's ORM abstraction layer, the entire system can switch to PostgreSQL or MySQL in production simply by changing the `DATABASES` dictionary in `settings.py` without rewriting any SQL queries."*

### Q10: "What was your individual contribution to the project?" *(Each member should pick their piece!)*
* **Member 1 (Backend/API):** *"I developed the REST API layer under `api_views.py`, the QR code generation logic, and the automated unit test suite."*
* **Member 2 (Database & Security):** *"I architected the 3NF relational models, enforced the `UNIQUE` assistance constraints, and configured the RBAC decorators and audit logging."*
* **Member 3 (Frontend & Workflow):** *"I built the citizen intake portal, the responsive dashboard with Chart.js analytics, and the printable certificate templates."*
* **Member 4 (QA & Integration):** *"I tested the API endpoints in Postman, authored the 15-section documentation report, and validated the CSV census ingestion pipeline."*
