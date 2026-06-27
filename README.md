
================================================================================
  LoanCheck — Loan Eligibility Checker
  Project README & Technical Documentation
  Version 1.0.0  |  June 2025
================================================================================
 
CONTENTS
--------
  1.  Project Overview
  2.  Technology Stack
  3.  Project Structure
  4.  Setup & Installation
  5.  Eligibility Rules
  6.  Database Design
  7.  API Reference
  8.  Features
  9.  Frontend Validation Rules
  10. Quick MySQL Reference
  11. Important Notes
 
 
================================================================================
  1. PROJECT OVERVIEW
================================================================================
 
LoanCheck is a full-stack web application that automates the loan eligibility
evaluation process for financial institutions. When a customer submits their
financial details, the system instantly evaluates eligibility against
configurable rules, stores the result in a MySQL database, and returns a
detailed decision — all without manual intervention.
 
WHO USES IT
-----------
  Customer  : Submits a loan application through a guided web form and
              receives an instant Eligible / Not Eligible decision.
 
  Admin     : Reviews all applications, searches records, updates eligibility
              criteria, and exports data to CSV — all from a dashboard.
 
KEY CAPABILITIES
----------------
  - Instant eligibility decisions with itemised rejection reasons
  - EMI calculation using the standard reducing-balance formula
  - Admin dashboard with live statistics, record search, and CSV export
  - Configurable eligibility criteria — no server restart needed
  - Single-file frontend (loan_checker.html) for easy deployment
 
 
================================================================================
  2. TECHNOLOGY STACK
================================================================================
 
  Layer       Technology                  Purpose
  ----------  --------------------------  ------------------------------------
  Frontend    HTML5 + CSS3 + Vanilla JS   Customer form & admin dashboard
  Backend     Python 3.10+  |  Flask 3.0  REST API, business logic, EMI calc
  Database    MySQL 8.0+                  Persistent storage
  Connector   mysql-connector-python      Python <-> MySQL bridge
 
 
================================================================================
  3. PROJECT STRUCTURE
================================================================================
 
  loan_app/
  |
  +-- app.py                  Flask backend (all API routes + EMI logic)
  +-- schema.sql              MySQL table definitions + sample data + views
  +-- requirements.txt        Python dependencies
  +-- README.txt              This document
  |
  +-- templates/
  |     loan_checker.html     Single-file frontend (customer + admin pages)
  |
  +-- static/                 (only if using the multi-file version)
        css/
          style.css
        js/
          customer.js
          admin.js
 
 
================================================================================
  4. SETUP & INSTALLATION
================================================================================
 
PREREQUISITES
-------------
  - Python 3.10 or higher
  - MySQL 8.0 or higher (running locally or on a remote server)
  - pip (Python package manager)
 
STEP-BY-STEP INSTALLATION
--------------------------
 
  Step 1 — Install Python dependencies
 
      pip install flask mysql-connector-python
 
  Step 2 — Create the database and tables
 
      mysql -u root -p < schema.sql
 
  Step 3 — Configure the database connection
            Open app.py and update DB_CONFIG:
 
      DB_CONFIG = {
          'host':     'localhost',
          'user':     'root',
          'password': 'YOUR_PASSWORD_HERE',   # <-- change this
          'database': 'loan_eligibility_db'
      }
 
  Step 4 — Start the Flask server
 
      python app.py
 
  Step 5 — Open in your browser
 
      Customer form  -->  http://localhost:5000/
      Admin panel    -->  http://localhost:5000/admin
 
NOTE: On first run, app.py calls init_db() which creates the tables
automatically if they do not exist. Running schema.sql directly is
recommended for production as it also inserts sample data and views.
 
 
================================================================================
  5. ELIGIBILITY RULES
================================================================================
 
All four rules must pass for an applicant to be marked Eligible.
The admin can update these thresholds live from the Criteria Settings panel.
 
  Rule                  Default Value          Rejection message (if failed)
  --------------------  ---------------------  --------------------------------
  Monthly income        Minimum Rs. 25,000     Income below required threshold
  Credit score          Minimum 700            Credit score too low
  EMI-to-income ratio   Maximum 40%            EMI burden exceeds 40% of income
  Loan amount limit     Varies by loan type    Amount exceeds the type limit
 
LOAN AMOUNT LIMITS & INTEREST RATES
-------------------------------------
 
  Loan Type          Maximum Amount       Interest Rate (p.a.)
  -----------------  -------------------  --------------------
  Home Loan          Rs. 1,00,00,000      8.5%
  Personal Loan      Rs.    5,00,000      14.0%
  Car Loan           Rs.   15,00,000      10.5%
  Education Loan     Rs.   20,00,000      9.0%
  Business Loan      Rs.   50,00,000      12.0%
 
EMI FORMULA (Reducing Balance)
--------------------------------
  EMI  =  P * r * (1+r)^n
           ---------------
            (1+r)^n - 1
 
  Where:
    P  =  Principal (loan amount)
    r  =  Monthly interest rate  (annual rate / 12 / 100)
    n  =  Tenure in months
 
 
================================================================================
  6. DATABASE DESIGN
================================================================================
 
Two tables are used. A one-to-many relationship exists between them:
one customer can have many eligibility checks.
 
  customers  ||----o{  eligibility_checks
 
--------------------------------------
TABLE: customers
--------------------------------------
  Column        Type              Notes
  ------------  ----------------  -------------------------------------------
  customer_id   INT  PK AUTO      Unique identifier, auto-incremented
  name          VARCHAR(150)      Full name of the applicant
  mobile        VARCHAR(15) UNQ   10-digit mobile number (natural unique key)
  email         VARCHAR(150)      Contact email address
  created_at    DATETIME          Timestamp of first registration
 
--------------------------------------
TABLE: eligibility_checks
--------------------------------------
  Column              Type              Notes
  ------------------  ----------------  --------------------------------------
  check_id            INT  PK AUTO      Unique check identifier
  customer_id         INT  FK           References customers.customer_id
  loan_type           VARCHAR(50)       Home / Personal / Car / Education / Business
  monthly_income      DECIMAL(12,2)     Gross monthly income in Rs.
  employment_type     VARCHAR(50)       Salaried / Self-Employed / Business / Freelancer
  credit_score        INT               CIBIL score (300-900)
  existing_emi        DECIMAL(12,2)     Current monthly EMI obligations in Rs.
  requested_amount    DECIMAL(14,2)     Loan amount applied for in Rs.
  tenure_months       INT               Requested repayment period in months
  calculated_emi      DECIMAL(12,2)     System-computed new EMI in Rs.
  emi_ratio           DECIMAL(5,4)      (existing + new EMI) / income  e.g. 0.3500 = 35%
  result              ENUM              'Eligible' or 'Not Eligible'
  rejection_reasons   TEXT              Semicolon-separated list of failed rules
  checked_at          DATETIME          Timestamp of the check
 
--------------------------------------
DATABASE VIEWS (created by schema.sql)
--------------------------------------
  v_loan_applications   Full join of both tables — all columns in one query
  v_dashboard_stats     Aggregated KPIs: totals, approval rate, averages
 
 
================================================================================
  7. API REFERENCE
================================================================================
 
  Method  URL                        Purpose
  ------  -------------------------  ------------------------------------------
  POST    /api/check-eligibility     Evaluate application, save & return result
  GET     /api/records?search=       Fetch all checks (filterable by name/mobile)
  GET     /api/stats                 Dashboard summary counts + breakdown
  GET     /api/criteria              Read current eligibility thresholds
  POST    /api/criteria              Update thresholds at runtime (no restart)
  GET     /api/export?search=        Download filtered records as CSV file
 
--------------------------------------
POST /api/check-eligibility
--------------------------------------
  Request body (JSON):
    {
      "name":             "Aisha Krishnamurthy",
      "mobile":           "9876543210",
      "email":            "aisha@example.com",
      "loan_type":        "Personal Loan",
      "employment_type":  "Salaried",
      "monthly_income":   60000,
      "credit_score":     740,
      "existing_emi":     5000,
      "requested_amount": 300000,
      "tenure_months":    36
    }
 
  Response (JSON):
    {
      "result":          "Eligible",
      "reasons":         [],
      "calculated_emi":  9802.75,
      "total_emi":       14802.75,
      "emi_ratio_pct":   24.67,
      "check_id":        12
    }
 
--------------------------------------
POST /api/criteria
--------------------------------------
  Request body (JSON):
    {
      "min_income":       25000,
      "min_credit_score": 700,
      "max_emi_ratio":    0.40,
      "loan_limits": {
        "Home Loan":      10000000,
        "Personal Loan":  500000
      }
    }
 
 
================================================================================
  8. FEATURES
================================================================================
 
CUSTOMER SIDE
-------------
  - Three-section guided form: Personal Info, Loan Details, Financial Profile
  - Inline field validation with real-time error messages on every input
  - Live credit score colour bar (green >= 750, amber 700-749, red < 700)
  - EMI calculated using the reducing-balance formula with loan-type rates
  - Result card shows: decision, estimated EMI, total EMI burden,
    EMI-to-income ratio, and a reference check ID
  - If rejected: every failed rule is listed as a separate reason
 
ADMIN SIDE
----------
  - Dashboard tab: total checks, eligible/not-eligible counts, approval
    rate percentage, bar chart breakdown by loan type
  - Records tab: full searchable table (name or mobile), inline rejection
    reason rows, sorted by most recent first
  - Criteria Settings tab: update all thresholds and loan limits live;
    changes take effect immediately without restarting the server
  - Export button: downloads the current filtered view as a UTF-8 CSV file
 
 
================================================================================
  9. FRONTEND VALIDATION RULES
================================================================================
 
  Field               Rule                                Error shown
  ------------------  ----------------------------------  ----------------------
  Full name           Letters & spaces, min 2 chars       Enter a valid full name.
  Mobile number       Starts 6-9, exactly 10 digits       Enter a valid 10-digit number.
  Email               Standard email format               Enter a valid email address.
  Loan type           Must select an option               Select a loan type.
  Employment type     Must select an option               Select an employment type.
  Monthly income      Greater than 0                      Enter your monthly income.
  Credit score        Between 300 and 900                 Credit score must be 300-900.
  Existing EMI        Zero or greater                     Enter 0 if no existing EMIs.
  Loan amount         Minimum Rs. 1,000                   Minimum amount is Rs. 1,000.
  Tenure              6 to 360 months                     Tenure must be 6-360 months.
 
 
================================================================================
  10. QUICK MYSQL REFERENCE
================================================================================
 
-- Log in to MySQL
mysql -u root -p
 
-- Select the database
USE loan_eligibility_db;
 
-- List all tables
SHOW TABLES;
 
-- View table structure
DESCRIBE customers;
DESCRIBE eligibility_checks;
 
-- View all data
SELECT * FROM customers;
SELECT * FROM eligibility_checks;
 
-- Filter by result
SELECT * FROM eligibility_checks WHERE result = 'Eligible';
SELECT * FROM eligibility_checks WHERE result = 'Not Eligible';
 
-- Search by customer name
SELECT * FROM customers WHERE name LIKE '%Aisha%';
 
-- Search by mobile
SELECT * FROM customers WHERE mobile = '9876543210';
 
-- Full join — customer name + check result
SELECT c.name, c.mobile, ec.loan_type, ec.result, ec.checked_at
FROM customers c
JOIN eligibility_checks ec ON c.customer_id = ec.customer_id
ORDER BY ec.checked_at DESC;
 
-- Count by result
SELECT result, COUNT(*) AS total
FROM eligibility_checks
GROUP BY result;
 
-- Dashboard stats (using the view)
SELECT * FROM v_dashboard_stats;
 
-- Full application view
SELECT * FROM v_loan_applications;
 
 
================================================================================
  11. IMPORTANT NOTES
================================================================================
 
PRODUCTION DEPLOYMENT
----------------------
  [!] Set  debug=False  in app.py before deploying to production.
  [!] Use a WSGI server (gunicorn or uWSGI) instead of the Flask dev server.
  [!] Store the database password in an environment variable, not hardcoded.
 
      Example (Linux/Mac):
        export DB_PASSWORD="your_secure_password"
 
      Then in app.py:
        import os
        DB_CONFIG = {
            ...
            'password': os.environ.get('DB_PASSWORD', ''),
            ...
        }
 
CRITERIA PERSISTENCE
---------------------
  [!] Eligibility criteria updated via the Admin panel are stored in memory
      only. They reset to defaults when the server restarts. To persist
      changes permanently, update the CRITERIA dict in app.py or save
      criteria to a dedicated database table.
 
CSV EXPORT
-----------
  [i] The export file is encoded as UTF-8 with BOM (utf-8-sig) for
      compatibility with Microsoft Excel on Windows.
 
SAME CUSTOMER, MULTIPLE CHECKS
--------------------------------
  [i] Customers are identified by mobile number. If the same mobile number
      submits multiple applications, only one customers row exists and
      multiple eligibility_checks rows are created — one per application.
 
INTEREST RATES
---------------
  [i] Interest rates are defined in LOAN_RATES in app.py. They are used
      only for EMI calculation and do not affect the eligibility decision.
      Update them directly in app.py if rates change.
 
 
================================================================================
  LoanCheck v1.0.0  |  Flask + MySQL + Vanilla JS  |  June 2025
  For issues or questions, refer to the inline code comments in app.py.
================================================================================
