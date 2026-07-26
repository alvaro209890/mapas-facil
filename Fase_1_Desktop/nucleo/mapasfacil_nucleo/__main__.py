from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable, TextIO

from mapasfacil_nucleo import doctor, leitor_artefato, sessao
from mapasfacil_nucleo import cofre, jobs
from mapasfacil_nucleo.agente import servico as agente_servico
from mapasfacil_nucleo.contas import servico as contas_servico
from mapasfacil_nucleo.conversas import servico as conversas_servico
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.galeria import servico as galeria_servico
from mapasfacil_nucleo.mapspec.diff import diff as mapspec_diff
from mapasfacil_nucleo.mapspec.validar import validar
from mapasfacil_nucleo.motores.gerar import gerar_mapa
from mapasfacil_nucleo.progresso import RastreadorProgresso
from mapasfacil_nucleo.protocolo import (
    Emissor,
    Roteador,
    configurar_sink_assincrono,
    envelope_erro,
    novo_id,
    parsear_linha,
    serializar_linha,
)
from mapasfacil_nucleo.workspace import servico as workspace_servico
from mapasfacil_nucleo.workspace.recibo_car import parsear as parsear_recibo
from mapasfacil_nucleo.motores.manifesto import listar_templates, verificar_template
from mapasfacil_nucleo.quantitativos.calcular import calcular as calcular_quantitativos
from mapasfacil_nucleo.quantitativos.png_tabela import renderizar_png_tabela
from mapasfacil_nucleo.quantitativos.xlsx import exportar_xlsx
from mapasfacil_nucleo.validacao.comparar_pdf import comparar_pdf
from mapasfacil_nucleo.workspace.zip_simcar import extrair as zip_extrair
from mapasfacil_nucleo.workspace.zip_simcar import listar as zip_listar


def criar_roteador() -> Roteador:
    roteador = Roteador()
    roteador.registrar("doctor.rodar", lambda _params: doctor.rodar())
    roteador.registrar("mapspec.validar", _handler_mapspec_validar)
    roteador.registrar("mapspec.diff", _handler_mapspec_diff)
    roteador.registrar("workspace.abrir", _handler_workspace_abrir)
    roteador.registrar("workspace.reindexar", _handler_workspace_reindexar)
    roteador.registrar("workspace.inspecionar", _handler_workspace_inspecionar)
    roteador.registrar("car.ler_recibo", _handler_car_ler_recibo)
    roteador.registrar("mapa.gerar", _handler_mapa_gerar, com_eventos=True)
    roteador.registrar("mapa.cancelar", jobs.handler_cancelar)
    roteador.registrar("artefato.ler", leitor_artefato.ler)
    roteador.registrar("cofre.definir", cofre.handler_definir)
    roteador.registrar("cofre.existe", cofre.handler_existe)
    roteador.registrar("cofre.testar", cofre.handler_testar)
    roteador.registrar("zip.listar", _handler_zip_listar)
    roteador.registrar("zip.extrair", _handler_zip_extrair)
    roteador.registrar("template.listar", _handler_template_listar)
    roteador.registrar("template.verificar", _handler_template_verificar)
    roteador.registrar("validacao.comparar_pdf", _handler_validacao_comparar_pdf)
    roteador.registrar("quantitativos.calcular", _handler_quantitativos_calcular)
    roteador.registrar("quantitativos.exportar_xlsx", _handler_quantitativos_exportar_xlsx)
    roteador.registrar("quantitativos.renderizar_png", _handler_quantitativos_renderizar_png)
    roteador.registrar("galeria.listar", galeria_servico.listar)
    roteador.registrar("galeria.detalhar", galeria_servico.detalhar)
    roteador.registrar("galeria.montar_mapspec", galeria_servico.montar)
    roteador.registrar("conta.criar", contas_servico.criar)
    roteador.registrar("conta.entrar", contas_servico.entrar)
    roteador.registrar("conta.sair", contas_servico.sair)
    roteador.registrar("conta.estado", contas_servico.estado)
    roteador.registrar("sessao.definir", sessao.handler_definir)
    roteador.registrar("sessao.estado", sessao.handler_estado)
    roteador.registrar("chat.criar_conversa", conversas_servico.criar_conversa)
    roteador.registrar("chat.listar_conversas", conversas_servico.listar_conversas)
    roteador.registrar("chat.abrir_conversa", conversas_servico.abrir_conversa)
    roteador.registrar("chat.carregar_anteriores", conversas_servico.carregar_anteriores)
    roteador.registrar("chat.renomear", conversas_servico.renomear)
    roteador.registrar("chat.arquivar", conversas_servico.arquivar)
    roteador.registrar("chat.apagar", conversas_servico.apagar)
    roteador.registrar("chat.ramificar", conversas_servico.ramificar)
    roteador.registrar("chat.buscar", conversas_servico.buscar)
    roteador.registrar("chat.gravar_mensagem", conversas_servico.gravar_mensagem)
    roteador.registrar("chat.enviar", agente_servico.enviar, com_eventos=True)
    roteador.registrar("chat.cancelar", agente_servico.cancelar)
    roteador.registrar("ping", lambda _params: {"pong": True})
    return roteador


def _handler_mapspec_validar(params: dict[str, Any]) -> dict[str, Any]:
    mapspec = params.get("mapspec")
    if not isinstance(mapspec, dict):
        raise ErroNucleo("NU-201", "Parâmetro 'mapspec' precisa ser um objeto.")
    fontes = params.get("fontes_locais")
    fontes_locais = frozenset(fontes) if isinstance(fontes, list) else None
    estado = workspace_servico.estado_atual()
    if fontes_locais is None and estado and estado.indice.get("fontes_locais"):
        fontes_locais = frozenset(estado.indice["fontes_locais"])
    return validar(mapspec, fontes_locais=fontes_locais)


def _handler_mapspec_diff(params: dict[str, Any]) -> dict[str, Any]:
    antes = params.get("antes")
    depois = params.get("depois")
    if not isinstance(antes, dict) or not isinstance(depois, dict):
        raise ErroNucleo("NU-201", "Parâmetros 'antes' e 'depois' precisam ser objetos MapSpec.")
    return mapspec_diff(antes, depois)


def _handler_workspace_abrir(params: dict[str, Any]) -> dict[str, Any]:
    caminho = params.get("caminho")
    if not isinstance(caminho, str) or not caminho:
        raise ErroNucleo("NU-001", "Parâmetro 'caminho' é obrigatório.")
    return workspace_servico.abrir(caminho)


def _handler_workspace_reindexar(params: dict[str, Any]) -> dict[str, Any]:
    caminho = params.get("caminho")
    if caminho is not None and not isinstance(caminho, str):
        raise ErroNucleo("NU-001", "Parâmetro 'caminho' inválido.")
    return workspace_servico.reindexar(caminho)


def _handler_workspace_inspecionar(params: dict[str, Any]) -> dict[str, Any]:
    arquivo = params.get("arquivo")
    if not isinstance(arquivo, str) or not arquivo:
        raise ErroNucleo("NU-041", "Parâmetro 'arquivo' é obrigatório.")
    return workspace_servico.inspecionar(arquivo)


def _handler_car_ler_recibo(params: dict[str, Any]) -> dict[str, Any]:
    pdf = params.get("pdf")
    if not isinstance(pdf, str) or not pdf:
        raise ErroNucleo("NU-041", "Parâmetro 'pdf' é obrigatório.")
    estado = workspace_servico.estado_atual()
    if estado is None:
        raise ErroNucleo("NU-040", "Abra um workspace antes de ler o recibo.")
    caminho = estado.guard.resolver(pdf)
    dados = parsear_recibo(caminho).para_dict()
    assert "cpf" not in dados
    return dados


def _fontes_idx_do_estado(estado) -> dict[str, str]:
    """Stem + alias de papel curto; stem vence se houver colisão de papel."""
    return workspace_servico.fontes_idx(estado)


def _recibo_do_estado(estado) -> dict[str, Any] | None:
    rel = estado.indice.get("recibo_car")
    if not rel:
        return None
    try:
        return parsear_recibo(estado.guard.resolver(rel)).para_dict()
    except ErroNucleo:
        return None


def _handler_mapa_gerar(params: dict[str, Any], emissor: Emissor) -> dict[str, Any]:
    sessao.exigir_conectado("gerar mapa")
    mapspec = params.get("mapspec")
    if not isinstance(mapspec, dict):
        raise ErroNucleo("NU-201", "Parâmetro 'mapspec' precisa ser um objeto.")
    estado = workspace_servico.estado_atual()
    if estado is None:
        raise ErroNucleo("NU-040", "Abra um workspace antes de gerar o mapa.")
    comparar_baseline = bool(params.get("comparar_baseline"))
    job_id = jobs.registrar()
    try:
        return gerar_mapa(
            mapspec,
            estado.guard,
            _fontes_idx_do_estado(estado),
            comparar_baseline=comparar_baseline,
            recibo=_recibo_do_estado(estado),
            progresso=RastreadorProgresso(emissor.emitir, job_id=job_id),
        )
    finally:
        jobs.liberar(job_id)


def _handler_zip_listar(params: dict[str, Any]) -> dict[str, Any]:
    caminho = params.get("caminho")
    if not isinstance(caminho, str) or not caminho:
        raise ErroNucleo("NU-001", "Parâmetro 'caminho' é obrigatório.")
    estado = workspace_servico.estado_atual()
    if estado is None:
        raise ErroNucleo("NU-040", "Abra um workspace antes de listar o ZIP.")
    return zip_listar(estado.guard.resolver(caminho))


def _handler_zip_extrair(params: dict[str, Any]) -> dict[str, Any]:
    caminho = params.get("caminho")
    if not isinstance(caminho, str) or not caminho:
        raise ErroNucleo("NU-001", "Parâmetro 'caminho' é obrigatório.")
    estado = workspace_servico.estado_atual()
    if estado is None:
        raise ErroNucleo("NU-040", "Abra um workspace antes de extrair o ZIP.")
    subpasta = params.get("subpasta")
    if subpasta is not None and not isinstance(subpasta, str):
        raise ErroNucleo("NU-001", "Parâmetro 'subpasta' inválido.")
    return zip_extrair(
        estado.guard.resolver(caminho),
        guard=estado.guard,
        subpasta=subpasta,
    )


def _handler_template_listar(params: dict[str, Any]) -> dict[str, Any]:
    status = params.get("status")
    if status is not None and not isinstance(status, str):
        raise ErroNucleo("NU-001", "Parâmetro 'status' inválido.")
    templates = listar_templates(status=status)
    return {"templates": templates, "total": len(templates)}


def _handler_template_verificar(params: dict[str, Any]) -> dict[str, Any]:
    template_id = params.get("id")
    if not isinstance(template_id, str) or not template_id:
        raise ErroNucleo("NU-001", "Parâmetro 'id' é obrigatório.")
    return verificar_template(template_id)


def _handler_validacao_comparar_pdf(params: dict[str, Any]) -> dict[str, Any]:
    gerado = params.get("gerado")
    referencia = params.get("referencia")
    if not isinstance(gerado, str) or not gerado:
        raise ErroNucleo("NU-041", "Parâmetro 'gerado' é obrigatório.")
    if not isinstance(referencia, str) or not referencia:
        raise ErroNucleo("NU-041", "Parâmetro 'referencia' é obrigatório.")

    estado = workspace_servico.estado_atual()
    guard = estado.guard if estado else None
    gerado_path = Path(gerado)
    referencia_path = Path(referencia)
    if guard is not None and not gerado_path.is_absolute():
        gerado_path = guard.resolver(gerado)
    if guard is not None and not referencia_path.is_absolute():
        referencia_path = guard.resolver(referencia)

    dpi = params.get("dpi", 150)
    tolerancia = params.get("tolerancia_pct", 0.3)
    if not isinstance(dpi, int) or dpi < 36:
        raise ErroNucleo("NU-001", "Parâmetro 'dpi' inválido.")
    if not isinstance(tolerancia, (int, float)) or tolerancia < 0:
        raise ErroNucleo("NU-001", "Parâmetro 'tolerancia_pct' inválido.")

    return comparar_pdf(
        gerado_path,
        referencia_path,
        dpi=dpi,
        tolerancia_pct=float(tolerancia),
    )


def _handler_quantitativos_calcular(params: dict[str, Any]) -> dict[str, Any]:
    mapspec = params.get("mapspec")
    if not isinstance(mapspec, dict):
        raise ErroNucleo("NU-201", "Parâmetro 'mapspec' precisa ser um objeto.")
    estado = workspace_servico.estado_atual()
    if estado is None:
        raise ErroNucleo("NU-040", "Abra um workspace antes de calcular quantitativos.")
    return calcular_quantitativos(
        mapspec,
        guard=estado.guard,
        fontes_idx=_fontes_idx_do_estado(estado),
    )


def _handler_quantitativos_exportar_xlsx(params: dict[str, Any]) -> dict[str, Any]:
    sessao.exigir_conectado("exportar a planilha")
    mapspec = params.get("mapspec")
    if not isinstance(mapspec, dict):
        raise ErroNucleo("NU-201", "Parâmetro 'mapspec' precisa ser um objeto.")
    estado = workspace_servico.estado_atual()
    if estado is None:
        raise ErroNucleo("NU-040", "Abra um workspace antes de exportar quantitativos.")

    dados = params.get("dados")
    if dados is None:
        dados = calcular_quantitativos(
            mapspec,
            guard=estado.guard,
            fontes_idx=_fontes_idx_do_estado(estado),
        )
    elif not isinstance(dados, dict):
        raise ErroNucleo("NU-201", "Parâmetro 'dados' inválido.")

    saida_cfg = mapspec.get("saida") or {}
    pasta = saida_cfg.get("pasta", "Mapas")
    nome_base = saida_cfg.get("nome_base", "mapa")
    destino_rel = params.get("arquivo") or f"{pasta}/{nome_base}_Quantitativos.xlsx"
    destino = estado.guard.resolver(destino_rel, escrita=True)
    recibo = _recibo_do_estado(estado)
    exportar_xlsx(dados, destino, recibo=recibo)
    from mapasfacil_nucleo.quantitativos.conferencia import montar_conferencia

    conferencia = montar_conferencia(dados, recibo)
    return {
        "xlsx": str(destino.relative_to(estado.guard.raiz)),
        "quantitativos": dados,
        "conferencia": conferencia,
    }


def _handler_quantitativos_renderizar_png(params: dict[str, Any]) -> dict[str, Any]:
    mapspec = params.get("mapspec")
    if not isinstance(mapspec, dict):
        raise ErroNucleo("NU-201", "Parâmetro 'mapspec' precisa ser um objeto.")
    estado = workspace_servico.estado_atual()
    if estado is None:
        raise ErroNucleo("NU-040", "Abra um workspace antes de renderizar a tabela PNG.")

    dados = params.get("dados")
    if dados is None:
        dados = calcular_quantitativos(
            mapspec,
            guard=estado.guard,
            fontes_idx=_fontes_idx_do_estado(estado),
        )
    elif not isinstance(dados, dict):
        raise ErroNucleo("NU-201", "Parâmetro 'dados' inválido.")

    saida_cfg = mapspec.get("saida") or {}
    pasta = saida_cfg.get("pasta", "Mapas")
    destino_rel = params.get("arquivo") or f"{pasta}/recursos/tabela_quantitativos.png"
    destino = estado.guard.resolver(destino_rel, escrita=True)
    meta = renderizar_png_tabela(dados, destino)
    return {
        "png": str(destino.relative_to(estado.guard.raiz)),
        "dpi_efetivo": meta["dpi_efetivo"],
        "ok_dpi": meta["ok_dpi"],
        "largura_px": meta["largura_px"],
        "altura_px": meta["altura_px"],
        "quantitativos": dados,
    }


def processar_linha(
    linha: str,
    roteador: Roteador | None = None,
    *,
    emitir: Callable[[dict[str, Any]], None] | None = None,
) -> str:
    """Processa uma linha NDJSON e devolve a(s) linha(s) de saída.

    Com `emitir`, os eventos (`tipo:"evt"`) saem na hora pelo callback — é o que o
    Electron consome durante um job. Sem ele, os eventos entram no prefixo da string
    devolvida, na ordem em que aconteceram, antes da linha de `res`.
    """
    roteador = roteador or criar_roteador()
    buffer: list[str] = []

    def _sink(envelope: dict[str, Any]) -> None:
        if emitir is not None:
            emitir(envelope)
        else:
            buffer.append(serializar_linha(envelope) + "\n")

    id_req = novo_id()
    try:
        mensagem = parsear_linha(linha)
        id_req = mensagem.get("id", id_req)
        resposta = roteador.despachar(mensagem, _sink)
    except ErroNucleo as exc:
        resposta = envelope_erro(id_req, exc)
    except Exception as exc:  # noqa: BLE001 — loop NDJSON não pode morrer
        resposta = envelope_erro(
            id_req,
            ErroNucleo("NU-000", f"Erro interno: {exc.__class__.__name__}: {exc}"),
        )
    return "".join(buffer) + serializar_linha(resposta) + "\n"


def loop_ndjson(
    entrada: TextIO | None = None,
    saida: TextIO | None = None,
    roteador: Roteador | None = None,
) -> None:
    """Loop stdio. Jobs longos (`mapa.gerar`, `chat.enviar`) rodam em thread
    para `mapa.cancelar` / `chat.cancelar` poderem chegar no meio (A10).
    """
    import threading

    entrada = entrada or sys.stdin
    saida = saida or sys.stdout
    roteador = roteador or criar_roteador()
    try:
        contas_servico.restaurar_se_lembrada()
    except ErroNucleo:
        sessao.resetar()

    escrita_lock = threading.Lock()

    def _emitir(envelope: dict[str, Any]) -> None:
        with escrita_lock:
            saida.write(serializar_linha(envelope) + "\n")
            saida.flush()

    def _escrever_resposta(texto: str) -> None:
        with escrita_lock:
            saida.write(texto)
            saida.flush()

    # Eventos fora de req (A12 `workspace.mudou`) usam o mesmo canal stdout.
    configurar_sink_assincrono(_emitir)

    metodos_em_background = frozenset({"mapa.gerar", "chat.enviar"})
    threads_bg: list[threading.Thread] = []

    def _em_background(linha: str) -> None:
        try:
            _escrever_resposta(processar_linha(linha, roteador, emitir=_emitir))
        except Exception as exc:  # noqa: BLE001 — thread não pode morrer silenciosa
            _escrever_resposta(
                serializar_linha(
                    envelope_erro(
                        novo_id(),
                        ErroNucleo("NU-000", f"Erro interno: {exc.__class__.__name__}: {exc}"),
                    )
                )
                + "\n"
            )

    try:
        for linha in entrada:
            linha = linha.strip()
            if not linha:
                continue
            metodo = None
            try:
                bruto = parsear_linha(linha)
                metodo = bruto.get("metodo") if isinstance(bruto, dict) else None
            except ErroNucleo:
                metodo = None
            if isinstance(metodo, str) and metodo in metodos_em_background:
                t = threading.Thread(
                    target=_em_background,
                    args=(linha,),
                    name=f"mf-{metodo}",
                    daemon=True,
                )
                threads_bg.append(t)
                t.start()
            else:
                _escrever_resposta(processar_linha(linha, roteador, emitir=_emitir))
    finally:
        # Espera jobs em voo (mapa.gerar/chat.enviar) antes de fechar o sink.
        for t in threads_bg:
            t.join(timeout=600)
        configurar_sink_assincrono(None)
        workspace_servico.fechar()


def main_cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Sidecar Mapas Fácil")
    sub = parser.add_subparsers(dest="comando")

    sub.add_parser("stdio", help="Loop NDJSON (padrão do Electron)")
    doctor_parser = sub.add_parser("doctor", help="Diagnóstico do ambiente")
    doctor_parser.add_argument("--json", action="store_true", help="Saída JSON")
    doctor_parser.add_argument(
        "--completo",
        action="store_true",
        help="Sondar licença arcpy (lento; só Windows com ArcMap)",
    )

    args = parser.parse_args()
    if args.comando in (None, "stdio"):
        loop_ndjson()
        return
    if args.comando == "doctor":
        resultado = doctor.rodar(sondar_arcpy=args.completo)
        if args.json:
            print(json.dumps(resultado, ensure_ascii=False, indent=2))
        else:
            print(f"Mapas Fácil núcleo {resultado['nucleo']} — {resultado['so']}")
            print(f"Python {resultado['python']}")
            print(f"ogr2ogr: {resultado['gdal']['ogr2ogr'] or 'não encontrado'}")
            print(f"Pronto para MXD: {resultado['pronto_para_mxd']}")
        return
    parser.error(f"Comando desconhecido: {args.comando}")


if __name__ == "__main__":
    main_cli()
