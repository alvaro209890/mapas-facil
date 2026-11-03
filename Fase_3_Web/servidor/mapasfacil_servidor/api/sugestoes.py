"""Sugestões do chat vazio (W5-18).

Regra do plano: cada sugestão é **texto de mensagem** — o clique manda aquilo como se o
usuário tivesse digitado, sem endpoint paralelo e sem caminho especial no núcleo. Aqui só
se monta a lista; quem executa é o chat.

O que decide cada uma:

| Condição | Sugestão |
|---|---|
| sempre | "Faz a Dinâmica {ano corrente}" |
| o projeto tem AVN e AC | "Mapa de uso do solo com quantitativos" |
| sempre | "Série completa da Análise de área (20 mapas)" |
| imóvel alongado (razão do bbox > 1,6) e folha em retrato | "Qual folha deixa o mapa mais detalhado?" |
| o imóvel tem recibo do CAR lido | "Confere as áreas do CAR neste mapa" |

A razão do bbox só existe quando a indexação deixou `bbox` no resumo; sem ela a sugestão de
folha não aparece — melhor não sugerir do que sugerir no escuro.
"""

from __future__ import annotations

from datetime import date
from typing import Any

RAZAO_ALONGADO = 1.6
SERIE_COMPLETA = "Série completa da Análise de área (20 mapas)"


def _papeis(resumo: dict[str, Any] | None) -> set[str]:
    if not isinstance(resumo, dict):
        return set()
    workspace = resumo.get("workspace")
    if not isinstance(workspace, dict):
        workspace = resumo
    papeis: set[str] = set()
    for shp in workspace.get("shapefiles") or []:
        papel = shp.get("papel")
        if isinstance(papel, str) and papel:
            papeis.add(papel.upper())
    # o índice também guarda a contagem por papel
    contagem = resumo.get("papeis")
    if isinstance(contagem, dict):
        papeis.update(str(k).upper() for k, v in contagem.items() if v)
    return papeis


def _razao_bbox(resumo: dict[str, Any] | None) -> float | None:
    """Razão maior/menor lado do retângulo do imóvel (ATP, senão a primeira camada)."""
    if not isinstance(resumo, dict):
        return None
    workspace = resumo.get("workspace")
    if not isinstance(workspace, dict):
        workspace = resumo
    candidatos = [
        shp
        for shp in workspace.get("shapefiles") or []
        if isinstance(shp.get("bbox"), dict)
    ]
    if not candidatos:
        imovel = resumo.get("imovel")
        if isinstance(imovel, dict) and isinstance(imovel.get("bbox"), dict):
            candidatos = [{"bbox": imovel["bbox"]}]
    candidatos.sort(key=lambda s: 0 if str(s.get("papel") or "").upper() == "ATP" else 1)
    for shp in candidatos:
        bbox = shp["bbox"]
        try:
            largura = abs(float(bbox["xmax"]) - float(bbox["xmin"]))
            altura = abs(float(bbox["ymax"]) - float(bbox["ymin"]))
        except (KeyError, TypeError, ValueError):
            continue
        menor, maior = min(largura, altura), max(largura, altura)
        if menor <= 0:
            continue
        return maior / menor
    return None


def montar(
    *,
    folha: dict[str, Any] | None,
    resumo: dict[str, Any] | None,
    hoje: date | None = None,
) -> list[dict[str, Any]]:
    """Lista de sugestões, na ordem em que aparecem nos cartões do chat vazio."""
    ano = (hoje or date.today()).year
    papeis = _papeis(resumo)
    orientacao = str((folha or {}).get("orientacao") or "").strip().lower()

    sugestoes: list[dict[str, Any]] = [
        {
            "id": "dinamica",
            "texto": f"Faz a Dinâmica {ano}",
            "porque": "o mapa do ano corrente, que é o que quase todo processo pede",
        }
    ]
    if {"AVN", "AC"} <= papeis:
        sugestoes.append(
            {
                "id": "uso_do_solo",
                "texto": "Mapa de uso do solo com quantitativos",
                "porque": "as duas camadas de uso (AVN e AC) estão na pasta",
            }
        )
    sugestoes.append(
        {
            "id": "serie_completa",
            "texto": SERIE_COMPLETA,
            "porque": "a série inteira da Análise de área em um pedido",
        }
    )
    razao = _razao_bbox(resumo)
    if razao is not None and razao > RAZAO_ALONGADO and orientacao == "retrato":
        sugestoes.append(
            {
                "id": "qual_folha",
                "texto": "Qual folha deixa o mapa mais detalhado?",
                "porque": f"o imóvel é alongado (razão {razao:.2f}) e a folha atual é retrato",
            }
        )
    if isinstance(resumo, dict) and (resumo.get("imovel") or {}).get("car"):
        sugestoes.append(
            {
                "id": "conferir_car",
                "texto": "Confere as áreas do CAR neste mapa",
                "porque": "o recibo do CAR foi lido na importação",
            }
        )
    return sugestoes


# --------------------------------------------------------------------------- rota


from fastapi import APIRouter, Depends  # noqa: E402

from .. import projetos_repo  # noqa: E402
from ..auth import contas  # noqa: E402
from . import deps  # noqa: E402

router = APIRouter()


@router.get("/projetos/{projeto_id}/sugestoes")
def listar_sugestoes(
    projeto_id: str,
    con=Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
) -> dict:
    """Cartões do chat vazio: só texto, montado do que a importação já sabe."""
    projeto = projetos_repo.exigir(
        con, projeto_id, usuario_id=usuario.id, admin=usuario.papel == "admin"
    )
    linha = con.execute(
        "SELECT resumo FROM importacoes WHERE projeto_id = ? AND estado = 'pronto'"
        " ORDER BY criada_em DESC LIMIT 1",
        (projeto.id,),
    ).fetchone()
    resumo = None
    if linha is not None and linha["resumo"]:
        import json

        try:
            resumo = json.loads(linha["resumo"])
        except json.JSONDecodeError:
            resumo = None
    if isinstance(resumo, dict) and projeto.imovel:
        resumo.setdefault("imovel", projeto.imovel)
    return {"projeto_id": projeto.id, "sugestoes": montar(folha=projeto.folha, resumo=resumo)}
