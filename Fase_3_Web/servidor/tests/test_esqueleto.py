"""W0 — o esqueleto do servidor: versão, boot que falha cedo e guardas do plano."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from mapasfacil_servidor import __version__
from mapasfacil_servidor.__main__ import main
from mapasfacil_servidor.config import (
    CHAVES_OBRIGATORIAS_SEGREDOS,
    CHAVES_OPCIONAIS_SEGREDOS,
    carregar,
    ler_segredos,
)
from mapasfacil_servidor.erros import (
    ConfiguracaoInvalida,
    HostInvalido,
    SegredoAusente,
)

RAIZ_SERVIDOR = Path(__file__).resolve().parents[1]


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    base = {
        "MF_RAIZ": str(tmp_path),
        "MF_ADMIN_EMAIL": "admin@mapasfacil.local",
    }
    base.update(extra)
    return base


TODAS_AS_CHAVES = CHAVES_OBRIGATORIAS_SEGREDOS + CHAVES_OPCIONAIS_SEGREDOS


def _arquivo_segredos(tmp_path: Path, chaves=TODAS_AS_CHAVES) -> Path:
    pasta = tmp_path / "segredos"
    pasta.mkdir(exist_ok=True)
    caminho = pasta / "servidor.env"
    linhas = ["# teste — valores fictícios, nunca reais", ""]
    linhas += [f"{nome}=valor-falso-de-teste" for nome in chaves]
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    caminho.chmod(0o600)  # no Linux o app recusa segredo legível por outros (SV-000)
    return caminho


@pytest.mark.anel1
def test_version_na_cli(capsys, monkeypatch):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


@pytest.mark.anel1
def test_sem_mf_raiz_e_sv000(capsys, monkeypatch):
    monkeypatch.delenv("MF_RAIZ", raising=False)
    assert main(["serve"]) == 2
    saida = capsys.readouterr().err
    assert "SV-000" in saida
    assert "MF_RAIZ" in saida


@pytest.mark.anel1
def test_sem_servidor_env_e_sv000_dizendo_o_arquivo(tmp_path):
    with pytest.raises(ConfiguracaoInvalida) as exc:
        carregar(_env(tmp_path))
    erro = exc.value
    assert erro.codigo == "SV-000"
    assert "servidor.env" in erro.mensagem
    assert erro.detalhes and erro.detalhes["arquivo"].endswith("servidor.env")


@pytest.mark.anel1
def test_chave_do_provedor_faltando_e_sv002_sem_valor(tmp_path):
    """Sem a chave do provedor o app não tem chat: é a única obrigatória."""
    _arquivo_segredos(
        tmp_path,
        chaves=("MAPASFACIL_SEMA_AUTHKEY", "MAPASFACIL_PLANET_API_KEY"),
    )
    with pytest.raises(SegredoAusente) as exc:
        carregar(_env(tmp_path))
    erro = exc.value
    assert erro.codigo == "SV-002"
    assert "MAPASFACIL_PROVEDOR_CHAVE" in erro.mensagem
    assert "valor-falso-de-teste" not in erro.mensagem
    assert "valor-falso-de-teste" not in str(erro)


@pytest.mark.anel1
def test_sem_as_chaves_geo_o_app_sobe_e_avisa(tmp_path):
    """Faltar SEMA/Planet custa o WFS autenticado e o WMTS — não o boot.

    Medido em 03/11/2026: exigir as duas travava o deploy inteiro, e elas não existem em
    cofre nenhum da frota. O certo é subir, gerar mapa com as camadas do `.zip` e dizer
    (só com nomes) qual fonte está fora.
    """
    _arquivo_segredos(tmp_path, chaves=("MAPASFACIL_PROVEDOR_CHAVE",))
    cfg = carregar(_env(tmp_path))
    assert set(cfg.segredos_ausentes) == {
        "MAPASFACIL_SEMA_AUTHKEY",
        "MAPASFACIL_PLANET_API_KEY",
    }
    # Nome pode aparecer; valor, nunca.
    assert "valor-falso-de-teste" not in repr(cfg)
    assert "valor-falso-de-teste" not in str(cfg.segredos_ausentes)


@pytest.mark.anel1
def test_com_as_chaves_geo_nada_ausente(tmp_path):
    _arquivo_segredos(tmp_path)
    cfg = carregar(_env(tmp_path))
    assert cfg.segredos_ausentes == ()


@pytest.mark.anel1
def test_config_completa_carrega_defaults_do_plano(tmp_path):
    _arquivo_segredos(tmp_path)
    cfg = carregar(_env(tmp_path))
    assert cfg.host == "127.0.0.1"
    assert cfg.porta == 3130
    assert cfg.url_publica == "https://mapasfacil-app.cursar.space"
    assert cfg.max_workers == 6
    assert cfg.max_jobs == 2
    assert cfg.worker_ocioso_s == 900
    assert cfg.timeout_req_s == 1800
    assert cfg.upload_max_mb == 2048
    assert cfg.upload_parte_mb == 8
    assert cfg.extraido_max_mb == 8192
    assert cfg.modelo_chat == "ag/gemini-3.8-flash-high"
    assert cfg.modelo_visao == "ag/gemini-3.8-flash-high"
    assert cfg.raciocinio == "high"
    assert cfg.provedor_url == "http://100.104.255.35:20128/v1"
    assert cfg.segredos_lidos["MAPASFACIL_PROVEDOR_CHAVE"] == "valor-falso-de-teste"
    # Os caminhos derivados saem da raiz.
    assert cfg.banco == tmp_path / "dados" / "mapasfacil.sqlite"


@pytest.mark.anel1
def test_bind_fora_do_loopback_e_recusado(tmp_path):
    _arquivo_segredos(tmp_path)
    with pytest.raises(HostInvalido) as exc:
        carregar(_env(tmp_path, MF_HOST="0.0.0.0"))
    assert exc.value.codigo == "SV-001"


@pytest.mark.anel1
def test_url_publica_sem_https_e_recusada(tmp_path):
    _arquivo_segredos(tmp_path)
    with pytest.raises(ConfiguracaoInvalida):
        carregar(_env(tmp_path, MF_URL_PUBLICA="http://exemplo"))


@pytest.mark.anel1
def test_inteiro_invalido_falha_cedo(tmp_path):
    _arquivo_segredos(tmp_path)
    with pytest.raises(ConfiguracaoInvalida):
        carregar(_env(tmp_path, MF_MAX_WORKERS="seis"))


@pytest.mark.anel1
def test_segredos_ignoram_comentario_e_aspas(tmp_path):
    caminho = tmp_path / "s.env"
    caminho.write_text("# comentario\nA=1\nB='dois'\n\nC=\"tres\"\n", encoding="utf-8")
    caminho.chmod(0o600)
    lidos = ler_segredos(caminho)
    assert lidos == {"A": "1", "B": "dois", "C": "tres"}


@pytest.mark.anel1
def test_comando_sem_corpo_responde_sv098(capsys, tmp_path, monkeypatch):
    """O contrato do W0 sobrevive: comando sem corpo é `SV-098` e exit 3.

    `migrar`, `limpar-lixeira` e `conta` ganharam corpo no W3, então o teste passa a
    exercitar o mesmo contrato pelo caminho que ainda existe — uma ação de `conta`
    fora da lista do parser não chega aqui, e `NaoImplementado` continua respondendo
    o código certo para qualquer comando futuro.
    """
    from mapasfacil_servidor.erros import NaoImplementado

    erro = NaoImplementado("exemplo", "W99")
    assert erro.codigo == "SV-098"
    assert erro.status_http == 501

    segredos = _arquivo_segredos(tmp_path)
    monkeypatch.setenv("MF_RAIZ", str(tmp_path))
    monkeypatch.setenv("MF_SEGREDOS", str(segredos))
    # ação inválida é recusada pelo argparse antes de qualquer efeito
    with pytest.raises(SystemExit) as exc:
        main(["conta", "apagar-tudo"])
    assert exc.value.code == 2


@pytest.mark.anel1
def test_servidor_nao_tem_bind_aberto():
    """Guardas do W-01: `0.0.0.0` não aparece no código nem no deploy."""
    alvos = [RAIZ_SERVIDOR, RAIZ_SERVIDOR.parent / "deploy"]
    proibidos = {"__pycache__", ".venv", "venv", "node_modules", ".pytest_cache"}
    achados: list[str] = []
    for alvo in alvos:
        if not alvo.exists():
            continue
        for arquivo in alvo.rglob("*"):
            if not arquivo.is_file():
                continue
            if proibidos & set(arquivo.parts):
                continue
            if arquivo.suffix in {".pyc", ".png", ".jpg", ".zip", ".mxd", ".md"}:
                continue
            # O guarda não vale para o próprio teste (ele cita o literal).
            if arquivo.name == "test_esqueleto.py":
                continue
            try:
                texto = arquivo.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for numero, linha in enumerate(texto.splitlines(), start=1):
                if "0.0.0.0" in linha:
                    achados.append(f"{arquivo.relative_to(RAIZ_SERVIDOR.parent)}:{numero}")
    assert achados == [], achados


@pytest.mark.anel1
def test_nenhum_segredo_em_texto_no_pacote():
    """O pacote não carrega chave real: `authkey=`/`api_key=` só em exemplo falso."""
    padrao = re.compile(r"(authkey|api_key)=[A-Za-z0-9\-_]{12,}")
    achados: list[str] = []
    for arquivo in RAIZ_SERVIDOR.rglob("*"):
        if arquivo.is_file() and arquivo.suffix in {".py", ".env", ".sh", ".yml", ".yaml"}:
            if "__pycache__" in arquivo.parts:
                continue
            texto = arquivo.read_text(encoding="utf-8", errors="ignore")
            for numero, linha in enumerate(texto.splitlines(), start=1):
                if padrao.search(linha):
                    achados.append(f"{arquivo.name}:{numero}")
    assert achados == [], achados
