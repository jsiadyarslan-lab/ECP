from datetime import datetime, timezone

import pytest

from ecp.credential_binding import (
    AuthorizationGrant,
    AuthorizationRequired,
    BindingScopeError,
    CredentialBinding,
    CredentialDefinition,
    CredentialRequirement,
    CredentialContractError,
    ScopedReleaseRequest,
    validate_binding,
)
from ecp.credentials import CredentialGateway, CredentialIdentity, CredentialScopeError


def contracts(scope=frozenset({"invoke"}), target="ECP-TARGET-A"):
    definition = CredentialDefinition("ECP-DEFINITION-TEST", "provider-a", "model-api", "token", "invoke")
    requirement = CredentialRequirement("ECP-REQUIREMENT-TEST", target, definition.definition_id, "invoke", scope)
    binding = CredentialBinding("ECP-BINDING-TEST", requirement.requirement_id, target, "provider-a", "model-api", "invoke", "cred-a", scope)
    return definition, requirement, binding


def grant(binding, target="ECP-TARGET-A", scope=frozenset({"invoke"}), status="GRANTED"):
    return AuthorizationGrant("ECP-AUTH-TEST", binding.binding_id, target, "invoke", scope, "2099-01-01T00:00:00Z", status)


def request(binding, target="ECP-TARGET-A", scope=frozenset({"invoke"})):
    return ScopedReleaseRequest("ECP-REQUEST-TEST", binding.binding_id, target, "cred-a", "invoke", scope, 60, "2026-09-11T00:00:00Z")


def test_definition_requirement_binding_are_metadata_only():
    definition, requirement, binding = contracts()
    for value in (definition.metadata(), requirement.metadata(), binding.metadata()):
        rendered = repr(value).lower()
        assert "secret" not in rendered
    validate_binding(definition, requirement, binding)


def test_binding_is_target_scoped_and_does_not_transfer():
    definition, requirement, binding = contracts(target="ECP-TARGET-A")
    other_requirement = CredentialRequirement("ECP-REQUIREMENT-B", "ECP-TARGET-B", definition.definition_id, "invoke", frozenset({"invoke"}))
    with pytest.raises(BindingScopeError):
        validate_binding(definition, other_requirement, binding)


def test_invalid_opaque_reference_and_lease_bounds_fail_closed():
    with pytest.raises(CredentialContractError):
        CredentialBinding("binding", "ECP-REQ", "ECP-TARGET-A", "provider", "iface", "invoke", "api-key=secret", frozenset({"invoke"}))
    definition, requirement, binding = contracts()
    with pytest.raises(CredentialContractError):
        ScopedReleaseRequest("ECP-REQUEST-BAD", binding.binding_id, binding.target_id, "cred-a", "invoke", frozenset({"invoke"}), 3601, "2026-09-11T00:00:00Z")


def test_gateway_rejects_legacy_unscoped_retrieve():
    identity = CredentialIdentity("cred-a", "provider-a", "invoke", frozenset({"invoke"}))
    gateway, _ = CredentialGateway.for_testing({"cred-a": identity})
    with pytest.raises(AuthorizationRequired, match="unscoped"):
        gateway.retrieve("cred-a", "invoke")


def test_gateway_release_requires_exact_binding_and_authorization():
    definition, requirement, binding = contracts()
    validate_binding(definition, requirement, binding)
    identity = CredentialIdentity("cred-a", "provider-a", "invoke", frozenset({"invoke"}))
    gateway, _ = CredentialGateway.for_testing({"cred-a": identity})
    gateway.provision_for_testing("cred-a", "synthetic-phase-c-secret")
    lease = gateway.release(request(binding), binding, grant(binding))
    assert lease.value == "synthetic-phase-c-secret"
    assert "synthetic-phase-c-secret" not in repr(lease)
    assert "synthetic-phase-c-secret" not in str(lease)
    with pytest.raises(AuthorizationRequired):
        gateway.release(request(binding), binding, grant(binding, status="REVOKED"))
    other = CredentialBinding("ECP-BINDING-OTHER", binding.requirement_id, binding.target_id, binding.provider_id, binding.interface, binding.purpose, binding.credential_ref, binding.scope)
    with pytest.raises(BindingScopeError):
        gateway.release(request(binding), other, grant(binding))


def test_gateway_release_does_not_probe_secret_existence_before_authorization():
    identity = CredentialIdentity("cred-a", "provider-a", "invoke", frozenset({"invoke"}))
    gateway, _ = CredentialGateway.for_testing({"cred-a": identity})
    definition, requirement, binding = contracts()
    with pytest.raises(AuthorizationRequired):
        gateway.release(request(binding), binding, grant(binding, status="REVOKED"))


def test_gateway_scope_is_not_global():
    identity = CredentialIdentity("cred-a", "provider-a", "invoke", frozenset({"invoke"}))
    gateway, _ = CredentialGateway.for_testing({"cred-a": identity})
    gateway.provision_for_testing("cred-a", "synthetic-phase-c-secret")
    definition, requirement, binding = contracts(scope=frozenset({"invoke"}))
    bad_request = request(binding, scope=frozenset({"admin"}))
    bad_grant = grant(binding, scope=frozenset({"admin"}))
    with pytest.raises(BindingScopeError):
        gateway.release(bad_request, binding, bad_grant)
