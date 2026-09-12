"""Secure local execution console boundary for ECP."""
from __future__ import annotations
import argparse, json, os, secrets, threading, uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlparse
from .canonical import canonical_bytes
from .credentials import CredentialError, CredentialGateway, CredentialIdentity, CredentialNotFound, SecretLease, SecretRedactionFilter, safe_exception_message
from .credential_binding import AuthorizationGrant, CredentialBinding, ScopedReleaseRequest
from .execution_contract import (
    ClientExecutionIntent,
    ContractViolation,
    ExecutionContractResolver,
    ExecutionNotAuthorizedError,
    UniversalExecutionResult,
    UnknownCredentialError,
    UnknownEvaluationError,
    UnknownTestError,
)
from .hashing import hash_document
from .runtime_adapters import RuntimeAdapterError, RuntimeAdapterRegistry, RuntimeAdapterTransportError, RuntimeAdapterUnavailable

DEFAULT_PORT=8765
DEFAULT_CONSOLE_ORIGINS=("https://jsiadyarslan-lab.github.io","http://127.0.0.1:8766","http://localhost:8766")
PAIRING_TTL_SECONDS=600
DEMO_GRANT_TTL_SECONDS=86400
POLL_INTERVAL_MS=1500
EXECUTION_TIMEOUT_SECONDS=120
_ALLOWED_REQUEST_KEYS={"evaluation_id","test_id","system_id","credential_ref","request_id"}

#: Session-console routes served by an attached session component (owner
#: order: UNIVERSAL VISUAL PROVIDER & MODEL EVALUATION CONSOLE v1). Each
#: route delegates to the component; the component owns no new authority —
#: credentials flow through the credential gateway, execution flows through
#: the single existing execution path above.
_SESSION_ROUTES={
    "/api/v1/credentials/session":"open_session",
    "/api/v1/credentials/session/revoke":"revoke_session",
    "/api/v1/discovery":"discover",
    "/api/v1/session/targets":"select_target",
}
_SESSION_BODY_SECRET_KEYS=frozenset({"credential_secret","api_key","secret","secret_value","token","password","authorization"})

class ConsoleError(Exception): pass
class AuthorizationError(ConsoleError): pass
class ExecutionAuthorizationError(ConsoleError): pass
class AdapterUnavailable(ConsoleError): pass
class AdapterFailure(ConsoleError):
    def __init__(self,category:str,message:str="provider adapter failed")->None: self.category=category; super().__init__(message)

@dataclass(frozen=True)
class AuthorizedTest: test_id:str; label:str; scope:str
@dataclass(frozen=True)
class AuthorizedEvaluation:
    evaluation_id:str; system_id:str; provider:str; adapter:str; credential:CredentialIdentity; tests:tuple[AuthorizedTest,...]; credential_binding:CredentialBinding|None=None; authorization_grant:AuthorizationGrant|None=None
    def safe_metadata(self)->dict[str,Any]:
        return {"evaluation_id":self.evaluation_id,"system_id":self.system_id,"provider":self.provider,"adapter":self.adapter,"credential":self.credential.metadata(),"tests":[{"test_id":t.test_id,"label":t.label,"scope":t.scope} for t in self.tests]}

class ProviderAdapter:
    provider="unknown"; adapter_id="unknown"
    def execute(self,lease:SecretLease,request:Mapping[str,str])->Mapping[str,Any]: raise NotImplementedError
class UnconfiguredAdapter(ProviderAdapter):
    provider="unconfigured"; adapter_id="unconfigured"
    def execute(self,lease:SecretLease,request:Mapping[str,str])->Mapping[str,Any]: del lease,request; raise AdapterUnavailable("no provider adapter is registered")

class _DemoCredentialGateway(CredentialGateway):
    """Expose the demo fixture's in-memory provisioning state in its catalog."""
    def __init__(self, store, identities, provisioned):
        super().__init__(store, identities)
        self._demo_provisioned = provisioned

    def metadata(self, credential_id):
        metadata = super().metadata(credential_id)
        if not self._demo_provisioned:
            metadata["status"] = "NOT_PROVISIONED"
        return metadata

class ExecutionStore:
    def __init__(self,root:Path|None=None)->None: self.root=root; self._records={}; self._idempotency={}; self._lock=threading.RLock()
    def get(self,execution_id):
        with self._lock:
            r=self._records.get(execution_id); return json.loads(json.dumps(r)) if r else None
    def by_request(self,request_id):
        with self._lock:
            eid=self._idempotency.get(request_id); return self.get(eid) if eid else None
    def create(self,request_id,safe_request):
        with self._lock:
            existing=self.by_request(request_id)
            if existing: return existing
            eid=f"ECP-EXEC-CONSOLE-{uuid.uuid4().hex}"; now=_utc_now()
            r={"execution_id":eid,"request_id":request_id,"system_id":safe_request["system_id"],"evaluation_id":safe_request["evaluation_id"],"test_id":safe_request["test_id"],"credential_ref":safe_request["credential_ref"],"status":"REQUESTED","execution_status":"NOT_STARTED","response_status":"NOT_RECEIVED","evidence_status":"NOT_GENERATED","audit_status":"NOT_GENERATED","persistence_status":"NOT_PERSISTED","created_at":now,"updated_at":now}
            self._records[eid]=r; self._idempotency[request_id]=eid; return json.loads(json.dumps(r))
    def update(self,eid,**fields):
        with self._lock: self._records[eid].update(fields,updated_at=_utc_now()); return json.loads(json.dumps(self._records[eid]))
    def persist(self,eid,evidence,audit):
        if self.root is None: return "PUSH_PENDING","not configured"
        target=self.root/"external-executions"/eid; target.mkdir(parents=True,exist_ok=True); (target/"evidence.json").write_bytes(canonical_bytes(dict(evidence))); (target/"audit.json").write_bytes(canonical_bytes(dict(audit))); return "PERSISTED_LOCALLY",str(target.relative_to(self.root))

@dataclass
class GatewayConfig:
    allowed_origins:frozenset[str]; port:int=DEFAULT_PORT; pairing_ttl_seconds:int=PAIRING_TTL_SECONDS; artifact_root:Path|None=None

class LocalGateway:
    def __init__(self,config,evaluations,credential_gateway,adapters=None,store=None,clock=None,cases=None,session_console=None):
        if not config.allowed_origins: raise ValueError("at least one explicit console origin is required")
        if not 1<=config.port<=65535: raise ValueError("port must be between 1 and 65535")
        self.config=config; self.evaluations=dict(evaluations); self.credential_gateway=credential_gateway; self.adapters=adapters if isinstance(adapters, RuntimeAdapterRegistry) else RuntimeAdapterRegistry(adapters or {}); self.store=store or ExecutionStore(config.artifact_root); self._pairing_code=secrets.token_urlsafe(24); self._clock=clock or __import__("time").time; self._pairing_expires=self._clock()+config.pairing_ttl_seconds; self._session_tokens=set(); self._session_lock=threading.RLock(); self._httpd=None; self._session_console=None
        self._contract=ExecutionContractResolver(self.evaluations,cases,self.adapters)
        if session_console is not None: self.enable_session_console(session_console)

    @property
    def contract_resolver(self): return self._contract
    @property
    def pairing_code(self): return self._pairing_code
    def enable_session_console(self,session_console):
        """Attach the session console component (credential sessions, unified
        provider/model discovery, model selection/onboarding delegation).

        The component is a thin composition layer: it holds no execution
        authority of its own — every execution still flows through
        :meth:`execute` above, and every credential release still flows
        through the attached credential gateway.
        """
        for method in ("open_session","revoke_session","discover","select_target","descriptors"):
            if not callable(getattr(session_console,method,None)): raise ValueError(f"session console component requires a callable {method}()")
        self._session_console=session_console
    def register_evaluation(self,evaluation):
        """Register one additional authorized evaluation (additive seam).

        Console sessions that onboard targets at runtime register the fully
        wired evaluation here so the single existing execution path serves
        it. Re-registering the same evaluation object is a no-op; a different
        object under an occupied identifier is a deterministic failure.
        """
        evaluation_id=getattr(evaluation,"evaluation_id",None)
        if not isinstance(evaluation_id,str) or not evaluation_id.strip(): raise ConsoleError("registered evaluations require an evaluation_id")
        existing=self.evaluations.get(evaluation_id)
        if existing is not None and existing is not evaluation: raise ConsoleError(f"evaluation {evaluation_id} is already registered with different wiring")
        self.evaluations[evaluation_id]=evaluation; self._contract.register(evaluation)
    def session_descriptors(self):
        """The discovery descriptor registry view (registry-driven UI data)."""
        if self._session_console is None: raise ConsoleError("session console is not enabled")
        return self._session_console.descriptors()
    def execute_session_route(self,path,body):
        """Dispatch one session-console route with submitted-secret redaction."""
        if self._session_console is None: raise ConsoleError("session console is not enabled")
        method=_SESSION_ROUTES.get(path)
        if method is None: raise ConsoleError("unknown session route")
        try: return getattr(self._session_console,method)(dict(body))
        except Exception as exc:
            message=safe_exception_message(exc); redactor=SecretRedactionFilter(_submitted_secret_values(body))
            raise ConsoleError(redactor.redact(message)) from None
    def pair(self,code):
        if not secrets.compare_digest(str(code),self._pairing_code) or self._clock()>=self._pairing_expires: raise AuthorizationError("pairing code is invalid or expired")
        token=secrets.token_urlsafe(32)
        with self._session_lock: self._session_tokens.add(token)
        return token
    def authenticate(self,token):
        if not token: raise AuthorizationError("authentication required")
        with self._session_lock:
            if token not in self._session_tokens: raise AuthorizationError("authentication required")
    def has_authenticated_sessions(self):
        with self._session_lock: return bool(self._session_tokens)
    def catalog(self):
        evaluations=[]
        for e in self.evaluations.values():
            metadata=e.safe_metadata()
            try: metadata["credential"]=self.credential_gateway.metadata(e.credential.credential_id)
            except CredentialNotFound: metadata["credential"]={**e.credential.metadata(),"status":"NOT_PROVISIONED"}
            evaluations.append(metadata)
        return {"evaluations":evaluations,"poll_interval_ms":POLL_INTERVAL_MS,"timeout_seconds":EXECUTION_TIMEOUT_SECONDS}
    def execute(self,request):
        intent=ClientExecutionIntent.from_client_payload(request)
        try: resolved=self._contract.resolve(intent)
        except UnknownEvaluationError as exc: raise ConsoleError(str(exc)) from exc
        except UnknownCredentialError as exc: raise ConsoleError(str(exc)) from exc
        except UnknownTestError as exc: raise ConsoleError(str(exc)) from exc
        except ExecutionNotAuthorizedError as exc: raise ExecutionAuthorizationError(str(exc)) from exc
        evaluation=self.evaluations[resolved.evaluation_id]
        safe_request=resolved.intent.identifiers(); record=self.store.create(safe_request["request_id"],safe_request)
        if record["status"]!="REQUESTED": return record
        eid=record["execution_id"]; self.store.update(eid,status="AUTHORIZED",execution_status="RUNNING"); lease=None
        try:
            rr=ScopedReleaseRequest(request_id=resolved.request_id,binding_id=resolved.binding_id,target_id=evaluation.credential_binding.target_id,credential_ref=resolved.credential_ref,purpose=resolved.test_scope,scope=frozenset({resolved.test_scope}),lease_seconds=60,requested_at=_utc_now())
            lease=self.credential_gateway.release(rr,evaluation.credential_binding,evaluation.authorization_grant); adapter=self.adapters.resolve(evaluation.adapter,evaluation.provider)
            raw=dict(adapter.execute(lease,resolved.transport_request())); unified=UniversalExecutionResult.from_provider_payload(raw,request_id=resolved.request_id); result=unified.to_record_dict()
            self.store.update(eid,status="COMPLETED",execution_status="SUCCESS",response_status="RECEIVED",result=_safe_result(result,(lease.value,)))
            try: self._finalize(eid,evaluation,resolved,unified,"SUCCESS",(lease.value,))
            except Exception as exc: self.store.update(eid,status="PARTIAL_SUCCESS",evidence_status="FAILED",audit_status="FAILED",persistence_status="FAILED",failure_stage="evidence_audit_or_persistence",error=_safe_exception_message(exc,lease))
        except ContractViolation as exc: self.store.update(eid,status="FAILED",execution_status="INVALID",response_status="NOT_RECEIVED",error_classification="CONTRACT_VIOLATION",error=_safe_exception_message(exc,lease))
        except CredentialError as exc: self.store.update(eid,status="FAILED",execution_status="INVALID",response_status="NOT_RECEIVED",error_classification="CREDENTIAL_ERROR",error=_safe_exception_message(exc,lease))
        except AdapterFailure as exc: self.store.update(eid,status="FAILED",execution_status=exc.category,response_status="NOT_RECEIVED",error_classification=exc.category,error=_safe_exception_message(exc,lease))
        except AdapterUnavailable as exc: self.store.update(eid,status="FAILED",execution_status="INCONCLUSIVE",response_status="NOT_RECEIVED",error_classification="ADAPTER_UNAVAILABLE",error=_safe_exception_message(exc,lease))
        except RuntimeAdapterUnavailable as exc: self.store.update(eid,status="FAILED",execution_status="INCONCLUSIVE",response_status="NOT_RECEIVED",error_classification="ADAPTER_UNAVAILABLE",error=_safe_exception_message(exc,lease))
        except RuntimeAdapterTransportError as exc: self.store.update(eid,status="FAILED",execution_status="INCONCLUSIVE",response_status="NOT_RECEIVED",error_classification=str(exc),error=_safe_exception_message(exc,lease))
        except RuntimeAdapterError as exc: self.store.update(eid,status="FAILED",execution_status="INCONCLUSIVE",response_status="NOT_RECEIVED",error_classification="ADAPTER_ERROR",error=_safe_exception_message(exc,lease))
        except Exception as exc: self.store.update(eid,status="FAILED",execution_status="ERROR",response_status="NOT_RECEIVED",error_classification="ADAPTER_ERROR",error=_safe_exception_message(exc,lease))
        return self.store.get(eid) or {}
    def _finalize(self,eid,evaluation,resolved,unified,outcome,secrets_to_redact=()):
        suffix=eid.rsplit("-",1)[-1]; evid=f"ECP-EVID-CONSOLE-{suffix}"; audit_id=f"ECP-AUDIT-CONSOLE-{suffix}"
        evidence={"ecp_object":"console-evidence","evidence_id":evid,"execution_id":eid,"evaluation_id":resolved.evaluation_id,"system_id":resolved.system_id,"test_id":resolved.test_id,"provider":evaluation.provider,"adapter":evaluation.adapter,"credential_ref":resolved.credential_ref,"outcome":outcome,"result":_safe_result(unified.to_record_dict(),secrets_to_redact),"created_at":_utc_now(),"model":resolved.model_identifier,"adapter_version":resolved.adapter_version,"protocol_version":resolved.protocol_version,"case_id":resolved.experiment.case_id,"prompt_hash":resolved.experiment.prompt_hash,"prompt_reference":resolved.prompt_reference,"experiment_identity":resolved.experiment.identity_document(),"experiment_identity_hash":resolved.experiment.identity_hash()}
        evidence["evidence_hash"]=hash_document(evidence); audit={"ecp_object":"console-audit","audit_id":audit_id,"execution_id":eid,"evidence_id":evid,"evidence_hash":evidence["evidence_hash"],"audit_status":"PENDING_HUMAN_REVIEW","created_at":_utc_now()}; persistence,location=self.store.persist(eid,evidence,audit); self.store.update(eid,status="SUCCESS" if persistence in {"PERSISTED_LOCALLY","PUSH_PENDING"} else "PARTIAL_SUCCESS",evidence_status="GENERATED",audit_status="GENERATED",persistence_status=persistence,persistence_location=location,evidence_id=evid,audit_id=audit_id)
    def make_server(self):
        gateway=self
        class Handler(BaseHTTPRequestHandler):
            server_version="ECP-Local-Gateway/1.0"
            def _origin(self): return self.headers.get("Origin")
            def _check_origin(self):
                if self._origin() not in gateway.config.allowed_origins: self._json(403,{"error":"origin denied","state":"SECURITY_BLOCKED"},include_cors=False); return False
                return True
            def _json(self,status,payload,*,include_cors=True):
                data=json.dumps(payload,ensure_ascii=False,separators=(",",":")).encode(); self.send_response(status); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(data)))
                if include_cors and self._origin() in gateway.config.allowed_origins: self.send_header("Access-Control-Allow-Origin",self._origin() or ""); self.send_header("Vary","Origin"); self.send_header("Access-Control-Allow-Headers","Content-Type, X-ECP-Session"); self.send_header("Access-Control-Allow-Methods","GET, POST, OPTIONS")
                self.end_headers(); self.wfile.write(data)
            def do_OPTIONS(self):
                if self._check_origin(): self._json(204,{})
            def do_GET(self):
                if not self._check_origin(): return
                path=urlparse(self.path).path
                if path=="/api/v1/status": self._json(200,{"gateway":"CONNECTED","authentication":"PAIRED" if gateway.has_authenticated_sessions() else "AUTHENTICATION_REQUIRED","binding":"127.0.0.1","port":gateway.config.port}); return
                try:
                    gateway.authenticate(self.headers.get("X-ECP-Session"))
                    if path=="/api/v1/catalog": self._json(200,gateway.catalog())
                    elif path=="/api/v1/discovery/descriptors":
                        try: self._json(200,{"descriptors":gateway.session_descriptors()})
                        except ConsoleError as exc: self._json(404,{"error":str(exc)})
                    elif path.startswith("/api/v1/executions/"):
                        execution=gateway.store.get(path.rsplit("/",1)[-1]); self._json(200 if execution else 404,execution or {"error":"execution not found"})
                    else: self._json(404,{"error":"not found"})
                except AuthorizationError as exc: self._json(401,{"error":str(exc),"state":"AUTHENTICATION_REQUIRED"})
            def do_POST(self):
                if not self._check_origin(): return
                path=urlparse(self.path).path
                try:
                    length=int(self.headers.get("Content-Length","0"));
                    if length>16384: raise ConsoleError("request too large")
                    body=json.loads(self.rfile.read(length) or b"{}")
                    if not isinstance(body,dict): raise ConsoleError("request must be a JSON object")
                    if path=="/api/v1/pair": self._json(200,{"session":gateway.pair(body.get("pairing_code",""))}); return
                    gateway.authenticate(self.headers.get("X-ECP-Session"))
                    if path=="/api/v1/executions": self._json(200,gateway.execute(body))
                    elif path in _SESSION_ROUTES: self._json(200,gateway.execute_session_route(path,body))
                    else: self._json(404,{"error":"not found"})
                except ExecutionAuthorizationError as exc: self._json(403,{"error":str(exc),"state":"EXECUTION_AUTHORIZATION_REQUIRED"})
                except AuthorizationError as exc: self._json(401,{"error":str(exc),"state":"AUTHENTICATION_REQUIRED"})
                except (ConsoleError,ValueError,json.JSONDecodeError) as exc: self._json(400,{"error":safe_exception_message(exc),"state":"INVALID"})
            def log_message(self,fmt,*args): print("ECP gateway: "+fmt%tuple(args))
        self._httpd=ThreadingHTTPServer(("127.0.0.1",self.config.port),Handler); return self._httpd
    def serve_forever(self,server=None): (server or self.make_server()).serve_forever()

def _safe_result(result,secrets_to_redact=()):
    safe={}; redactor=SecretRedactionFilter(secrets_to_redact)
    for key,value in result.items():
        if key.lower() in {"secret","secret_value","api_key","token","authorization","password"}: continue
        if isinstance(value,str): safe[key]=redactor.redact(value)
        elif isinstance(value,(int,float,bool)) or value is None: safe[key]=value
    return safe
def _submitted_secret_values(body):
    """String values of secret-bearing request keys, for redaction only."""
    values=[]
    if isinstance(body,Mapping):
        for key,value in body.items():
            if str(key).lower() in _SESSION_BODY_SECRET_KEYS and isinstance(value,str) and value: values.append(value)
    return tuple(values)
def _safe_exception_message(error,lease=None):
    message=safe_exception_message(error); return SecretRedactionFilter((lease.value,)).redact(message) if lease is not None else message
def _utc_now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def default_gateway_config():
    origins=frozenset(filter(None,os.environ.get("ECP_CONSOLE_ALLOWED_ORIGINS",",".join(DEFAULT_CONSOLE_ORIGINS)).split(","))); port=int(os.environ.get("ECP_GATEWAY_PORT",str(DEFAULT_PORT))); root=os.environ.get("ECP_ARTIFACT_ROOT"); return GatewayConfig(origins,port,PAIRING_TTL_SECONDS,Path(root) if root else None)
def build_demo_gateway(config=None,provision_demo_credential=True):
    identity=CredentialIdentity("credential-ref-example","example-provider","console integration",frozenset({"execute"}),status="PROVISIONED")
    _base_gateway,_store=CredentialGateway.for_testing({identity.credential_id:identity})
    gateway=_DemoCredentialGateway(_store,{identity.credential_id:identity},provision_demo_credential)
    if provision_demo_credential: gateway.provision_for_testing(identity.credential_id,secrets.token_urlsafe(32))
    binding=CredentialBinding("ECP-BINDING-CONSOLE-EXAMPLE","ECP-REQUIREMENT-CONSOLE-EXAMPLE","ECP-SYSTEM-CONSOLE-EXAMPLE","example-provider","environment-variable","execute","credential-ref-example",frozenset({"execute"}))
    grant=AuthorizationGrant("ECP-AUTH-CONSOLE-EXAMPLE","ECP-BINDING-CONSOLE-EXAMPLE","ECP-SYSTEM-CONSOLE-EXAMPLE","execute",frozenset({"execute"}),(datetime.now(timezone.utc)+timedelta(seconds=DEMO_GRANT_TTL_SECONDS)).replace(microsecond=0).isoformat().replace("+00:00","Z"))
    evaluation=AuthorizedEvaluation("ECP-EVAL-CONSOLE-EXAMPLE","ECP-SYSTEM-CONSOLE-EXAMPLE","example-provider","example-adapter",identity,(AuthorizedTest("connectivity-probe","Registered connectivity probe","execute"),),binding,grant)
    return LocalGateway(config or default_gateway_config(),{evaluation.evaluation_id:evaluation},gateway,{"example-adapter":UnconfiguredAdapter()})
def main(argv=None):
    parser=argparse.ArgumentParser(description="Run the loopback-only ECP local evaluation gateway"); parser.add_argument("--port",type=int,default=None); parser.add_argument("--artifact-root",default=None); args=parser.parse_args(argv); config=default_gateway_config();
    if args.port is not None: config.port=args.port
    if args.artifact_root is not None: config.artifact_root=Path(args.artifact_root)
    gateway=build_demo_gateway(config); server=gateway.make_server(); print(f"ECP Local Gateway listening on 127.0.0.1:{config.port}"); print(f"PAIRING CODE (expires in {config.pairing_ttl_seconds}s): {gateway.pairing_code}"); print("Allowed origins: "+", ".join(sorted(config.allowed_origins))); gateway.serve_forever(server); return 0
__all__=["AdapterFailure","AdapterUnavailable","AuthorizedEvaluation","AuthorizedTest","ExecutionAuthorizationError","ExecutionStore","GatewayConfig","LocalGateway","ProviderAdapter","build_demo_gateway","default_gateway_config"]
if __name__=="__main__": raise SystemExit(main())
