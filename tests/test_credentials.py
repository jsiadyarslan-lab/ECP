import pytest
from datetime import datetime, timedelta, timezone
from ecp.credentials import (
    CredentialGateway,
    CredentialIdentity,
    CredentialExpired,
    CredentialNotFound,
    CredentialRevoked,
    CredentialScopeError,
    CredentialStateError,
    redact_secrets,
    safe_exception_message,
    SecretRedactionFilter,
)


def test_credential_identity_metadata_is_safe():
    identity = CredentialIdentity(
        credential_id="test-id",
        provider="test-provider",
        purpose="testing",
        scope=frozenset(["read"]),
        expires_at="2026-12-31T23:59:59Z",
    )
    meta = identity.metadata()
    assert meta["credential_id"] == "test-id"
    assert meta["provider"] == "test-provider"
    assert meta["scope"] == ["read"]
    assert "secret" not in meta
    assert "value" not in meta


def test_gateway_retrieval_lifecycle():
    identity = CredentialIdentity(
        credential_id="c1",
        provider="p1",
        purpose="t1",
        scope=frozenset(["execute"]),
    )
    gateway, store = CredentialGateway.for_testing({"c1": identity})
    with pytest.raises(CredentialNotFound, match="not provisioned"):
        gateway.retrieve("c1", "execute")

    gateway.provision_for_testing("c1", "secret-value-123")
    lease = gateway.retrieve("c1", "execute")
    assert lease.value == "secret-value-123"
    assert lease.metadata["credential_id"] == "c1"
    assert "secret-value-123" not in repr(lease)
    assert "[REDACTED]" in repr(lease)
    assert "secret-value-123" not in str(lease)

    with pytest.raises(CredentialScopeError):
        gateway.retrieve("c1", "admin")


def test_secret_store_is_not_a_public_gateway_surface():
    identity = CredentialIdentity(
        credential_id="boundary",
        provider="p1",
        purpose="t1",
        scope=frozenset(["read"]),
    )
    gateway, store = CredentialGateway.for_testing({"boundary": identity})
    gateway.provision_for_testing("boundary", "synthetic-only")
    assert not hasattr(gateway, "secret_store")
    assert not hasattr(gateway, "get_secret")
    assert "synthetic-only" not in repr(gateway)


def test_expiry_enforcement():
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    identity = CredentialIdentity(
        credential_id="expired-id",
        provider="p1",
        purpose="t1",
        scope=frozenset(["read"]),
        expires_at=past,
    )
    gateway, store = CredentialGateway.for_testing({"expired-id": identity})
    store._write("expired-id", "1", "secret")
    with pytest.raises(CredentialExpired):
        gateway.retrieve("expired-id", "read")


def test_revocation():
    identity = CredentialIdentity(
        credential_id="revokable",
        provider="p1",
        purpose="t1",
        scope=frozenset(["read"]),
    )
    gateway, store = CredentialGateway.for_testing({"revokable": identity})
    gateway.provision_for_testing("revokable", "secret")
    gateway.revoke("revokable")
    with pytest.raises(CredentialRevoked):
        gateway.retrieve("revokable", "read")
    assert store._read("revokable", "1") is None


def test_rotation():
    i1 = CredentialIdentity(
        credential_id="r1",
        provider="p1",
        purpose="t1",
        scope=frozenset(["read"]),
        version="1",
    )
    gateway, store = CredentialGateway.for_testing({"r1": i1})
    gateway.provision_for_testing("r1", "v1-secret")
    i2 = CredentialIdentity(
        credential_id="r1",
        provider="p1",
        purpose="t1",
        scope=frozenset(["read"]),
        version="2",
    )
    gateway = gateway.rotate_for_testing(i2, "v2-secret")
    lease = gateway.retrieve("r1", "read")
    assert lease.value == "v2-secret"
    assert lease.metadata["version"] == "2"


def test_redaction_patterns():
    assert redact_secrets("Authorization: Bearer sk-123") == "Authorization: Bearer [REDACTED]"
    assert redact_secrets("api-key: xyz") == "api-key: [REDACTED]"
    assert redact_secrets("API_KEY=abc") == "API_KEY=[REDACTED]"
    assert redact_secrets("Bearer 12345") == "Bearer [REDACTED]"
    err = ValueError("failed with API_KEY=secret")
    assert "secret" not in safe_exception_message(err)
    assert "[REDACTED]" in safe_exception_message(err)


def test_logging_filter():
    redactor = SecretRedactionFilter(["my-real-secret"])
    assert redactor.redact("sending my-real-secret to server") == "sending [REDACTED] to server"
    assert redactor.redact("Authorization: Bearer sk-123") == "Authorization: Bearer [REDACTED]"


def test_environment_source(monkeypatch):
    monkeypatch.setenv("ECP_TEST_KEY", "env-secret")
    identity = CredentialIdentity(
        credential_id="env-id",
        provider="p1",
        purpose="t1",
        scope=frozenset(["read"]),
    )
    gateway = CredentialGateway.from_environment(identity, "ECP_TEST_KEY")
    lease = gateway.retrieve("env-id", "read")
    assert lease.value == "env-secret"
    with pytest.raises(CredentialStateError):
        gateway.provision_for_testing("env-id", "fail")


def test_serialization_safety():
    identity = CredentialIdentity(
        credential_id="s1",
        provider="p1",
        purpose="t1",
        scope=frozenset(["read"]),
    )
    gateway, store = CredentialGateway.for_testing({"s1": identity})
    gateway.provision_for_testing("s1", "secret")
    lease = gateway.retrieve("s1", "read")
    import json
    try:
        json.dumps(lease.__dict__)
    except (AttributeError, TypeError):
        pass
    assert "secret" not in str(lease.metadata)


def test_provider_neutral_adapter_contract():
    from ecp.credentials import ExternalSystemAdapter

    class SyntheticAdapter:
        provider = "synthetic-provider"

        def execute(self, lease, request):
            assert request == {"kind": "probe"}
            return {"provider": self.provider, "credential_id": lease.metadata["credential_id"]}

    identity = CredentialIdentity(
        credential_id="adapter-id",
        provider="synthetic-provider",
        purpose="adapter-test",
        scope=frozenset(["invoke"]),
    )
    gateway, _ = CredentialGateway.for_testing({"adapter-id": identity})
    gateway.provision_for_testing("adapter-id", "synthetic-adapter-secret")
    lease = gateway.retrieve("adapter-id", "invoke")
    adapter = SyntheticAdapter()
    assert isinstance(adapter, ExternalSystemAdapter)
    assert adapter.execute(lease, {"kind": "probe"}) == {
        "provider": "synthetic-provider",
        "credential_id": "adapter-id",
    }
