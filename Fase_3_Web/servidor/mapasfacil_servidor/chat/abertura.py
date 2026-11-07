"""Abertura automática do projeto com a leitura do ZIP (Recurso B / W5-22 / D41).

Quando o projeto passa a 'pronto', o servidor dispara um turno automático
(origem 'sistema', motivo 'importacao_concluida'), um por importação.
Apresenta o imóvel apenas com dados da indexação e oferece a escolha do modelo
com os mapas possíveis da galeria (multipla=true).

A abertura é **determinística**: texto e opções saem da indexação + `galeria.listar`,
sem LLM. O turno do modelo levava de 52 a 75 s com um pacote real (06/11/2026) e,
nesse intervalo, a tela mostrava a leitura do pacote sem nenhuma opção.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any

from ..db import Banco
from ..erros import ErroServidor
from ..eventos.log import LogEventos
from ..eventos.sse import Hub
from ..ponte.pool import Pool

_LOG = logging.getLogger("mapasfacil.chat.abertura")

#: Prefixo de toda mensagem que o servidor manda ao agente em nome do sistema. A tela esconde
#: as mensagens com esse prefixo (não são fala do usuário).
PREFIXO_SISTEMA = "[ORIGEM: sistema"

MAPA_PAPEIS_HUMANOS: dict[str, str] = {
    "ATP": "Perímetro do imóvel",
    "AVN": "Vegetação nativa",
    "AC": "Área consolidada",
    "AUAS": "Área de uso antropizado",
    "APP": "Área de preservação permanente (APP)",
    "APPD": "APP degradada",
    "APPRL": "APP sobreposta à reserva legal",
    "ARL": "Reserva legal (ARL)",
    "TIPOLOGIA": "Tipologia vegetal",
    "AIR": "Área de infraestrutura rural",
    "NASCENTE": "Nascentes",
    "VEREDA": "Veredas",
    "AURD": "Área de uso restrito degradada",
    "AREA_USO_RESTRITO": "Área de uso restrito",
    "AREA_UMIDA": "Áreas úmidas",
    "HIDRO_POLIGONO": "Hidrografia (rios e lagos)",
    "HIDRO_LINHA": "Hidrografia (cursos d'água)",
}


def _emitir(
    hub: Hub,
    projeto_id: str,
    evento: str,
    dados: dict[str, Any],
    *,
    raiz: Path | None = None,
    req_id: str | None = None,
    origem: str = "servidor",
) -> None:
    """Publica no SSE do projeto.

    Com `raiz`, o evento passa pelo `LogEventos` (ganha `seq` e fica no replay). Sem `seq`,
    o fluxo ao vivo **descarta** o evento (`seq <= ultimo_seq`) — era por isso que a abertura
    nunca aparecia na tela.
    """
    if raiz is not None:
        envelope = LogEventos(raiz).registrar(
            origem=origem, evento=evento, dados=dados, req_id=req_id
        )
        hub.publicar(projeto_id, envelope)
        return
    hub.publicar(
        projeto_id,
        {
            "projeto_id": projeto_id,
            "evento": evento,
            "dados": dados,
            "ts": time.time(),
        },
    )


def extrair_dados_abertura(resumo: dict[str, Any]) -> dict[str, Any]:
    """Extrai os dados factuais da indexação para a mensagem de abertura.

    LGPD (W-11): CPF e nome do proprietário nunca entram aqui.
    """
    imovel = resumo.get("imovel") or {}
    recibo = resumo.get("recibo") or {}
    shapefiles = resumo.get("shapefiles") or resumo.get("workspace", {}).get("shapefiles", [])

    nome_imovel = (
        imovel.get("nome")
        or recibo.get("nome_imovel")
        or recibo.get("imovel")
        or "Imóvel rural"
    )

    area_ha = 0.0
    if imovel.get("area_ha"):
        area_ha = float(imovel["area_ha"])
    elif recibo.get("area_imovel_ha"):
        area_ha = float(recibo["area_imovel_ha"])
    elif shapefiles:
        for s in shapefiles:
            if s.get("papel") == "ATP" and s.get("area_ha"):
                area_ha = float(s["area_ha"])
                break

    municipio = imovel.get("municipio") or recibo.get("municipio") or ""
    uf = imovel.get("uf") or recibo.get("uf") or ""
    municipio_uf = f"{municipio} - {uf}" if (municipio and uf) else (municipio or uf or "Não informado")

    # Detecção de datum e conversão SAD69
    veio_sad69 = False
    datum = "SIRGAS 2000"
    for s in shapefiles:
        s_datum = str(s.get("datum") or "").upper()
        s_epsg = s.get("epsg")
        if "SAD69" in s_datum or s_epsg in (29182, 29192, 29193, 29183, 4291):
            veio_sad69 = True
            break
    for av in resumo.get("avisos", []):
        if isinstance(av, dict) and "sad69" in str(av.get("mensagem", "")).lower():
            veio_sad69 = True
            break

    # Camadas encontradas em linguagem humana
    camadas_rotulos: list[str] = []
    papeis_encontrados: set[str] = set()
    for s in shapefiles:
        papel = s.get("papel") or ""
        papeis_encontrados.add(papel)
        rotulo = MAPA_PAPEIS_HUMANOS.get(papel) or s.get("id_local") or "Camada vetorial"
        if rotulo not in camadas_rotulos:
            camadas_rotulos.append(rotulo)

    # Divergência com recibo do CAR
    divergencia_recibo: str | None = None
    area_recibo = float(recibo.get("area_imovel_ha") or 0.0)
    if area_recibo > 0 and area_ha > 0:
        dif = abs(area_ha - area_recibo)
        if dif / area_recibo > 0.01:
            divergencia_recibo = (
                f"Aviso: a área medida da geometria ({area_ha:.4f} ha) diverge da área "
                f"declarada no recibo do CAR ({area_recibo:.4f} ha)."
            )

    # Sugestão de folha
    bbox = imovel.get("bbox") or resumo.get("bbox")
    sugestao_folha = "A4 retrato"
    if bbox and len(bbox) == 4:
        dx = abs(bbox[2] - bbox[0])
        dy = abs(bbox[3] - bbox[1])
        if dx > dy * 1.15:
            sugestao_folha = "A4 paisagem"

    imoveis_raw = resumo.get("imoveis") or resumo.get("workspace", {}).get("imoveis") or []
    imoveis_lista: list[dict[str, Any]] = []
    if isinstance(imoveis_raw, list):
        for im in imoveis_raw:
            if isinstance(im, dict):
                imoveis_lista.append(
                    {
                        "id": im.get("id"),
                        "nome": im.get("nome"),
                        "car": im.get("car"),
                        "matricula": im.get("matricula"),
                        "area_ha": im.get("area") or im.get("area_ha"),
                        "principal": bool(im.get("principal")),
                    }
                )

    return {
        "nome_imovel": nome_imovel,
        "area_ha": area_ha,
        "imoveis": imoveis_lista,
        "municipio_uf": municipio_uf,
        "datum": datum,
        "veio_sad69": veio_sad69,
        "camadas_encontradas": camadas_rotulos,
        "papeis_encontrados": sorted(papeis_encontrados),
        "divergencia_recibo": divergencia_recibo,
        "sugestao_folha": sugestao_folha,
        "bbox": bbox,
    }


def montar_texto_abertura(dados: dict[str, Any]) -> str:
    """Monta a mensagem de abertura determinística a partir dos dados indexados."""
    linhas = ["Leitura do pacote concluída:"]
    imoveis = dados.get("imoveis") or []
    if len(imoveis) > 1:
        linhas.append(f"• Imóveis identificados no pacote ({len(imoveis)} imóveis):")
        for idx, im in enumerate(imoveis, start=1):
            nome_im = im.get("nome") or f"Imóvel {idx}"
            area_val = im.get("area_ha")
            area_str = f"{area_val:.4f} ha" if isinstance(area_val, (int, float)) else "área não informada"
            detalhes = []
            if im.get("car"):
                detalhes.append(f"CAR: {im['car']}")
            if im.get("principal"):
                detalhes.append("Principal")
            detalhes_str = f" ({', '.join(detalhes)})" if detalhes else ""
            linhas.append(f"  {idx}. {nome_im} — {area_str}{detalhes_str}")
    else:
        linhas.append(f"• Imóvel: {dados['nome_imovel']}")
        linhas.append(f"• Área: {dados['area_ha']:.4f} ha")

    linhas.append(f"• Município/UF: {dados['municipio_uf']}")
    if dados["veio_sad69"]:
        linhas.append("• Datum: SIRGAS 2000 (convertido de SAD69 para SIRGAS 2000)")
    else:
        linhas.append(f"• Datum: {dados['datum']}")

    if dados["camadas_encontradas"]:
        linhas.append(f"• Camadas identificadas: {', '.join(dados['camadas_encontradas'])}")
    else:
        linhas.append("• Camadas identificadas: nenhuma camada vetorial reconhecida")

    if dados.get("divergencia_recibo"):
        linhas.append(f"• {dados['divergencia_recibo']}")

    linhas.append(f"• Sugestão de folha: {dados['sugestao_folha']}")
    linhas.append("\nEscolha abaixo qual mapa você deseja gerar:")
    return "\n".join(linhas)


def montar_pergunta_galeria(modelos_galeria: list[dict[str, Any]]) -> dict[str, Any]:
    """Monta o payload da tool `perguntar` com os modelos possíveis da galeria."""
    opcoes = []

    # `galeria.listar` devolve `nome` (não `titulo`): sem isto o botão mostrava o id técnico
    # ("dinamica_2008_spot_quadro (pronto)").
    def _titulo(m: dict[str, Any]) -> str:
        return str(m.get("titulo") or m.get("nome") or m.get("id"))

    # Ordenar: prontos primeiro
    modelos_ordenados = sorted(
        modelos_galeria,
        key=lambda m: (0 if m.get("status") == "pronto" else 1, _titulo(m)),
    )
    for m in modelos_ordenados[:6]:
        mid = str(m.get("id"))
        titulo = _titulo(m)
        status = m.get("status")
        motivo = m.get("motivo") or ""
        if status == "pronto":
            rotulo = f"{titulo} (pronto)"
            # O subtítulo diz para que serve ("Dinâmica 2008 · SPOT · quadro de áreas").
            desc = str(m.get("subtitulo") or "Pronto para gerar")
        else:
            rotulo = f"{titulo} (falta: {motivo or 'dados'})"
            desc = f"Faltam dados: {motivo}" if motivo else "Indisponível para os dados atuais"
        opcoes.append({"id": mid, "rotulo": rotulo, "descricao": desc})

    if len(opcoes) < 2:
        opcoes.append({"id": "personalizado", "rotulo": "Criar mapa personalizado", "descricao": "Definir camadas manualmente"})

    return {
        "pergunta": "Qual mapa você deseja gerar?",
        "opcoes": opcoes[:6],
        "multipla": True,
        "permitir_texto": True,
        "motivo": "escolha_modelo_inicial",
    }


def _abertura_ja_feita(banco: Banco, importacao_id: str) -> bool:
    """Idempotência (D41): cada importação abre uma vez só.

    Fica fora do `_executar_abertura` para o aviso `chat.turno` não piscar na tela num
    reload de uma importação que já foi aberta.
    """
    con = banco.conectar()
    try:
        linha = con.execute(
            "SELECT id, abertura_feita FROM importacoes WHERE id = ?",
            (importacao_id,),
        ).fetchone()
        if linha is not None and "abertura_feita" in linha.keys() and linha["abertura_feita"]:
            return True
        return False
    finally:
        con.close()


async def _conversa_do_projeto(banco: Banco, projeto_id: str) -> str | None:
    con = banco.conectar()
    try:
        linha = con.execute(
            "SELECT conversa_id FROM projetos WHERE id = ?", (projeto_id,)
        ).fetchone()
        return linha["conversa_id"] if linha is not None and linha["conversa_id"] else None
    finally:
        con.close()


async def _gravar_abertura_na_conversa(
    *,
    banco: Banco,
    worker: Any,
    projeto_id: str,
    raiz: Path | None,
    nome_imovel: str,
    texto: str,
    pergunta: dict[str, Any],
) -> None:
    """Guarda a leitura + o cartão da pergunta como mensagem do assistente.

    `chat.gravar_mensagem` não chama LLM: grava exatamente o que já foi exibido e o trace do
    `perguntar`, que é de onde o web reconstrói o cartão ao recarregar. Sem isto, um F5
    antes da primeira resposta deixava a tela sem as opções (o replay do SSE descarta os
    eventos de um turno que já terminou).
    """
    if worker is None:
        return
    try:
        conversa_id = await _conversa_do_projeto(banco, projeto_id)
        if not conversa_id:
            criada = await worker.chamar(
                "chat.criar_conversa",
                {
                    "workspace": str(raiz) if raiz is not None else projeto_id,
                    "title": nome_imovel,
                },
            )
            conversa_id = criada.get("conversation_id") or criada.get("id")
            if conversa_id:
                con = banco.conectar()
                try:
                    con.execute(
                        "UPDATE projetos SET conversa_id = ? WHERE id = ?",
                        (conversa_id, projeto_id),
                    )
                    con.commit()
                finally:
                    con.close()
        if not conversa_id:
            return

        # Só os campos que o cartão da web usa; `descricao` fica de fora para o resumo de
        # 500 caracteres do núcleo não cortar opções.
        args = {
            "pergunta": pergunta.get("pergunta"),
            "opcoes": [
                {"id": o.get("id"), "rotulo": o.get("rotulo")}
                for o in (pergunta.get("opcoes") or [])
                if isinstance(o, dict) and o.get("rotulo")
            ],
            "permite_texto_livre": True,
        }
        await worker.chamar(
            "chat.gravar_mensagem",
            {
                "conversation_id": conversa_id,
                "papel": "assistente",
                "conteudo": texto,
                "tool_traces": [
                    {
                        "tool": "perguntar",
                        "args_resumo": json.dumps(args, ensure_ascii=False),
                        "ok": True,
                    }
                ],
            },
        )
    except Exception as exc:  # a tela já recebeu tudo ao vivo; gravar é para o recarregar
        _LOG.warning(
            "Não consegui gravar a abertura na conversa do projeto %s: %s", projeto_id, exc
        )


async def _executar_abertura(
    *,
    banco: Banco,
    pool: Pool,
    hub: Hub,
    projeto_id: str,
    importacao_id: str,
    resumo: dict[str, Any],
    raiz: Path | None = None,
) -> None:
    """Executa a abertura automática do projeto (Recurso B / W5-22 / D41)."""
    # 1. Checagem de idempotência: garante que cada importação só abre uma vez
    if _abertura_ja_feita(banco, importacao_id):
        return

    dados = extrair_dados_abertura(resumo)
    canal = f"projeto:{projeto_id}"

    # 2. Eventos reais de animação no palco
    if dados.get("bbox"):
        _emitir(hub, projeto_id, "viewport.foco", {"bbox": dados["bbox"]})

    shapefiles = resumo.get("shapefiles") or resumo.get("workspace", {}).get("shapefiles", [])
    for s in shapefiles:
        _emitir(
            hub,
            projeto_id,
            "camada.renderizada",
            {
                "id": s.get("id_local") or s.get("caminho"),
                "papel": s.get("papel"),
                "tipo": s.get("tipo_geometria"),
            },
        )

    # A apresentação não depende do worker: sai da indexação e chega antes de qualquer
    # chamada ao núcleo (2,4 s → 0,2 s medidos em 06/11/2026). É o que tira a tela do
    # estado "nada foi enviado" enquanto a galeria é consultada.
    def emitir(evento: str, dados_evento: dict[str, Any], **kw: Any) -> None:
        _emitir(hub, projeto_id, evento, dados_evento, raiz=raiz, **kw)

    texto_abertura = montar_texto_abertura(dados)
    req_id = f"abertura-{uuid.uuid4().hex[:12]}"
    emitir("chat.delta", {"texto": texto_abertura}, req_id=req_id)

    # 3. O worker entra só para listar a galeria (barato). A abertura é determinística: não
    # chama o LLM. Com um pacote real, em 06/11/2026, o modelo levou 52 s para começar a
    # raciocinar e 75 s para chamar `perguntar`; nesse intervalo a tela mostrava a leitura do
    # pacote e **nenhuma opção** ("Escolha abaixo..." sem nada abaixo). A galeria é factual
    # e sai em ~1 s.
    modelos_galeria: list[dict[str, Any]] = []
    worker = None
    try:
        worker = await pool.obter(projeto_id)
        resp_galeria = await worker.chamar("galeria.listar", {})
        modelos_galeria = resp_galeria.get("modelos") or []
    except Exception as exc:
        _LOG.info("Sem galeria na abertura do projeto %s (%s); oferece o mapa personalizado.", projeto_id, exc)

    pergunta_payload = montar_pergunta_galeria(modelos_galeria)
    pergunta_id = uuid.uuid4().hex[:12]

    # 4. A mesma leitura + pergunta vai para a conversa do núcleo **antes** de o cartão
    # aparecer: recarregar a página antes de responder não pode perder as opções (o replay do
    # SSE descarta eventos de turno já terminado), e responder no primeiro instante não pode
    # deixar a leitura depois da fala do usuário no histórico.
    await _gravar_abertura_na_conversa(
        banco=banco,
        worker=worker,
        projeto_id=projeto_id,
        raiz=raiz,
        nome_imovel=dados["nome_imovel"],
        texto=texto_abertura,
        pergunta=pergunta_payload,
    )

    emitir(
        "chat.pergunta",
        {
            "pergunta_id": pergunta_id,
            "pergunta": pergunta_payload["pergunta"],
            "opcoes": pergunta_payload["opcoes"],
            "multipla": pergunta_payload.get("multipla", True),
            "permitir_texto": True,
            "permite_texto_livre": True,
            "motivo": pergunta_payload.get("motivo", "escolha_modelo_inicial"),
        },
        req_id=req_id,
    )
    emitir("nucleo.res", {"req_id": req_id, "ok": True}, req_id=req_id)

    # 5. Registra que a abertura desta importação foi finalizada
    con = banco.conectar()
    try:
        # Tenta atualizar abertura_feita se a coluna existir
        con.execute(
            "UPDATE importacoes SET abertura_feita = 1 WHERE id = ?",
            (importacao_id,),
        )
        con.commit()
    except Exception:
        pass
    finally:
        con.close()


async def disparar_abertura_projeto(
    *,
    banco: Banco,
    pool: Pool,
    hub: Hub,
    projeto_id: str,
    importacao_id: str,
    resumo: dict[str, Any],
    raiz: Path | None = None,
) -> None:
    """Executa a abertura automática do projeto (Recurso B / W5-22 / D41).

    O par `chat.turno` (início/fim) cerca o turno inteiro. A abertura **não tem bolha de
    usuário** (o prompt é de origem sistema e a tela o esconde): sem esse aviso o chat
    ficava vazio enquanto a IA lia o pacote e a tela mostrava a caixa de boas-vindas
    ("O que você precisa neste mapa?"), como se nada tivesse sido enviado — achado
    06/11/2026. O `finally` garante o fim também quando o worker não sobe.
    """
    if _abertura_ja_feita(banco, importacao_id):
        return
    req_id = f"abertura-{uuid.uuid4().hex[:12]}"
    _emitir(
        hub,
        projeto_id,
        "chat.turno",
        {"fase": "inicio", "origem": "abertura"},
        raiz=raiz,
        req_id=req_id,
    )
    try:
        await _executar_abertura(
            banco=banco,
            pool=pool,
            hub=hub,
            projeto_id=projeto_id,
            importacao_id=importacao_id,
            resumo=resumo,
            raiz=raiz,
        )
    finally:
        _emitir(
            hub,
            projeto_id,
            "chat.turno",
            {"fase": "fim", "origem": "abertura"},
            raiz=raiz,
            req_id=req_id,
        )
