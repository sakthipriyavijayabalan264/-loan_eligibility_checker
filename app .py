# =============================================================================
#  LoanCheck – Flask Backend
#  File    : app.py
#  Tech    : Python 3.10+ | Flask | mysql-connector-python
#  Install : pip install flask mysql-connector-python
#  Run     : python app.py   →  http://localhost:5000
# =============================================================================

from flask import Flask, request, jsonify, render_template, send_file
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import csv
import io

app = Flask(__name__)

# -----------------------------------------------------------------------------
# 1.  DATABASE CONFIGURATION
#     Update 'password' to match your MySQL root password.
# -----------------------------------------------------------------------------
DB_CONFIG = {
    'host':     'localhost',
    'user':     'root',
    'password': 'root',      # <-- change this
    'database': 'loan_eligibility_db'
}

# -----------------------------------------------------------------------------
# 2.  ELIGIBILITY CRITERIA
#     These defaults are used at startup.
#     Admin can update them at runtime via POST /api/criteria — no restart needed.
# -----------------------------------------------------------------------------
CRITERIA = {
    'min_income':       25000,   # Minimum monthly income in ₹
    'min_credit_score': 700,     # Minimum CIBIL / credit score
    'max_emi_ratio':    0.40,    # Max allowed (existing + new EMI) / income
    'loan_limits': {             # Maximum loan amount per loan type (₹)
        'Home Loan':      10_000_000,
        'Personal Loan':     500_000,
        'Car Loan':        1_500_000,
        'Education Loan':  2_000_000,
        'Business Loan':   5_000_000,
    }
}

# Interest rates used for EMI calculation (annual %, reducing balance)
LOAN_RATES = {
    'Home Loan':       8.5,
    'Personal Loan':  14.0,
    'Car Loan':       10.5,
    'Education Loan':  9.0,
    'Business Loan':  12.0,
}

# =============================================================================
# 3.  DATABASE HELPERS
# =============================================================================

def get_db():
    """Open and return a new MySQL connection."""
    return mysql.connector.connect(**DB_CONFIG)


def init_db():
    """
    Create tables if they do not already exist.
    Called once at startup (see __main__ block).
    For a clean setup prefer running schema.sql directly:
        mysql -u root -p < schema.sql
    """
    conn = get_db()
    cur  = conn.cursor()

    # -- customers table -------------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id  INT          AUTO_INCREMENT PRIMARY KEY,
            name         VARCHAR(150) NOT NULL,
            mobile       VARCHAR(15)  NOT NULL UNIQUE,
            email        VARCHAR(150) NOT NULL,
            created_at   DATETIME     DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_mobile (mobile),
            INDEX idx_name   (name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # -- eligibility_checks table ----------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS eligibility_checks (
            check_id          INT             AUTO_INCREMENT PRIMARY KEY,
            customer_id       INT             NOT NULL,
            loan_type         VARCHAR(50),
            monthly_income    DECIMAL(12, 2),
            employment_type   VARCHAR(50),
            credit_score      INT,
            existing_emi      DECIMAL(12, 2),
            requested_amount  DECIMAL(14, 2),
            tenure_months     INT,
            calculated_emi    DECIMAL(12, 2),
            emi_ratio         DECIMAL(5,  4),
            result            ENUM('Eligible', 'Not Eligible') NOT NULL,
            rejection_reasons TEXT,
            checked_at        DATETIME        DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
                ON DELETE CASCADE,
            INDEX idx_result     (result),
            INDEX idx_checked_at (checked_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("[DB] Tables ready.")

# =============================================================================
# 4.  UTILITY: EMI CALCULATOR
# =============================================================================

def calculate_emi(principal: float, tenure_months: int, annual_rate_pct: float) -> float:
    """
    Standard reducing-balance EMI formula:
        EMI = P * r * (1+r)^n / ((1+r)^n - 1)
    where r = monthly interest rate, n = tenure in months.
    """
    r = (annual_rate_pct / 12) / 100
    if r == 0:
        return principal / tenure_months
    factor = (1 + r) ** tenure_months
    return principal * r * factor / (factor - 1)

# =============================================================================
# 5.  PAGE ROUTES
# =============================================================================

@app.route('/')
def index():
    """Serve the customer eligibility form."""
    return render_template('loan_checker.html')   # single-file frontend


@app.route('/admin')
def admin():
    """Serve the admin dashboard (same single-file frontend)."""
    return render_template('loan_checker.html')

# =============================================================================
# 6.  API ROUTES
# =============================================================================

# ---------------------------------------------------------------------------
# 6a.  POST /api/check-eligibility
#      Receives customer loan application, evaluates eligibility,
#      stores the result, and returns the decision.
# ---------------------------------------------------------------------------
@app.route('/api/check-eligibility', methods=['POST'])
def check_eligibility():
    data = request.get_json(force=True)

    # -- Extract and coerce request fields -----------------------------------
    name             = str(data.get('name',             '')).strip()
    mobile           = str(data.get('mobile',           '')).strip()
    email            = str(data.get('email',            '')).strip()
    loan_type        = str(data.get('loan_type',        '')).strip()
    employment_type  = str(data.get('employment_type',  '')).strip()
    monthly_income   = float(data.get('monthly_income',   0))
    credit_score     = int(  data.get('credit_score',     0))
    existing_emi     = float(data.get('existing_emi',     0))
    requested_amount = float(data.get('requested_amount', 0))
    tenure_months    = int(  data.get('tenure_months',    0))

    # -- Calculate new loan EMI and combined ratio ---------------------------
    annual_rate = LOAN_RATES.get(loan_type, 12.0)
    new_emi     = calculate_emi(requested_amount, tenure_months, annual_rate)
    total_emi   = existing_emi + new_emi
    emi_ratio   = (total_emi / monthly_income) if monthly_income > 0 else 1.0

    # -- Apply eligibility rules ---------------------------------------------
    rejection_reasons = []

    if monthly_income < CRITERIA['min_income']:
        rejection_reasons.append(
            f"Monthly income ₹{monthly_income:,.0f} is below the minimum ₹{CRITERIA['min_income']:,.0f}"
        )

    if credit_score < CRITERIA['min_credit_score']:
        rejection_reasons.append(
            f"Credit score {credit_score} is below the minimum {CRITERIA['min_credit_score']}"
        )

    if emi_ratio > CRITERIA['max_emi_ratio']:
        rejection_reasons.append(
            f"Total EMI-to-income ratio {emi_ratio*100:.1f}% exceeds the "
            f"{CRITERIA['max_emi_ratio']*100:.0f}% limit"
        )

    loan_limit = CRITERIA['loan_limits'].get(loan_type, 0)
    if requested_amount > loan_limit:
        rejection_reasons.append(
            f"Requested amount ₹{requested_amount:,.0f} exceeds the "
            f"{loan_type} limit of ₹{loan_limit:,.0f}"
        )

    result = 'Eligible' if not rejection_reasons else 'Not Eligible'

    # -- Persist to database -------------------------------------------------
    try:
        conn = get_db()
        cur  = conn.cursor()

        # Upsert customer: reuse existing record if mobile already known
        cur.execute("SELECT customer_id FROM customers WHERE mobile = %s", (mobile,))
        row = cur.fetchone()
        if row:
            customer_id = row[0]
        else:
            cur.execute(
                "INSERT INTO customers (name, mobile, email) VALUES (%s, %s, %s)",
                (name, mobile, email)
            )
            customer_id = cur.lastrowid

        # Insert eligibility check record
        cur.execute("""
            INSERT INTO eligibility_checks
                (customer_id, loan_type, monthly_income, employment_type,
                 credit_score, existing_emi, requested_amount, tenure_months,
                 calculated_emi, emi_ratio, result, rejection_reasons)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            customer_id, loan_type, monthly_income, employment_type,
            credit_score, existing_emi, requested_amount, tenure_months,
            round(new_emi, 2), round(emi_ratio, 4),
            result,
            '; '.join(rejection_reasons) if rejection_reasons else None
        ))

        conn.commit()
        check_id = cur.lastrowid

    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

    return jsonify({
        'result':          result,
        'reasons':         rejection_reasons,
        'calculated_emi':  round(new_emi, 2),
        'total_emi':       round(total_emi, 2),
        'emi_ratio_pct':   round(emi_ratio * 100, 2),
        'check_id':        check_id,
    })


# ---------------------------------------------------------------------------
# 6b.  GET /api/records?search=<name|mobile>
#      Returns all eligibility check records, optionally filtered.
# ---------------------------------------------------------------------------
@app.route('/api/records', methods=['GET'])
def get_records():
    search = request.args.get('search', '').strip()

    base_query = """
        SELECT
            ec.check_id,
            c.name,
            c.mobile,
            c.email,
            ec.loan_type,
            ec.monthly_income,
            ec.employment_type,
            ec.credit_score,
            ec.existing_emi,
            ec.requested_amount,
            ec.tenure_months,
            ec.calculated_emi,
            ec.emi_ratio,
            ec.result,
            ec.rejection_reasons,
            ec.checked_at
        FROM eligibility_checks ec
        JOIN customers c ON ec.customer_id = c.customer_id
    """

    try:
        conn = get_db()
        cur  = conn.cursor(dictionary=True)

        if search:
            like = f'%{search}%'
            cur.execute(
                base_query + " WHERE c.name LIKE %s OR c.mobile LIKE %s ORDER BY ec.checked_at DESC",
                (like, like)
            )
        else:
            cur.execute(base_query + " ORDER BY ec.checked_at DESC")

        rows = cur.fetchall()

        # Serialize datetime and Decimal fields for JSON
        for row in rows:
            if row.get('checked_at'):
                row['checked_at'] = row['checked_at'].strftime('%Y-%m-%d %H:%M')
            if row.get('emi_ratio') is not None:
                row['emi_ratio'] = float(row['emi_ratio'])

        return jsonify(rows)

    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# 6c.  GET /api/stats
#      Returns dashboard summary counts and breakdown by loan type.
# ---------------------------------------------------------------------------
@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        conn = get_db()
        cur  = conn.cursor(dictionary=True)

        # Overall counts
        cur.execute("""
            SELECT
                COUNT(*)                          AS total,
                SUM(result = 'Eligible')          AS eligible,
                SUM(result = 'Not Eligible')      AS not_eligible
            FROM eligibility_checks
        """)
        summary = cur.fetchone()

        # Convert aggregates to plain int (MySQL returns Decimal for SUM)
        summary['total']       = int(summary['total']       or 0)
        summary['eligible']    = int(summary['eligible']    or 0)
        summary['not_eligible']= int(summary['not_eligible']or 0)

        # Breakdown by loan type
        cur.execute("""
            SELECT loan_type, COUNT(*) AS cnt
            FROM eligibility_checks
            GROUP BY loan_type
            ORDER BY cnt DESC
        """)
        by_type = cur.fetchall()
        for row in by_type:
            row['cnt'] = int(row['cnt'])

        return jsonify({'summary': summary, 'by_type': by_type})

    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# 6d.  GET /api/criteria          – read current thresholds
#      POST /api/criteria  {…}   – update thresholds at runtime
# ---------------------------------------------------------------------------
@app.route('/api/criteria', methods=['GET'])
def get_criteria():
    return jsonify(CRITERIA)


@app.route('/api/criteria', methods=['POST'])
def update_criteria():
    data = request.get_json(force=True)

    if 'min_income'        in data: CRITERIA['min_income']       = float(data['min_income'])
    if 'min_credit_score'  in data: CRITERIA['min_credit_score'] = int(  data['min_credit_score'])
    if 'max_emi_ratio'     in data: CRITERIA['max_emi_ratio']    = float(data['max_emi_ratio'])
    if 'loan_limits'       in data: CRITERIA['loan_limits'].update(data['loan_limits'])

    return jsonify({'status': 'updated', 'criteria': CRITERIA})


# ---------------------------------------------------------------------------
# 6e.  GET /api/export?search=<…>
#      Downloads all (filtered) records as a CSV file.
# ---------------------------------------------------------------------------
@app.route('/api/export', methods=['GET'])
def export_csv():
    search = request.args.get('search', '').strip()

    base_query = """
        SELECT
            ec.check_id,
            c.name,
            c.mobile,
            c.email,
            ec.loan_type,
            ec.monthly_income,
            ec.employment_type,
            ec.credit_score,
            ec.existing_emi,
            ec.requested_amount,
            ec.tenure_months,
            ec.calculated_emi,
            ec.emi_ratio,
            ec.result,
            ec.rejection_reasons,
            ec.checked_at
        FROM eligibility_checks ec
        JOIN customers c ON ec.customer_id = c.customer_id
    """

    try:
        conn = get_db()
        cur  = conn.cursor(dictionary=True)

        if search:
            like = f'%{search}%'
            cur.execute(
                base_query + " WHERE c.name LIKE %s OR c.mobile LIKE %s ORDER BY ec.checked_at DESC",
                (like, like)
            )
        else:
            cur.execute(base_query + " ORDER BY ec.checked_at DESC")

        rows = cur.fetchall()

        if not rows:
            return jsonify({'message': 'No records to export.'}), 404

        # Build CSV in memory
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        for row in rows:
            if hasattr(row.get('checked_at'), 'strftime'):
                row['checked_at'] = row['checked_at'].strftime('%Y-%m-%d %H:%M')
            writer.writerow(row)

        output.seek(0)
        filename = f"loan_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),  # utf-8-sig for Excel compat
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )

    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


# =============================================================================
# 7.  ENTRY POINT
# =============================================================================
if __name__ == '__main__':
    init_db()          # create tables if missing
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True     # set debug=False in production
    )
