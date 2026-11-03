"""W4 — upload por partes, extração segura e importação."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mapasfacil_servidor.app import create_app
from mapasfacil_servidor.config import carregar
from mapasfacil_servidor.db import Banco
from mapasfacil_servidor.importacao import extrair, upload as upload_mod

API = "/api/v1"
SENHA = "uma-senha-longa-123"


# --- fixtures -------------------------------------------------------------


def zip_bytes(arquivos: dict[str, bytes], *, compressao: int = zipfile.ZIP_DEFLATED) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compressao) as zf:
        for nome, dados in arquivos.items():
            zf.writestr(nome, dados)
    return buffer.getvalue()


def zip_do_imovel() -> bytes:
    return zip_bytes(
        {
            "CAR/ATP.shp": b"shp-fake",
            "CAR/ATP.shx": b"shx-fake",
            "CAR/ATP.dbf": b"dbf-fake",
            "CAR/ATP.prj": b'PROJCS["SIRGAS 2000 / UTM zone 22S"]',
            "CAR/AVN.shp": b"avn",
            "CAR - Recibo.pdf": b"%PDF-1.4 fake",
            "leiame.txt": b"pacote de teste",
        }
    )


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
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
    monkeypatch.setenv("MF_ADMIN_EMAIL", "chefe@imap.com.br")
    cfg = carregar()
    banco = Banco(cfg.banco)
    banco.migrar()
    app = create_app(
        banco=banco,
        admin_email=cfg.admin_email,
        origem="https://testserver",
        config=cfg,
    )
    with TestClient(app, base_url="https://testserver") as cliente:
        yield cliente, cfg, banco


def entrar_e_criar(cliente, nome="Pacote"):
    cliente.post(
        f"{API}/auth/cadastrar",
        json={"nome": "Ana", "email": "ana@imap.com.br", "senha": SENHA},
    )
    csrf = cliente.get(f"{API}/auth/eu").json()["csrf"]
    projeto = cliente.post(
        f"{API}/projetos",
        json={"nome": nome, "folha": {"formato": "A4", "orientacao": "retrato"}},
        headers={"X-MF-CSRF": csrf},
    ).json()["projeto"]
    return csrf, projeto


def enviar_zip(cliente, csrf: str, conteudo: bytes, *, parte_mb: int = 1) -> str:
    criado = cliente.post(
        f"{API}/uploads",
        json={"nome": "imovel.zip", "tamanho": len(conteudo)},
        headers={"X-MF-CSRF": csrf},
    )
    assert criado.status_code == 201, criado.text
    dados = criado.json()
    parte_bytes = parte_mb * 1024 * 1024
    hexes = []
    for numero in range(dados["total_partes"]):
        pedaco = conteudo[numero * parte_bytes : (numero + 1) * parte_bytes]
        hash_parte = hashlib.sha256(pedaco).hexdigest()
        hexes.append(hash_parte)
        resposta = cliente.put(
            f"{API}/uploads/{dados['upload_id']}/partes/{numero}",
            content=pedaco,
            headers={"X-MF-CSRF": csrf, "X-Parte-SHA256": hash_parte},
        )
        assert resposta.status_code == 204, resposta.text
    hash_partes = hashlib.sha256("".join(hexes).encode("ascii")).hexdigest()
    concluido = cliente.post(
        f"{API}/uploads/{dados['upload_id']}/concluir",
        json={"hash_partes": hash_partes},
        headers={"X-MF-CSRF": csrf},
    )
    assert concluido.status_code == 200, concluido.text
    return dados["upload_id"]


# --- upload ---------------------------------------------------------------


def test_upload_por_partes_e_conclusao(ambiente):
    cliente, cfg, _ = ambiente
    csrf, _projeto = entrar_e_criar(cliente)
    conteudo = zip_do_imovel()
    upload_id = enviar_zip(cliente, csrf, conteudo)

    estado = cliente.get(f"{API}/uploads/{upload_id}")
    assert estado.status_code == 200
    assert estado.json()["faltam"] == []
    assert (cfg.uploads / upload_id / "entrada.zip").read_bytes() == conteudo


def test_parte_com_hash_errado_sv101(ambiente):
    cliente, _, _ = ambiente
    csrf, _ = entrar_e_criar(cliente)
    criado = cliente.post(
        f"{API}/uploads",
        json={"nome": "x.zip", "tamanho": 10},
        headers={"X-MF-CSRF": csrf},
    ).json()
    resposta = cliente.put(
        f"{API}/uploads/{criado['upload_id']}/partes/0",
        content=b"0123456789",
        headers={"X-MF-CSRF": csrf, "X-Parte-SHA256": "0" * 64},
    )
    assert resposta.status_code == 400
    assert resposta.json()["erro"]["codigo"] == "SV-101"


def test_parte_repetida_e_idempotente(ambiente):
    cliente, _, _ = ambiente
    csrf, _ = entrar_e_criar(cliente)
    criado = cliente.post(
        f"{API}/uploads",
        json={"nome": "x.zip", "tamanho": 4},
        headers={"X-MF-CSRF": csrf},
    ).json()
    hash_parte = hashlib.sha256(b"abcd").hexdigest()
    for _ in range(2):
        resposta = cliente.put(
            f"{API}/uploads/{criado['upload_id']}/partes/0",
            content=b"abcd",
            headers={"X-MF-CSRF": csrf, "X-Parte-SHA256": hash_parte},
        )
        assert resposta.status_code == 204


def test_retomada_mostra_partes_que_faltam(ambiente):
    cliente, _, _ = ambiente
    csrf, _ = entrar_e_criar(cliente)
    conteudo = b"a" * (3 * 1024 * 1024)
    criado = cliente.post(
        f"{API}/uploads",
        json={"nome": "x.zip", "tamanho": len(conteudo)},
        headers={"X-MF-CSRF": csrf},
    ).json()
    parte_bytes = criado["parte_bytes"]
    total = criado["total_partes"]
    assert total == -(-len(conteudo) // parte_bytes)
    parte0 = conteudo[:parte_bytes]
    cliente.put(
        f"{API}/uploads/{criado['upload_id']}/partes/0",
        content=parte0,
        headers={"X-MF-CSRF": csrf, "X-Parte-SHA256": hashlib.sha256(parte0).hexdigest()},
    )
    estado = cliente.get(f"{API}/uploads/{criado['upload_id']}").json()
    assert estado["partes_ok"] == [0]
    assert estado["faltam"] == list(range(1, total))


def test_concluir_sem_todas_as_partes_sv102(ambiente):
    cliente, _, _ = ambiente
    csrf, _ = entrar_e_criar(cliente)
    criado = cliente.post(
        f"{API}/uploads", json={"nome": "x.zip", "tamanho": 2 * 1024 * 1024},
        headers={"X-MF-CSRF": csrf},
    ).json()
    resposta = cliente.post(
        f"{API}/uploads/{criado['upload_id']}/concluir",
        json={"hash_partes": "0" * 64},
        headers={"X-MF-CSRF": csrf},
    )
    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "SV-102"


def test_hash_partes_errado_sv102(ambiente):
    cliente, _, _ = ambiente
    csrf, _ = entrar_e_criar(cliente)
    criado = cliente.post(
        f"{API}/uploads", json={"nome": "x.zip", "tamanho": 4},
        headers={"X-MF-CSRF": csrf},
    ).json()
    cliente.put(
        f"{API}/uploads/{criado['upload_id']}/partes/0",
        content=b"abcd",
        headers={"X-MF-CSRF": csrf, "X-Parte-SHA256": hashlib.sha256(b"abcd").hexdigest()},
    )
    resposta = cliente.post(
        f"{API}/uploads/{criado['upload_id']}/concluir",
        json={"hash_partes": "f" * 64},
        headers={"X-MF-CSRF": csrf},
    )
    assert resposta.status_code == 400
    assert resposta.json()["erro"]["codigo"] == "SV-102"


# --- extração -------------------------------------------------------------


def test_extracao_segura_de_pacote_valido(tmp_path):
    origem = tmp_path / "entrada.zip"
    origem.write_bytes(zip_do_imovel())
    destino = tmp_path / "entrada"
    resultado = extrair.extrair(origem, destino, max_extraido_bytes=10 * 1024 * 1024)
    assert resultado.total == 7
    assert (destino / "CAR" / "ATP.shp").read_bytes() == b"shp-fake"
    assert (destino / "CAR - Recibo.pdf").is_file()
    assert resultado.avisos == []


def test_zip_slip_recusado(tmp_path):
    origem = tmp_path / "mal.zip"
    origem.write_bytes(zip_bytes({"../fora.shp": b"x"}))
    with pytest.raises(Exception) as exc:
        extrair.extrair(origem, tmp_path / "entrada", max_extraido_bytes=1024)
    assert exc.value.codigo == "SV-104"


def test_caminho_absoluto_recusado(tmp_path):
    origem = tmp_path / "mal.zip"
    origem.write_bytes(zip_bytes({"/etc/passwd": b"x"}))
    with pytest.raises(Exception) as exc:
        extrair.extrair(origem, tmp_path / "entrada", max_extraido_bytes=1024)
    assert exc.value.codigo == "SV-104"


def test_extensao_fora_da_allowlist_vira_aviso(tmp_path):
    origem = tmp_path / "pacote.zip"
    origem.write_bytes(zip_bytes({"script.exe": b"MZ", "ATP.shp": b"ok"}))
    resultado = extrair.extrair(origem, tmp_path / "entrada", max_extraido_bytes=1024 * 1024)
    assert resultado.ignorados == ["script.exe"]
    assert resultado.arquivos == ["ATP.shp"]
    assert any(a["codigo"] == "SV-120" for a in resultado.avisos)


def test_zip_invalido_sv110(tmp_path):
    origem = tmp_path / "nao_zip.zip"
    origem.write_bytes(b"isto nao e um zip")
    with pytest.raises(Exception) as exc:
        extrair.extrair(origem, tmp_path / "entrada", max_extraido_bytes=1024)
    assert exc.value.codigo == "SV-110"


def test_zip_bomba_sv106(tmp_path):
    origem = tmp_path / "grande.zip"
    origem.write_bytes(zip_bytes({"grande.shp": b"0" * (2 * 1024 * 1024)}))
    with pytest.raises(Exception) as exc:
        extrair.extrair(origem, tmp_path / "entrada", max_extraido_bytes=1024 * 1024)
    assert exc.value.codigo == "SV-106"


def test_entradas_demais_sv108(tmp_path, monkeypatch):
    monkeypatch.setattr(extrair, "MAX_ENTRADAS", 2)
    origem = tmp_path / "muitos.zip"
    origem.write_bytes(zip_bytes({f"a{i}.shp": b"x" for i in range(3)}))
    with pytest.raises(Exception) as exc:
        extrair.extrair(origem, tmp_path / "entrada", max_extraido_bytes=1024 * 1024)
    assert exc.value.codigo == "SV-108"


def test_nome_cp437_e_decodificado(tmp_path):
    origem = tmp_path / "cp437.zip"
    with zipfile.ZipFile(origem, "w") as zf:
        info = zipfile.ZipInfo("relatório.shp")
        # simula ZIP antigo: grava cp437 sem flag UTF-8
        info.filename = "relat¢rio.shp"
        zf.writestr(info, b"x")
    resultado = extrair.extrair(origem, tmp_path / "entrada", max_extraido_bytes=1024 * 1024)
    assert resultado.total == 1


def test_entrada_marcada_somente_leitura(tmp_path):
    origem = tmp_path / "entrada.zip"
    origem.write_bytes(zip_do_imovel())
    destino = tmp_path / "entrada"
    extrair.extrair(origem, destino, max_extraido_bytes=10 * 1024 * 1024)
    extrair.marcar_somente_leitura(destino)
    modo = (destino / "leiame.txt").stat().st_mode & 0o777
    if modo:  # Windows não aplica modo POSIX
        assert modo & 0o222 == 0


# --- guarda de CPF (W4-09) ------------------------------------------------


def test_nenhum_cpf_nas_respostas_da_importacao(ambiente):
    """CPF de recibo nunca chega a resumo, log, banco ou evento (AP-09)."""
    import re

    cliente, cfg, banco = ambiente
    csrf, projeto = entrar_e_criar(cliente)
    cpf = "123.456.789-09"
    conteudo = zip_bytes(
        {
            "CAR/ATP.shp": b"shp-fake",
            "CAR - Recibo.pdf": b"%PDF-1.4 titular CPF " + cpf.encode(),
            "dados.txt": cpf.encode(),
        }
    )
    upload_id = enviar_zip(cliente, csrf, conteudo)

    importacao_id = cliente.post(
        f"{API}/projetos/{projeto['id']}/importacao",
        json={"upload_id": upload_id},
        headers={"X-MF-CSRF": csrf},
    ).json()["importacao_id"]

    padrao = re.compile(r"\d{3}\.\d{3}\.\d{3}-\d{2}")
    respostas = [
        cliente.get(f"{API}/importacoes/{importacao_id}").text,
        cliente.get(f"{API}/projetos/{projeto['id']}").text,
        cliente.get(f"{API}/projetos/{projeto['id']}/resumo").text,
        cliente.get(f"{API}/projetos").text,
    ]
    for corpo in respostas:
        assert not padrao.search(corpo), corpo[:400]

    con = banco.conectar()
    try:
        for tabela in ("projetos", "importacoes", "auditoria"):
            for linha in con.execute(f"SELECT * FROM {tabela}").fetchall():
                texto = " ".join(str(valor) for valor in tuple(linha) if valor is not None)
                assert not padrao.search(texto), (tabela, texto[:200])
    finally:
        con.close()


# --- importação ponta a ponta --------------------------------------------


def test_importacao_de_ponta_a_ponta(ambiente):
    cliente, cfg, banco = ambiente
    csrf, projeto = entrar_e_criar(cliente)
    upload_id = enviar_zip(cliente, csrf, zip_do_imovel())

    resposta = cliente.post(
        f"{API}/projetos/{projeto['id']}/importacao",
        json={"upload_id": upload_id},
        headers={"X-MF-CSRF": csrf},
    )
    assert resposta.status_code == 202, resposta.text
    importacao_id = resposta.json()["importacao_id"]

    estado = cliente.get(f"{API}/importacoes/{importacao_id}").json()
    assert estado["estado"] == "pronto", estado
    assert estado["resumo"]["arquivos"] == 7

    detalhe = cliente.get(f"{API}/projetos/{projeto['id']}")
    assert detalhe.json()["projeto"]["estado"] == "pronto"

    pasta = cfg.projetos / projeto["id"]
    assert (pasta / "entrada.zip").is_file()
    assert (pasta / "entrada" / "CAR" / "ATP.shp").is_file()
    # o upload temporário some depois de importado
    assert not (cfg.uploads / upload_id / "entrada.zip").exists()


def test_importacao_sem_concluir_upload_409(ambiente):
    cliente, _, _ = ambiente
    csrf, projeto = entrar_e_criar(cliente)
    criado = cliente.post(
        f"{API}/uploads", json={"nome": "x.zip", "tamanho": 10},
        headers={"X-MF-CSRF": csrf},
    ).json()
    resposta = cliente.post(
        f"{API}/projetos/{projeto['id']}/importacao",
        json={"upload_id": criado["upload_id"]},
        headers={"X-MF-CSRF": csrf},
    )
    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "SV-100"


def test_importacao_de_projeto_alheio_404(ambiente):
    cliente, _, _ = ambiente
    csrf, projeto = entrar_e_criar(cliente)
    upload_id = enviar_zip(cliente, csrf, zip_do_imovel())
    cliente.post(f"{API}/auth/sair")

    cliente.post(
        f"{API}/auth/cadastrar",
        json={"nome": "Bia", "email": "bia@imap.com.br", "senha": SENHA},
    )
    csrf2 = cliente.get(f"{API}/auth/eu").json()["csrf"]
    resposta = cliente.post(
        f"{API}/projetos/{projeto['id']}/importacao",
        json={"upload_id": upload_id},
        headers={"X-MF-CSRF": csrf2},
    )
    assert resposta.status_code == 404


def test_zip_invalido_deixa_projeto_em_erro(ambiente):
    cliente, cfg, _ = ambiente
    csrf, projeto = entrar_e_criar(cliente)
    upload_id = enviar_zip(cliente, csrf, b"isto nao e zip")

    resposta = cliente.post(
        f"{API}/projetos/{projeto['id']}/importacao",
        json={"upload_id": upload_id},
        headers={"X-MF-CSRF": csrf},
    )
    assert resposta.status_code == 202
    importacao_id = resposta.json()["importacao_id"]
    estado = cliente.get(f"{API}/importacoes/{importacao_id}").json()
    assert estado["estado"] == "erro"
    assert estado["erro_codigo"] == "SV-110"

    detalhe = cliente.get(f"{API}/projetos/{projeto['id']}").json()
    assert detalhe["projeto"]["estado"] == "erro"
    assert detalhe["projeto"]["erro_codigo"] == "SV-110"


def test_upload_maior_que_limite_sv103(tmp_path):
    from mapasfacil_servidor.erros import ErroServidor

    with pytest.raises(ErroServidor) as exc:
        upload_mod.criar(
            tmp_path, nome="grande.zip", tamanho=5 * 1024 * 1024, tamanho_max_bytes=1024
        )
    assert exc.value.codigo == "SV-103"
    assert exc.value.status_http == 413


# --- SSE pela rota (W5-02) ------------------------------------------------


def test_sse_entrega_eventos_da_importacao(ambiente):
    """A rota devolve `text/event-stream` e os eventos gravados no log do projeto."""
    cliente, cfg, _ = ambiente
    csrf, projeto = entrar_e_criar(cliente)
    upload_id = enviar_zip(cliente, csrf, zip_do_imovel())
    importacao_id = cliente.post(
        f"{API}/projetos/{projeto['id']}/importacao",
        json={"upload_id": upload_id},
        headers={"X-MF-CSRF": csrf},
    ).json()["importacao_id"]
    assert cliente.get(f"{API}/importacoes/{importacao_id}").json()["estado"] == "pronto"

    eventos: list[dict] = []
    with cliente.stream("GET", f"{API}/projetos/{projeto['id']}/eventos?desde=0") as resposta:
        assert resposta.status_code == 200
        assert resposta.headers["content-type"].startswith("text/event-stream")
        for linha in resposta.iter_lines():
            if not linha.startswith("data: "):
                continue
            eventos.append(json.loads(linha[6:]))
            if len(eventos) >= 3:
                break

    nomes = [e["evento"] for e in eventos]
    assert "projeto.estado" in nomes
    assert eventos[0]["seq"] == 1
    assert [e["seq"] for e in eventos] == sorted(e["seq"] for e in eventos)


def test_sse_de_projeto_alheio_404(ambiente):
    cliente, _, _ = ambiente
    _csrf, projeto = entrar_e_criar(cliente)
    cliente.post(f"{API}/auth/sair")
    cliente.post(
        f"{API}/auth/cadastrar",
        json={"nome": "Bia", "email": "bia@imap.com.br", "senha": SENHA},
    )
    resposta = cliente.get(f"{API}/projetos/{projeto['id']}/eventos?desde=0")
    assert resposta.status_code == 404
