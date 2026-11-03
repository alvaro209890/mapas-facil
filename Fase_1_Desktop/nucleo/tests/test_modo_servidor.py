"""W1-13 — o modo servidor do núcleo: fronteira sem keyring, sem APPDATA, sem ArcPy."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from mapasfacil_nucleo import cofre, config, jobs, sessao, vagas
from mapasfacil_nucleo import projeto_servidor
from mapasfacil_nucleo.agente import provisao, tools
from mapasfacil_nucleo.mapspec import migrar
from mapasfacil_nucleo.mapspec.validar import validar
from mapasfacil_nucleo.motores import folhas
from mapasfacil_nucleo.workspace import servico as workspace_servico
from mapasfacil_nucleo.workspace import watcher as watcher_mod


@pytest.fixture
def modo_servidor_env(monkeypatch, tmp_path):
    monkeypatch.setenv("MAPASFACIL_MODO", "servidor")
    monkeypatch.setenv(sessao.ENV_USUARIO_SERVIDOR, "usuario_01")
    monkeypatch.setenv(vagas.ENV_DIR, str(tmp_path / "vagas"))
    monkeypatch.setenv(vagas.ENV_MAX, "1")
    monkeypatch.setenv("MAPASFACIL_SEMA_AUTHKEY", "sema-de-teste")
    monkeypatch.setenv("MAPASFACIL_PLANET_API_KEY", "planet-de-teste")
    monkeypatch.setenv("MAPASFACIL_DEEPSEEK_API_KEY", "deepseek-de-teste")
    yield
    projeto_servidor.limpar()


# --- config ---------------------------------------------------------------


def test_modo_desktop_por_padrao(monkeypatch):
    monkeypatch.delenv("MAPASFACIL_MODO", raising=False)
    assert config.modo() == "desktop"
    assert config.modo_servidor() is False


def test_modo_desconhecido_cai_para_desktop(monkeypatch):
    monkeypatch.setenv("MAPASFACIL_MODO", "turbo")
    assert config.modo() == "desktop"


def test_pasta_de_saida_por_versao(modo_servidor_env):
    assert config.pasta_saida_versao(3) == "Mapas/v003"
    assert config.pasta_saida(versao=3) == "Mapas/v003"
    assert config.pasta_saida() == "Mapas"


def test_pasta_de_saida_no_desktop(monkeypatch):
    monkeypatch.delenv("MAPASFACIL_MODO", raising=False)
    assert config.pasta_saida(versao=3) == "Mapas"


# --- cofre ----------------------------------------------------------------


def test_cofre_le_env_e_nao_toca_keyring(modo_servidor_env, monkeypatch):
    class KeyringProibido:
        def __getattr__(self, nome):  # pragma: no cover - só falha se for tocado
            raise AssertionError(f"keyring.{nome} foi tocado em modo servidor")

    monkeypatch.setitem(sys.modules, "keyring", KeyringProibido())
    cofre.configurar_backend(None)

    assert cofre.usar("sema_authkey") == "sema-de-teste"
    assert cofre.existe("planet_api_key") is True
    assert cofre.existe("sema_authkey") is True
    assert cofre.chaves_configuradas() == {"deepseek": True, "sema": True, "planet": True}


def test_cofre_definir_no_servidor_e_nu060(modo_servidor_env):
    with pytest.raises(Exception) as exc:
        cofre.definir("sema_authkey", "x")
    assert getattr(exc.value, "codigo", None) == "NU-060"


# --- sessão ---------------------------------------------------------------


def test_sessao_do_servidor(modo_servidor_env):
    estado = sessao.estado_atual()
    assert estado == {"estado": "conectado", "conta_id": "usuario_01", "expira_em": None}
    assert sessao.conectada() is True
    sessao.exigir_conectado("gerar mapa")  # não levanta


def test_sessao_sem_usuario_do_servidor(monkeypatch, modo_servidor_env):
    monkeypatch.delenv(sessao.ENV_USUARIO_SERVIDOR)
    assert sessao.conectada() is False
    with pytest.raises(Exception) as exc:
        sessao.exigir_conectado("gerar mapa")
    assert getattr(exc.value, "codigo", None) == "AUTH-030"


def test_sessao_definir_no_servidor_e_auth090(modo_servidor_env):
    with pytest.raises(Exception) as exc:
        sessao.definir(estado="conectado", conta_id="x")
    assert getattr(exc.value, "codigo", None) == "AUTH-090"


# --- provisão e watcher ---------------------------------------------------


def test_provisao_desligada_no_servidor(modo_servidor_env):
    assert provisao.sincronizar_chave_projeto_no_cofre() == {
        "ok": False,
        "motivo": "modo_servidor",
    }


def test_watcher_nao_sobe_thread_no_servidor(modo_servidor_env, tmp_path):
    w = watcher_mod.reiniciar(
        tmp_path,
        obter_indice=lambda: {},
        reindexar=lambda *_a, **_k: {},
    )
    assert w.ativo is False
    watcher_mod.parar()


# --- projeto.json ---------------------------------------------------------


def _pasta_projeto(tmp_path: Path) -> Path:
    raiz = tmp_path / "projeto"
    (raiz / ".servidor").mkdir(parents=True)
    (raiz / ".servidor" / "projeto.json").write_text(
        json.dumps(
            {
                "id": "01HXPROJETO",
                "nome": "Fazenda Fictícia",
                "folha": {"formato": "A3", "orientacao": "paisagem", "escala_elementos": "proporcional"},
                "dono": "usuario_01",
            }
        ),
        encoding="utf-8",
    )
    return raiz


def test_projeto_do_servidor_entra_na_memoria(modo_servidor_env, tmp_path, monkeypatch):
    raiz = _pasta_projeto(tmp_path)
    projeto_servidor.definir_raiz(raiz)

    memoria = tools.montar_memoria_trabalho()
    assert memoria["projeto"] == {
        "nome": "Fazenda Fictícia",
        "folha": {"formato": "A3", "orientacao": "paisagem", "escala_elementos": "proporcional"},
        # W5-14: a mesma folha em texto, do jeito que a IA fala com o usuário.
        "folha_texto": "A3 paisagem",
    }

    # No desktop o mesmo projeto não aparece.
    monkeypatch.delenv("MAPASFACIL_MODO")
    assert tools.montar_memoria_trabalho().get("projeto") is None


def test_abrir_workspace_devolve_projeto(modo_servidor_env, tmp_path):
    raiz = _pasta_projeto(tmp_path)
    resultado = workspace_servico.abrir(str(raiz))
    assert resultado["projeto"]["nome"] == "Fazenda Fictícia"
    projeto_servidor.limpar()


# --- folhas ---------------------------------------------------------------


def test_folhas_mm_e_fator():
    assert folhas.folha_mm("A4") == (210.0, 297.0)
    assert folhas.folha_mm("A4", "paisagem") == (297.0, 210.0)
    assert folhas.folha_mm("A0") == (841.0, 1189.0)
    assert folhas.fator_k("A4") == 1.0
    # k = largura_retrato_mm / 210 — o valor real vem dos mm ISO (297/210), não de √2.
    assert abs(folhas.fator_k("A3") - 2**0.5) < 0.001
    assert abs(folhas.fator_k("A0") - 4.0) < 0.01


def test_folha_invalida_da_erro_de_folha():
    for args in (("A9",), ("A4", "diagonal")):
        with pytest.raises(Exception) as exc:
            folhas.folha_mm(*args)
        assert str(getattr(exc.value, "codigo", "")).startswith("NU-3")


def test_folha_do_template_le_o_manifest():
    assert folhas.folha_do_template("tipologia_paisagem") == {
        "formato": "A4",
        "orientacao": "paisagem",
        "escala_elementos": "proporcional",
    }
    assert folhas.folha_do_template("nao_existe") is None


def test_cli_folhas_json(capsys):
    from mapasfacil_nucleo.__main__ import main_cli

    sys.argv = ["mapasfacil_nucleo", "folhas", "--json"]
    main_cli()
    dados = json.loads(capsys.readouterr().out)
    assert dados["ordem"] == ["A4", "A3", "A2", "A1", "A0"]
    assert abs(dados["formatos"]["A0"]["fator_k"] - 4.0) < 0.01


# --- MapSpec v3 -----------------------------------------------------------


def _spec_v2() -> dict:
    caminho = Path(__file__).resolve().parents[3] / "shared/fixtures/mapspecs/dinamica_2026_canonico.json"
    spec = json.loads(caminho.read_text(encoding="utf-8"))
    spec["contract_version"] = 2
    spec.pop("folha", None)
    return spec


def test_v2_migra_para_v3_com_folha_do_template():
    spec = _spec_v2()
    migrado = migrar.migrar(spec)
    assert migrado["contract_version"] == 3
    assert migrado["folha"]["formato"] in {"A4", "A3", "A2", "A1", "A0"}
    assert migrado["folha"]["orientacao"] in {"retrato", "paisagem"}
    # original intocado
    assert spec["contract_version"] == 2 and "folha" not in spec


def test_spec_v2_continua_valido_pela_migracao():
    resultado = validar(_spec_v2(), fontes_locais=frozenset({"ATP", "AVN", "AUAS"}))
    assert resultado["valido"], resultado["erros"]


def test_spec_sem_folha_no_v3_ganha_folha():
    spec = _spec_v2()
    spec["contract_version"] = 3
    migrado = migrar.migrar(spec)
    assert isinstance(migrado["folha"], dict)


def test_folha_invalida_reprova():
    spec = _spec_v2()
    spec["contract_version"] = 3
    spec["folha"] = {"formato": "A9", "orientacao": "retrato", "escala_elementos": "proporcional"}
    resultado = validar(spec, fontes_locais=frozenset({"ATP", "AVN", "AUAS"}))
    assert resultado["valido"] is False
    assert any(e["codigo"] in {"NU-201", "NU-301"} for e in resultado["erros"])


# --- vagas ----------------------------------------------------------------


def test_vaga_unica_bloqueia_a_segunda(modo_servidor_env, tmp_path):
    (tmp_path / "vagas").mkdir(exist_ok=True)
    primeira = vagas.tentar_agora()
    assert primeira is not None, "a primeira vaga deveria ser obtida"
    assert vagas.tentar_agora() is None, "com MF_MAX_JOBS=1 a segunda não pode entrar"

    arquivo, indice = primeira  # type: ignore[misc]
    assert indice == 0
    vagas._destravar(arquivo)
    arquivo.close()  # type: ignore[union-attr]

    segunda = vagas.tentar_agora()
    assert segunda is not None
    arquivo2, _ = segunda  # type: ignore[misc]
    vagas._destravar(arquivo2)
    arquivo2.close()  # type: ignore[union-attr]


def test_vaga_libera_ao_sair_do_bloco(modo_servidor_env, tmp_path):
    (tmp_path / "vagas").mkdir(exist_ok=True)
    with vagas.vaga(espera_s=0.01):
        assert vagas.tentar_agora() is None
    livre = vagas.tentar_agora()
    assert livre is not None
    arquivo, _ = livre  # type: ignore[misc]
    vagas._destravar(arquivo)
    arquivo.close()  # type: ignore[union-attr]


def test_vaga_no_desktop_e_no_op(monkeypatch):
    monkeypatch.delenv("MAPASFACIL_MODO", raising=False)
    with vagas.vaga(espera_s=0.01) as indice:
        assert indice is None


def test_vaga_cancelada_desiste(modo_servidor_env, tmp_path):
    (tmp_path / "vagas").mkdir(exist_ok=True)
    ocupada = vagas.tentar_agora()
    assert ocupada is not None
    try:
        with pytest.raises(Exception) as exc:
            with vagas.vaga(
                espera_s=0.01,
                cancelado=lambda: True,
                dormir=lambda _s: None,
            ):
                pass
        assert getattr(exc.value, "codigo", None) == "NU-050"
    finally:
        arquivo, _ = ocupada  # type: ignore[misc]
        vagas._destravar(arquivo)
        arquivo.close()  # type: ignore[union-attr]


def test_jobs_cancelado_le_o_estado():
    job_id = jobs.registrar()
    try:
        assert jobs.cancelado(job_id) is False
        jobs.obter(job_id).cancelado = True  # type: ignore[union-attr]
        assert jobs.cancelado(job_id) is True
    finally:
        jobs.liberar(job_id)


# --- ArcPy no servidor ----------------------------------------------------


def test_gerar_no_servidor_recusa_arcpy(monkeypatch):
    """W1-10 sem tocar `doctor.py` (arquivo de outro trabalho, proibido pelo Álvaro).

    A recusa mora no caminho que importa — `motores.gerar` — e não em `doctor.rodar`;
    o `/api/v1/saude` do servidor (W3) reporta modo e motor a partir de `config`.
    """
    from mapasfacil_nucleo.erros import ErroNucleo
    from mapasfacil_nucleo.motores import gerar

    monkeypatch.setenv("MAPASFACIL_MODO", "servidor")
    with pytest.raises(ErroNucleo) as exc:
        gerar._recusar_arcpy_no_servidor()
    assert exc.value.codigo == "NU-127"
