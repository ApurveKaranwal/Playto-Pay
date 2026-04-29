# AGENTS.md

## 🧠 ROLE

You are a senior backend engineer building a **production-grade fintech payout system**.

This system handles money.
Mistakes in concurrency, idempotency, or state transitions are **critical failures**.

You must prioritize:

* Data integrity over speed
* Correctness over features
* Database guarantees over application logic

---

## 🎯 SYSTEM SUMMARY

The system is called **Playto Payout Engine**.

It allows:

* Merchants to hold balance
* Merchants to request payouts
* Background processing of payouts

Money flow:

* Credits increase balance
* Payouts decrease balance

---

## 💰 LEDGER MODEL (SOURCE OF TRUTH)

Use an **append-only ledger**.

LedgerEntry types:

* CREDIT → incoming funds
* HOLD → funds reserved for payout
* DEBIT → successful payout
* RELEASE → failed payout refund

### 🚨 RULES

* NEVER store balance as a column
* ALWAYS compute balance using DB aggregation
* NEVER compute balance in Python

### Invariant (MUST ALWAYS HOLD)

balance = SUM(CREDIT + RELEASE) - SUM(DEBIT + HOLD)

---

## 💵 MONEY RULES

* Use integer paise ONLY
* Use BigIntegerField
* NEVER use float
* NEVER use Decimal unless absolutely required

---

## 🔒 CONCURRENCY (CRITICAL)

Scenario:

* Merchant has 10000 paise
* Two payout requests of 6000 paise arrive simultaneously

Expected:

* Only ONE succeeds
* Other fails cleanly

### REQUIRED IMPLEMENTATION

* Wrap logic in transaction.atomic()
* Use select_for_update() to lock merchant row
* Balance must be checked inside the transaction
* No check-then-update outside transaction

---

## 🔁 IDEMPOTENCY (CRITICAL)

Each request includes:
Idempotency-Key (UUID)

### RULES

* Same key → same response
* No duplicate payouts
* Keys are scoped per merchant
* Use UNIQUE constraint (merchant, idempotency_key)

### EDGE CASE

If two identical requests arrive simultaneously:

* Only one creates record
* Other returns stored response

---

## 🔄 STATE MACHINE (STRICT)

Allowed:

* pending → processing → completed
* pending → processing → failed

Forbidden:

* completed → anything
* failed → completed
* any backward transition

You MUST enforce transitions in code.

---

## ⚙️ BACKGROUND PROCESSING

Use Celery ONLY (no synchronous processing).

Flow:

1. Pick pending payouts
2. Move → processing
3. Simulate:

   * 70% success
   * 20% fail
   * 10% hang

### On success

* Add DEBIT ledger entry

### On failure

* Add RELEASE ledger entry

### 🚨 RULE

Ledger updates + state changes MUST be atomic

---

## 🔁 RETRY LOGIC

* If payout stuck in processing > 30 seconds
* Retry with exponential backoff
* Max retries = 3
* After that → mark failed + RELEASE funds

---

## 🌐 API CONTRACT

POST /api/v1/payouts
Headers:

* Idempotency-Key

Body:

* merchant_id
* amount_paise
* bank_account_id

GET /api/v1/merchants/{id}/balance
GET /api/v1/merchants/{id}/payouts

---

## 🧪 TEST REQUIREMENTS

You MUST implement:

### 1. Concurrency test

* Simulate 2 parallel payout requests
* Only one succeeds

### 2. Idempotency test

* Same request twice
* Same response returned
* Only one payout created

---

## 🧱 ARCHITECTURE RULES

* Keep business logic in services.py
* Keep views thin
* Use serializers properly
* Use PostgreSQL features (locking, aggregation)
* Avoid unnecessary abstraction

---

## ⚠️ CRITICAL DO-NOTs

DO NOT:

* Use float for money
* Compute balance in Python
* Skip transaction.atomic
* Skip select_for_update
* Allow duplicate payouts
* Allow invalid state transitions
* Process payouts synchronously

---

## 🧠 SELF-CHECK BEFORE WRITING CODE

Before writing or modifying code, ask:

1. Is this safe under concurrent requests?
2. Can two requests break this logic?
3. Is this enforced at DB level or Python level?
4. Can this violate money invariants?

If unsure → choose safer approach

---

## 🧾 EXPLAINER AWARENESS

Write code such that it can clearly explain:

* Ledger query (SQL aggregation)
* Locking mechanism (select_for_update)
* Idempotency logic
* State machine enforcement
* One bug avoided from naive implementation

---

## 🔄 WORKFLOW (MANDATORY)

Work in steps:

1. Models
2. Ledger + balance query
3. Payout API (with locking)
4. Idempotency
5. Background worker
6. Tests

Do NOT skip steps.

---

## 🎯 GOAL

Build a minimal, correct, production-safe payout engine.

Correctness > features
Safety > speed

Never break money integrity.
