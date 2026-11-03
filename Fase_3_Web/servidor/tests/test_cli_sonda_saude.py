"""W12-04 — `sonda-saude`: 3 falhas seguidas viram alerta; uma falha isolada, não.

Alarme que grita em deploy/restart vira ruído e o operador aprende a ignorar. O contador de
falhas fica em `logs/.saude_falhas`; o alerta em `logs/alertas.log` (uma linha JSON).
"""

from __future__ import annotations

import http.server
import json
import threading

from mapasfacil_servidor import __main__ as cli


def _ambiente(monkeypatch, tmp_path):
    raiz = tmp_path / "raiz"
    raiz.mkdir()
    segredos = raiz / "segredos" / "servidor.env"
    segredos.parent.mkdir()
    segredos.write_text(
        "MAPASFACIL_PROVEDOR_CHAVE=chave-de-teste\n"
        "MAPASFACIL_SEMA_AUTHKEY=sema-de-teste\n"
        "MAPASFACIL_PLANET_API_KEY=planet-de-teste\n",
        encoding="utf-8",
    )
    segredos.chmod(0o600)
    monkeypatch.setenv("MF_RAIZ", str(raiz))
    monkeypatch.setenv("MF_SEGREDOS", str(segredos))
    monkeypatch.setenv("MF_HOST", "127.0.0.1")
    return raiz


def _porta_livre() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def test_uma_falha_nao_alerta(monkeypatch, tmp_path):
    raiz = _ambiente(monkeypatch, tmp_path)
    monkeypatch.setenv("MF_PORTA", str(_porta_livre()))
    assert cli.main(["sonda-saude"]) == 0
    alertas = raiz / "logs" / "alertas.log"
    assert not alertas.exists(), "uma falha isolada não pode virar alerta"
    assert (raiz / "logs" / ".saude_falhas").read_text(encoding="utf-8").strip() == "1"


def test_tres_falhas_seguidas_alertam(monkeypatch, tmp_path):
    raiz = _ambiente(monkeypatch, tmp_path)
    monkeypatch.setenv("MF_PORTA", str(_porta_livre()))
    assert cli.main(["sonda-saude"]) == 0
    assert cli.main(["sonda-saude"]) == 0
    assert cli.main(["sonda-saude"]) == 1, "na terceira falha o comando tem de falhar"
    alertas = raiz / "logs" / "alertas.log"
    assert alertas.is_file()
    linhas = [json.loads(l) for l in alertas.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(linhas) == 1
    assert linhas[0]["codigo"] == "SV-SAUDE"
    assert linhas[0]["nivel"] == "erro"
    assert "3 falhas" in linhas[0]["mensagem"]


def test_sucesso_zera_o_contador(monkeypatch, tmp_path):
    raiz = _ambiente(monkeypatch, tmp_path)
    monkeypatch.setenv("MF_PORTA", str(_porta_livre()))
    assert cli.main(["sonda-saude"]) == 0
    assert (raiz / "logs" / ".saude_falhas").read_text(encoding="utf-8").strip() == "1"

    # Servidor de mentira respondendo o /saude.
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - nome do http.server
            corpo = json.dumps({"estado": "ok", "versao": "teste"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, *args):  # silencia o log do teste
            return

    servidor = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=servidor.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("MF_PORTA", str(servidor.server_address[1]))
        assert cli.main(["sonda-saude"]) == 0
    finally:
        servidor.shutdown()
        servidor.server_close()

    assert (raiz / "logs" / ".saude_falhas").read_text(encoding="utf-8").strip() == "0"
