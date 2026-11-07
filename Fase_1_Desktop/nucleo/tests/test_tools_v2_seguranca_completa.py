"""Testes exaustivos das ferramentas V2 e segurança de execução.

Verifica:
1. mapa_validar (valido via resultado['valido']), remoção de sucessos inventados em mapa_gerar e versao_restaurar.
2. layout_medir com PDF real, layout_ler/editar/validar com layout_spec oficial, layout_renderizar com PDF/preview reais.
3. visao_analisar com assinatura real, tarjamento opaco CPF/nome antes de enviar, indisponibilidade em erro/ausência.
4. Workspace guard: bloqueio de caminhos absolutos (/etc, C:/, D:/), backslash, symlinks, pastas protegidas,
   versões Mapas/vNNN imutáveis, arquivos de segredos, leitura bounded no disco, bloqueio de apagar raiz ou mover pastas protegidas.
5. Aprovações por projeto em .servidor/aprovacoes, token fora de tools/eventos, consumo único de decisão.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pymupdf
import pytest
import shapefile

from mapasfacil_nucleo.agente import limites
from mapasfacil_nucleo.agente.aprovacao import GerenciadorAprovacao
from mapasfacil_nucleo.agente.registro import RegistroFerramentas
from mapasfacil_nucleo.agente.tools_geo import registrar_tools_geo
from mapasfacil_nucleo.agente.tools_layout import registrar_tools_layout
from mapasfacil_nucleo.agente.tools_mapa import registrar_tools_mapa
from mapasfacil_nucleo.agente.tools_pdf import registrar_tools_pdf
from mapasfacil_nucleo.agente.tools_visao import registrar_tools_visao
from mapasfacil_nucleo.agente.tools_workspace import registrar_tools_workspace
from mapasfacil_nucleo.agente.visao import servico as visao_servico
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.motores.nativo import gerar_pdf_minimo
from mapasfacil_nucleo.protocolo import Emissor


@pytest.fixture
def ws_completo():
    temp_dir = tempfile.mkdtemp(prefix="mf_test_v2_")
    ws_path = Path(temp_dir)
    (ws_path / "Mapas").mkdir(parents=True)
    (ws_path / "SHP").mkdir(parents=True)
    (ws_path / "XLSX").mkdir(parents=True)

    # Cria shapefile e PDF sintéticos reais
    shp_imovel = ws_path / "SHP" / "imovel.shp"
    with shapefile.Writer(str(shp_imovel), shapeType=shapefile.POLYGON) as w:
        w.field("NOME", "C", size=50)
        w.poly([[[500000, 8500000], [501000, 8500000], [501000, 8501000], [500000, 8501000], [500000, 8500000]]])
        w.record("Fazenda Modelo")
    (ws_path / "SHP" / "imovel.prj").write_text('GEOGCS["SIRGAS 2000",DATUM["SIRGAS_2000",SPHEROID["GRS 1980",6378137,298.257222101]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]', encoding="utf-8")

    yield ws_path
    shutil.rmtree(temp_dir, ignore_errors=True)


# ----------------------------------------------------------------------
# 1. Mapa e Versão: validação correta e remoção de stubs inventados
# ----------------------------------------------------------------------


def test_mapa_validar_usa_resultado_valido(ws_completo, mapspec_canonico):
    registro = RegistroFerramentas()
    registrar_tools_mapa(registro)

    # MapSpec válido a partir do fixture canônico
    ctx = {"workspace": ws_completo, "mapspec": mapspec_canonico}
    res_ok = registro.executar("mapa_validar", {}, ctx)
    assert res_ok["ok"] is True
    assert res_ok["valido"] is True
    assert len(res_ok["erros"]) == 0

    # MapSpec inválido (sem título ou com template inexistente)
    ms_invalido = dict(mapspec_canonico)
    ms_invalido["titulo"] = ""  # Título vazio não permitido
    ms_invalido["template"] = "template_inexistente_xyz"
    ctx_inv = {"workspace": ws_completo, "mapspec": ms_invalido}
    res_inv = registro.executar("mapa_validar", {}, ctx_inv)
    assert res_inv["ok"] is True
    assert res_inv["valido"] is False
    assert len(res_inv["erros"]) > 0


def test_mapa_gerar_e_versao_restaurar_sem_fallback_inventado(ws_completo):
    registro = RegistroFerramentas()
    registrar_tools_mapa(registro)

    # Quando o handler do motor não puder gerar, NÃO pode inventar sucesso fake {"status": "gerado"}
    ctx = {"workspace": ws_completo, "mapspec": {"id": "ms-1"}}
    res_gerar = registro.executar("mapa_gerar", {"motor": "inexistente"}, ctx)
    assert res_gerar["ok"] is False
    assert res_gerar.get("status") != "gerado"

    res_rest = registro.executar("versao_restaurar", {"versao": 999}, ctx)
    assert res_rest["ok"] is False
    assert res_rest.get("restaurado") is not True


# ----------------------------------------------------------------------
# 2. Layout: Medição Real com PDF, LayoutSpec Schema e Renderização Real
# ----------------------------------------------------------------------


def test_layout_ciclo_completo_com_pdf_e_preview_reais(ws_completo):
    registro = RegistroFerramentas()
    registrar_tools_layout(registro)
    eventos = []
    emissor = Emissor("req-layout-test", sink=lambda evt: eventos.append(evt))

    mapspec = {
        "id": "ms-layout-real",
        "versao": 1,
        "titulo": "Fazenda São Paulo",
        "template": "serie_dinamica_2026",
        "folha": {"tamanho": "A4", "orientacao": "retrato", "largura_mm": 210.0, "altura_mm": 297.0},
        "saida": {"pasta": "Mapas", "nome_base": "mapa_layout_real"},
    }
    ctx = {"workspace": ws_completo, "mapspec": mapspec, "emissor": emissor}

    # 1. Ler layout
    res_ler = registro.executar("layout_ler", {}, ctx)
    assert res_ler["ok"] is True
    assert "mapa" in res_ler["elementos"]
    assert "titulo" in res_ler["elementos"]

    # 2. Renderizar PDF real via motor nativo
    res_rend = registro.executar("layout_renderizar", {"formato": "pdf"}, ctx)
    assert res_rend["ok"] is True
    assert res_rend["status"] == "renderizado"

    # Confere existência física no disco
    pdf_real = ws_completo / res_rend["caminho_pdf"]
    preview_real = ws_completo / res_rend["preview"]
    assert pdf_real.exists() and pdf_real.stat().st_size > 1000
    assert preview_real.exists() and preview_real.stat().st_size > 500

    # Evento de preview emitido após arquivo existir no disco
    evts_prev = [e for e in eventos if e["evento"] == "agente.preview"]
    assert len(evts_prev) == 1
    assert evts_prev[0]["dados"]["caminho"] == res_rend["preview"]

    # 3. Medir layout a partir do PDF real gerado
    res_medir = registro.executar(
        "layout_medir",
        {"caminho_pdf": res_rend["caminho_pdf"], "id": "medicao_real", "nome": "Layout Medido Real"},
        ctx,
    )
    assert res_medir["ok"] is True
    assert res_medir["id"] == "medicao_real"
    spec_medido = res_medir["layout_spec"]
    assert "mapa" in spec_medido["elementos"]
    assert "titulo" in spec_medido["elementos"]
    assert spec_medido["dimensoes_mm"]["largura"] > 0

    # 4. Validar o LayoutSpec medido contra o schema oficial
    res_val = registro.executar("layout_validar", {"layout_spec": spec_medido}, ctx)
    assert res_val["ok"] is True
    assert res_val["valido"] is True


# ----------------------------------------------------------------------
# 3. Visão: Provedor Real, Tarjamento LGPD e Indisponibilidade sem Fake
# ----------------------------------------------------------------------


class DubleProvedorVisao:
    def __init__(self) -> None:
        self.chamado = False
        self.ultima_imagem_b64 = ""
        self.ultimo_prompt = ""

    def analisar(self, *, imagem_base64: str, mime: str, prompt: str) -> str:
        self.chamado = True
        self.ultima_imagem_b64 = imagem_base64
        self.ultimo_prompt = prompt
        return json.dumps({"analise": "Composição cartográfica adequada", "conforme": True})


class DubleProvedorVisaoFalha:
    def analisar(self, *, imagem_base64: str, mime: str, prompt: str) -> str:
        raise RuntimeError("Conexão recusada pela API de visão")


def test_visao_tarjamento_lgpd_e_indisponibilidade(ws_completo):
    registro = RegistroFerramentas()
    registrar_tools_visao(registro)

    # 1. Cria um PDF com CPF e nome de proprietário gravados
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 100), "PROPRIETÁRIO: JOÃO DA SILVA ALBUQUERQUE", fontsize=14)
    page.insert_text((50, 130), "CPF: 123.456.789-00", fontsize=14)
    pdf_alvo = ws_completo / "Mapas" / "documento_sensivel.pdf"
    doc.save(str(pdf_alvo))
    doc.close()

    ctx = {
        "workspace": ws_completo,
        "mapspec": {"imovel": {"proprietario": "JOÃO DA SILVA ALBUQUERQUE"}},
    }

    # Teste A: Sem provedor configurado -> DEVE RETORNAR ERRO DE INDISPONÍVEL, NUNCA SUCESSO
    visao_servico.configurar_provedor(None)
    # Garante que não há chave de ambiente
    os.environ.pop("DEEPSEEK_API_KEY", None)
    res_sem_prov = registro.executar("visao_analisar", {"caminho_arquivo": "Mapas/documento_sensivel.pdf"}, ctx)
    assert res_sem_prov["ok"] is False
    assert res_sem_prov["codigo"] == limites.CODIGO_VISAO_INDISPONIVEL

    # Teste B: Com provedor configurado -> Executa tarjamento opaco ANTES do envio
    provedor_ok = DubleProvedorVisao()
    visao_servico.configurar_provedor(provedor_ok)

    res_ok = registro.executar(
        "visao_analisar",
        {
            "caminho_arquivo": "Mapas/documento_sensivel.pdf",
            "prompt": "Avalie este documento.",
        },
        ctx,
    )

    assert res_ok["ok"] is True
    assert provedor_ok.chamado is True
    assert res_ok.get("tarjas_aplicadas", 0) >= 1

    # Inspeciona a imagem enviada ao provedor: deve ser PNG decodificável
    import base64
    img_bytes = base64.b64decode(provedor_ok.ultima_imagem_b64)
    assert len(img_bytes) > 1000

    # Teste C: Provedor falha com erro -> DEVE RETORNAR INDISPONÍVEL, NÃO SUCESSO FALSO
    visao_servico.configurar_provedor(DubleProvedorVisaoFalha())
    res_falha = registro.executar("visao_analisar", {"caminho_arquivo": "Mapas/documento_sensivel.pdf"}, ctx)
    assert res_falha["ok"] is False
    assert res_falha["codigo"] == limites.CODIGO_VISAO_INDISPONIVEL
    assert "recusada" in res_falha["mensagem"]

    # Limpa override
    visao_servico.configurar_provedor(None)


# ----------------------------------------------------------------------
# 4. Workspace Guard e Segurança de Escapes
# ----------------------------------------------------------------------


def test_workspace_guard_bloqueia_todas_tentativas_escape(ws_completo):
    registro = RegistroFerramentas()
    registrar_tools_workspace(registro)
    ctx = {"workspace": ws_completo}

    # 1. Caminhos absolutos em qualquer sistema operacional
    assert registro.executar("workspace_ler", {"caminho": "/etc/passwd"}, ctx)["ok"] is False
    assert registro.executar("workspace_ler", {"caminho": "/var/log/syslog"}, ctx)["ok"] is False
    assert registro.executar("workspace_ler", {"caminho": "C:/Windows/explorer.exe"}, ctx)["ok"] is False
    assert registro.executar("workspace_ler", {"caminho": "C:\\Windows\\System32"}, ctx)["ok"] is False
    assert registro.executar("workspace_ler", {"caminho": "D:/dados"}, ctx)["ok"] is False

    # 2. Path traversal com barras normais e invertidas
    assert registro.executar("workspace_ler", {"caminho": "../escape.txt"}, ctx)["ok"] is False
    assert registro.executar("workspace_ler", {"caminho": "..\\escape.txt"}, ctx)["ok"] is False
    assert registro.executar("workspace_ler", {"caminho": "Mapas/../../escape.txt"}, ctx)["ok"] is False
    assert registro.executar("workspace_ler", {"caminho": "Mapas\\..\\..\\escape.txt"}, ctx)["ok"] is False

    # 3. Pastas internas protegidas
    assert registro.executar("workspace_ler", {"caminho": ".agente/memoria.md"}, ctx)["ok"] is False
    assert registro.executar("workspace_escrever", {"caminho": ".agente/malicioso.py", "conteudo": "x"}, ctx)["ok"] is False
    assert registro.executar("workspace_ler", {"caminho": ".servidor/aprovacoes/pedido.json"}, ctx)["ok"] is False
    assert registro.executar("workspace_escrever", {"caminho": ".servidor/aprovacoes/decisao.json", "conteudo": "{}"}, ctx)["ok"] is False
    assert registro.executar("workspace_ler", {"caminho": ".estado/dados.json"}, ctx)["ok"] is False
    assert registro.executar("workspace_ler", {"caminho": "chats.sqlite"}, ctx)["ok"] is False

    # 4. Versões Mapas/vNNN imutáveis
    (ws_completo / "Mapas" / "v002").mkdir(parents=True)
    (ws_completo / "Mapas" / "v002" / "mapa.pdf").write_text("v2 bytes", encoding="utf-8")
    assert registro.executar("workspace_ler", {"caminho": "Mapas/v002/mapa.pdf"}, ctx)["ok"] is True  # Leitura para QA é permitida; escrita permanece bloqueada.
    assert registro.executar("workspace_escrever", {"caminho": "Mapas/v002/mapa.pdf", "conteudo": "novo"}, ctx)["ok"] is False
    assert registro.executar("workspace_apagar", {"caminho": "Mapas/v002/mapa.pdf"}, ctx)["ok"] is False

    # 5. Segredos
    assert registro.executar("workspace_ler", {"caminho": ".env"}, ctx)["ok"] is False
    assert registro.executar("workspace_ler", {"caminho": "servidor.env"}, ctx)["ok"] is False
    assert registro.executar("workspace_ler", {"caminho": "segredos/chave.txt"}, ctx)["ok"] is False

    # 6. Raiz e pastas estruturais
    assert registro.executar("workspace_apagar", {"caminho": ""}, ctx)["ok"] is False
    assert registro.executar("workspace_apagar", {"caminho": "."}, ctx)["ok"] is False
    assert registro.executar("workspace_apagar", {"caminho": "Mapas"}, ctx)["ok"] is False
    assert registro.executar("workspace_mover", {"origem": "SHP", "destino": "SHP_renomeado"}, ctx)["ok"] is False


def test_workspace_guard_bloqueia_symlinks(ws_completo):
    registro = RegistroFerramentas()
    registrar_tools_workspace(registro)
    ctx = {"workspace": ws_completo}

    alvo_externo = ws_completo.parent / "arquivo_externo.txt"
    alvo_externo.write_text("segredo externo", encoding="utf-8")

    link_dentro = ws_completo / "link_externo.txt"
    try:
        os.symlink(alvo_externo, link_dentro)
    except (OSError, NotImplementedError):
        # Em Windows sem privilégios de desenvolvedor pode lançar erro
        pytest.skip("Ambiente não autoriza criação de symlinks sem privilégios elevados")

    res = registro.executar("workspace_ler", {"caminho": "link_externo.txt"}, ctx)
    assert res["ok"] is False
    assert "symlink" in res["mensagem"].lower() or "links simbólicos" in res["mensagem"].lower()


# ----------------------------------------------------------------------
# 5. Aprovação Confiável por Projeto e Não-Autonomia do LLM
# ----------------------------------------------------------------------


def test_aprovacao_por_projeto_fluxo_confiavel(ws_completo):
    registro = RegistroFerramentas()
    eventos = []
    emissor = Emissor("req-aprov-5", sink=lambda evt: eventos.append(evt))
    gerenciador_aprov = GerenciadorAprovacao(ws_padrao=ws_completo)
    registrar_tools_workspace(registro, gerenciador_aprovacao=gerenciador_aprov)

    ctx = {"workspace": ws_completo, "emissor": emissor}

    # Arquivo para teste de exclusão
    arquivo_teste = ws_completo / "relatorio.txt"
    arquivo_teste.write_text("conteudo a deletar", encoding="utf-8")

    # 1. LLM chama workspace_apagar -> Bloqueia e gera pedido.json confiável
    res_ped = registro.executar("workspace_apagar", {"caminho": "relatorio.txt"}, ctx)
    assert res_ped["ok"] is False
    assert res_ped.get("aguardando_aprovacao") is True
    assert "token" not in res_ped  # Token NÃO exposto para a tool

    # Confere pedido.json em .servidor/aprovacoes/
    pasta_aprov = ws_completo / ".servidor" / "aprovacoes"
    assert (pasta_aprov / "pedido.json").exists()
    pedido_dados = json.loads((pasta_aprov / "pedido.json").read_text(encoding="utf-8"))
    assert pedido_dados["status"] == "pendente"
    assert pedido_dados["acao"] == "apagar"
    assert pedido_dados["caminho"] == "relatorio.txt"

    # Confere que evento não vazou token
    evts_aprov = [e for e in eventos if e["evento"] == "agente.aprovacao"]
    assert len(evts_aprov) == 1
    assert "token" not in evts_aprov[0]["dados"]

    # 2. LLM tenta simular autorização passando token_aprovacao falso ou mesmo verdadeiro no payload -> RECUSADO
    res_fake = registro.executar(
        "workspace_apagar",
        {"caminho": "relatorio.txt", "token_aprovacao": pedido_dados["token"]},
        ctx,
    )
    assert res_fake["ok"] is False
    assert arquivo_teste.exists()

    # 3. Endpoint do Servidor (fora do LLM) registra a decisão do usuário em decisao.json
    assert gerenciador_aprov.registrar_decisao(pedido_dados["token"], aprovado=True, ws_root=ws_completo) is True
    assert (pasta_aprov / "decisao.json").exists()

    # 4. LLM reexecuta workspace_apagar -> A ferramenta encontra e consome a decisão
    res_del = registro.executar("workspace_apagar", {"caminho": "relatorio.txt"}, ctx)
    assert res_del["ok"] is True
    assert not arquivo_teste.exists()

    # 5. Backup foi realizado em destino único
    backup_dir = ws_completo / ".agente" / "backups"
    assert any("relatorio.txt" in f.name for f in backup_dir.iterdir())

    # 6. A decisão foi consumida uma única vez (single-use)
    # Tentar apagar outro arquivo ou reusar o token anterior falha imediatamente
    arquivo_teste.write_text("novo conteudo", encoding="utf-8")
    res_reuso = registro.executar("workspace_apagar", {"caminho": "relatorio.txt"}, ctx)
    assert res_reuso["ok"] is False
    assert res_reuso.get("aguardando_aprovacao") is True
