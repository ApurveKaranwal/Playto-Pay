const defaultHeaders = {
  Accept: "application/json",
  "Content-Type": "application/json",
};

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      ...defaultHeaders,
      ...(options.headers || {}),
    },
  });

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message =
      typeof payload === "object" && payload !== null
        ? payload.error || JSON.stringify(payload)
        : payload || "Request failed";
    throw new Error(message);
  }

  return payload;
}

export const api = {
  listMerchants() {
    return request("/api/v1/merchants", { method: "GET" });
  },
  createMerchant(body) {
    return request("/api/v1/merchants", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
  createCredit(body) {
    return request("/api/v1/credits", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
  getBalance(merchantId) {
    return request(`/api/v1/merchants/${merchantId}/balance`, { method: "GET" });
  },
  listPayouts(merchantId) {
    return request(`/api/v1/merchants/${merchantId}/payouts`, { method: "GET" });
  },
  listLedger(merchantId) {
    return request(`/api/v1/merchants/${merchantId}/ledger`, { method: "GET" });
  },
  createPayout(body, idempotencyKey) {
    return request("/api/v1/payouts", {
      method: "POST",
      headers: {
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(body),
    });
  },
};
