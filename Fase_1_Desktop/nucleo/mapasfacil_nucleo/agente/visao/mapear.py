# F1-07 — resposta do modelo de visão → proposta sanitizada → MapSpec candidato
# ou perguntas. Regra do plano: confiança abaixo de 0,7 em qualquer item vira
# pergunta, não palpite. Estilo/template fora do catálogo é descartado (AP-04) —
# nunca aceito só porque o modelo disse.

from __future__ import annotations

import json
from typing import Any

from mapasfacil_nucleo.agente import limites
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.galeria.montar import montar_mapspec
from mapasfacil_nucleo.mapspec.validar import ESTILOS_PERMITIDOS

LIMIAR_CONFIANCA = 0.7

# mapa_da_serie (vocabulário do prompt) → modelos da galeria candidatos, na
# ordem de preferência. Só os que já existem em shared/galeria/modelos.json —
# não inventa modelo novo.
MAPEAMENTO_SERIE_MODELO: dict[str, list[str]] = {
    "dinamica": ["dinamica_2026_retrato", "dinamica_2026_quantitativos"],
    "tipologia": ["tipologia_paisagem"],
    "terras_indigenas": ["terras_indigenas_paisagem"],
    "uc": ["uc_paisagem"],
}

MAPAS_SERIE_CONHECIDOS = frozenset(MAPEAMENTO_SERIE_MODELO)


def parsear_resposta(bruto: str) -> dict[str, Any]:
    """Texto cru do provedor → dict. `IA-061` se não for JSON (modelo alucinou formato)."""
    texto = bruto.strip()
    if texto.startswith("```"):
        texto = texto.strip("`")
        if texto[:4].lower() == "json":
            texto = texto[4:]
        texto = texto.strip()
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as exc:
        raise ErroNucleo(
            limites.CODIGO_VISAO_RESPOSTA_INVALIDA,
            f"Resposta do modelo de visão não é JSON válido: {exc}",
        ) from exc
    if not isinstance(dados, dict):
        raise ErroNucleo(
            limites.CODIGO_VISAO_RESPOSTA_INVALIDA,
            "Resposta do modelo de visão não é um objeto JSON.",
        )
    return dados


def _confianca(valor: Any) -> float:
    num = float(valor) if isinstance(valor, (int, float)) and not isinstance(valor, bool) else 0.0
    return max(0.0, min(1.0, num))


def sanitizar_resposta(bruto: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Aplica o vocabulário fechado (AP-04) — descarta, nunca aceita palpite."""
    avisos: list[str] = []

    mapa_da_serie = bruto.get("mapa_da_serie")
    if mapa_da_serie not in MAPAS_SERIE_CONHECIDOS:
        if mapa_da_serie is not None:
            avisos.append(f"mapa_da_serie fora do catálogo, ignorado: {mapa_da_serie!r}")
        mapa_da_serie = None

    template_sugerido = bruto.get("template_sugerido")
    template_sugerido = template_sugerido if isinstance(template_sugerido, str) else None

    ano = bruto.get("ano")
    ano = ano if isinstance(ano, int) and not isinstance(ano, bool) else None

    camadas_ok: list[dict[str, Any]] = []
    for item in bruto.get("camadas") or []:
        if not isinstance(item, dict):
            continue
        estilo = item.get("estilo_sugerido")
        if estilo not in ESTILOS_PERMITIDOS:
            avisos.append(
                f"estilo fora do catálogo, ignorado: {estilo!r} "
                f"(legenda lida: {str(item.get('legenda_lida'))[:60]!r})"
            )
            continue
        camadas_ok.append(
            {
                "legenda_lida": str(item.get("legenda_lida") or "")[:120],
                "cor_amostrada": str(item.get("cor_amostrada") or "")[:16],
                "estilo_sugerido": estilo,
                "confianca": _confianca(item.get("confianca")),
            }
        )

    metadados_ok: list[dict[str, str]] = []
    for m in bruto.get("metadados_lidos") or []:
        if isinstance(m, dict) and m.get("rotulo") and m.get("valor"):
            metadados_ok.append(
                {"rotulo": str(m["rotulo"])[:60], "valor": str(m["valor"])[:120]}
            )

    observacoes = [
        str(o)[:200] for o in (bruto.get("observacoes") or []) if isinstance(o, str) and o.strip()
    ][:10]

    analise = {
        "mapa_da_serie": mapa_da_serie,
        "ano": ano,
        "template_sugerido": template_sugerido,
        "confianca": _confianca(bruto.get("confianca")),
        "camadas": camadas_ok,
        "metadados_lidos": metadados_ok,
        "tabela_presente": bool(bruto.get("tabela_presente")),
        "observacoes": observacoes,
    }
    return analise, avisos


def _escolher_modelo_galeria(mapa_da_serie: str | None, orientacao: str | None) -> str | None:
    if mapa_da_serie is None:
        return None
    candidatos = MAPEAMENTO_SERIE_MODELO.get(mapa_da_serie) or []
    if not candidatos:
        return None
    if orientacao == "retrato":
        retrato = [c for c in candidatos if "retrato" in c]
        if retrato:
            return retrato[0]
    return candidatos[0]


def montar_proposta(
    *,
    analise: dict[str, Any] | None,
    avisos_sanitizacao: list[str],
    orientacao: str | None,
) -> dict[str, Any]:
    """Decide entre MapSpec candidato e perguntas — nunca os dois pela metade.

    Reusa `galeria.montar.montar_mapspec` (determinístico, já testado) em vez de
    reinventar a montagem do MapSpec — a análise de visão só escolhe QUAL modelo,
    a montagem em si é o mesmo caminho de `usar_modelo_da_galeria`.
    """
    avisos = list(avisos_sanitizacao)
    perguntas: list[str] = []
    mapspec_candidato: dict[str, Any] | None = None
    modelo_usado: str | None = None

    if analise is None:
        return {
            "mapa_da_serie": None,
            "ano": None,
            "template_sugerido": None,
            "confianca": None,
            "camadas": [],
            "metadados_lidos": [],
            "tabela_presente": False,
            "observacoes": [],
            "perguntas": [],
            "avisos": avisos,
            "mapspec_candidato": None,
            "modelo_galeria_usado": None,
        }

    if analise["confianca"] < LIMIAR_CONFIANCA or analise["mapa_da_serie"] is None:
        perguntas.append(
            "Não tenho certeza de qual mapa da série é este "
            f"(confiança {analise['confianca']:.2f}). É Dinâmica, Tipologia, "
            "Terras Indígenas ou Unidade de Conservação?"
        )
    else:
        modelo_id = _escolher_modelo_galeria(analise["mapa_da_serie"], orientacao)
        if modelo_id is None:
            avisos.append(
                f"sem modelo de galeria pronto para a série '{analise['mapa_da_serie']}'."
            )
            perguntas.append(
                f"Reconheci a série '{analise['mapa_da_serie']}', mas não tenho um modelo "
                "pronto pra ela ainda — quer que eu monte manualmente com criar_mapa?"
            )
        else:
            try:
                pacote = montar_mapspec(modelo_id)
            except ErroNucleo as exc:
                avisos.append(f"não consegui montar o modelo '{modelo_id}': {exc.mensagem}")
                perguntas.append(
                    f"Encontrei o modelo '{modelo_id}' para essa série, mas não consegui "
                    f"montar com os dados da pasta atual ({exc.mensagem}). Quer confirmar a "
                    "pasta ou seguir manualmente?"
                )
            else:
                mapspec_candidato = pacote["mapspec"]
                modelo_usado = modelo_id
                avisos.extend(pacote.get("avisos") or [])

    for camada in analise["camadas"]:
        if camada["confianca"] < LIMIAR_CONFIANCA:
            perguntas.append(
                f"Legenda '{camada['legenda_lida']}' (cor aproximada {camada['cor_amostrada']}): "
                f"qual estilo do catálogo é esse? Confiança baixa ({camada['confianca']:.2f})."
            )

    return {
        **analise,
        "perguntas": perguntas,
        "avisos": avisos,
        "mapspec_candidato": mapspec_candidato,
        "modelo_galeria_usado": modelo_usado,
    }
