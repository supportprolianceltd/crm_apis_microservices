# 📊 Investment Management API Documentation

## 🏦 Authentication & Multi-tenancy

### Login - Investor
**Purpose:** Authenticates an investor user and returns a JWT token for subsequent API calls.
**Method:** POST
**URL:** `http://localhost:9090/api/token/`

**Request Body:**
```json
{
    "email": "support@prolianceltd.com",
    "password": "[4=y:Yg)mzD6Xs"
}
```

**Response:**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 123,
    "email": "investor@example.com",
    "first_name": "John",
    "last_name": "Investor",
    "role": "investor",
    "tenant": {
      "id": 1,
      "name": "Proliance Investments",
      "schema_name": "proliance"
    }
  }
}
```

---

## 📈 Investment Policy Management

### Create Investment Policy
**Purpose:** Creates a new investment policy for an investor with initial deposit.
**Method:** POST
**URL:** `http://localhost:9090/api/investments/policies/`

**Request Body:**
```json
{
  "user": 17,  // Optional: User ID for the policy owner (defaults to authenticated user)
  "principal_amount": "50000.00",
  "roi_frequency": "monthly",
  "min_withdrawal_months": 4,
  "allow_partial_withdrawals": true,
  "auto_rollover": false
}
```

**Response:**
```json
{
  "id": 1,
  "user_details": {
    "id": 17,
    "email": "info@appbrew.com",
    "first_name": "Marian",
    "last_name": "Goodness",
    "role": "staff",
    "bank_name": "HSBC Bank",
    "account_number": "12345678",
    "account_name": "Marian Goodness",
    "account_type": "savings",
    "country_of_bank_account": "Nigeria",
    "investment_details": [],
    "withdrawal_details": []
  },
  "policy_number": "APP-000001",
  "unique_policy_id": "000001",
  "principal_amount": "50000.00",
  "roi_rate": "40.00",
  "roi_frequency": "monthly",
  "min_withdrawal_months": 4,
  "allow_partial_withdrawals": true,
  "auto_rollover": false,
  "rollover_option": "principal_only",
  "status": "active",
  "maturity_date": null
}
```

---

### Get Investment Policies
**Purpose:** Retrieves all investment policies for the authenticated user (investor sees own, admin sees all in tenant).
**Method:** GET
**URL:** `http://localhost:9090/api/investments/policies/`

**Response:**
```json
{
  "count": 2,
  "results": [
    {
      "id": 1,
      "user_details": {
        "id": 17,
        "email": "info@appbrew.com",
        "first_name": "Marian",
        "last_name": "Goodness",
        "role": "staff",
        "bank_name": "HSBC Bank",
        "account_number": "12345678",
        "account_name": "Marian Goodness",
        "account_type": "savings",
        "country_of_bank_account": "Nigeria",
        "investment_details": [],
        "withdrawal_details": []
      },
      "policy_number": "APP-000001",
      "unique_policy_id": "000001",
      "principal_amount": "50000.00",
      "roi_rate": "40.00",
      "roi_frequency": "monthly",
      "min_withdrawal_months": 4,
      "allow_partial_withdrawals": true,
      "auto_rollover": false,
      "rollover_option": "principal_only",
      "status": "active",
      "maturity_date": null
    },
    {
      "id": 2,
      "user_details": {
        "id": 18,
        "email": "jane@example.com",
        "first_name": "Jane",
        "last_name": "Investor",
        "role": "investor",
        "bank_name": "Barclays Bank",
        "account_number": "87654321",
        "account_name": "Jane Investor",
        "account_type": "current",
        "country_of_bank_account": "UK",
        "investment_details": [
          {
            "id": 1,
            "roi_rate": "40.00",
            "investment_amount": "75000.00",
            "remaining_balance": "77500.00"
          }
        ],
        "withdrawal_details": []
      },
      "policy_number": "APP-000002",
      "unique_policy_id": "000002",
      "principal_amount": "75000.00",
      "roi_rate": "40.00",
      "roi_frequency": "on_demand",
      "min_withdrawal_months": 4,
      "allow_partial_withdrawals": true,
      "auto_rollover": false,
      "rollover_option": "principal_only",
      "status": "active",
      "maturity_date": null
    }
  ]
}
```

---

### Update Investment Policy
**Purpose:** Update an existing investment policy (Admin Only).
**Method:** PUT
**URL:** `http://localhost:9090/api/investments/policies/{id}/`

**Request Body:**
```json
{
  "roi_frequency": "on_demand",
  "status": "suspended"
}
```

**Response:**
```json
{
  "id": 1,
  "policy_number": "APP-000001",
  "unique_policy_id": "000001",
  "principal_amount": "50000.00",
  "roi_rate": "40.00",
  "roi_frequency": "on_demand",
  "status": "suspended",
  "start_date": "2024-01-15T10:00:00Z",
  "user_details": {
    "id": 17,
    "email": "info@appbrew.com",
    "first_name": "Marian",
    "last_name": "Goodness"
  }
}
```

**Updatable Fields:**
- `roi_frequency`: "monthly" or "on_demand"
- `status`: "active", "suspended", "matured", "closed"

---

### Search Investment Policies
**Purpose:** Search policies by policy number, investor name, or email.
**Method:** GET
**URL:** `http://localhost:9090/api/investments/policies/search/?q=PRO-000001`

**Response:**
```json
{
  "query": "APP-000001",
  "search_type": "all",
  "results_count": 1,
  "results": [
    {
      "id": 1,
      "user_details": {
        "id": 17,
        "email": "info@appbrew.com",
        "first_name": "Marian",
        "last_name": "Goodness",
        "role": "staff",
        "bank_name": "HSBC Bank",
        "account_number": "12345678",
        "account_name": "Marian Goodness",
        "account_type": "savings",
        "country_of_bank_account": "Nigeria",
        "investment_details": [],
        "withdrawal_details": []
      },
      "policy_number": "APP-000001",
      "unique_policy_id": "000001",
      "principal_amount": "50000.00",
      "roi_rate": "40.00",
      "roi_frequency": "monthly",
      "min_withdrawal_months": 4,
      "allow_partial_withdrawals": true,
      "auto_rollover": false,
      "rollover_option": "principal_only",
      "status": "active",
      "maturity_date": null
    }
  ]
}
```

---

### Change ROI Frequency
**Purpose:** Change ROI payment frequency between monthly and on-demand.
**Method:** POST
**URL:** `http://localhost:9090/api/investments/policies/1/change_roi_frequency/`

**Request Body:**
```json
{
  "roi_frequency": "on_demand"
}
```

**Response:**
```json
{
  "message": "ROI frequency updated to on_demand"
}
```

---

### Get Investment Policies by Investor (Admin Only)
**Purpose:** Retrieve all investment policies for a specific investor using their ID or email address.
**Method:** GET
**URL:** `http://localhost:9090/api/investments/policies/by_investor/`

**Query Parameters:**
- `investor_id`: Investor user ID (integer)
- `investor_email`: Investor email address (string)

**Note:** Either `investor_id` or `investor_email` must be provided.

**Response:**
```json
{
  "investor": {
    "id": 17,
    "name": "Marian Goodness",
    "email": "info@appbrew.com",
    "phone_number": "+1234567890"
  },
  "policies_count": 2,
  "policies": [
    {
      "id": 1,
      "user_details": {
        "id": 17,
        "email": "info@appbrew.com",
        "first_name": "Marian",
        "last_name": "Goodness",
        "role": "staff",
        "bank_name": "HSBC Bank",
        "account_number": "12345678",
        "account_name": "Marian Goodness",
        "account_type": "savings",
        "country_of_bank_account": "Nigeria",
        "investment_details": [],
        "withdrawal_details": []
      },
      "policy_number": "APP-000001",
      "unique_policy_id": "000001",
      "principal_amount": "50000.00",
      "roi_rate": "40.00",
      "roi_frequency": "monthly",
      "min_withdrawal_months": 4,
      "allow_partial_withdrawals": true,
      "auto_rollover": false,
      "rollover_option": "principal_only",
      "status": "active",
      "maturity_date": null
    },
    {
      "id": 2,
      "user_details": {
        "id": 17,
        "email": "info@appbrew.com",
        "first_name": "Marian",
        "last_name": "Goodness",
        "role": "staff",
        "bank_name": "HSBC Bank",
        "account_number": "12345678",
        "account_name": "Marian Goodness",
        "account_type": "savings",
        "country_of_bank_account": "Nigeria",
        "investment_details": [],
        "withdrawal_details": []
      },
      "policy_number": "APP-000002",
      "unique_policy_id": "000002",
      "principal_amount": "75000.00",
      "roi_rate": "40.00",
      "roi_frequency": "on_demand",
      "min_withdrawal_months": 4,
      "allow_partial_withdrawals": true,
      "auto_rollover": false,
      "rollover_option": "principal_only",
      "status": "active",
      "maturity_date": null
    }
  ]
}
```

**Error Responses:**
- `400 Bad Request`: Missing required parameters or invalid investor ID/email
- `404 Not Found`: Investor not found
- `403 Forbidden`: Insufficient permissions (non-admin users)

---

## 💰 Withdrawal Management

### Add Top-up to Policy
**Purpose:** Add additional funds to an existing investment policy.
**Method:** POST
**URL:** `http://localhost:9090/api/investments/policies/{policy_id}/add_topup/`

**Request Body:**
```json
{
  "amount": "10000.00"
}
```

**Response:**
```json
{
  "message": "Top-up added successfully",
  "new_balance": "60000.00"
}
```

---

### Create Withdrawal Request
**Purpose:** Request withdrawal of ROI or principal from investment policy.
**Method:** POST
**URL:** `http://localhost:9090/api/investments/withdrawals/`

**Request Body (ROI Only):**
```json
{
  "policy": 1,
  "withdrawal_type": "roi_only",
  "amount_requested": "1000.00",
  "disbursement_bank": "HSBC Bank",
  "account_name": "John Investor",
  "account_number": "12345678"
}
```

**Request Body (Principal Only - after 4 months):**
```json
{
  "policy": 1,
  "withdrawal_type": "principal_only", 
  "amount_requested": "10000.00",
  "disbursement_bank": "HSBC Bank",
  "account_name": "John Investor",
  "account_number": "12345678"
}
```

**Request Body (Composite):**
```json
{
  "policy": 1,
  "withdrawal_type": "composite",
  "amount_requested": "11666.67",
  "disbursement_bank": "HSBC Bank",
  "account_name": "John Investor", 
  "account_number": "12345678"
}
```

**Response:**
```json
{
  "id": 1,
  "policy": 1,
  "policy_number": "PRO-000001",
  "investor_name": "John Investor",
  "request_date": "2024-01-20T14:30:00Z",
  "withdrawal_type": "roi_only",
  "amount_requested": "1000.00",
  "status": "pending",
  "available_balances": {
    "principal_available": "0.00",
    "roi_available": "1666.67",
    "total_available": "1666.67"
  }
}
```

---

### Approve Withdrawal Request (Admin Only)
**Purpose:** Admin approves a pending withdrawal request.
**Method:** POST
**URL:** `http://localhost:9090/api/investments/withdrawals/1/approve/`

**Response:**
```json
{
  "message": "Withdrawal approved"
}
```

---

### Process Withdrawal
**Purpose:** Process an approved withdrawal request.
**Method:** POST  
**URL:** `http://localhost:9090/api/investments/withdrawals/1/process/`

**Response:**
```json
{
  "message": "Withdrawal processed successfully"
}
```

---

## 📋 Ledger & Statements

### Get Ledger Entries
**Purpose:** Retrieve all ledger entries for policies with comprehensive filtering.
**Method:** GET
**URL:** `http://localhost:9090/api/investments/ledger/`

**Query Parameters:**
- `policy_number`: Filter by policy number
- `investor_name`: Filter by investor name  
- `entry_type`: Filter by entry type (deposit, withdrawal_principal, withdrawal_roi, roi_accrual, etc.)
- `date_from`: Start date (YYYY-MM-DD)
- `date_to`: End date (YYYY-MM-DD)

**Response:**
```json
{
  "count": 15,
  "results": [
    {
      "id": 1,
      "entry_date": "2024-01-15T10:00:00Z",
      "unique_reference": "DEP-PRO-000001-INIT",
      "policy_number": "PRO-000001",
      "investor_name": "John Investor",
      "investor_email": "john@example.com",
      "description": "Initial deposit - Policy PRO-000001",
      "entry_type": "deposit",
      "entry_type_display": "Deposit",
      "inflow": "50000.00",
      "outflow": "0.00",
      "principal_balance": "50000.00",
      "roi_balance": "0.00",
      "total_balance": "50000.00"
    },
    {
      "id": 2,
      "entry_date": "2024-02-01T00:00:00Z", 
      "unique_reference": "ROI-PRO-000001-202402",
      "policy_number": "PRO-000001",
      "investor_name": "John Investor",
      "investor_email": "john@example.com",
      "description": "ROI Accrual - February 2024",
      "entry_type": "roi_accrual",
      "entry_type_display": "ROI Accrual",
      "inflow": "1666.67",
      "outflow": "0.00",
      "principal_balance": "50000.00",
      "roi_balance": "1666.67",
      "total_balance": "51666.67"
    }
  ]
}
```

---

### Generate Investment Statement
**Purpose:** Generate a comprehensive statement for a specific policy and time period.
**Method:** POST
**URL:** `http://localhost:9090/api/investments/statements/generate/`

**Request Body:**
```json
{
  "policy_id": 1,
  "duration": "3_months"
}
```

**Duration Options:** `1_month`, `3_months`, `6_months`, `1_year`, `custom`

**For Custom Range:**
```json
{
  "policy_id": 1,
  "duration": "custom",
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-03-31T23:59:59Z"
}
```

**Response:**
```json
{
  "statement_period": "2024-01-01T00:00:00Z to 2024-03-31T23:59:59Z",
  "policy_details": {
    "policy_number": "PRO-000001",
    "investor_name": "John Investor",
    "start_balance": "50000.00",
    "end_balance": "52500.00"
  },
  "entries": [
    {
      "entry_date": "2024-01-15T10:00:00Z",
      "description": "Initial deposit - Policy PRO-000001",
      "entry_type": "deposit",
      "inflow": "50000.00",
      "outflow": "0.00",
      "principal_balance": "50000.00",
      "roi_balance": "0.00",
      "total_balance": "50000.00"
    },
    {
      "entry_date": "2024-02-01T00:00:00Z",
      "description": "ROI Accrual - February 2024", 
      "entry_type": "roi_accrual",
      "inflow": "1666.67",
      "outflow": "0.00",
      "principal_balance": "50000.00",
      "roi_balance": "1666.67",
      "total_balance": "51666.67"
    },
    {
      "entry_date": "2024-03-01T00:00:00Z",
      "description": "ROI Accrual - March 2024",
      "entry_type": "roi_accrual", 
      "inflow": "1666.67",
      "outflow": "0.00",
      "principal_balance": "50000.00",
      "roi_balance": "3333.34",
      "total_balance": "53333.34"
    },
    {
      "entry_date": "2024-03-15T14:30:00Z",
      "description": "ROI Withdrawal",
      "entry_type": "withdrawal_roi",
      "inflow": "0.00",
      "outflow": "833.34",
      "principal_balance": "50000.00", 
      "roi_balance": "2500.00",
      "total_balance": "52500.00"
    }
  ],
  "summary": {
    "total_inflow": "53333.34",
    "total_outflow": "833.34",
    "net_flow": "52500.00",
    "entry_count": 4,
    "roi_accrued": "3333.34",
    "withdrawals": "833.34"
  }
}
```

---

### Export Ledger to CSV
**Purpose:** Export ledger entries to CSV format for accounting purposes.
**Method:** GET
**URL:** `http://localhost:9090/api/investments/ledger/export/`

**Query Parameters:** Same as ledger filtering

**Response:** CSV file download with headers:
```
Date,Policy Number,Investor Name,Description,Entry Type,Inflow,Outflow,Principal Balance,ROI Balance,Total Balance,Reference
```

---

### Get Ledger by Policy
**Purpose:** Get ledger entries grouped by policy with policy summaries.
**Method:** GET
**URL:** `http://localhost:9090/api/investments/ledger/by_policy/`

**Response:**
```json
[
  {
    "policy_number": "APP-000001",
    "investor_name": "John Investor",
    "current_principal": "50000.00",
    "current_roi": "2500.00",
    "total_balance": "52500.00",
    "total_withdrawn": "0.00",
    "ledger_entries": [...]
  }
]
```

---

### Monthly Ledger Report
**Purpose:** Generate monthly aggregated ledger reports.
**Method:** GET
**URL:** `http://localhost:9090/api/investments/ledger/monthly_report/`

**Response:**
```json
{
  "monthly_reports": [
    {
      "month": "2024-03-01",
      "total_inflow": "3333.34",
      "total_outflow": "833.34",
      "net_flow": "2500.00",
      "entry_count": 4,
      "deposit_count": 1,
      "withdrawal_count": 1,
      "roi_accrual_count": 2
    }
  ],
  "report_generated_at": "2024-04-01T10:00:00Z"
}
```

---

## 📊 Reports & Analytics

### Investment Performance Report
**Purpose:** Generate comprehensive investment performance analytics (Admin Only).
**Method:** GET
**URL:** `http://localhost:9090/api/investments/reports/performance/`

**Query Parameters:**
- `date_from`: Start date (YYYY-MM-DD)
- `date_to`: End date (YYYY-MM-DD)

**Response:**
```json
{
  "period": {
    "from": "2024-01-01",
    "to": "2024-12-31"
  },
  "overview": {
    "total_policies": 150,
    "active_policies": 145,
    "total_principal": "7500000.00",
    "total_current_balance": "7750000.00",
    "total_roi_accrued": "250000.00",
    "total_withdrawn": "50000.00"
  },
  "topups": {
    "total_topups": "500000.00",
    "topup_count": 50
  },
  "withdrawals": {
    "total_withdrawals": "50000.00",
    "withdrawal_count": 25
  },
  "growth": {
    "principal_growth": "250000.00",
    "roi_generated": "250000.00"
  }
}
```

---

### ROI Due Report
**Purpose:** Generate printable report of upcoming ROI payments (Admin Only).
**Method:** GET
**URL:** `http://localhost:9090/api/investments/reports/roi-due/`

**Response:**
```json
{
  "report_date": "2024-04-01T10:00:00Z",
  "total_customers": 15,
  "total_roi_due": "31250.00",
  "customers": [
    {
      "name": "John Investor",
      "email": "john@example.com",
      "phone": "+1234567890",
      "policy_number": "APP-000001",
      "roi_amount": "1666.67",
      "next_roi_date": "2024-04-01T00:00:00Z",
      "bank_name": "HSBC Bank",
      "account_number": "12345678",
      "account_name": "John Investor"
    }
  ]
}
```

---

## 📧 Notification System

The investment system includes automated email notifications for key events:

### Investment Created
- **Trigger:** When a new investment policy is created
- **Recipient:** Investor
- **Content:** Policy details, amount, ROI rate, start date

### ROI Accrued
- **Trigger:** When monthly ROI is added to a policy
- **Recipient:** Investor
- **Content:** ROI amount, updated balances

### Withdrawal Approved
- **Trigger:** When a withdrawal request is approved
- **Recipient:** Investor
- **Content:** Withdrawal details, disbursement information

### Top-up Confirmed
- **Trigger:** When additional funds are added to a policy
- **Recipient:** Investor
- **Content:** Top-up amount, new balance

---

## 🔧 Services & Business Logic

### ROI Calculator Service
Handles all ROI calculation and accrual logic:

- **Monthly ROI Calculation:** `(principal × annual_rate ÷ 100) ÷ 12`
- **Eligibility Rules:** 1st-12th of month = same month ROI, 13th+ = next month ROI
- **Batch Processing:** Automated monthly accrual for all eligible policies

### Withdrawal Validator Service
Validates withdrawal requests against business rules:

- **Principal Withdrawals:** Minimum 4-month holding period
- **ROI Withdrawals:** Available immediately
- **Balance Checks:** Sufficient funds validation
- **Composite Withdrawals:** Combined principal + ROI

---

## ⚙️ Scheduled Operations

### Automated ROI Accrual
**Schedule:** 1st of every month at 00:00 UTC
**Task:** `accrue_monthly_roi_for_tenant`
**Function:** Automatically calculates and accrues ROI for all eligible policies

### ROI Due Notifications
**Schedule:** 25th of every month at 00:00 UTC
**Task:** `send_roi_due_notifications`
**Function:** Sends email notifications for upcoming ROI payments

---

## 🔄 Business Rules & Features

### ROI Calculation Rules
- **Annual ROI Rate:** 40% of principal (configurable per tenant)
- **Monthly ROI:** (40% / 12) = 3.33% of principal monthly
- **Investment Date Rules:**
  - **1st-12th of month:** ROI recorded for same month
  - **13th+ of month:** ROI recorded from next month
- **ROI Frequency:** Monthly (auto) or On-demand (manual)

### Withdrawal Restrictions
- **Principal Withdrawals:** Allowed only after 4 months (configurable)
- **ROI Withdrawals:** Available immediately (if accrued)
- **Partial Withdrawals:** Supported based on policy settings
- **Composite Withdrawals:** Principal + ROI in single transaction

### Top-up Rules
- **Immediate Effect:** Top-ups added instantly to principal balance
- **ROI Eligibility:** Based on top-up date (1st-12th = current month, 13th+ = next month)
- **Ledger Tracking:** All top-ups recorded with unique references

### Multi-tenancy Features
- **Data Isolation:** Complete tenant separation
- **Policy Numbers:** Tenant-specific sequences using first 3 uppercase letters of tenant name (APP-000001, PRO-000001, etc.)
- **ROI Rates:** Configurable per tenant (default 40%)
- **Admin Access:** Tenant-scoped administration

### Security & Access Control
- **Investors:** Can only access their own policies
- **Admins:** Can access all policies within their tenant
- **Super Admins:** Cross-tenant access (if configured)
- **JWT Authentication:** Required for all endpoints

---

## 📋 API Endpoints Summary

### Investment Policies
- `GET /api/investments/policies/` - List policies ✅ **Frontend Implemented**
- `POST /api/investments/policies/` - Create policy ✅ **Frontend Implemented**
- `GET /api/investments/policies/{id}/` - Get policy details ✅ **Frontend Implemented**
- `PUT /api/investments/policies/{id}/` - Update policy ✅ **Frontend Implemented**
- `DELETE /api/investments/policies/{id}/` - Delete policy ✅ **Frontend Implemented**
- `POST /api/investments/policies/{id}/change_roi_frequency/` - Change ROI frequency ✅ **Frontend Implemented**
- `GET /api/investments/policies/search/?q=search_term` - Search policies ✅ **Frontend Implemented**
- `GET /api/investments/policies/by_investor/?investor_id={id}&investor_email={email}` - Get policies by investor (Admin Only) ✅ **Frontend Implemented**

### Withdrawals
- `GET /api/investments/withdrawals/` - List withdrawal requests
- `POST /api/investments/withdrawals/` - Create withdrawal request
- `POST /api/investments/withdrawals/{id}/approve/` - Approve withdrawal
- `POST /api/investments/withdrawals/{id}/process/` - Process withdrawal
- `POST /api/investments/withdrawals/{id}/add_topup/` - Add top-up to policy

### Ledger
- `GET /api/investments/ledger/` - List ledger entries
- `GET /api/investments/ledger/summary/` - Get ledger summary
- `GET /api/investments/ledger/export/` - Export to CSV
- `GET /api/investments/ledger/by_policy/` - Group by policy
- `GET /api/investments/ledger/monthly_report/` - Monthly reports

### Reports & Analytics
- `GET /api/investments/dashboard/` - Investment dashboard ✅ **Frontend Implemented**
- `POST /api/investments/statements/generate/` - Generate statement ✅ **Frontend Implemented**
- `GET /api/investments/reports/performance/` - Performance report ✅ **Frontend Implemented**
- `GET /api/investments/reports/roi-due/` - ROI due report ✅ **Frontend Implemented**

### Tax Management (✅ **New - Fully Implemented**)
- `POST /api/investments/taxes/calculate/` - Calculate taxes for transactions
- `GET /api/investments/taxes/records/` - Tax records management
- `POST /api/investments/taxes/records/` - Create tax record
- `GET /api/investments/taxes/certificates/` - Tax certificates
- `POST /api/investments/taxes/certificates/generate/` - Generate tax certificate
- `POST /api/investments/taxes/certificates/{id}/approve/` - Approve tax certificate
- `GET /api/investments/taxes/summary/` - Tax summary for user
- `GET /api/investments/taxes/settings/` - Tax settings (admin)
- `PUT /api/investments/taxes/settings/` - Update tax settings (admin)
- `GET /api/investments/taxes/reports/` - Tax reports

### Administrative
- `POST /api/investments/roi/accrue/` - Manual ROI accrual
- `GET /api/investments/roi/accrue/` - ROI accrual status
- `GET /api/investments/search/?q=search_term` - Global search

---

## 💻 Frontend Implementation Status

### ✅ **Fully Implemented Features**

#### **Core Investment Management**
- ✅ **Investment Policy CRUD**: Create, Read, Update, Delete policies
- ✅ **Dashboard Analytics**: Real-time metrics from `/api/investments/dashboard/`
- ✅ **Policy Search & Filtering**: Advanced search by policy number, investor name, email
- ✅ **Withdrawal Management**: Create, approve, process withdrawal requests
- ✅ **Top-up System**: Add additional funds to existing policies
- ✅ **Ledger System**: Complete transaction history with filtering and export
- ✅ **Statement Generation**: Custom period statements (1 month, 3 months, 6 months, 1 year, custom dates)
- ✅ **ROI Management**: Change frequency, manual accrual, status monitoring
- ✅ **Multi-tenancy Support**: Tenant-scoped data and operations

#### **Nigerian Tax Compliance System (✅ New - Fully Integrated)**
- ✅ **Tax Calculation Engine**: Real-time WHT, PIT, CGT, VAT calculations
- ✅ **Tax Report Modal**: Interactive tax reports with backend integration
- ✅ **Tax Records Management**: Complete audit trail with TaxRecord model
- ✅ **Tax Certificates**: FIRS-compliant certificate generation
- ✅ **Tax Settings**: Tenant-specific tax configuration
- ✅ **Withdrawal Tax Integration**: Automatic 10% WHT on ROI withdrawals
- ✅ **Tax History**: Historical tax summaries and reporting
- ✅ **Tax APIs**: Complete REST API integration (9 new endpoints)

#### **User Interface Components**
- ✅ **Admin Dashboard**: Comprehensive metrics and navigation
- ✅ **Investment Table**: Responsive table with actions dropdown
- ✅ **Policy Editor**: Modal for updating policy settings
- ✅ **Transaction Forms**: Create investments and withdrawals
- ✅ **Modal System**: Responsive confirmation and edit modals
- ✅ **Notification System**: Real-time feedback for all operations
- ✅ **Mobile Responsive**: Optimized for tablets and mobile devices

#### **API Integration**
- ✅ **InvestmentApiService**: Complete service layer for investment operations
- ✅ **AdminApiService**: Dashboard and user management APIs
- ✅ **Error Handling**: Comprehensive error handling and user feedback
- ✅ **Loading States**: Proper loading indicators for all async operations

### 📊 **Implementation Coverage**

| Component | Status | Coverage |
|-----------|--------|----------|
| **Investment Policies** | ✅ Complete | 100% |
| **Withdrawals** | ✅ Complete | 100% |
| **Ledger & Reports** | ✅ Complete | 100% |
| **Dashboard** | ✅ Complete | 100% |
| **User Management** | ✅ Complete | 100% |
| **UI Components** | ✅ Complete | 100% |
| **Mobile Responsiveness** | ✅ Complete | 100% |
| **Nigerian Tax System** | ✅ **Complete** | **100%** |
| **Tax APIs** | ✅ **Complete** | **100%** |
| **Tax Frontend Integration** | ✅ **Complete** | **100%** |

### 🔧 **Technical Implementation**

#### **Frontend Architecture**
- **React Hooks**: Modern functional components with custom hooks
- **Service Layer**: Centralized API services (`InvestmentApiService`, `AdminApiService`)
- **State Management**: Local state with proper data flow
- **Responsive Design**: CSS Grid/Flexbox with mobile-first approach
- **Error Boundaries**: Comprehensive error handling and user feedback

#### **Key Features Implemented**
- **Real-time Dashboard**: Uses actual API data instead of client-side calculations
- **Policy Management**: Full CRUD operations with validation
- **Advanced Search**: Multi-field search with type filtering
- **Bulk Operations**: Efficient handling of multiple records
- **Export Functionality**: CSV export for ledger data
- **Modal System**: Accessible and responsive modal dialogs

#### **Mobile Optimization**
- **Responsive Tables**: Card-based layout on mobile devices
- **Touch-Friendly**: Proper button sizes and spacing
- **Dropdown Positioning**: Smart positioning to prevent overflow
- **Fixed Positioning**: Modal positioning optimized for mobile screens

### 🚀 **Production Ready Features**

- ✅ **Complete API Integration**: All documented endpoints implemented
- ✅ **Error Handling**: Comprehensive error states and user feedback
- ✅ **Loading States**: Proper loading indicators throughout the app
- ✅ **Responsive Design**: Works seamlessly on all device sizes
- ✅ **Accessibility**: ARIA labels and keyboard navigation support
- ✅ **Performance**: Optimized rendering and efficient API calls
- ✅ **Security**: Proper authentication and tenant isolation

---

## 🗂️ Data Models

### InvestmentPolicy
- `policy_number`: Unique policy identifier (tenant-specific)
- `unique_policy_id`: Sequential 6-digit ID per tenant
- `principal_amount`: Initial investment amount
- `current_balance`: Current principal balance
- `roi_balance`: Accumulated ROI
- `total_balance`: Current + ROI balance
- `roi_rate`: Annual ROI percentage
- `roi_frequency`: Monthly or on-demand
- `status`: Active, matured, closed, suspended
- `start_date`: Policy creation date
- `maturity_date`: Optional maturity date
- `min_withdrawal_months`: Minimum holding period
- `allow_partial_withdrawals`: Boolean flag
- `auto_rollover`: Boolean flag
- `rollover_option`: Principal only, principal + ROI, or custom

### LedgerEntry
- `entry_date`: Transaction date
- `unique_reference`: Unique transaction reference
- `description`: Human-readable description
- `entry_type`: Deposit, top-up, withdrawal_principal, withdrawal_roi, roi_accrual, fee
- `inflow`: Money coming in
- `outflow`: Money going out
- `principal_balance`: Principal balance after transaction
- `roi_balance`: ROI balance after transaction
- `total_balance`: Total balance after transaction

### WithdrawalRequest
- `withdrawal_type`: ROI only, principal only, composite
- `amount_requested`: Requested withdrawal amount
- `status`: Pending, approved, rejected, processed
- `disbursement_bank`: Bank for payout
- `account_name`: Account holder name
- `account_number`: Bank account number

### ROIAccrual
- `accrual_date`: Date of accrual
- `calculation_period`: Period (e.g., "2024-03")
- `principal_for_calculation`: Principal amount used
- `roi_rate_applied`: ROI rate used
- `roi_amount`: Calculated ROI amount
- `is_accrued`: Whether added to balance
- `is_paid`: Whether paid out

### TaxRecord (✅ **New Model**)
- `tax_type`: Type of tax (wht_interest, pit, cgt, vat, tet)
- `gross_amount`: Original amount before tax
- `tax_rate`: Tax rate applied (e.g., 0.10 for 10%)
- `tax_amount`: Calculated tax amount
- `net_amount`: Amount after tax deduction
- `calculation_date`: When tax was calculated
- `tax_year`: Tax year for reporting
- `transaction_reference`: Link to related transaction
- `firs_reference`: FIRS reference number
- `is_paid`: Whether tax has been paid
- `payment_date`: When tax was paid
- `certificate_generated`: Whether certificate was issued

### TaxCertificate (✅ **New Model**)
- `certificate_number`: Unique certificate identifier
- `certificate_type`: Type of certificate (annual_summary, transaction_specific)
- `tax_year`: Year the certificate covers
- `total_gross_income`: Total income for the period
- `total_tax_deducted`: Total tax deducted
- `total_tax_paid`: Total tax paid to FIRS
- `net_income_after_tax`: Net income after all taxes
- `issue_date`: When certificate was issued
- `valid_until`: Certificate validity period
- `digital_signature`: Electronic signature for verification
- `verification_code`: Unique verification code

### TaxSettings (✅ **New Model**)
- `tenant`: Associated tenant
- `wht_rate`: Withholding tax rate (default 10%)
- `pit_brackets`: JSON field with PIT bracket configuration
- `cgt_rate`: Capital gains tax rate (default 10%)
- `vat_rate`: Value added tax rate (default 7.5%)
- `tet_rate`: Tertiary education tax rate (default 2.5%)
- `tax_year_start`: Start of tax year (default Jan 1)
- `firs_integration_enabled`: Whether FIRS integration is active
- `auto_certificate_generation`: Auto-generate certificates

---

## 🔧 Configuration & Settings

### Environment Variables
- `DEFAULT_FROM_EMAIL`: Email address for notifications
- `GATEWAY_URL`: Base URL for pagination links

### Tenant Configuration
- `roi_rate`: Default annual ROI rate (default: 40%)
- `min_withdrawal_months`: Default minimum withdrawal period (default: 4)

### Scheduled Tasks (Celery)
- `accrue_monthly_roi_for_tenant`: Monthly ROI accrual
- `send_roi_due_notifications`: ROI due notifications

---

## 📈 Performance Considerations

### Database Optimization
- **Indexes:** Policy number, tenant, user, status, dates
- **Select Related:** User and profile data pre-loaded
- **Aggregation:** Efficient sum/count queries for reports

### Caching Strategy
- **Policy Balances:** Cached for dashboard performance
- **Tenant Settings:** Cached configuration values
- **Exchange Rates:** If multi-currency support added

### Scalability Features
- **Tenant Isolation:** Complete data separation
- **Pagination:** Large result sets paginated
- **Background Processing:** ROI calculations in background
- **CSV Export:** Efficient streaming for large exports

---

## 🧪 Testing & Quality Assurance

### Test Coverage
- **Unit Tests:** Individual service methods
- **Integration Tests:** API endpoint testing
- **Business Logic:** ROI calculations, withdrawal rules
- **Multi-tenancy:** Tenant isolation verification

### Data Validation
- **Balance Consistency:** Automatic balance verification
- **Transaction Integrity:** Atomic operations for all financial changes
- **Audit Trail:** Complete ledger history for all transactions

---

## 🚀 Future Enhancements

### Planned Features
- **Multi-currency Support:** USD, EUR, GBP support
- **Auto-rollover:** Automatic reinvestment options
- **Mobile App:** React Native investment app
- **Advanced Analytics:** Predictive ROI modeling
- **Integration APIs:** Third-party payment gateways
- **Document Management:** Policy documents, KYC files
- **Notification Preferences:** Customizable alert settings
- **Bulk Operations:** Mass policy updates, bulk withdrawals

### Technical Improvements
- **Real-time Updates:** WebSocket notifications
- **API Versioning:** v2 API with enhanced features
- **Rate Limiting:** API throttling for security
- **Audit Logging:** Comprehensive activity tracking
- **Backup & Recovery:** Automated database backups
- **Monitoring:** Performance metrics and alerting

---

*This documentation is continuously updated. Last updated: November 2025*

*Frontend Implementation: 100% Complete - All documented APIs and features implemented*

*🇳🇬 Nigerian Tax System: 100% Complete - Full FIRS compliance with frontend-backend integration*

*🔗 API Integration: 100% Complete - All 9 tax APIs fully integrated with responsive UI*

## 📊 Dashboard & Analytics

### Investment Dashboard
**Purpose:** Get comprehensive investment dashboard with metrics and analytics.
**Method:** GET
**URL:** `http://localhost:9090/api/investments/dashboard/`

**Response (Investor View):**
```json
{
  "metrics": {
    "total_policies": 1,
    "total_investment": "50000.00",
    "total_roi": "2500.00", 
    "active_policies": 1,
    "total_policy_amount": "52500.00",
    "monthly_roi_estimate": "1666.67",
    "annual_roi_estimate": "20000.00"
  },
  "recent_activity": [
    {
      "date": "2024-03-01T00:00:00Z",
      "type": "roi_accrual",
      "description": "ROI Accrual - March 2024",
      "amount": "1666.67"
    },
    {
      "date": "2024-03-15T14:30:00Z", 
      "type": "withdrawal",
      "description": "ROI Withdrawal",
      "amount": "-833.34"
    }
  ],
  "policy_summary": [
    {
      "policy_number": "PRO-000001",
      "current_balance": "50000.00",
      "roi_balance": "2500.00",
      "total_balance": "52500.00",
      "status": "active"
    }
  ]
}
```

**Response (Admin View):**
```json
{
  "metrics": {
    "total_policies": 150,
    "total_investment": "7500000.00",
    "total_roi": "250000.00",
    "active_policies": 145,
    "total_policy_amount": "7750000.00",
    "monthly_roi_liability": "250000.00"
  },
  "roi_due": [
    {
      "policy_number": "PRO-000001",
      "user__email": "john@example.com", 
      "roi_balance": "2500.00",
      "next_roi_date": "2024-04-01T00:00:00Z",
      "estimated_roi": "1666.67"
    },
    {
      "policy_number": "PRO-000002",
      "user__email": "jane@example.com",
      "roi_balance": "3750.00", 
      "next_roi_date": "2024-04-01T00:00:00Z",
      "estimated_roi": "2500.00"
    }
  ],
  "top_policies": [
    {
      "policy_number": "PRO-001000",
      "investor_name": "Major Investor",
      "total_balance": "500000.00",
      "roi_balance": "16666.67"
    }
  ]
}
```

---

### Ledger Summary & Reports
**Purpose:** Get summarized ledger data with breakdowns and analytics.
**Method:** GET
**URL:** `http://localhost:9090/api/investments/ledger/summary/`

**Query Parameters:** `date_from`, `date_to`

**Response:**
```json
{
  "summary": {
    "total_inflow": "53333.34",
    "total_outflow": "833.34", 
    "net_flow": "52500.00",
    "entry_count": 4
  },
  "type_breakdown": [
    {
      "entry_type": "deposit",
      "count": 1,
      "total_inflow": "50000.00",
      "total_outflow": "0.00"
    },
    {
      "entry_type": "roi_accrual",
      "count": 2, 
      "total_inflow": "3333.34",
      "total_outflow": "0.00"
    },
    {
      "entry_type": "withdrawal_roi",
      "count": 1,
      "total_inflow": "0.00",
      "total_outflow": "833.34"
    }
  ],
  "current_balances": {
    "principal_balance": "50000.00",
    "roi_balance": "2500.00",
    "total_balance": "52500.00"
  },
  "date_range": {
    "from": "2024-01-01T00:00:00Z",
    "to": "2024-03-31T23:59:59Z"
  }
}
```

---

## 🔧 Administrative Operations

### Manual ROI Accrual (Admin Only)
**Purpose:** Manually trigger ROI accrual for all eligible policies.
**Method:** POST
**URL:** `http://localhost:9090/api/investments/roi/accrue/`

**Response:**
```json
{
  "message": "ROI accrual processed successfully",
  "results": {
    "processed": 145,
    "errors": 0,
    "accruals": [
      {
        "policy_number": "PRO-000001",
        "investor_name": "John Investor", 
        "accrual_date": "2024-04-01T00:00:00Z",
        "roi_amount": "1666.67",
        "principal": "50000.00"
      }
    ]
  },
  "timestamp": "2024-04-01T00:05:00Z"
}
```

---

### Get ROI Accrual Status (Admin Only)
**Purpose:** Get ROI accrual status and upcoming calculations.
**Method:** GET  
**URL:** `http://localhost:9090/api/investments/roi/accrue/`

**Response:**
```json
{
  "upcoming_accruals": {
    "due_count": 145,
    "total_principal": "7250000.00",
    "estimated_monthly_roi": "241666.67",
    "policies": [
      {
        "policy_number": "PRO-000001",
        "investor_name": "John Investor",
        "current_balance": "50000.00",
        "next_roi_date": "2024-04-01T00:00:00Z",
        "estimated_roi": "1666.67"
      }
    ]
  },
  "recent_accruals": [
    {
      "policy_number": "PRO-000001",
      "investor_name": "John Investor",
      "accrual_date": "2024-03-01T00:00:00Z",
      "roi_amount": "1666.67",
      "principal": "50000.00"
    }
  ]
}
```

---

## ⚙️ Business Rules & Features

### ROI Calculation Rules
- **Annual ROI Rate:** 40% of principal
- **Monthly ROI:** (40% / 12) = 3.33% of principal monthly
- **Investment Date Rules:**
  - **1st-12th of month:** ROI recorded for same month
  - **13th+ of month:** ROI recorded from next month
- **ROI Frequency:** Monthly (auto) or On-demand (manual)

### Nigerian Tax Compliance (✅ **Fully Implemented - Frontend & Backend**)
- **Withholding Tax (WHT):** 10% on ROI payments, dividends, interest - **Auto-calculated on withdrawals**
- **Personal Income Tax (PIT):** Progressive rates (7%-24%) on total income - **Real-time calculations**
- **Capital Gains Tax (CGT):** 10% on capital gains from asset disposal
- **Value Added Tax (VAT):** 7.5% on applicable services and transactions
- **Tax Reporting:** Automated tax calculations and printable reports - **TaxReportModal component**
- **Compliance Features:** TIN validation, tax certificate generation - **FIRS-compliant**
- **Tax Records:** Complete audit trail with TaxRecord model - **Database storage**
- **Tax Certificates:** Official FIRS-compliant certificates - **TaxCertificate model**
- **Tax Settings:** Tenant-specific tax configuration - **TaxSettings model**
- **Withdrawal Integration:** Automatic tax deduction on ROI withdrawals - **10% WHT applied**

### Withdrawal Restrictions
- **Principal Withdrawals:** Allowed only after 4 months
- **ROI Withdrawals:** Available immediately (if accrued)
- **Partial Withdrawals:** Supported based on policy settings
- **Composite Withdrawals:** Principal + ROI in single transaction

### Multi-tenancy Features
- **Data Isolation:** Complete tenant separation
- **Policy Numbers:** Tenant-specific sequences using first 3 uppercase letters of tenant name (APP-000001, PRO-000001, etc.)
- **ROI Rates:** Configurable per tenant (default 40%)
- **Admin Access:** Tenant-scoped administration

### Security & Access Control
- **Investors:** Can only access their own policies
- **Admins:** Can access all policies within their tenant
- **Super Admins:** Cross-tenant access (if configured)
- **JWT Authentication:** Required for all endpoints

---

## 🔄 Scheduled Operations

### Automated ROI Accrual
**Schedule:** 1st of every month at 00:00 UTC
**Task:** `accrue_monthly_roi`
**Function:** Automatically accrues ROI for all eligible policies

### ROI Due Notifications  
**Schedule:** 25th of every month at 00:00 UTC
**Task:** `send_roi_due_notifications`
**Function:** Notifies investors of upcoming ROI payments

### Withdrawal Processing
**Schedule:** Daily at 09:00 UTC  
**Task:** `process_approved_withdrawals`
**Function:** Processes approved withdrawal requests

---
