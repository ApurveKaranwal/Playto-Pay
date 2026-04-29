import { useEffect, useMemo, useState } from "react";

import { api } from "./api";

const initialMerchantForm = { name: "" };
const initialCreditForm = { amount_paise: "", reference_id: "" };
const initialPayoutForm = {
  amount_paise: "",
  bank_account_id: "",
  idempotency_key: "",
};

function formatDate(value) {
  if (!value) {
    return "-";
  }

  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function statusTone(status) {
  return `status-pill status-${status || "neutral"}`;
}

export default function App() {
  const [merchants, setMerchants] = useState([]);
  const [selectedMerchantId, setSelectedMerchantId] = useState("");
  const [balance, setBalance] = useState(null);
  const [payouts, setPayouts] = useState([]);
  const [ledger, setLedger] = useState([]);
  const [merchantForm, setMerchantForm] = useState(initialMerchantForm);
  const [creditForm, setCreditForm] = useState(initialCreditForm);
  const [payoutForm, setPayoutForm] = useState(initialPayoutForm);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const selectedMerchant = useMemo(
    () => merchants.find((merchant) => merchant.id === Number(selectedMerchantId)) || null,
    [merchants, selectedMerchantId],
  );

  async function loadMerchants(preferredMerchantId) {
    const merchantList = await api.listMerchants();
    setMerchants(merchantList);

    const nextMerchantId =
      preferredMerchantId ||
      selectedMerchantId ||
      (merchantList.length > 0 ? String(merchantList[0].id) : "");
    setSelectedMerchantId(nextMerchantId ? String(nextMerchantId) : "");

    return merchantList;
  }

  async function loadMerchantData(merchantId) {
    if (!merchantId) {
      setBalance(null);
      setPayouts([]);
      setLedger([]);
      return;
    }

    const [balanceData, payoutData, ledgerData] = await Promise.all([
      api.getBalance(merchantId),
      api.listPayouts(merchantId),
      api.listLedger(merchantId),
    ]);

    setBalance(balanceData.balance_paise);
    setPayouts(payoutData);
    setLedger(ledgerData);
  }

  async function refreshDashboard(preferredMerchantId, options = {}) {
    setError("");
    if (!options.keepMessage) {
      setMessage("");
    }
    setIsLoading(true);

    try {
      const merchantList = await loadMerchants(preferredMerchantId);
      const resolvedMerchantId =
        preferredMerchantId ||
        selectedMerchantId ||
        (merchantList.length > 0 ? merchantList[0].id : "");
      await loadMerchantData(resolvedMerchantId);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    refreshDashboard();
  }, []);

  useEffect(() => {
    if (!selectedMerchantId) {
      setBalance(null);
      setPayouts([]);
      setLedger([]);
      return;
    }

    loadMerchantData(selectedMerchantId).catch((requestError) => {
      setError(requestError.message);
    });
  }, [selectedMerchantId]);

  async function handleMerchantCreate(event) {
    event.preventDefault();
    setIsSubmitting(true);
    setError("");
    setMessage("");

    try {
      const merchant = await api.createMerchant(merchantForm);
      setMerchantForm(initialMerchantForm);
      setMessage(`Merchant ${merchant.name} created.`);
      await refreshDashboard(merchant.id, { keepMessage: true });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCreditCreate(event) {
    event.preventDefault();
    if (!selectedMerchantId) {
      setError("Select a merchant before adding credit.");
      return;
    }

    setIsSubmitting(true);
    setError("");
    setMessage("");

    try {
      const payload = {
        merchant_id: Number(selectedMerchantId),
        amount_paise: Number(creditForm.amount_paise),
        reference_id: creditForm.reference_id,
      };
      const response = await api.createCredit(payload);
      setCreditForm(initialCreditForm);
      setMessage(`Credit posted. New balance: ${response.balance_paise} paise.`);
      await refreshDashboard(selectedMerchantId, { keepMessage: true });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handlePayoutCreate(event) {
    event.preventDefault();
    if (!selectedMerchantId) {
      setError("Select a merchant before requesting a payout.");
      return;
    }

    setIsSubmitting(true);
    setError("");
    setMessage("");

    try {
      const idempotencyKey = payoutForm.idempotency_key || crypto.randomUUID();
      const payload = {
        merchant_id: Number(selectedMerchantId),
        amount_paise: Number(payoutForm.amount_paise),
        bank_account_id: payoutForm.bank_account_id,
      };
      const response = await api.createPayout(payload, idempotencyKey);
      setPayoutForm({
        amount_paise: "",
        bank_account_id: "",
        idempotency_key: idempotencyKey,
      });
      setMessage(`Payout ${response.id} accepted with status ${response.status}.`);
      await refreshDashboard(selectedMerchantId, { keepMessage: true });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="shell">
      <div className="aurora aurora-one" />
      <div className="aurora aurora-two" />

      <header className="hero">
        <div>
          <p className="eyebrow">Playto Fintech Console</p>
          <h1>Ledger-backed payouts with idempotent request handling.</h1>
        </div>
        <button className="secondary-button" onClick={() => refreshDashboard(selectedMerchantId)}>
          Refresh
        </button>
      </header>

      {error ? <div className="banner banner-error">{error}</div> : null}
      {message ? <div className="banner banner-success">{message}</div> : null}

      <section className="grid grid-top">
        <article className="panel">
          <div className="panel-heading">
            <h2>Merchants</h2>
            <span>{merchants.length} records</span>
          </div>

          <form className="stack" onSubmit={handleMerchantCreate}>
            <label>
              Merchant name
              <input
                value={merchantForm.name}
                onChange={(event) => setMerchantForm({ name: event.target.value })}
                placeholder="Acme Payments"
                required
              />
            </label>
            <button disabled={isSubmitting}>Create merchant</button>
          </form>

          <div className="merchant-list">
            {merchants.map((merchant) => (
              <button
                key={merchant.id}
                className={merchant.id === Number(selectedMerchantId) ? "merchant-card active" : "merchant-card"}
                onClick={() => setSelectedMerchantId(String(merchant.id))}
              >
                <strong>{merchant.name}</strong>
                <span>ID {merchant.id}</span>
                <span>{merchant.balance_paise} paise available</span>
              </button>
            ))}
            {!merchants.length && !isLoading ? <p className="empty">Create the first merchant to begin.</p> : null}
          </div>
        </article>

        <article className="panel highlight-panel">
          <div className="panel-heading">
            <h2>Selected merchant</h2>
            <span>{selectedMerchant ? `ID ${selectedMerchant.id}` : "No selection"}</span>
          </div>

          <div className="balance-strip">
            <div>
              <p className="metric-label">Available balance</p>
              <p className="metric-value">{balance ?? 0}</p>
              <p className="metric-foot">Integer paise, computed from ledger aggregation.</p>
            </div>
            <div className="merchant-meta">
              <span>{selectedMerchant?.name || "No merchant selected"}</span>
              <span>{selectedMerchant ? formatDate(selectedMerchant.created_at) : "-"}</span>
            </div>
          </div>

          <div className="grid grid-actions">
            <form className="panel inset" onSubmit={handleCreditCreate}>
              <div className="panel-heading">
                <h3>Add credit</h3>
                <span>CREDIT ledger entry</span>
              </div>
              <label>
                Amount paise
                <input
                  type="number"
                  min="1"
                  value={creditForm.amount_paise}
                  onChange={(event) =>
                    setCreditForm((current) => ({
                      ...current,
                      amount_paise: event.target.value,
                    }))
                  }
                  required
                />
              </label>
              <label>
                Reference ID
                <input
                  value={creditForm.reference_id}
                  onChange={(event) =>
                    setCreditForm((current) => ({
                      ...current,
                      reference_id: event.target.value,
                    }))
                  }
                  placeholder="invoice-2026-04-27"
                />
              </label>
              <button disabled={isSubmitting || !selectedMerchantId}>Post credit</button>
            </form>

            <form className="panel inset" onSubmit={handlePayoutCreate}>
              <div className="panel-heading">
                <h3>Request payout</h3>
                <span>Creates HOLD, then Celery processes</span>
              </div>
              <label>
                Amount paise
                <input
                  type="number"
                  min="1"
                  value={payoutForm.amount_paise}
                  onChange={(event) =>
                    setPayoutForm((current) => ({
                      ...current,
                      amount_paise: event.target.value,
                    }))
                  }
                  required
                />
              </label>
              <label>
                Bank account ID
                <input
                  value={payoutForm.bank_account_id}
                  onChange={(event) =>
                    setPayoutForm((current) => ({
                      ...current,
                      bank_account_id: event.target.value,
                    }))
                  }
                  placeholder="bank-account-001"
                  required
                />
              </label>
              <label>
                Idempotency key
                <input
                  value={payoutForm.idempotency_key}
                  onChange={(event) =>
                    setPayoutForm((current) => ({
                      ...current,
                      idempotency_key: event.target.value,
                    }))
                  }
                  placeholder="Leave blank to auto-generate"
                />
              </label>
              <button disabled={isSubmitting || !selectedMerchantId}>Submit payout</button>
            </form>
          </div>
        </article>
      </section>

      <section className="grid grid-bottom">
        <article className="panel">
          <div className="panel-heading">
            <h2>Payouts</h2>
            <span>{payouts.length} records</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Status</th>
                  <th>Amount</th>
                  <th>Attempts</th>
                  <th>Bank account</th>
                  <th>Idempotency key</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {payouts.map((payout) => (
                  <tr key={payout.id}>
                    <td>{payout.id}</td>
                    <td>
                      <span className={statusTone(payout.status)}>{payout.status}</span>
                    </td>
                    <td>{payout.amount_paise}</td>
                    <td>{payout.attempts}</td>
                    <td>{payout.bank_account_id}</td>
                    <td className="mono">{payout.idempotency_key}</td>
                    <td>{formatDate(payout.updated_at)}</td>
                  </tr>
                ))}
                {!payouts.length && !isLoading ? (
                  <tr>
                    <td colSpan="7" className="empty-cell">
                      No payouts for this merchant.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </article>

        <article className="panel">
          <div className="panel-heading">
            <h2>Ledger</h2>
            <span>{ledger.length} entries</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Type</th>
                  <th>Amount</th>
                  <th>Payout ID</th>
                  <th>Payout status</th>
                  <th>Reference</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {ledger.map((entry) => (
                  <tr key={entry.id}>
                    <td>{entry.id}</td>
                    <td>
                      <span className={statusTone(entry.entry_type.toLowerCase())}>{entry.entry_type}</span>
                    </td>
                    <td>{entry.amount_paise}</td>
                    <td>{entry.payout_id || "-"}</td>
                    <td>{entry.payout_status || "-"}</td>
                    <td className="mono">{entry.reference_id || "-"}</td>
                    <td>{formatDate(entry.created_at)}</td>
                  </tr>
                ))}
                {!ledger.length && !isLoading ? (
                  <tr>
                    <td colSpan="7" className="empty-cell">
                      No ledger entries for this merchant.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </article>
      </section>
    </div>
  );
}
