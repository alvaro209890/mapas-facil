# galeria.montar_mapspec — 13 passos determinísticos (F1-15 D5).

from __future__ import annotations

import re
import unicodedata
from typing import Any

from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.galeria.catalogo import obter_modelo
from mapasfacil_nucleo.galeria.estado import fontes_do_indice, papéis_presentes
from mapasfacil_nucleo.motores import manifesto
from mapasfacil_nucleo.protocolo import novo_id
from mapasfacil_nucleo.workspace import servico as workspace_servico

SOBRESCITAS_OK = frozenset({"titulo", "escala", "saidas", "mapeamento", "elementos_layout"})

ROTULO_COLUNA = {
    "ATP": "Área total da propriedade (ha)",
    "AVN": "Área de vegetação nativa (ha)",
    "AC": "Área consolidada (ha)",
    "AUAS": "Área Derivada de Desmate Após 2008 (ha)",
    "APP": "APP (ha)",
    "ARL": "ARL (ha)",
    "SIGEF": "SIGEF (ha)",
    "RESERVA_LEGAL": "Reserva legal (ha)",
}

ID_CAMADA = {
    "ATP": "perimetro",
    "AVN": "avn",
    "AC": "ac",
    "AUAS": "auas",
    "APP": "app",
    "ARL": "arl",
    "SIGEF": "sigef",
    "RESERVA_LEGAL": "reserva_legal",
}


def _ascii_nome(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    limpo = re.sub(r"[^A-Za-z0-9]+", "_", sem_acento).strip("_")
    return limpo or "Mapa"


def _resolver_nome(template: str, recibo: dict[str, Any] | None) -> str:
    if "{imovel.nome}" not in template:
        return template
    nome = (recibo or {}).get("nome_imovel") or "Imovel"
    return template.replace("{imovel.nome}", str(nome))


def _resolver_fonte(
    papel: str,
    indice: dict[str, Any],
    mapeamento: dict[str, str],
) -> str | None:
    if papel in mapeamento:
        fonte = mapeamento[papel]
        return fonte if fonte.startswith("local.") else f"local.{fonte}"
    fontes = fontes_do_indice(indice)
    if papel in fontes:
        return f"local.{papel}"
    # id_local que casa com o papel
    for shp in indice.get("shapefiles") or []:
        if shp.get("papel") == papel:
            return f"local.{shp['id_local']}"
    return None


def _valor_filtro(caminho: str, recibo: dict[str, Any] | None, imovel: dict[str, Any]) -> str | None:
    if caminho == "imovel.municipio.nome":
        return (imovel.get("municipio") or {}).get("nome") or (recibo or {}).get("municipio")
    if caminho == "imovel.municipio.uf":
        return (imovel.get("municipio") or {}).get("uf") or (recibo or {}).get("uf")
    return None


def montar_mapspec(
    modelo_id: str,
    *,
    workspace: str | None = None,
    sobrescritas: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Monta MapSpec determinístico. Não gera mapa."""
    sobrescritas = sobrescritas or {}
    extras = set(sobrescritas) - SOBRESCITAS_OK
    if extras:
        raise ErroNucleo(
            "NU-232",
            "sobrescritas com chave fora da allowlist.",
            {"chaves": sorted(extras)},
        )

    modelo = obter_modelo(modelo_id)

    # 2. template no MANIFEST + sha256
    try:
        info = manifesto.verificar_template(modelo["template"])
    except ErroNucleo as exc:
        raise ErroNucleo(
            "NU-231",
            f"Template do modelo ausente ou inacessível: {modelo['template']}",
            {"template": modelo["template"], "causa": exc.codigo},
        ) from exc
    if info.get("sha256") is None or info.get("status") == "a_preparar":
        raise ErroNucleo(
            "NU-231",
            f"Template ainda não preparado: {modelo['template']}",
            {"template": modelo["template"], "status": info.get("status")},
        )
    if not info.get("sha256_ok"):
        raise ErroNucleo(
            "NU-231",
            f"sha256 do template diverge do MANIFEST: {modelo['template']}",
            {"template": modelo["template"]},
        )

    tpl = manifesto.obter_template(modelo["template"])

    # 3–4. índice + recibo
    if workspace:
        aberto = workspace_servico.abrir(workspace)
    else:
        estado = workspace_servico.estado_atual()
        if estado is None:
            raise ErroNucleo("NU-040", "Nenhum workspace aberto. Use workspace.abrir primeiro.")
        aberto = {
            "workspace": estado.indice,
            "recibo": estado.recibo,
        }
    indice = aberto["workspace"]
    recibo = aberto.get("recibo")

    mapeamento = dict(sobrescritas.get("mapeamento") or {})
    avisos: list[str] = []
    camadas: list[dict[str, Any]] = []

    # 5. requisitos_camadas
    for req in modelo.get("requisitos_camadas") or []:
        papel = req["papel"]
        fonte = _resolver_fonte(papel, indice, mapeamento)
        if fonte is None:
            if req.get("obrigatorio"):
                raise ErroNucleo(
                    "NU-233",
                    f"Requisito obrigatório ausente no workspace: {papel}",
                    {"requisitos_faltando": [papel]},
                )
            avisos.append(f"camada opcional omitida: {papel}")
            continue
        nome = _resolver_nome(req["nome_no_mxd"], recibo if isinstance(recibo, dict) else None)
        camada: dict[str, Any] = {
            "id": ID_CAMADA.get(papel, papel.lower()),
            "nome_no_mxd": nome,
            "fonte": fonte,
            "estilo": req["estilo"],
            "legenda": nome,
            "ordem": req["ordem"],
        }
        if papel == "ATP":
            camada["rotulo_texto"] = nome
        camadas.append(camada)

    # imovel
    nome_imovel = (recibo or {}).get("nome_imovel") if isinstance(recibo, dict) else None
    municipio_nome = (recibo or {}).get("municipio") if isinstance(recibo, dict) else None
    uf = (recibo or {}).get("uf") if isinstance(recibo, dict) else None
    car = (recibo or {}).get("car_estadual") if isinstance(recibo, dict) else None
    area = (recibo or {}).get("area_total_ha") if isinstance(recibo, dict) else None
    fonte_geo = next((c["fonte"] for c in camadas if c["id"] == "perimetro"), None)

    imovel: dict[str, Any] = {
        "nome": nome_imovel or "Imovel",
        "car": car,
        "matricula": None,
        "area_total_ha": area,
        "municipio": {
            "nome": municipio_nome or "Desconhecido",
            "uf": (uf or "MT")[:2],
        },
        "geometria": fonte_geo,
    }
    # ibge só entra se conhecido — o schema não aceita null.

    # 6. camadas_catalogo
    for cat in modelo.get("camadas_catalogo") or []:
        camada_cat: dict[str, Any] = {
            "id": cat["fonte"].split(".", 1)[-1],
            "nome_no_mxd": cat["nome_no_mxd"],
            "fonte": cat["fonte"],
            "estilo": cat["estilo"],
            "legenda": cat["nome_no_mxd"],
            "ordem": cat["ordem"],
        }
        filtro_de = cat.get("filtro_de")
        if filtro_de:
            valor = _valor_filtro(filtro_de, recibo if isinstance(recibo, dict) else None, imovel)
            if valor:
                campo = "nome" if filtro_de.endswith(".nome") else "uf"
                camada_cat["filtro"] = {"campo": campo, "operador": "=", "valor": valor}
            else:
                avisos.append(f"filtro {filtro_de} sem valor — camada de catálogo sem filtro")
        camadas.append(camada_cat)

    # 7. CRS
    crs = tpl.get("crs_data_frame") or "EPSG:31982"

    # 8. escala
    escala = sobrescritas.get("escala", modelo.get("escala_padrao", "auto"))

    # 9. tabela
    colunas_de = list((modelo.get("tabela_padrao") or {}).get("colunas_de") or [])
    colunas = ["Propriedade"] + [ROTULO_COLUNA.get(p, p) for p in colunas_de]
    tabela = {
        "titulo_bloco": None,
        "colunas": colunas,
        "linhas": [],
        "total_geral": bool((modelo.get("tabela_padrao") or {}).get("total_geral", True)),
        "casas_decimais": int((modelo.get("tabela_padrao") or {}).get("casas_decimais", 4)),
    }

    # 10. metadados
    metadados = [dict(m) for m in modelo.get("metadados_padrao") or []]

    # 11. saida
    ano = "2026"
    nome_base = _ascii_nome(f"{modelo['nome']}_{ano}")

    # elementos_layout
    elementos = dict(modelo.get("elementos_layout_padrao") or {})
    if isinstance(sobrescritas.get("elementos_layout"), dict):
        elementos.update(sobrescritas["elementos_layout"])

    saidas = sobrescritas.get("saidas") or list(modelo.get("saidas_padrao") or ["pdf"])
    titulo = sobrescritas.get("titulo") or modelo["nome"]

    # 12. id ULID
    mapspec: dict[str, Any] = {
        "contract_version": 2,
        "perfil": "harmonia",
        "id": novo_id(),
        "versao": 1,
        "parent_id": None,
        "titulo": titulo,
        "template": modelo["template"],
        "saidas": saidas,
        "imovel": imovel,
        "crs": crs,
        "escala": escala,
        "extent": None,
        "camadas": camadas,
        "basemap": dict(modelo.get("basemap_padrao") or {"tipo": "planet_mensal"}),
        "elementos_layout": elementos,
        "metadados": metadados,
        "tabela": tabela,
        "saida": {
            "pasta": "Mapas",
            "nome_base": nome_base,
            "caminhos_relativos": True,
            "materializar_camadas_em": "SHP",
        },
    }

    return {"mapspec": mapspec, "avisos": avisos}
