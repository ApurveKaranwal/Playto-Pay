# 💰 Playto Payout Engine

> A **production-grade fintech payout system** built with Django, PostgreSQL, and Celery. Engineered for correctness, safety, and reliability in handling merchant payouts and balance management.

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue)](https://www.python.org/)
[![Django 4.2+](https://img.shields.io/badge/Django-4.2%2B-green)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-13%2B-336791)](https://www.postgresql.org/)
[![React 18+](https://img.shields.io/badge/React-18.3%2B-61dafb)](https://react.dev/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](./LICENSE)

---

## 🎯 Overview

**Playto Payout Engine** is a robust backend service designed to handle merchant balance management and payout processing in a fintech environment. The system prioritizes **data integrity**, **correctness**, and **safety** over speed, making it suitable for production environments where money is involved.

### Key Principles

- ✅ **Data Integrity First** - Database constraints enforce all money rules
- ✅ **Correctness Over Features** - Minimal, battle-tested implementation
- ✅ **Safe Concurrency** - Row-level locking prevents race conditions
- ✅ **Idempotent Operations** - No duplicate payouts on retries
- ✅ **Append-Only Ledger** - Single source of truth for all money movements

---

## 🏗️ Architecture

### System Design Philosophy

The system is built on an **append-only ledger model**, where every financial transaction is immutable and tracked. This ensures:

- **Auditability** - Complete history of all money movements
- **Correctness** - Balance is always computed, never stored
- **Recoverability** - Can reconstruct state at any point in time

### Core Components

#### 1. **Ledger System** (Source of Truth)

The `LedgerEntry` model tracks all financial movements:

```
Balance = SUM(CREDIT + RELEASE) - SUM(DEBIT + HOLD)
```

**Entry Types:**
- `CREDIT` - Incoming funds (merchant deposit)
- `HOLD` - Funds reserved for a payout (pending)
- `DEBIT` - Successful payout completion
- `RELEASE` - Refund of held funds (payout failed)

#### 2. **Concurrency Control**

Using PostgreSQL **row-level locking** with `select_for_update()`:

```python
with transaction.atomic():
    merchant = Merchant.objects.select_for_update().get(id=merchant_id)
    # Check balance
    # Create payout atomically
```

**Why this matters:**
- Two simultaneous requests for 6000 paise with 10000 balance → Only ONE succeeds
- Database enforces constraints, not application code
- Impossible to create duplicate payouts or overdraw balance

#### 3. **Idempotency**

Each payout request includes an `Idempotency-Key` (UUID):

```
POST /api/v1/payouts
Headers: Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
```

**Guarantee:** Same key = same response (idempotent)

- First request with key → Creates payout, stores response
- Retry with same key → Returns stored response, no duplicate created
- Scoped per merchant (different merchants can use same key)

#### 4. **State Machine** (Strict)

```
pending → processing → completed
pending → processing → failed
```

**Forbidden transitions:**
- ❌ `completed → anything`
- ❌ `failed → completed`
- ❌ `any backward transition`

#### 5. **Background Processing** (Celery)

Payouts are processed asynchronously via Celery with:

- **70% Success Rate** - Payout completed, DEBIT ledger entry created
- **20% Failure Rate** - Payout failed, RELEASE ledger entry created (refund)
- **10% Hang Rate** - Stuck in processing, triggers retry logic

**Retry Logic:**
- If payout stuck in `processing` > 30 seconds → Retry with exponential backoff
- Max retries = 3
- After max retries → Mark as failed, RELEASE funds automatically

---

## 📊 Data Model

### Merchant

```python
class Merchant(models.Model):
    name = CharField(max_length=255)
    created_at = DateTimeField(auto_now_add=True)
    
    # Computed balance (never stored):
    # balance = SUM(CREDIT + RELEASE) - SUM(DEBIT + HOLD)
```

### Payout

```python
class Payout(models.Model):
    merchant = ForeignKey(Merchant)
    amount_paise = BigIntegerField  # Integer only, no floats
    status = CharField(choices=['pending', 'processing', 'completed', 'failed'])
    idempotency_key = CharField(max_length=255)
    bank_account_id = CharField(max_length=255)
    attempts = PositiveIntegerField(default=0)
    processing_started_at = DateTimeField(null=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    
    # Constraints:
    # - UNIQUE(merchant, idempotency_key)
    # - CHECK(amount_paise > 0)
```

### LedgerEntry

```python
class LedgerEntry(models.Model):
    merchant = ForeignKey(Merchant)
    payout = ForeignKey(Payout, null=True)
    entry_type = CharField(choices=['CREDIT', 'DEBIT', 'HOLD', 'RELEASE'])
    amount_paise = BigIntegerField
    reference_id = CharField(max_length=255, blank=True)
    created_at = DateTimeField(auto_now_add=True)
    
    # Indexes for fast balance queries
```

### IdempotencyKey

```python
class IdempotencyKey(models.Model):
    merchant = ForeignKey(Merchant)
    key = CharField(max_length=255)
    response_status_code = PositiveSmallIntegerField
    response_data = JSONField
    payout = OneToOneField(Payout, null=True)
    created_at = DateTimeField(auto_now_add=True)
    
    # UNIQUE(merchant, key)
```

---

## 🔒 Money Rules

### Absolute Rules (Enforced)

1. **Integer Only** - All amounts in `paise` (1 INR = 100 paise)
2. **No Floats** - Never use `float` type for money
3. **BigIntegerField** - Use Django's `BigIntegerField` (64-bit integers)
4. **Database Constraints** - CHECK constraints enforce positive amounts
5. **Computed Balance** - Balance = DB aggregation, never stored column

### Why These Rules?

```python
# ❌ WRONG - Floating point precision errors
balance = 10000.50  # What if it's 10000.500000000001?

# ✅ RIGHT - Integer paise
balance_paise = 1000050  # No ambiguity, exact value
```

---

## 🛠️ Tech Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| **Backend** | Django + DRF | 4.2+ |
| **Database** | PostgreSQL | 13+ |
| **Task Queue** | Celery | Latest |
| **Message Broker** | Redis | Latest |
| **Frontend** | React + Vite | 18.3+ / 5.4+ |
| **Language** | Python | 3.12+ |
| **Environment** | Docker (optional) | - |

---

## 📁 Project Structure

```
Playto-Pay/
├── backend/                          # Django backend
│   ├── config/
│   │   ├── settings.py               # Django settings
│   │   ├── urls.py                   # URL routing
│   │   ├── wsgi.py                   # WSGI entry point
│   │   └── celery.py                 # Celery configuration
│   ├── payouts/                      # Main app
│   │   ├── models.py                 # Merchant, Payout, LedgerEntry, IdempotencyKey
│   │   ├── views.py                  # DRF API endpoints
│   │   ├── serializers.py            # Request/response serialization
│   │   ├── services.py               # Business logic (atomic operations)
│   │   ├── tasks.py                  # Celery tasks (async processing)
│   │   ├── constants.py              # Ledger types, payout statuses
│   │   ├── utils.py                  # Helper functions (balance queries)
│   │   └── tests.py                  # Comprehensive test suite
│   ├── manage.py                     # Django CLI
│   └── requirements.txt              # Python dependencies
├── frontend/                         # React frontend
│   ├── src/
│   │   ├── App.jsx                   # Main React component
│   │   ├── api.js                    # API client
│   │   ├── main.jsx                  # Entry point
│   │   └── styles.css                # Styles
│   ├── package.json                  # Node.js dependencies
│   ├── vite.config.js                # Vite configuration
│   └── index.html                    # HTML template
├── AGENTS.md                         # AI agent configuration
├── .gitignore                        # Git ignore rules
├── README.md                         # This file
└── LICENSE                           # MIT License
```

---

## ⚙️ Installation & Setup

### Prerequisites

- Python 3.12+
- PostgreSQL 13+
- Node.js 16+
- Redis (for Celery)
- Git

### Backend Setup

#### 1. Clone Repository

```bash
git clone https://github.com/ApurveKaranwal/Playto-Pay.git
cd Playto-Pay/backend
```

#### 2. Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

#### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

#### 4. Configure Environment

Create `.env` file in `backend/`:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/playto_payout

# Django
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Celery/Redis
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

#### 5. Initialize Database

```bash
python manage.py migrate
python manage.py createsuperuser  # Optional
```

#### 6. Start Services

```bash
# Terminal 1: Django development server
python manage.py runserver

# Terminal 2: Celery worker
celery -A config worker -l info

# Terminal 3: Celery beat (scheduled tasks)
celery -A config beat -l info
```

### Frontend Setup

#### 1. Install Dependencies

```bash
cd frontend
npm install
```

#### 2. Start Development Server

```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`

---

## 🚀 Running the Project

### Using Provided Scripts

```bash
# Start all services
.\start-dev.ps1  # PowerShell
bash start-dev.sh  # Linux/Mac

# Stop all services
.\stop-dev.ps1  # PowerShell
bash stop-dev.sh  # Linux/Mac

# Full project setup and run
.\run-project.ps1  # PowerShell
bash run-project.sh  # Linux/Mac
```

### Manual Startup

```bash
# Terminal 1: Backend
cd backend
python manage.py runserver 0.0.0.0:8000

# Terminal 2: Celery Worker
cd backend
celery -A config worker -l info --concurrency=4

# Terminal 3: Celery Beat
cd backend
celery -A config beat -l info

# Terminal 4: Frontend
cd frontend
npm run dev
```

---

## 📡 API Documentation

### Base URL

```
http://localhost:8000/api/v1
```

### Endpoints

#### Merchants

```http
GET /merchants
```
List all merchants with their current balance.

**Response:**
```json
[
  {
    "id": 1,
    "name": "Acme Corp",
    "balance_paise": 500000,
    "created_at": "2026-04-29T10:00:00Z"
  }
]
```

---

```http
POST /merchants
Content-Type: application/json

{
  "name": "New Merchant"
}
```
Create a new merchant.

**Response:** `201 Created`

---

#### Credits (Add Funds)

```http
POST /merchants/{id}/credits
Content-Type: application/json

{
  "amount_paise": 1000000,
  "reference_id": "deposit-123"
}
```
Add funds to merchant balance.

**Response:**
```json
{
  "ledger_entry_id": 42,
  "merchant_id": 1,
  "amount_paise": 1000000,
  "entry_type": "CREDIT",
  "reference_id": "deposit-123",
  "balance_paise": 1500000
}
```

---

#### Payouts

```http
POST /payouts
Content-Type: application/json
Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000

{
  "merchant_id": 1,
  "amount_paise": 100000,
  "bank_account_id": "ACC-001"
}
```
Request a payout. Will be processed asynchronously.

**Response:** `201 Created`
```json
{
  "id": 5,
  "merchant_id": 1,
  "amount_paise": 100000,
  "status": "pending",
  "bank_account_id": "ACC-001",
  "created_at": "2026-04-29T10:05:00Z"
}
```

**Error Responses:**
- `400` - Insufficient balance or invalid amount
- `409` - Duplicate idempotency key (returns original response)

---

```http
GET /merchants/{id}/payouts
```
List all payouts for a merchant.

**Response:**
```json
[
  {
    "id": 5,
    "merchant_id": 1,
    "amount_paise": 100000,
    "status": "completed",
    "bank_account_id": "ACC-001",
    "attempts": 1,
    "created_at": "2026-04-29T10:05:00Z"
  }
]
```

---

#### Balance & Ledger

```http
GET /merchants/{id}/balance
```
Get current merchant balance snapshot.

**Response:**
```json
{
  "merchant_id": 1,
  "balance_paise": 1400000,
  "last_updated": "2026-04-29T10:10:00Z"
}
```

---

```http
GET /merchants/{id}/ledger
```
List all ledger entries for a merchant.

**Response:**
```json
[
  {
    "id": 1,
    "merchant_id": 1,
    "entry_type": "CREDIT",
    "amount_paise": 1000000,
    "reference_id": "deposit-123",
    "payout_id": null,
    "created_at": "2026-04-29T10:00:00Z"
  },
  {
    "id": 2,
    "merchant_id": 1,
    "entry_type": "HOLD",
    "amount_paise": 100000,
    "reference_id": "",
    "payout_id": 5,
    "created_at": "2026-04-29T10:05:00Z"
  }
]
```

---

## 🧪 Testing

### Run All Tests

```bash
cd backend
python manage.py test
```

### Run Specific Test

```bash
python manage.py test payouts.tests.ConcurrencyTest
```

### Test Coverage

```bash
coverage run --source='.' manage.py test
coverage report
coverage html  # Generate HTML report
```

### Key Test Scenarios

#### 1. Concurrency Test
Verifies that two simultaneous payout requests with insufficient balance result in only one success:

```python
def test_concurrent_payout_requests():
    # Create merchant with 10000 paise
    # Send two requests for 6000 paise simultaneously
    # Assert: Only one succeeds, other fails with insufficient balance
```

#### 2. Idempotency Test
Verifies that identical requests return the same response without creating duplicates:

```python
def test_idempotent_payout_creation():
    # Send same payout request twice with same Idempotency-Key
    # Assert: Same response both times, only one payout created
```

#### 3. State Machine Test
Verifies that invalid state transitions are rejected:

```python
def test_invalid_state_transitions():
    # Try to move payout from completed → processing
    # Assert: Raises ValidationError
```

#### 4. Balance Calculation Test
Verifies that balance is correctly computed from ledger entries:

```python
def test_balance_calculation():
    # Create CREDIT, HOLD, DEBIT, RELEASE entries
    # Assert: balance = CREDIT + RELEASE - DEBIT - HOLD
```

#### 5. Retry Logic Test
Verifies that stuck payouts are retried and eventually marked failed:

```python
def test_payout_retry_logic():
    # Mark payout as stuck in processing
    # Wait for retry task
    # Assert: Attempt count increases, eventually marked failed + RELEASE
```

---

## 🔍 Core Features Explained

### Feature: Append-Only Ledger

**Problem:** How do we ensure balance is always correct?

**Solution:** Store every transaction in an immutable ledger.

```sql
SELECT COALESCE(SUM(CASE 
    WHEN entry_type IN ('CREDIT', 'RELEASE') THEN amount_paise
    ELSE -amount_paise
  END), 0) AS balance
FROM ledger_entries
WHERE merchant_id = 1;
```

**Benefits:**
- ✅ Balance can never be negative (derived, not stored)
- ✅ Complete audit trail
- ✅ Can recover from any corruption

---

### Feature: Row-Level Locking

**Problem:** Two payouts of 6000 paise arrive simultaneously with 10000 balance. Both could overdraw!

**Solution:** Lock merchant row during atomic transaction.

```python
with transaction.atomic():
    merchant = Merchant.objects.select_for_update().get(id=merchant_id)
    balance = get_merchant_balance(merchant_id)
    
    if balance < amount_paise:
        raise InsufficientBalanceError()
    
    # Create HOLD + Payout
    # Only one request gets past the lock
```

**Lock Timeline:**
1. Request A acquires lock at T1
2. Request B waits for lock
3. Request A checks balance → ✓ Sufficient
4. Request A creates HOLD + Payout
5. Request A releases lock at T2
6. Request B acquires lock at T2
7. Request B checks balance → ✗ Insufficient → Fails

---

### Feature: Idempotency

**Problem:** Network timeout causes client to retry. Creates duplicate payout!

**Solution:** Store Idempotency-Key + response. Return stored response on retry.

```python
# First request
stored = IdempotencyKey.objects.filter(
    merchant_id=merchant_id,
    key=idempotency_key
).first()

if stored:
    return stored.response_data, stored.response_status_code

# Create payout...
# Store response with key
IdempotencyKey.objects.create(
    merchant_id=merchant_id,
    key=idempotency_key,
    response_data=response_dict,
    response_status_code=201,
    payout=payout
)
```

---

### Feature: Background Processing

**Problem:** Payout processing takes time. Can't block API response.

**Solution:** Queue async task, return immediately.

```python
# API creates payout in pending state
payout = Payout.objects.create(
    merchant_id=merchant_id,
    amount_paise=amount_paise,
    status=PAYOUT_PENDING,
    idempotency_key=idempotency_key
)

# Queue async processing
process_payout.delay(payout_id=payout.id)

# Return immediately
return {"id": payout.id, "status": "pending"}
```

**Celery Task:**
```python
@app.task(bind=True, max_retries=3)
def process_payout(self, payout_id):
    payout = Payout.objects.get(id=payout_id)
    
    try:
        # Simulate payout (70% success, 20% fail, 10% hang)
        result = simulate_payout(payout.bank_account_id, payout.amount_paise)
        
        if result == 'success':
            # Mark completed + create DEBIT entry
            finalize_payout_success(payout)
        else:
            # Mark failed + create RELEASE entry
            finalize_payout_failure(payout)
            
    except Exception as exc:
        # Retry with exponential backoff
        if payout.attempts < MAX_RETRIES:
            raise self.retry(exc=exc, countdown=2 ** payout.attempts)
        else:
            # Max retries exceeded, mark failed
            finalize_payout_failure(payout)
```

---

## 🐛 Debugging

### View Ledger Entries

```bash
python manage.py shell
```

```python
from payouts.models import LedgerEntry, Merchant

merchant = Merchant.objects.get(id=1)
ledger = LedgerEntry.objects.filter(merchant=merchant).order_by('-created_at')

for entry in ledger:
    print(f"{entry.entry_type:10} {entry.amount_paise:>10} {entry.created_at}")
```

### Check Merchant Balance

```python
from payouts.utils import get_merchant_balance

balance = get_merchant_balance(merchant_id=1)
print(f"Balance: {balance} paise = {balance / 100} INR")
```

### Monitor Celery Tasks

```bash
# Watch running tasks
celery -A config inspect active

# View task statistics
celery -A config inspect stats
```

---

## 🤝 Contributing

### Development Workflow

1. Create feature branch: `git checkout -b feature/your-feature`
2. Make changes following principles above
3. Run tests: `python manage.py test`
4. Submit pull request with description

### Code Style

- Use Django best practices
- Type hints where applicable
- Docstrings for non-obvious logic
- Keep business logic in `services.py`
- Keep views thin

### Testing Requirements

- All critical paths must have tests
- Test concurrency and race conditions
- Test state transitions
- Test idempotency
- Test error cases

---

## 📋 Deployment Checklist

- [ ] Set `DEBUG=False` in production
- [ ] Configure proper `ALLOWED_HOSTS`
- [ ] Use strong `SECRET_KEY`
- [ ] Configure PostgreSQL in production
- [ ] Set up Redis for Celery
- [ ] Configure proper email backend
- [ ] Run `python manage.py collectstatic`
- [ ] Set up SSL/HTTPS
- [ ] Configure logging and monitoring
- [ ] Run full test suite
- [ ] Backup database strategy
- [ ] Monitor Celery queue health

---

## 📚 Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [React Documentation](https://react.dev/)

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.

---

## 📧 Support

For issues, questions, or suggestions, please open a GitHub issue or contact the maintainers.

---

## 🙏 Acknowledgments

Built with principles from:
- **Financial Systems Engineering** - Correctness-first design
- **Distributed Systems** - Concurrency and idempotency
- **Database Design** - Ledger model and constraints
- **Django Community** - Best practices and patterns

---

**Built with ❤️ for financial correctness**
