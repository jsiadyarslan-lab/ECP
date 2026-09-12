(() => {
  "use strict";
  const gatewayUrl = "http://127.0.0.1:8765";
  const sessionStorageKey = "ecp.console.session";
  let session = localStorage.getItem(sessionStorageKey);
  let catalog = null;
  let current = null;
  let credentialRef = null;
  let discoveryDocument = null;
  let selectedModel = null;
  const $ = (id) => document.getElementById(id);
  const setPill = (id, text, tone = "neutral") => { const el = $(id); el.textContent = text; el.className = `pill ${tone}`; };
  const setText = (id, text) => { $(id).textContent = text == null ? "—" : String(text); };
  const safeError = (error) => { $("error").textContent = error instanceof Error ? error.message : "Gateway request failed"; };
  const clearCatalog = () => {
    catalog = null;
    current = null;
    $("evaluation-select").replaceChildren();
    $("evaluation-select").disabled = true;
    $("credential-select").replaceChildren();
    $("credential-select").disabled = true;
    $("test-select").replaceChildren();
    $("test-select").disabled = true;
    $("run-button").disabled = true;
    setPill("catalog-state", "NOT LOADED", "neutral");
    setText("selection-detail", "Pair with the current temporary code to load the authorized evaluation catalog.");
  };
  const clearSession = () => {
    session = null;
    localStorage.removeItem(sessionStorageKey);
    clearCatalog();
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
        await loadDescriptors();
        setPill("gateway-state", "CONNECTED", "good");
        setText("gateway-detail", "Authenticated loopback gateway is ready.");
        m3elrProbe();
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
      await loadDescriptors();
      setPill("gateway-state", "CONNECTED", "good");
      setText("gateway-detail", "Authenticated loopback gateway is ready.");
      m3elrProbe();
    } catch (error) {
      if (error.status === 401 || error.state === "AUTHENTICATION_REQUIRED") requirePairing();
      setPill("gateway-state", "ERROR", "bad");
      safeError(error);
    }
  }
  // ------------------------------------------------------------------
  // Universal provider & model discovery (credential session flow)
  // ------------------------------------------------------------------
  async function loadDescriptors() {
    const payload = await call("/api/v1/discovery/descriptors");
    const select = $("provider-hint-select");
    select.replaceChildren(new Option("Auto-detect", ""));
    for (const descriptor of payload.descriptors) {
      const label = descriptor.requires_base_url
        ? `${descriptor.display_name} (needs endpoint below)`
        : descriptor.display_name;
      select.add(new Option(label, descriptor.discovery_id));
    }
    select.disabled = false;
  }
  async function openCredentialSession() {
    $("error").textContent = "";
    const input = $("owner-credential-input");
    const value = input.value;
    input.value = "";
    try {
      if (!value) throw new Error("Paste a provider credential first.");
      const payload = await call("/api/v1/credentials/session", { method: "POST", body: JSON.stringify({ credential_secret: value }) });
      credentialRef = payload.credential_ref;
      resetDiscoveryView();
      setPill("discovery-state", "OPEN", "good");
      setText("credential-session-detail", `Credential session open until ${payload.expires_at}. Reference ${credentialRef}; the value is held in-process by the credential gateway only.`);
      $("discover-button").disabled = false;
      $("credential-revoke-button").disabled = false;
      $("discover-button").focus();
      m3elrUpdateRunButton();
    } catch (error) {
      if (error.status === 401 || error.state === "AUTHENTICATION_REQUIRED") requirePairing();
      setPill("discovery-state", "ERROR", "bad");
      safeError(error);
    }
  }
  function resetDiscoveryView() {
    discoveryDocument = null;
    selectedModel = null;
    $("discovery-provider").hidden = true;
    $("models-block").hidden = true;
    $("session-run-button").disabled = true;
    $("discovery-probes").hidden = true;
    setPill("discovery-state", credentialRef ? "OPEN" : "CLOSED", credentialRef ? "good" : "neutral");
    setText("discovery-detail", "Discovery probes candidate provider dialects through the unified discovery fabric. If no dialect answers, the state is UNKNOWN — it is never guessed.");
  }
  function resetExecutionAttribution() {
    setText("execution-provider", "—");
    setText("execution-model", "—");
    setText("execution-adapter", "—");
    setText("execution-endpoint", "—");
    setText("execution-transport", "—");
    setText("execution-status-code", "—");
    setText("execution-latency", "—");
    setText("execution-error-classification", "—");
  }
  async function discover() {
    $("error").textContent = "";
    if (!credentialRef) { safeError(new Error("Open a credential session first.")); return; }
    $("discover-button").disabled = true;
    setPill("discovery-state", "DISCOVERING", "warn");
    setText("discovery-detail", "Probing provider dialects through the unified discovery fabric…");
    try {
      const body = { credential_ref: credentialRef };
      const hint = $("provider-hint-select").value;
      const endpoint = $("custom-endpoint-input").value.trim();
      const headerConfig = $("gateway-headers-input").value.trim();
      if (hint) body.provider_hint = hint;
      if (endpoint) body.base_url = endpoint;
      if (headerConfig) {
        try {
          body.gateway_headers = JSON.parse(headerConfig);
        } catch (parseError) {
          throw new Error("Gateway headers must be valid JSON like the placeholder example.");
        }
      }
      discoveryDocument = await call("/api/v1/discovery", { method: "POST", body: JSON.stringify(body) });
      renderDiscovery();
    } catch (error) {
      if (error.status === 401 || error.state === "AUTHENTICATION_REQUIRED") requirePairing();
      setPill("discovery-state", "ERROR", "bad");
      safeError(error);
      setText("discovery-detail", "Discovery failed before any provider was identified.");
    }
    finally { $("discover-button").disabled = !credentialRef; }
  }
  function renderDiscovery() {
    const document_ = discoveryDocument;
    if (!document_) return;
    const failed = document_.status !== "DISCOVERED";
    setPill("discovery-state", failed ? (document_.identification === "UNKNOWN" ? "UNKNOWN" : "DISCOVERY_FAILED") : "DISCOVERED", failed ? "bad" : "good");
    const provider = document_.provider || {};
    if (!failed) {
      $("discovery-provider").hidden = false;
      setText("discovered-provider-name", provider.display_name || "—");
      setText("discovered-provider-id", provider.provider_id || "—");
      setText("discovered-adapter", `${document_.adapter && document_.adapter.protocol ? document_.adapter.protocol : "—"} · ${document_.adapter && document_.adapter.adapter_kind ? document_.adapter.adapter_kind : "—"}`);
      setText("discovered-endpoint", document_.adapter && document_.adapter.endpoint_base ? document_.adapter.endpoint_base : "—");
      setText("discovery-detail", `${provider.identification_basis || "provider identified"}. Select a model, then run the evaluation through the universal fabric.`);
    } else {
      $("discovery-provider").hidden = true;
      setText("discovery-detail", "No provider was identified from the credential. The state is explicit — the fabric never guesses a provider identity.");
    }
    const models = document_.models || [];
    $("models-block").hidden = models.length === 0;
    setPill("discovery-model-count", document_.models_truncated ? `${models.length} of ${document_.total_models}` : String(models.length), models.length ? "good" : "neutral");
    const list = $("models-list");
    list.replaceChildren();
    for (const model of models) {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "model-row";
      row.setAttribute("role", "option");
      row.dataset.modelIdentifier = model.model_identifier;
      const name = document.createElement("span");
      name.className = "model-name";
      name.textContent = model.display_name || model.model_identifier;
      const identifier = document.createElement("span");
      identifier.className = "model-id";
      identifier.textContent = model.model_identifier;
      const meta = document.createElement("span");
      meta.className = "model-meta";
      const capabilities = (model.capabilities || []).slice(0, 4).join(", ");
      meta.textContent = capabilities ? capabilities : (model.availability || "AVAILABLE");
      row.append(name, identifier, meta);
      row.addEventListener("click", () => selectModel(model.model_identifier));
      list.append(row);
    }
    selectedModel = null;
    $("session-run-button").disabled = true;
    const probes = document_.probes || [];
    $("discovery-probes").hidden = probes.length === 0;
    $("discovery-probe-detail").textContent = JSON.stringify(probes, null, 2);
  }
  function selectModel(modelIdentifier) {
    selectedModel = modelIdentifier;
    for (const row of $("models-list").children) {
      row.classList.toggle("selected", row.dataset.modelIdentifier === modelIdentifier);
    }
    $("session-run-button").disabled = false;
    setText("discovery-detail", `Model ${modelIdentifier} selected. RUN EVALUATION onboards it through the universal fabric and executes the conformance probe.`);
  }
  async function runSessionEvaluation() {
    $("error").textContent = "";
    if (!credentialRef || !selectedModel) { safeError(new Error("Open a credential session, discover, and select a model first.")); return; }
    $("session-run-button").disabled = true;
    setPill("execution-state", "RUNNING", "warn");
    try {
      const target = await call("/api/v1/session/targets", { method: "POST", body: JSON.stringify({ credential_ref: credentialRef, model_identifier: selectedModel }) });
      const requestId = (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`);
      const request = { evaluation_id: target.evaluation_id, system_id: target.system_id, credential_ref: target.credential_ref, test_id: target.test_id, request_id: requestId };
      const record = await call("/api/v1/executions", { method: "POST", body: JSON.stringify(request) });
      render(record);
      catalog = await call("/api/v1/catalog");
      populate();
    } catch (error) {
      if (error.status === 401 || error.state === "AUTHENTICATION_REQUIRED") {
        requirePairing();
        setPill("execution-state", "ERROR", "bad");
        safeError(new Error("Gateway session expired. Pair again with the current temporary code."));
      } else {
        setPill("execution-state", "ERROR", "bad");
        safeError(error);
      }
    }
    finally { $("session-run-button").disabled = !(credentialRef && selectedModel); }
  }
  async function revokeCredential() {
    $("error").textContent = "";
    if (!credentialRef) return;
    try {
      await call("/api/v1/credentials/session/revoke", { method: "POST", body: JSON.stringify({ credential_ref: credentialRef }) });
    } catch (error) {
      safeError(error);
    }
    credentialRef = null;
    resetDiscoveryView();
    resetExecutionAttribution();
    setText("credential-session-detail", "Credential session closed. The gateway no longer holds the credential value.");
    $("discover-button").disabled = true;
    $("credential-revoke-button").disabled = true;
    $("session-run-button").disabled = true;
    m3elrUpdateRunButton();
  }
  function render(record) {
    current = record;
    const result = record.result || {};
    setText("execution-id", record.execution_id);
    setText("execution-provider", record.provider);
    setText("execution-model", record.model);
    setText("execution-adapter", record.adapter);
    setText("execution-endpoint", record.endpoint);
    setText("execution-transport", result.transport_kind || (record.transport_kind || "—"));
    setText("execution-status-code", result.http_status != null ? String(result.http_status) : (record.http_status != null ? String(record.http_status) : "—"));
    setText("execution-latency", result.latency_ms != null ? `${result.latency_ms} ms` : "—");
    setText("execution-error-classification", record.error_classification || "—");
    setText("external-status", record.execution_status);
    setText("response-status", record.response_status);
    setText("evidence-status", record.evidence_status);
    setText("evidence-id", record.evidence_id || "—");
    setText("audit-id", record.audit_id || "—");
    setText("audit-status", record.audit_status);
    setText("persistence-status", record.persistence_status);
    setText("persistence-location", record.persistence_location || "—");
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
        safeError(new Error("Gateway session expired. Pair again with the current temporary code."));
      } else {
        setPill("execution-state", "ERROR", "bad");
        safeError(error);
      }
    }
    finally { $("run-button").disabled = !session; }
  }
  // ------------------------------------------------------------------
  // M3-ELR scientific campaign (frozen registration package)
  // ------------------------------------------------------------------
  let m3elrAvailable = false;
  let m3elrStatus = null;
  let m3elrPollTimer = null;

  function m3elrSetPill(text, tone = "neutral") { setPill("m3elr-state", text, tone); }

  function m3elrRenderFacts(payload) {
    const registration = payload.registration || {};
    const condition = registration.condition || {};
    const gate = payload.gate || {};
    setText("m3elr-package", registration.package_id || "—");
    setText("m3elr-hash", (registration.package_hash || "—").slice(0, 24) + "…");
    setText("m3elr-model", registration.target_model_identifier || "—");
    setText("m3elr-condition", `${condition.model_state || "—"} · ${condition.level || "—"} · temp ${condition.temperature} · max_tokens ${condition.max_tokens} · timeout ${condition.transport_timeout_seconds}s`);
    setText("m3elr-cases", `${registration.case_count} registered`);
    const ordered = registration.ordered_test_ids || [];
    setText("m3elr-order", ordered.length ? `F-01b (${ordered[0]} … ${ordered[ordered.length - 1]})` : "—");
    setText("m3elr-evidence-root", payload.evidence_root || "—");
    setText("m3elr-gate", `${gate.pass} PASS / ${gate.pending} PENDING / ${gate.fail} FAIL`);
    setText("m3elr-attempts", `${registration.attempts_per_test} per test · no retries`);
  }

  function m3elrUpdateRunButton() {
    const campaign = m3elrStatus && m3elrStatus.campaign;
    $("m3elr-run-button").disabled = !(m3elrAvailable && credentialRef && (!campaign || campaign.status === "FAILED" && false));
    // one campaign per launcher process: the button stays disabled once a
    // campaign exists (any status) until the launcher is restarted.
    if (m3elrAvailable && credentialRef && !campaign) $("m3elr-run-button").disabled = false;
  }

  function m3elrRenderLedger(campaign) {
    if (!campaign) return;
    $("m3elr-progress").hidden = false;
    const body = $("m3elr-ledger-body");
    const rows = new Map();
    for (const row of body.children) rows.set(row.dataset.entryKey, row);
    for (const entry of campaign.entries || []) {
      const key = String(entry.position);
      let row = rows.get(key);
      if (!row) {
        row = document.createElement("tr");
        row.dataset.entryKey = key;
        row.innerHTML = '<td class="num"></td><td></td><td></td><td></td><td></td><td></td>';
        body.append(row);
        rows.set(key, row);
      }
      const cells = row.children;
      cells[0].textContent = String(entry.position).padStart(2, "0");
      cells[1].textContent = entry.test_id;
      cells[2].textContent = entry.execution_status;
      cells[2].className = entry.execution_status === "VALID" ? "good" : "bad";
      cells[3].textContent = entry.provider_status || "—";
      cells[4].textContent = entry.answer_state || "—";
      cells[5].textContent = entry.task_outcome || "—";
    }
    setPill("m3elr-progress-count", `${campaign.position}/${campaign.total}`, campaign.status === "COMPLETED" ? "good" : "warn");
    $("m3elr-current").textContent = campaign.current_test_id
      ? `Executing ${campaign.current_test_id} …`
      : (campaign.status === "RUNNING" ? "Preparing next test…" : "Idle.");
    if (campaign.status === "COMPLETED" && campaign.summary) {
      $("m3elr-summary").hidden = false;
      $("m3elr-summary").textContent = JSON.stringify(campaign.summary, null, 2);
      $("m3elr-ledger-path").hidden = false;
      $("m3elr-ledger-path").textContent = `Campaign ledger: ${campaign.ledger_path} — per-execution evidence and audit: ${(m3elrStatus && m3elrStatus.evidence_root) || ""}/executions/ (outside the repository).`;
    }
    if (campaign.status === "FAILED" && campaign.error) {
      $("m3elr-summary").hidden = false;
      $("m3elr-summary").textContent = `CAMPAIGN FAILED — ${campaign.error}`;
    }
    const tone = campaign.status === "COMPLETED" ? "good" : campaign.status === "FAILED" ? "bad" : "warn";
    m3elrSetPill(campaign.status, tone);
  }

  async function m3elrPoll() {
    try {
      m3elrStatus = await call("/api/v1/m3elr/campaign/status", { method: "POST", body: JSON.stringify({}) });
      m3elrRenderLedger(m3elrStatus.campaign);
      m3elrUpdateRunButton();
      const status = m3elrStatus.campaign && m3elrStatus.campaign.status;
      if (status === "COMPLETED" || status === "FAILED") { m3elrStopPolling(); return; }
    } catch (error) {
      if (error.status === 401 || error.state === "AUTHENTICATION_REQUIRED") { m3elrStopPolling(); requirePairing(); return; }
    }
    m3elrPollTimer = setTimeout(m3elrPoll, 1500);
  }

  function m3elrStopPolling() {
    if (m3elrPollTimer) { clearTimeout(m3elrPollTimer); m3elrPollTimer = null; }
  }

  async function m3elrProbe() {
    try {
      m3elrStatus = await call("/api/v1/m3elr/campaign/status", { method: "POST", body: JSON.stringify({}) });
      if (!m3elrStatus || m3elrStatus.m3elr_console !== true) return;
      m3elrAvailable = true;
      $("m3elr-card").hidden = false;
      m3elrRenderFacts(m3elrStatus);
      m3elrRenderLedger(m3elrStatus.campaign);
      m3elrUpdateRunButton();
      if (m3elrStatus.campaign && m3elrStatus.campaign.status === "RUNNING") m3elrPoll();
    } catch (_) {
      /* the M3-ELR campaign surface is not served by this gateway */
    }
  }

  async function m3elrRun() {
    $("error").textContent = "";
    if (!m3elrAvailable) return;
    if (!credentialRef) { safeError(new Error("Open a credential session first, then run the campaign.")); return; }
    $("m3elr-run-button").disabled = true;
    m3elrSetPill("STARTING", "warn");
    try {
      const payload = await call("/api/v1/m3elr/campaign", { method: "POST", body: JSON.stringify({ credential_ref: credentialRef }) });
      m3elrStatus = { ...(m3elrStatus || {}), campaign: payload.campaign };
      m3elrRenderLedger(payload.campaign);
      m3elrStopPolling();
      m3elrPoll();
    } catch (error) {
      if (error.status === 401 || error.state === "AUTHENTICATION_REQUIRED") { requirePairing(); }
      m3elrSetPill("ERROR", "bad");
      safeError(error);
      m3elrUpdateRunButton();
    }
  }

  $("m3elr-run-button").addEventListener("click", m3elrRun);

  // ------------------------------------------------------------------
  // M3-ELR scientific campaign (frozen registration package)
  // ------------------------------------------------------------------
  let m3elrAvailable = false;
  let m3elrStatus = null;
  let m3elrPollTimer = null;

  function m3elrRenderFacts(payload) {
    const registration = payload.registration || {};
    const condition = registration.condition || {};
    const gate = payload.gate || {};
    setText("m3elr-package", registration.package_id || "—");
    setText("m3elr-hash", (registration.package_hash || "—").slice(0, 24) + "…");
    setText("m3elr-model", registration.target_model_identifier || "—");
    setText("m3elr-condition", `${condition.model_state || "—"} · ${condition.level || "—"} · temp ${condition.temperature} · max_tokens ${condition.max_tokens} · timeout ${condition.transport_timeout_seconds}s`);
    setText("m3elr-cases", `${registration.case_count} registered`);
    const ordered = registration.ordered_test_ids || [];
    setText("m3elr-order", ordered.length ? `F-01b (${ordered[0]} … ${ordered[ordered.length - 1]})` : "—");
    setText("m3elr-evidence-root", payload.evidence_root || "—");
    setText("m3elr-gate", `${gate.pass} PASS / ${gate.pending} PENDING / ${gate.fail} FAIL`);
    setText("m3elr-attempts", `${registration.attempts_per_test} per test · no retries`);
  }

  function m3elrUpdateRunButton() {
    const campaign = m3elrStatus && m3elrStatus.campaign;
    // one campaign per launcher process: once a campaign exists (any
    // status) the button stays disabled until the launcher is restarted.
    $("m3elr-run-button").disabled = !(m3elrAvailable && credentialRef && !campaign);
  }

  function m3elrRenderLedger(campaign) {
    if (!campaign) return;
    $("m3elr-progress").hidden = false;
    const body = $("m3elr-ledger-body");
    const rows = new Map();
    for (const row of body.children) rows.set(row.dataset.entryKey, row);
    for (const entry of campaign.entries || []) {
      const key = String(entry.position);
      let row = rows.get(key);
      if (!row) {
        row = document.createElement("tr");
        row.dataset.entryKey = key;
        for (let i = 0; i < 6; i += 1) row.append(document.createElement("td"));
        body.append(row);
        rows.set(key, row);
      }
      const cells = row.children;
      cells[0].textContent = String(entry.position).padStart(2, "0");
      cells[0].className = "num";
      cells[1].textContent = entry.test_id;
      cells[2].textContent = entry.execution_status;
      cells[2].className = entry.execution_status === "VALID" ? "good" : "bad";
      cells[3].textContent = entry.provider_status || "—";
      cells[4].textContent = entry.answer_state || "—";
      cells[5].textContent = entry.task_outcome || "—";
    }
    setPill("m3elr-progress-count", `${campaign.position}/${campaign.total}`, campaign.status === "COMPLETED" ? "good" : "warn");
    $("m3elr-current").textContent = campaign.current_test_id
      ? `Executing ${campaign.current_test_id} …`
      : (campaign.status === "RUNNING" ? "Preparing next test…" : "Idle.");
    if (campaign.status === "COMPLETED" && campaign.summary) {
      $("m3elr-summary").hidden = false;
      $("m3elr-summary").textContent = JSON.stringify(campaign.summary, null, 2);
      $("m3elr-ledger-path").hidden = false;
      $("m3elr-ledger-path").textContent = `Campaign ledger: ${campaign.ledger_path} — per-execution evidence and audit: ${(m3elrStatus && m3elrStatus.evidence_root) || ""}/executions/ (outside the repository).`;
    }
    if (campaign.status === "FAILED" && campaign.error) {
      $("m3elr-summary").hidden = false;
      $("m3elr-summary").textContent = `CAMPAIGN FAILED — ${campaign.error}`;
    }
    const tone = campaign.status === "COMPLETED" ? "good" : campaign.status === "FAILED" ? "bad" : "warn";
    setPill("m3elr-state", campaign.status, tone);
  }

  function m3elrStopPolling() {
    if (m3elrPollTimer) { clearTimeout(m3elrPollTimer); m3elrPollTimer = null; }
  }

  async function m3elrPoll() {
    try {
      m3elrStatus = await call("/api/v1/m3elr/campaign/status", { method: "POST", body: JSON.stringify({}) });
      m3elrRenderLedger(m3elrStatus.campaign);
      m3elrUpdateRunButton();
      const status = m3elrStatus.campaign && m3elrStatus.campaign.status;
      if (status === "COMPLETED" || status === "FAILED") { m3elrStopPolling(); return; }
    } catch (error) {
      if (error.status === 401 || error.state === "AUTHENTICATION_REQUIRED") { m3elrStopPolling(); requirePairing(); return; }
    }
    m3elrPollTimer = setTimeout(m3elrPoll, 1500);
  }

  async function m3elrProbe() {
    try {
      m3elrStatus = await call("/api/v1/m3elr/campaign/status", { method: "POST", body: JSON.stringify({}) });
      if (!m3elrStatus || m3elrStatus.m3elr_console !== true) return;
      m3elrAvailable = true;
      $("m3elr-card").hidden = false;
      m3elrRenderFacts(m3elrStatus);
      m3elrRenderLedger(m3elrStatus.campaign);
      m3elrUpdateRunButton();
      if (m3elrStatus.campaign && m3elrStatus.campaign.status === "RUNNING") { m3elrStopPolling(); m3elrPoll(); }
    } catch (_) {
      /* the M3-ELR campaign surface is not served by this gateway */
    }
  }

  async function m3elrRun() {
    $("error").textContent = "";
    if (!m3elrAvailable) return;
    if (!credentialRef) { safeError(new Error("Open a credential session first, then run the campaign.")); return; }
    $("m3elr-run-button").disabled = true;
    setPill("m3elr-state", "STARTING", "warn");
    try {
      const payload = await call("/api/v1/m3elr/campaign", { method: "POST", body: JSON.stringify({ credential_ref: credentialRef }) });
      m3elrStatus = { ...(m3elrStatus || {}), campaign: payload.campaign };
      m3elrRenderLedger(payload.campaign);
      m3elrStopPolling();
      m3elrPoll();
    } catch (error) {
      if (error.status === 401 || error.state === "AUTHENTICATION_REQUIRED") requirePairing();
      setPill("m3elr-state", "ERROR", "bad");
      safeError(error);
      m3elrUpdateRunButton();
    }
  }

  $("m3elr-run-button").addEventListener("click", m3elrRun);

  $("pair-button").addEventListener("click", pair);
  $("run-button").addEventListener("click", run);
  $("evaluation-select").addEventListener("change", updateSelection);
  $("credential-open-button").addEventListener("click", openCredentialSession);
  $("credential-revoke-button").addEventListener("click", revokeCredential);
  $("discover-button").addEventListener("click", discover);
  $("session-run-button").addEventListener("click", runSessionEvaluation);
  $("owner-credential-input").addEventListener("keydown", (event) => { if (event.key === "Enter") openCredentialSession(); });
  status();
})();
