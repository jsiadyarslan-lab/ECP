(() => {
  "use strict";
  const gatewayUrl = "http://127.0.0.1:8765";
  const sessionStorageKey = "ecp.console.session";
  let session = localStorage.getItem(sessionStorageKey);
  let catalog = null;
  let current = null;
  const $ = (id) => document.getElementById(id);
  const setPill = (id, text, tone = "neutral") => { const el = $(id); el.textContent = text; el.className = `pill ${tone}`; };
  const setText = (id, text) => { $(id).textContent = text == null ? "—" : String(text); };
  const safeError = (error) => { $("error").textContent = error instanceof Error ? error.message : "Gateway request failed"; };
  const clearSession = () => {
    session = null;
    localStorage.removeItem(sessionStorageKey);
    $("run-button").disabled = true;
  };
  const requirePairing = () => {
    clearSession();
    setPill("gateway-state", "AUTHENTICATION REQUIRED", "warn");
    setText("gateway-detail", "Pair with the current temporary code printed by the local gateway.");
  };
  window.addEventListener("storage", (event) => {
    if (event.key !== sessionStorageKey) return;
    session = event.newValue;
    if (!session) {
      requirePairing();
      return;
    }
    status();
  });
  async function call(path, options = {}) {
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (session) headers["X-ECP-Session"] = session;
    const response = await fetch(`${gatewayUrl}${path}`, { ...options, headers });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(payload.error || `Gateway returned ${response.status}`);
      error.status = response.status;
      error.state = payload.state;
      throw error;
    }
    return payload;
  }
  async function status() {
    try {
      const payload = await call("/api/v1/status");
      if (!session) {
        setPill("gateway-state", "AUTHENTICATION REQUIRED", "warn");
        setText("gateway-detail", payload.gateway === "CONNECTED" ? "Gateway is running. Pair it with the short-lived code printed locally." : "Start the local gateway, then press PAIR.");
        return;
      }
      try {
        catalog = await call("/api/v1/catalog");
        populate();
        setPill("gateway-state", "CONNECTED", "good");
        setText("gateway-detail", "Authenticated loopback gateway is ready.");
      } catch (error) {
        if (error.status === 401 || error.state === "AUTHENTICATION_REQUIRED") requirePairing();
        else throw error;
      }
    } catch (_) {
      setPill("gateway-state", "NOT REACHABLE", "bad");
      setText("gateway-detail", "Start the local gateway, then press PAIR. No external call was attempted.");
    }
  }
  function populate() {
    const select = $("evaluation-select");
    select.replaceChildren();
    for (const evaluation of catalog.evaluations) {
      const option = new Option(`${evaluation.evaluation_id} · ${evaluation.provider}`, evaluation.evaluation_id);
      option.dataset.systemId = evaluation.system_id;
      select.add(option);
    }
    select.disabled = false;
    updateSelection();
    setPill("catalog-state", "LOADED", "good");
  }
  function updateSelection() {
    if (!catalog) return;
    const evaluation = catalog.evaluations.find((item) => item.evaluation_id === $("evaluation-select").value);
    if (!evaluation || !session) return;
    const credential = $("credential-select");
    credential.replaceChildren(new Option(`${evaluation.credential.credential_id} · ${evaluation.credential.status}`, evaluation.credential.credential_id));
    credential.disabled = false;
    const tests = $("test-select");
    tests.replaceChildren(...evaluation.tests.map((test) => new Option(`${test.test_id} · ${test.label}`, test.test_id)));
    tests.disabled = false;
    $("run-button").disabled = false;
    setText("selection-detail", `System ${evaluation.system_id}; provider ${evaluation.provider}; adapter ${evaluation.adapter}. Only registered identifiers are sent.`);
  }
  async function pair() {
    $("error").textContent = "";
    try {
      const code = $("pairing-code").value.trim();
      if (!code) throw new Error("Enter the temporary pairing code shown by the local gateway.");
      const payload = await call("/api/v1/pair", { method: "POST", body: JSON.stringify({ pairing_code: code }) });
      session = payload.session;
      localStorage.setItem(sessionStorageKey, session);
      $("pairing-code").value = "";
      catalog = await call("/api/v1/catalog");
      populate();
      setPill("gateway-state", "CONNECTED", "good");
      setText("gateway-detail", "Authenticated loopback gateway is ready.");
    } catch (error) {
      if (error.status === 401 || error.state === "AUTHENTICATION_REQUIRED") requirePairing();
      setPill("gateway-state", "ERROR", "bad");
      safeError(error);
    }
  }
  function render(record) {
    current = record;
    setText("execution-id", record.execution_id);
    setText("external-status", record.execution_status);
    setText("response-status", record.response_status);
    setText("evidence-status", record.evidence_status);
    setText("audit-status", record.audit_status);
    setText("persistence-status", record.persistence_status);
    setPill("execution-state", record.status, record.status === "SUCCESS" ? "good" : record.status === "RUNNING" ? "warn" : "bad");
    $("result").textContent = JSON.stringify(record.result || { error: record.error || "No safe result returned." }, null, 2);
  }
  async function run() {
    $("error").textContent = "";
    if (!session) { requirePairing(); return; }
    $("run-button").disabled = true;
    setPill("execution-state", "RUNNING", "warn");
    try {
      catalog = await call("/api/v1/catalog");
      populate();
      const evaluation = catalog.evaluations.find((item) => item.evaluation_id === $("evaluation-select").value);
      const requestId = (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`);
      const request = { evaluation_id: evaluation.evaluation_id, system_id: evaluation.system_id, credential_ref: $("credential-select").value, test_id: $("test-select").value, request_id: requestId };
      const record = await call("/api/v1/executions", { method: "POST", body: JSON.stringify(request) });
      render(record);
    } catch (error) {
      if (error.status === 401 || error.state === "AUTHENTICATION_REQUIRED") {
        requirePairing();
        setPill("execution-state", "ERROR", "bad");
        safeError(new Error("Gateway session expired or was replaced. Pair again with the current temporary code."));
      } else {
        setPill("execution-state", "ERROR", "bad");
        safeError(error);
      }
    }
    finally { $("run-button").disabled = !session; }
  }
  $("pair-button").addEventListener("click", pair);
  $("run-button").addEventListener("click", run);
  $("evaluation-select").addEventListener("change", updateSelection);
  status();
})();
