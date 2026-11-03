"""Abertura automática do projeto com a leitura do ZIP (Recurso B / W5-22 / D41).

Quando o projeto passa a 'pronto', o servidor dispara um turno automático
(origem 'sistema', motivo 'importacao_concluida'), um por importação.
Apresenta o imóvel apenas com dados da indexação e chama `perguntar` com os
modelos possíveis da galeria (multipla=true). Se o 9Router falhar ou demorar,
executa o Plano B determinístico sem LLM.
"""

from __future__ import annotations

import logging
from typing import Any

from ..db import Banco
from ..erros import ErroServidor
import time
from ..eventos.sse import Hub
from ..ponte.pool import Pool

_LOG = logging.getLogger("mapasfacil.chat.abertura")

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


def _emitir(hub: Hub, projeto_id: str, evento: str, dados: dict[str, Any]) -> None:
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

    return {
        "nome_imovel": nome_imovel,
        "area_ha": area_ha,
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
    linhas = [
        "Leitura do pacote concluída:",
        f"• Imóvel: {dados['nome_imovel']}",
        f"• Área: {dados['area_ha']:.4f} ha",
        f"• Município/UF: {dados['municipio_uf']}",
    ]
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
    # Ordenar: prontos primeiro
    modelos_ordenados = sorted(
        modelos_galeria,
        key=lambda m: (0 if m.get("status") == "pronto" else 1, m.get("titulo", "")),
    )
    for m in modelos_ordenados[:6]:
        mid = str(m.get("id"))
        titulo = str(m.get("titulo") or mid)
        status = m.get("status")
        motivo = m.get("motivo") or ""
        if status == "pronto":
            rotulo = f"{titulo} (pronto)"
            desc = "Pronto para gerar"
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


async def disparar_abertura_projeto(
    *,
    banco: Banco,
    pool: Pool,
    hub: Hub,
    projeto_id: str,
    importacao_id: str,
    resumo: dict[str, Any],
) -> None:
    """Executa a abertura automática do projeto (Recurso B / W5-22 / D41)."""
    # 1. Checagem de idempotência: garante que cada importação só abre uma vez
    con = banco.conectar()
    try:
        linha = con.execute(
            "SELECT id, abertura_feita FROM importacoes WHERE id = ?",
            (importacao_id,),
        ).fetchone()
        if linha is not None:
            # Se a coluna abertura_feita já existir e for 1, encerra
            if "abertura_feita" in linha.keys() and linha["abertura_feita"]:
                return
    finally:
        con.close()

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

    # 3. Obter worker do núcleo para o projeto
    try:
        worker = await pool.obter(projeto_id)
    except Exception as exc:
        _LOG.warning("Worker indisponível para abertura do projeto %s: %s", projeto_id, exc)
        return

    # Garante que a conversa principal do projeto existe
    conversa_id = None
    con = banco.conectar()
    try:
        p_row = con.execute("SELECT conversa_id, nome FROM projetos WHERE id = ?", (projeto_id,)).fetchone()
        if p_row and p_row["conversa_id"]:
            conversa_id = p_row["conversa_id"]
    finally:
        con.close()

    if not conversa_id:
        criada = await worker.chamar(
            "chat.criar_conversa",
            {"workspace": str(projeto_id), "title": dados["nome_imovel"]},
        )
        conversa_id = criada.get("conversation_id") or criada.get("id")
        if conversa_id:
            con = banco.conectar()
            try:
                con.execute("UPDATE projetos SET conversa_id = ? WHERE id = ?", (conversa_id, projeto_id))
                con.commit()
            finally:
                con.close()

    # 4. Listar modelos da galeria
    modelos_galeria: list[dict[str, Any]] = []
    try:
        resp_galeria = await worker.chamar("galeria.listar", {})
        modelos_galeria = resp_galeria.get("modelos") or []
    except Exception as exc:
        _LOG.debug("Falha ao listar galeria para abertura: %s", exc)

    texto_abertura = montar_texto_abertura(dados)
    pergunta_payload = montar_pergunta_galeria(modelos_galeria)

    # 5. Tenta via LLM com prompt de sistema ou cai no Plano B determinístico
    abertura_ok = False
    try:
        # Prompt de sistema para o modelo
        prompt_abertura = (
            f"[ORIGEM: sistema | MOTIVO: importacao_concluida]\n"
            f"O pacote de dados do projeto acabou de ser importado e indexado.\n"
            f"Apresente o imóvel ao usuário utilizando ESTRITAMENTE os dados factuais abaixo "
            f"(sem inventar nenhum dado):\n{texto_abertura}\n\n"
            f"Em seguida, use a ferramenta `perguntar` para oferecer os modelos de mapas possíveis da galeria."
        )
        resultado_turno = await worker.chamar(
            "chat.enviar",
            {
                "conversation_id": conversa_id,
                "mensagem": prompt_abertura,
            },
        )
        if resultado_turno and resultado_turno.get("message_id"):
            abertura_ok = True
    except Exception as exc:
        _LOG.info("LLM/9Router indisponível ou falhou (%s). Executando Plano B determinístico.", exc)

    if not abertura_ok:
        # Plano B Determinístico sem LLM (garante que o usuário nunca fica com chat vazio)
        try:
            await worker.chamar(
                "chat.gravar_mensagem",
                {
                    "conversation_id": conversa_id,
                    "papel": "assistant",
                    "conteudo": texto_abertura,
                },
            )
        except Exception as exc:
            _LOG.warning("Erro ao gravar mensagem do Plano B: %s", exc)

        # Emite no SSE para a tela atualizar
        _emitir(hub, projeto_id, "chat.chunk", {"conteudo": texto_abertura})
        _emitir(hub, projeto_id, "chat.fim", {"texto": texto_abertura})

        # Emite pergunta estruturada via SSE para a UI exibir os botões
        import uuid
        pergunta_id = uuid.uuid4().hex[:12]
        _emitir(
            hub,
            projeto_id,
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
        )
        try:
            await worker.chamar("perguntar", pergunta_payload)
        except Exception:
            pass

    # 6. Registra que a abertura desta importação foi finalizada
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
