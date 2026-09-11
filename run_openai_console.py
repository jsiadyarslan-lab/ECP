import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ecp.console import GatewayConfig
from ecp.openai_conformance import build_openai_conformance_gateway


REPO_ROOT = Path(__file__ ).resolve().parent
CONSOLE_PORT = 8766
GATEWAY_PORT = 8765
ARTIFACT_ROOT = REPO_ROOT / "local-browser-artifacts"

config = GatewayConfig(
    allowed_origins=frozenset({
        f"http://127.0.0.1:{CONSOLE_PORT}",
        f"http://localhost:{CONSOLE_PORT}",
    } ),
    port=GATEWAY_PORT,
    artifact_root=ARTIFACT_ROOT,
)

gateway = build_openai_conformance_gateway(
    config,
    model=os.environ.get("ECP_CONFORMANCE_MODEL", "gpt-5-mini"),
)

gateway_server = gateway.make_server()
threading.Thread(
    target=gateway_server.serve_forever,
    daemon=True,
).start()

print(f"ECP gateway listening on 127.0.0.1:{GATEWAY_PORT}")
print(f"PAIRING CODE: {gateway.pairing_code}")
print(f"Console: http://127.0.0.1:{CONSOLE_PORT}/" )
print("Press Ctrl+C to stop.")

os.chdir(REPO_ROOT / "console")
console_server = ThreadingHTTPServer(
    ("127.0.0.1", CONSOLE_PORT),
    SimpleHTTPRequestHandler,
)

try:
    console_server.serve_forever()
except KeyboardInterrupt:
    pass
finally:
    console_server.server_close()
    gateway_server.shutdown()
    gateway_server.server_close()
