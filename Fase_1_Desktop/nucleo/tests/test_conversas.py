# M6 / F1-17 — persistência local de conversas (anel 1, puro: sem rede, sem ArcMap).
#
# Os critérios de aceite do plano estão um a um aqui, com o nome do teste dizendo
# qual é. Nada de mock do SQLite: o banco é real, em `tmp_path`.

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from mapasfacil_nucleo.conversas import banco, fingerprint, repositorio as repo, servico, titulo
from mapasfacil_nucleo.erros import ErroNucleo

PASTA_MODULO = Path(banco.__file__).resolve().parent


@pytest.fixture(autouse=True)
def chats_em_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """`%APPDATA%\\MapasFacil` aponta para `tmp_path`; o repositório global é reaberto."""
    monkeypatch.setenv("MAPASFACIL_APPDATA", str(tmp_path / "MapasFacil"))
    repo.fechar()
    yield tmp_path
    repo.fechar()


@pytest.fixture
def r() -> repo.RepositorioConversas:
    return repo.redefinir()


# --------------------------------------------------------------------- esquema


def test_banco_nasce_migrado_em_wal(r: repo.RepositorioConversas):
    assert banco.versao_atual(r.conexao) == 1
    modo = r.conexao.execute("PRAGMA journal_mode").fetchone()[0]
    assert modo.lower() == "wal"
    assert r.conexao.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert banco.caminho_banco().exists()
    assert banco.caminho_banco().parent.name == "chats"


def test_esquema_consolidado_igual_ao_das_migracoes(r: repo.RepositorioConversas, tmp_path: Path):
    """`esquema.sql` é a forma alvo; migração 001 tem de produzir exatamente ela."""
    espelho = sqlite3.connect(tmp_path / "espelho.sqlite")
    espelho.executescript((PASTA_MODULO / "esquema.sql").read_text(encoding="utf-8"))

    def objetos(conexao: sqlite3.Connection) -> set[tuple[str, str, str]]:
        return {
            (linha[0], linha[1], " ".join((linha[2] or "").split()))
            for linha in conexao.execute(
                "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
            )
        }

    assert objetos(r.conexao) == objetos(espelho)
    espelho.close()


def test_migracao_e_idempotente(r: repo.RepositorioConversas):
    assert banco.aplicar_migracoes(r.conexao) == 1
    assert banco.aplicar_migracoes(r.conexao) == 1
    assert r.conexao.execute("SELECT COUNT(*) FROM schema_versao").fetchone()[0] == 1


# ------------------------------------------------------- ciclo criar → reabrir


def test_ciclo_completo_criar_gravar_fechar_reabrir(r: repo.RepositorioConversas, tmp_path: Path):
    projeto = tmp_path / "Fazenda Harmonia"
    projeto.mkdir()
    conversa = r.criar_conversa(workspace=str(projeto))
    for i in range(5):
        msg = r.acrescentar_mensagem(
            conversa["conversation_id"],
            papel="usuario" if i % 2 == 0 else "assistente",
            conteudo=f"mensagem {i + 1}",
        )
        if i == 1:
            r.registrar_tool_trace(
                conversa["conversation_id"],
                tool="workspace.inspecionar",
                message_id=msg["message_id"],
                args_resumo="SHP/ATP.shp",
                resultado_resumo="1 feição, SIRGAS 2000 / UTM 21S",
                ms=42,
            )

    # "fechar o processo do núcleo": conexão fechada, processo novo abre o mesmo arquivo
    r.fechar()
    novo = repo.redefinir()
    aberta = novo.abrir_conversa(conversa["conversation_id"])

    assert aberta["total"] == 5
    assert [m["seq"] for m in aberta["mensagens"]] == [1, 2, 3, 4, 5]
    assert [m["conteudo"] for m in aberta["mensagens"]] == [f"mensagem {i + 1}" for i in range(5)]
    assert aberta["tem_anteriores"] is False
    assert len(aberta["tool_traces"]) == 1
    assert aberta["tool_traces"][0]["tool"] == "workspace.inspecionar"
    assert aberta["conversa"]["workspace_nome"] == "Fazenda Harmonia"
    assert aberta["conversa"]["workspace_fingerprint"] == fingerprint.calcular(str(projeto))


def test_seq_e_monotonico_e_unico(r: repo.RepositorioConversas):
    conversa = r.criar_conversa()
    seqs = [
        r.acrescentar_mensagem(conversa["conversation_id"], papel="usuario", conteudo=str(i))["seq"]
        for i in range(10)
    ]
    assert seqs == list(range(1, 11))


def test_papel_invalido_recusado(r: repo.RepositorioConversas):
    conversa = r.criar_conversa()
    with pytest.raises(ErroNucleo) as exc:
        r.acrescentar_mensagem(conversa["conversation_id"], papel="robo", conteudo="oi")
    assert exc.value.codigo == "NU-243"


def test_conversa_inexistente_nu242(r: repo.RepositorioConversas):
    with pytest.raises(ErroNucleo) as exc:
        r.abrir_conversa("01HZZZZZZZZZZZZZZZZZZZZZZZ")
    assert exc.value.codigo == "NU-242"


# ---------------------------------------------------------- escala e paginação


@pytest.fixture
def conversa_de_200(r: repo.RepositorioConversas) -> str:
    conversa = r.criar_conversa()
    cid = conversa["conversation_id"]
    for i in range(200):
        r.acrescentar_mensagem(cid, papel="usuario", conteudo=f"linha {i + 1} do histórico")
    return cid


def test_abrir_200_mensagens_em_menos_de_300ms(r: repo.RepositorioConversas, conversa_de_200: str):
    """Critério de aceite F1-17: < 300 ms, 30 mensagens, `total: 200`.

    Tolerância: o teto é 300 ms de parede numa máquina de CI compartilhada; a
    medição real fica em ~2 ms porque a consulta usa o índice
    `(conversation_id, seq DESC)`. Se este teste começar a piscar, o problema é
    consulta perdendo índice, não o número.
    """
    inicio = time.perf_counter()
    aberta = r.abrir_conversa(conversa_de_200)
    decorrido_ms = (time.perf_counter() - inicio) * 1000

    assert aberta["total"] == 200
    assert len(aberta["mensagens"]) == 30
    assert aberta["mensagens"][0]["seq"] == 171
    assert aberta["mensagens"][-1]["seq"] == 200
    assert aberta["tem_anteriores"] is True
    assert decorrido_ms < 300, f"abrir_conversa levou {decorrido_ms:.1f} ms"


def test_carregar_anteriores_pagina_para_cima(r: repo.RepositorioConversas, conversa_de_200: str):
    pagina = r.carregar_anteriores(conversa_de_200, antes_de_seq=171, limite=50)
    assert [m["seq"] for m in pagina["mensagens"]] == list(range(121, 171))
    assert pagina["tem_mais"] is True

    topo = r.carregar_anteriores(conversa_de_200, antes_de_seq=21, limite=50)
    assert [m["seq"] for m in topo["mensagens"]] == list(range(1, 21))
    assert topo["tem_mais"] is False


def test_listar_conversas_pagina_e_filtra_por_pasta(r: repo.RepositorioConversas, tmp_path: Path):
    a = tmp_path / "obra-a"
    b = tmp_path / "obra-b"
    a.mkdir()
    b.mkdir()
    r.criar_conversa(workspace=str(a), title="chat A1")
    r.criar_conversa(workspace=str(a), title="chat A2")
    conversa_b = r.criar_conversa(workspace=str(b), title="chat B1")

    global_ = r.listar_conversas()
    assert len(global_["conversas"]) == 3
    assert global_["tem_mais"] is False

    so_a = r.listar_conversas(workspace=str(a))
    assert {c["title"] for c in so_a["conversas"]} == {"chat A1", "chat A2"}

    primeira_pagina = r.listar_conversas(limite=2)
    assert len(primeira_pagina["conversas"]) == 2
    assert primeira_pagina["tem_mais"] is True
    cursor = primeira_pagina["conversas"][-1]["updated_at"]
    segunda = r.listar_conversas(limite=2, antes_de=cursor)
    assert segunda["tem_mais"] is False

    r.acrescentar_mensagem(conversa_b["conversation_id"], papel="usuario", conteudo="  oi   mundo ")
    item_b = next(
        c for c in r.listar_conversas()["conversas"] if c["title"] == "chat B1"
    )
    assert item_b["ultimo_trecho"] == "oi mundo"
    assert item_b["mensagens_total"] == 1


def test_arquivada_sai_da_lista_e_volta(r: repo.RepositorioConversas):
    conversa = r.criar_conversa(title="some daqui")
    r.arquivar(conversa["conversation_id"], True)
    assert r.listar_conversas()["conversas"] == []
    assert len(r.listar_conversas(incluir_arquivadas=True)["conversas"]) == 1
    r.arquivar(conversa["conversation_id"], False)
    assert len(r.listar_conversas()["conversas"]) == 1


# ------------------------------------------------------------------- privacidade


def test_cpf_nao_entra_no_banco_nem_no_arquivo(r: repo.RepositorioConversas):
    conversa = r.criar_conversa()
    r.acrescentar_mensagem(
        conversa["conversation_id"],
        papel="usuario",
        conteudo="o proprietário é CPF 123.456.789-00, confere?",
    )
    lido = r.conexao.execute(
        "SELECT conteudo FROM mensagens WHERE conversation_id = ?",
        (conversa["conversation_id"],),
    ).fetchone()[0]
    assert "[CPF removido]" in lido
    assert "123.456.789" not in lido

    # `grep -a` do critério de aceite: nada do CPF em NENHUM arquivo de `chats/`
    # (o `.sqlite-wal` conta — é onde a escrita recém-feita ainda mora).
    r.fechar()
    bytes_no_disco = b"".join(
        arquivo.read_bytes() for arquivo in banco.pasta_chats().rglob("*") if arquivo.is_file()
    )
    assert b"123.456.789" not in bytes_no_disco
    assert b"12345678900" not in bytes_no_disco


def test_chave_de_api_nao_entra_no_traco_de_tool(r: repo.RepositorioConversas):
    conversa = r.criar_conversa()
    r.registrar_tool_trace(
        conversa["conversation_id"],
        tool="camada.resolver",
        args_resumo="wms?api_key=PLAKabcdef1234567890",
        resultado_resumo="200 OK",
    )
    linha = r.conexao.execute("SELECT args_resumo FROM tool_traces").fetchone()[0]
    assert "PLAKabcdef" not in linha
    assert "[chave removida]" in linha


def test_resumo_de_tool_e_cortado_no_teto(r: repo.RepositorioConversas):
    conversa = r.criar_conversa()
    r.registrar_tool_trace(
        conversa["conversation_id"],
        tool="quantitativos.calcular",
        args_resumo="a" * 900,
        resultado_resumo="b" * 3000,
    )
    linha = r.conexao.execute("SELECT args_resumo, resultado_resumo FROM tool_traces").fetchone()
    assert len(linha[0]) == 500
    assert len(linha[1]) == 1000


def test_workspace_path_fica_no_banco_mas_a_lista_so_mostra_o_nome(
    r: repo.RepositorioConversas, tmp_path: Path
):
    projeto = tmp_path / "Fazenda Santa Clara"
    projeto.mkdir()
    r.criar_conversa(workspace=str(projeto), title="x")
    item = r.listar_conversas()["conversas"][0]
    assert item["workspace_nome"] == "Fazenda Santa Clara"
    assert "workspace_path" not in item


# ------------------------------------------------------------------------ busca


def test_busca_ignora_acento_nos_dois_sentidos(r: repo.RepositorioConversas):
    conversa = r.criar_conversa()
    r.acrescentar_mensagem(
        conversa["conversation_id"], papel="usuario", conteudo="órgão ambiental de Mato Grosso"
    )
    r.acrescentar_mensagem(
        conversa["conversation_id"], papel="assistente", conteudo="area de preservacao permanente"
    )
    assert len(r.buscar("orgao")["resultados"]) == 1
    assert len(r.buscar("órgão")["resultados"]) == 1
    assert len(r.buscar("preservação")["resultados"]) == 1


def test_busca_destaca_o_trecho_e_aponta_a_mensagem(r: repo.RepositorioConversas):
    conversa = r.criar_conversa()
    alvo = r.acrescentar_mensagem(
        conversa["conversation_id"],
        papel="usuario",
        conteudo="preciso do mapa de dinâmica de uso do solo",
    )
    resultado = r.buscar("dinâmica")["resultados"][0]
    assert resultado["message_id"] == alvo["message_id"]
    assert resultado["seq"] == alvo["seq"]
    assert "[dinâmica]" in resultado["trecho_destacado"]


def test_busca_com_sintaxe_do_fts_no_termo_nao_explode(r: repo.RepositorioConversas):
    conversa = r.criar_conversa()
    r.acrescentar_mensagem(conversa["conversation_id"], papel="usuario", conteudo='citou "aspas" aqui')
    assert len(r.buscar('"aspas"')["resultados"]) == 1
    assert r.buscar("NEAR OR *")["resultados"] == []
    assert r.buscar("   ")["resultados"] == []


def test_indice_fts_acompanha_apagar_mensagem(r: repo.RepositorioConversas):
    conversa = r.criar_conversa()
    r.acrescentar_mensagem(
        conversa["conversation_id"], papel="usuario", conteudo="palavraunicaparaobusca"
    )
    assert len(r.buscar("palavraunicaparaobusca")["resultados"]) == 1
    r.apagar(conversa["conversation_id"])
    assert r.buscar("palavraunicaparaobusca")["resultados"] == []


# ------------------------------------------------------------------- ramificar


def test_ramificar_copia_ate_o_seq_e_registra_o_pai(r: repo.RepositorioConversas, tmp_path: Path):
    projeto = tmp_path / "obra"
    projeto.mkdir()
    origem = r.criar_conversa(workspace=str(projeto), title="conversa de 10")
    cid = origem["conversation_id"]
    for i in range(10):
        r.acrescentar_mensagem(cid, papel="usuario", conteudo=f"m{i + 1}")

    ramo = r.ramificar(cid, a_partir_do_seq=3)
    aberta = r.abrir_conversa(ramo["conversation_id"])

    assert aberta["total"] == 3
    assert [m["conteudo"] for m in aberta["mensagens"]] == ["m1", "m2", "m3"]
    assert aberta["conversa"]["parent_conversation_id"] == cid
    assert aberta["conversa"]["parent_message_seq"] == 3
    assert aberta["conversa"]["workspace_fingerprint"] == fingerprint.calcular(str(projeto))
    # a original continua com as 10: ramificar não move nada
    assert r.abrir_conversa(cid)["total"] == 10


def test_ramificar_copia_traco_de_tool_do_trecho(r: repo.RepositorioConversas):
    origem = r.criar_conversa()
    cid = origem["conversation_id"]
    primeira = r.acrescentar_mensagem(cid, papel="usuario", conteudo="m1")
    r.registrar_tool_trace(cid, tool="mapspec.validar", message_id=primeira["message_id"], ok=True)
    ultima = r.acrescentar_mensagem(cid, papel="assistente", conteudo="m2")
    r.registrar_tool_trace(cid, tool="mapa.gerar", message_id=ultima["message_id"], ok=True)

    ramo = r.ramificar(cid, a_partir_do_seq=1)
    traces = r.abrir_conversa(ramo["conversation_id"])["tool_traces"]
    assert [t["tool"] for t in traces] == ["mapspec.validar"]


def test_ramificar_conversa_vazia_nu244(r: repo.RepositorioConversas):
    origem = r.criar_conversa()
    with pytest.raises(ErroNucleo) as exc:
        r.ramificar(origem["conversation_id"], a_partir_do_seq=1)
    assert exc.value.codigo == "NU-244"
    assert r.listar_conversas()["conversas"][0]["ramificada"] is False


def test_ramificar_seq_zero_nu243(r: repo.RepositorioConversas):
    origem = r.criar_conversa()
    r.acrescentar_mensagem(origem["conversation_id"], papel="usuario", conteudo="só uma")
    with pytest.raises(ErroNucleo) as exc:
        r.ramificar(origem["conversation_id"], a_partir_do_seq=0)
    assert exc.value.codigo == "NU-243"


# ----------------------------------------------------------------- título


def test_titulo_nasce_padrao_e_a_ia_pode_trocar(r: repo.RepositorioConversas):
    conversa = r.criar_conversa()
    assert conversa["title"] == titulo.TITULO_PADRAO
    r.acrescentar_mensagem(
        conversa["conversation_id"],
        papel="usuario",
        conteudo="quero o mapa de dinâmica de uso do solo da Fazenda Harmonia para o relatório",
    )
    resultado = r.titular_automaticamente(conversa["conversation_id"])
    assert resultado["ok"] is True
    assert len(resultado["title"]) <= titulo.TETO_TITULO
    assert resultado["title"].startswith("quero o mapa")


def test_modelo_da_galeria_vence_a_primeira_mensagem(r: repo.RepositorioConversas):
    conversa = r.criar_conversa()
    r.acrescentar_mensagem(conversa["conversation_id"], papel="usuario", conteudo="boa tarde")
    resultado = r.titular_automaticamente(
        conversa["conversation_id"], modelo_galeria="Dinâmica de uso do solo · Harmonia"
    )
    assert resultado["title"] == "Dinâmica de uso do solo · Harmonia"


def test_renomear_sela_title_manual_e_a_ia_nao_sobrescreve(r: repo.RepositorioConversas):
    conversa = r.criar_conversa()
    r.renomear(conversa["conversation_id"], "Harmonia — dinâmica 2026")
    depois = r.titular_automaticamente(conversa["conversation_id"], modelo_galeria="outro nome")
    assert depois["ok"] is False
    assert depois["motivo"] == "title_manual"
    assert r.abrir_conversa(conversa["conversation_id"])["conversa"]["title"] == (
        "Harmonia — dinâmica 2026"
    )


def test_title_no_criar_ja_conta_como_manual(r: repo.RepositorioConversas):
    conversa = r.criar_conversa(title="nome que eu escolhi")
    assert r.titular_automaticamente(conversa["conversation_id"], modelo_galeria="x")["ok"] is False


def test_titulo_longo_e_encurtado_com_reticencia(r: repo.RepositorioConversas):
    longo = "análise de dinâmica de uso e ocupação do solo com quantitativos e conferência"
    conversa = r.criar_conversa(title=longo)
    assert len(conversa["title"]) <= titulo.TETO_TITULO
    assert conversa["title"].endswith("…")


def test_renomear_vazio_recusado(r: repo.RepositorioConversas):
    conversa = r.criar_conversa()
    with pytest.raises(ErroNucleo) as exc:
        r.renomear(conversa["conversation_id"], "   ")
    assert exc.value.codigo == "NU-243"


# ------------------------------------------------------------------- apagar


def test_apagar_leva_linhas_em_cascata_e_arquivos_do_disco(r: repo.RepositorioConversas):
    conversa = r.criar_conversa()
    cid = conversa["conversation_id"]
    msg = r.acrescentar_mensagem(cid, papel="usuario", conteudo="com anexo")
    r.registrar_tool_trace(cid, tool="zip.listar", message_id=msg["message_id"])
    pasta = banco.pasta_anexos(cid)
    pasta.mkdir(parents=True)
    (pasta / f"{msg['message_id']}-1.png").write_bytes(b"png")
    (pasta / f"{msg['message_id']}-2.pdf").write_bytes(b"pdf")
    r.registrar_anexo(
        cid,
        caminho_local=f"anexos/{cid}/{msg['message_id']}-1.png",
        nome_original="print.png",
        bytes_=3,
        sha256="0" * 64,
        message_id=msg["message_id"],
    )

    resultado = r.apagar(cid)
    assert resultado == {"ok": True, "anexos_removidos": 2}
    assert not pasta.exists()
    for tabela in ("conversas", "mensagens", "tool_traces", "anexos", "conversa_mapspecs"):
        assert r.conexao.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0] == 0


def test_apagar_conversa_ramificada_solta_o_filho(r: repo.RepositorioConversas):
    origem = r.criar_conversa()
    r.acrescentar_mensagem(origem["conversation_id"], papel="usuario", conteudo="m1")
    ramo = r.ramificar(origem["conversation_id"], a_partir_do_seq=1)
    r.apagar(origem["conversation_id"])
    # ON DELETE SET NULL: o ramo sobrevive órfão, não desaparece com o pai
    aberta = r.abrir_conversa(ramo["conversation_id"])
    assert aberta["conversa"]["parent_conversation_id"] is None
    assert aberta["total"] == 1


def test_mapspec_da_conversa_e_registrado_ao_gravar_a_mensagem(r: repo.RepositorioConversas):
    conversa = r.criar_conversa()
    r.acrescentar_mensagem(
        conversa["conversation_id"],
        papel="assistente",
        conteudo="mapa gerado",
        mapspec_id="01HXMAPSPEC0000000000000000",
        mapspec_versao=2,
    )
    aberta = r.abrir_conversa(conversa["conversation_id"])
    assert aberta["mapspecs"] == [
        {
            "mapspec_id": "01HXMAPSPEC0000000000000000",
            "versao": 2,
            "criado_em": aberta["mensagens"][0]["criado_em"],
        }
    ]


# ------------------------------------------------------ duas janelas (WAL)


def test_duas_janelas_escrevendo_nao_corrompem_o_banco(r: repo.RepositorioConversas):
    """Critério de aceite: abrir a mesma conversa em duas janelas não corrompe.

    Duas conexões, escrita intercalada na MESMA conversa — é onde o `seq` calculado
    fora do lock de escrita quebraria o `UNIQUE (conversation_id, seq)`.
    """
    outra = repo.RepositorioConversas()
    conversa = r.criar_conversa(title="duas janelas")
    cid = conversa["conversation_id"]
    try:
        for i in range(10):
            r.acrescentar_mensagem(cid, papel="usuario", conteudo=f"janela A {i}")
            outra.acrescentar_mensagem(cid, papel="assistente", conteudo=f"janela B {i}")
        assert r.conexao.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        aberta = outra.abrir_conversa(cid, limite=30)
        assert aberta["total"] == 20
        assert [m["seq"] for m in aberta["mensagens"]] == list(range(1, 21))
    finally:
        outra.fechar()


def test_logout_nao_apaga_o_historico(r: repo.RepositorioConversas):
    """D14 — "Sair" só revoga sessão; o arquivo continua lá com o conteúdo.

    Não existe `auth.sair` ainda (M5). O que este teste garante é a metade que
    depende do M6: nada em `conversas/` apaga banco por troca de conta, e reabrir
    devolve o histórico com a `conta_id` preservada.
    """
    conversa = r.criar_conversa(conta_id="conta-1", title="antes do logout")
    r.acrescentar_mensagem(conversa["conversation_id"], papel="usuario", conteudo="trabalho feito")
    r.fechar()

    depois = repo.redefinir()
    aberta = depois.abrir_conversa(conversa["conversation_id"])
    assert aberta["total"] == 1
    assert aberta["conversa"]["conta_id"] == "conta-1"


# ------------------------------------------------------------- handlers NDJSON


def test_handlers_chat_cobrem_o_ciclo_da_sidebar(r: repo.RepositorioConversas, tmp_path: Path):
    projeto = tmp_path / "obra-ndjson"
    projeto.mkdir()
    criada = servico.criar_conversa({"workspace": str(projeto)})
    cid = criada["conversation_id"]
    servico.registrar_mensagem({"conversation_id": cid, "conteudo": "primeira pergunta"})
    servico.registrar_mensagem(
        {"conversation_id": cid, "papel": "assistente", "conteudo": "primeira resposta"}
    )

    assert servico.listar_conversas({})["conversas"][0]["mensagens_total"] == 2
    assert servico.abrir_conversa({"conversation_id": cid, "limite": 1})["total"] == 2
    assert servico.carregar_anteriores(
        {"conversation_id": cid, "antes_de_seq": 2}
    )["mensagens"][0]["seq"] == 1
    assert servico.renomear({"conversation_id": cid, "title": "renomeada"})["ok"] is True
    assert servico.buscar({"termo": "resposta"})["resultados"][0]["conversation_id"] == cid
    ramo = servico.ramificar({"conversation_id": cid, "a_partir_do_seq": 1})
    assert ramo["mensagens_copiadas"] == 1
    assert servico.arquivar({"conversation_id": cid, "arquivada": True})["arquivada"] is True
    assert servico.apagar({"conversation_id": cid}) == {"ok": True, "anexos_removidos": 0}


def test_handler_usa_o_workspace_aberto_quando_o_param_falta(
    r: repo.RepositorioConversas, workspace: Path
):
    from mapasfacil_nucleo.workspace import servico as workspace_servico

    workspace_servico.abrir(str(workspace))
    criada = servico.criar_conversa({})
    aberta = servico.abrir_conversa({"conversation_id": criada["conversation_id"]})
    assert aberta["conversa"]["workspace_nome"] == workspace.name


@pytest.mark.parametrize(
    "chamada,params",
    [
        (servico.abrir_conversa, {}),
        (servico.renomear, {"conversation_id": "x"}),
        (servico.buscar, {}),
        (servico.carregar_anteriores, {"conversation_id": "x"}),
        (servico.ramificar, {"conversation_id": "x"}),
        (servico.registrar_mensagem, {"conversation_id": "x"}),
        (servico.listar_conversas, {"limite": "trinta"}),
        (servico.arquivar, {"conversation_id": "x", "arquivada": "sim"}),
    ],
)
def test_params_faltando_ou_com_tipo_errado_dao_nu243(r, chamada, params):
    with pytest.raises(ErroNucleo) as exc:
        chamada(params)
    assert exc.value.codigo == "NU-243"


def test_metodos_chat_estao_no_roteador():
    from mapasfacil_nucleo.__main__ import criar_roteador

    roteador = criar_roteador()
    esperados = {
        "chat.criar_conversa",
        "chat.listar_conversas",
        "chat.abrir_conversa",
        "chat.carregar_anteriores",
        "chat.renomear",
        "chat.arquivar",
        "chat.apagar",
        "chat.ramificar",
        "chat.buscar",
        "chat.registrar_mensagem",
    }
    assert esperados <= set(roteador._handlers)
    # `chat.enviar` e `chat.cancelar` são do M7: não podem existir ainda, senão a UI
    # acha que tem agente.
    assert "chat.enviar" not in roteador._handlers
    assert "chat.cancelar" not in roteador._handlers


# ------------------------------------------------------------- fingerprint


def test_fingerprint_normaliza_caixa_e_barra_final(tmp_path: Path):
    pasta = tmp_path / "Obra"
    pasta.mkdir()
    assert fingerprint.calcular(str(pasta)) == fingerprint.calcular(f"{pasta}/")
    # caixa: no Windows `C:\Obra` e `c:\obra` são a mesma pasta
    assert fingerprint.normalizar("C:/Obra/Harmonia") == fingerprint.normalizar("c:\\obra\\harmonia")
    assert fingerprint.calcular(None) == fingerprint.SEM_WORKSPACE
    assert fingerprint.calcular("") == fingerprint.SEM_WORKSPACE
    assert len(fingerprint.calcular(str(pasta))) == 64


def test_conversa_sem_pasta_e_listada(r: repo.RepositorioConversas):
    conversa = r.criar_conversa(title="antes de conectar pasta")
    item = r.listar_conversas()["conversas"][0]
    assert item["conversation_id"] == conversa["conversation_id"]
    assert item["workspace_nome"] is None


# ------------------------------------------------------------------ sem rede


def test_pacote_conversas_nao_tem_caminho_de_rede():
    """AP-12/D20 — local-only. Espelha o `grep` do critério de aceite."""
    proibidos = (
        "http://",
        "https://",
        "import requests",
        "import urllib",
        "import socket",
        "import http",
    )
    for arquivo in PASTA_MODULO.rglob("*"):
        if arquivo.suffix not in {".py", ".sql"}:
            continue
        texto = arquivo.read_text(encoding="utf-8")
        for termo in proibidos:
            assert termo not in texto, f"{arquivo.name} menciona {termo}"
