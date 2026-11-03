"""Motion — contrato dos três eventos que alimentam o palco (W7-01 / W-03 §Eventos novos).

O palco da web **não inventa animação**: cada passo (câmera voando, camada acendendo, elemento
entrando na folha) só existe porque o núcleo emitiu um destes três eventos. Por isso a validação
mora aqui, em funções **puras** — erro de dado é erro de programação do emissor, não do usuário,
e tem de estourar no teste, não na tela.

| Evento | Quando é real | Quem emite |
|---|---|---|
| `viewport.foco` | o núcleo **passou a saber** onde está o assunto (UF, município, perímetro, escala decidida, folha) | `motores/gerar.py`, `camadas/materializar.py`, `workspace/servico.py` |
| `camada.renderizada` | uma camada ficou **pronta para desenhar** (lida, recortada, reprojetada) | `camadas/materializar.py` |
| `layout.elemento` | o motor nativo **posicionou** um elemento da folha | `motores/nativo.py` |

Regras que este módulo garante (todas testadas em `tests/test_motion_contrato.py`):

* `nivel` de `viewport.foco` só anda para frente (`estado → municipio → imovel → enquadramento →
  folha`); voltar atrás é bug — quem chama passa o nível anterior;
* fora de job (`job_id is None`) só existe `estado` / `municipio` / `imovel`, e `etapa` é `None`;
* `bbox_4326` é `[oeste, sul, leste, norte]`, finito, com `oeste < leste`, `sul < norte`, dentro de
  `[-180,180] × [-90,90]`;
* `caminho` é **sempre relativo** e sempre sob `Mapas/.preview/<job_id>/` — caminho absoluto vaza
  o disco (`C:\\Users\\...`, `/home/...`) e é recusado aqui, não "filtrado na tela";
* `elemento` tem de ser um dos que o layout do MapSpec conhece;
* a **ordem de acendimento** das camadas é a do padrão do escritório (`PRIORIDADE_PAPEL`):
  perímetro → AVN → AC → hidrografia → AUAS → demais locais → externas → basemap. Não é estética:
  é a ordem de pintura do PDF, e o palco não pode mostrar diferente do que vai ser entregue.
"""

from __future__ import annotations

import math
from pathlib import PurePosixPath
from typing import Any, Final, Iterable

from mapasfacil_nucleo.progresso import IDS_ETAPAS

EVENTO_VIEWPORT: Final = "viewport.foco"
EVENTO_CAMADA: Final = "camada.renderizada"
EVENTO_LAYOUT: Final = "layout.elemento"

EVENTOS: Final[tuple[str, ...]] = (EVENTO_VIEWPORT, EVENTO_CAMADA, EVENTO_LAYOUT)

# Níveis da câmera, em ordem. Dentro de um job a sequência não volta (pode pular).
NIVEIS_VIEWPORT: Final[tuple[str, ...]] = (
    "estado",
    "municipio",
    "imovel",
    "enquadramento",
    "folha",
)
# Fora de job (indexação da importação) a câmera só conhece estes três.
NIVEIS_SEM_JOB: Final[tuple[str, ...]] = ("estado", "municipio", "imovel")

ORIGENS_VIEWPORT: Final[tuple[str, ...]] = (
    "ibge",
    "recibo_car",
    "geometria_local",
    "calculo_escala",
    "perfil_pagina",
)

GEOMETRIAS: Final[tuple[str, ...]] = ("poligono", "linha", "ponto", "raster")

PADROES: Final[tuple[str, ...]] = ("solido", "hachura", "vazado")

# Ordem de acendimento = ordem de pintura do padrão Harmonia.
PRIORIDADE_PAPEL: Final[tuple[str, ...]] = (
    "perimetro",
    "avn",
    "ac",
    "hidrografia",
    "hidro_poligono",
    "hidro_linha",
    "auas",
    "app",
    "appd",
    "apprl",
    "arl",
    "air",
    "nascente",
    "vereda",
    "aurd",
    "tipologia",
    "area_uso_restrito",
    "area_umida",
    "area_abrangencia",
    "externa",
    "basemap",
)

# Papel que não está na tabela vai para o fim da fila de locais (nunca para depois do basemap).
_PRIORIDADE: Final[dict[str, int]] = {papel: i for i, papel in enumerate(PRIORIDADE_PAPEL)}
_FIM_LOCAIS: Final[int] = _PRIORIDADE["externa"]
_PRIORIDADE_BASEMAP: Final[int] = _PRIORIDADE["basemap"]

# Elementos que o layout do MapSpec conhece (espelho de `agente/tools.py::ELEMENTOS_LAYOUT`,
# repetido aqui para `motion` não importar o agente — o agente importa o motor, não o contrário).
ELEMENTOS: Final[tuple[str, ...]] = (
    "creditos",
    "escala_grafica",
    "grade",
    "grade_linhas",
    "legenda",
    "logo",
    "metadados",
    "minimapa",
    "norte",
    "tabela",
    "titulo_caixa",
)

# Elemento do MapSpec → caixa do `perfil_pagina` onde ele é desenhado. Elemento sem caixa
# própria (créditos, escala gráfica) mora dentro de outra: o palco mostra no lugar certo.
ELEMENTO_PARA_CAIXA: Final[dict[str, str]] = {
    "titulo_caixa": "titulo",
    "norte": "rosa",
    "minimapa": "minimapa",
    "metadados": "metadados",
    "escala_grafica": "metadados",
    "creditos": "metadados",
    "legenda": "legenda",
    "tabela": "tabela",
    "logo": "logo",
    "grade": "mapa",
    "grade_linhas": "mapa",
}

# Ordem em que o motor nativo desenha a folha — é a ordem em que o palco monta.
# Espelha a ordem real de desenho de `motores/nativo.py`: moldura/grade, título, rosa,
# metadados (com escala gráfica e créditos), legenda, minimapa, logo, tabela.
ORDEM_LAYOUT: Final[tuple[str, ...]] = (
    "grade",
    "grade_linhas",
    "titulo_caixa",
    "norte",
    "metadados",
    "escala_grafica",
    "creditos",
    "legenda",
    "minimapa",
    "logo",
    "tabela",
)

FORMATOS_FOLHA: Final[tuple[str, ...]] = ("A4", "A3", "A2", "A1", "A0")
ORIENTACOES: Final[tuple[str, ...]] = ("retrato", "paisagem")

ROTULO_MAX = 120
_NOME_MAX = 120
_CAMADAS_MIN = 0


class MotionInvalido(ValueError):
    """Erro de programação: dado de evento de palco fora do contrato de W-03."""


# ---------------------------------------------------------------- utilitários
def prioridade_do_papel(papel: str) -> int:
    """Posição do papel na fila de acendimento (menor acende antes)."""
    chave = str(papel or "").strip().lower()
    if chave in _PRIORIDADE:
        return _PRIORIDADE[chave]
    if chave.startswith("externa"):
        return _PRIORIDADE["externa"]
    # Desconhecido: depois dos locais, antes do basemap.
    return _FIM_LOCAIS


def ordem_desenho(papel: str, ordem_mapspec: int | None = None) -> int:
    """`ordem_desenho` do evento: prioridade do papel, desempatada pela ordem do MapSpec."""
    base = prioridade_do_papel(papel) * 1000
    extra = 0 if ordem_mapspec is None else max(0, min(999, int(ordem_mapspec)))
    return base + extra


def ordenar_por_papel(papeis: Iterable[str]) -> list[str]:
    """Ordena uma lista de papéis pela fila de acendimento (estável)."""
    return sorted(papeis, key=lambda p: (prioridade_do_papel(p), str(p)))


def _numero(valor: Any, campo: str) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise MotionInvalido(f"{campo} tem de ser número, veio {valor!r}.")
    if not math.isfinite(float(valor)):
        raise MotionInvalido(f"{campo} não pode ser NaN/infinito.")
    return float(valor)


def _inteiro(valor: Any, campo: str, *, minimo: int = 0) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise MotionInvalido(f"{campo} tem de ser inteiro, veio {valor!r}.")
    if valor < minimo:
        raise MotionInvalido(f"{campo} tem de ser >= {minimo}, veio {valor!r}.")
    return valor


def _texto(valor: Any, campo: str, *, maximo: int = _NOME_MAX, vazio_ok: bool = False) -> str:
    if not isinstance(valor, str):
        raise MotionInvalido(f"{campo} tem de ser texto, veio {valor!r}.")
    texto = valor.strip()
    if not texto and not vazio_ok:
        raise MotionInvalido(f"{campo} não pode ser vazio.")
    if len(texto) > maximo:
        raise MotionInvalido(f"{campo} passa de {maximo} caracteres.")
    return texto


def _etapa(etapa: Any, *, job_id: str | None) -> str | None:
    if etapa is None:
        if job_id is not None:
            raise MotionInvalido("Evento de palco dentro de job precisa de 'etapa'.")
        return None
    if etapa not in IDS_ETAPAS:
        raise MotionInvalido(f"Etapa fora do contrato de job.progresso: {etapa!r}.")
    return str(etapa)


def _job_id(job_id: Any) -> str | None:
    if job_id is None:
        return None
    return _texto(job_id, "job_id", maximo=64)


def bbox_4326(bbox: Any, campo: str = "bbox_4326") -> list[float]:
    """`[oeste, sul, leste, norte]` válido, arredondado a 6 casas (o palco não precisa mais)."""
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        raise MotionInvalido(f"{campo} tem de ter 4 números [oeste, sul, leste, norte].")
    oeste, sul, leste, norte = (_numero(v, campo) for v in bbox)
    if not (-180.0 <= oeste <= 180.0 and -180.0 <= leste <= 180.0):
        raise MotionInvalido(f"{campo}: longitude fora de [-180, 180].")
    if not (-90.0 <= sul <= 90.0 and -90.0 <= norte <= 90.0):
        raise MotionInvalido(f"{campo}: latitude fora de [-90, 90].")
    if oeste >= leste:
        raise MotionInvalido(f"{campo}: oeste ({oeste}) tem de ser menor que leste ({leste}).")
    if sul >= norte:
        raise MotionInvalido(f"{campo}: sul ({sul}) tem de ser menor que norte ({norte}).")
    return [round(oeste, 6), round(sul, 6), round(leste, 6), round(norte, 6)]


def caminho_de_palco(
    caminho: Any, *, job_id: str | None, exigido: bool = True
) -> str | None:
    """Caminho relativo sob `Mapas/.preview/<job_id>/` — ou `None` quando não há arquivo.

    Absoluto é recusado (não normalizado): quem montou o caminho errado tem de ver o erro aqui.
    """
    if caminho is None:
        if exigido:
            raise MotionInvalido("Evento de palco com arquivo precisa de 'caminho'.")
        return None
    texto = str(caminho).replace("\\", "/").strip()
    if not texto:
        if exigido:
            raise MotionInvalido("'caminho' vazio.")
        return None
    if texto.startswith("/") or (len(texto) > 1 and texto[1] == ":"):
        raise MotionInvalido(f"Caminho absoluto em evento de palco: {caminho!r}.")
    partes = PurePosixPath(texto).parts
    if ".." in partes:
        raise MotionInvalido(f"'caminho' com '..': {caminho!r}.")
    if job_id is not None:
        prefixo = ("Mapas", ".preview", job_id)
        if partes[:3] != prefixo:
            raise MotionInvalido(
                f"'caminho' tem de começar em {'/'.join(prefixo)}/, veio {texto!r}."
            )
    if len(partes) < 4:
        raise MotionInvalido(f"'caminho' sem arquivo: {texto!r}.")
    return PurePosixPath(*partes).as_posix()


def estilo_do_padrao(estilo: dict[str, Any] | None, *, papel: str = "") -> dict[str, Any]:
    """Normaliza o `estilo` do evento para o que o MapLibre precisa.

    `{preenchimento: "#RRGGBBAA" | None, contorno: "#RRGGBB", espessura_pt: float,
    padrao: "solido" | "hachura" | "vazado"}`.

    Aceita o dicionário no formato do evento ou o formato interno de `motores/estilos.py`
    (`cor_linha`, `cor_preenchimento`, `hachura`, `largura`) — o emissor não precisa traduzir.
    """
    dados = dict(estilo or {})
    contorno = dados.get("contorno") or dados.get("cor_linha") or "#FFFF00"
    preenchimento = dados.get("preenchimento", dados.get("cor_preenchimento"))
    espessura = dados.get("espessura_pt", dados.get("largura", 1.0))
    padrao = dados.get("padrao")
    if padrao is None:
        if dados.get("hachura"):
            padrao = "hachura"
        elif preenchimento in (None, "", "none"):
            padrao = "vazado"
        else:
            padrao = "solido"
    if padrao not in PADROES:
        raise MotionInvalido(f"padrao fora do contrato: {padrao!r}.")
    return {
        "preenchimento": None if preenchimento in (None, "", "none") else str(preenchimento),
        "contorno": str(contorno),
        "espessura_pt": round(_numero(espessura, "espessura_pt"), 3),
        "padrao": str(padrao),
    }


# ------------------------------------------------------------ viewport.foco
def montar_dados_viewport(
    nivel: str,
    bbox: Any,
    rotulo: str,
    origem: str,
    *,
    job_id: str | None = None,
    etapa: str | None = None,
    escala: int | None = None,
    crs_mapa: str | None = None,
    quadro_mm: dict[str, Any] | tuple[float, float] | None = None,
    nivel_anterior: str | None = None,
) -> dict[str, Any]:
    """`dados` de `viewport.foco`, validado.

    `nivel_anterior` é o último nível emitido no mesmo job: voltar atrás levanta — a câmera do
    palco nunca desce e depois sobe no meio do mesmo job.
    """
    if nivel not in NIVEIS_VIEWPORT:
        raise MotionInvalido(f"Nível de viewport fora do contrato: {nivel!r}.")
    jid = _job_id(job_id)
    if jid is None and nivel not in NIVEIS_SEM_JOB:
        raise MotionInvalido(
            f"Nível {nivel!r} só existe dentro de job (fora de job: {list(NIVEIS_SEM_JOB)})."
        )
    if nivel_anterior is not None:
        if nivel_anterior not in NIVEIS_VIEWPORT:
            raise MotionInvalido(f"Nível anterior desconhecido: {nivel_anterior!r}.")
        if NIVEIS_VIEWPORT.index(nivel) < NIVEIS_VIEWPORT.index(nivel_anterior):
            raise MotionInvalido(
                f"viewport.foco voltou de {nivel_anterior!r} para {nivel!r} no mesmo job."
            )
    if origem not in ORIGENS_VIEWPORT:
        raise MotionInvalido(f"Origem de viewport fora do contrato: {origem!r}.")

    dados: dict[str, Any] = {
        "job_id": jid,
        "nivel": nivel,
        "bbox_4326": bbox_4326(bbox),
        "rotulo": _texto(rotulo, "rotulo", maximo=ROTULO_MAX),
        "origem": origem,
        "etapa": _etapa(etapa, job_id=jid),
        "escala": None,
        "crs_mapa": None,
        "quadro_mm": None,
    }

    if escala is not None:
        if nivel != "enquadramento":
            raise MotionInvalido("'escala' só vai em viewport.foco de nível 'enquadramento'.")
        dados["escala"] = _inteiro(escala, "escala", minimo=1)
    if crs_mapa is not None:
        if nivel != "enquadramento":
            raise MotionInvalido("'crs_mapa' só vai em viewport.foco de nível 'enquadramento'.")
        texto = _texto(crs_mapa, "crs_mapa", maximo=20)
        if not texto.upper().startswith("EPSG:"):
            raise MotionInvalido(f"crs_mapa tem de ser 'EPSG:xxxx', veio {crs_mapa!r}.")
        dados["crs_mapa"] = texto.upper()
    if quadro_mm is not None:
        if nivel not in ("enquadramento", "folha"):
            raise MotionInvalido(
                "'quadro_mm' só vai em viewport.foco de nível 'enquadramento' ou 'folha'."
            )
        if isinstance(quadro_mm, dict):
            largura = _numero(quadro_mm.get("largura"), "quadro_mm.largura")
            altura = _numero(quadro_mm.get("altura"), "quadro_mm.altura")
        else:
            if len(tuple(quadro_mm)) != 2:
                raise MotionInvalido("quadro_mm tem de ter largura e altura.")
            largura, altura = (_numero(v, "quadro_mm") for v in quadro_mm)
        if largura <= 0 or altura <= 0:
            raise MotionInvalido("quadro_mm com dimensão não positiva.")
        dados["quadro_mm"] = {"largura": round(largura, 2), "altura": round(altura, 2)}
    return dados


# -------------------------------------------------------- camada.renderizada
def montar_dados_camada(
    camada_id: str,
    papel: str,
    nome: str,
    geometria: str,
    *,
    sequencia: int,
    total: int,
    caminho: Any,
    job_id: str | None = None,
    etapa: str | None = "resolvendo_camadas_locais",
    bbox: Any = None,
    estilo: dict[str, Any] | None = None,
    n_feicoes: int = 0,
    area_ha: float | None = None,
    ordem_mapspec: int | None = None,
) -> dict[str, Any]:
    """`dados` de `camada.renderizada`, validado.

    `total` pode **crescer** depois (chegam as externas); a UI aceita `sequencia <= total` sempre.
    """
    if geometria not in GEOMETRIAS:
        raise MotionInvalido(f"Geometria fora do contrato: {geometria!r}.")
    jid = _job_id(job_id)
    seq = _inteiro(sequencia, "sequencia", minimo=1)
    tot = _inteiro(total, "total", minimo=1)
    if seq > tot:
        raise MotionInvalido(f"sequencia ({seq}) maior que total ({tot}).")

    dados: dict[str, Any] = {
        "job_id": jid,
        "camada_id": _texto(camada_id, "camada_id", maximo=64),
        "papel": _texto(papel, "papel", maximo=64),
        "nome": _texto(nome, "nome", maximo=_NOME_MAX),
        "geometria": geometria,
        "sequencia": seq,
        "total": tot,
        "ordem_desenho": ordem_desenho(papel, ordem_mapspec),
        "caminho": caminho_de_palco(caminho, job_id=jid),
        "bbox_4326": bbox_4326(bbox) if bbox is not None else None,
        "estilo": estilo_do_padrao(estilo, papel=papel),
        "n_feicoes": _inteiro(n_feicoes, "n_feicoes", minimo=0),
        "area_ha": None,
        "etapa": _etapa(etapa, job_id=jid),
    }
    if geometria == "raster" and dados["bbox_4326"] is None:
        raise MotionInvalido("Camada raster precisa de 'bbox_4326' para o palco encaixar o PNG.")
    if area_ha is not None:
        if geometria != "poligono":
            raise MotionInvalido("'area_ha' só vale para camada de polígono.")
        valor = _numero(area_ha, "area_ha")
        if valor < 0:
            raise MotionInvalido("'area_ha' não pode ser negativo.")
        dados["area_ha"] = round(valor, 4)
    return dados


def elementos_na_ordem(elementos: Iterable[str]) -> list[str]:
    """Filtra e ordena os elementos ligados na ordem de montagem da folha."""
    pedidos = {str(e) for e in elementos}
    return [e for e in ORDEM_LAYOUT if e in pedidos]


def caixa_do_elemento(perfil: Any, elemento: str) -> dict[str, float]:
    """`caixa_mm` do elemento no perfil da página (mm, origem no topo-esquerda)."""
    chave = ELEMENTO_PARA_CAIXA.get(elemento)
    if chave is None:
        raise MotionInvalido(f"Elemento sem caixa no perfil: {elemento!r}.")
    caixa = getattr(perfil, chave, None)
    if caixa is None:
        raise MotionInvalido(f"Perfil sem a caixa {chave!r} (elemento {elemento!r}).")
    return {"x0": caixa.x0, "y0": caixa.y0, "x1": caixa.x1, "y1": caixa.y1}


# ----------------------------------------------------------- layout.elemento
def montar_dados_layout(
    elemento: str,
    *,
    sequencia: int,
    total: int,
    folha: dict[str, Any],
    caixa_mm: dict[str, Any] | tuple[float, float, float, float],
    job_id: str | None = None,
    etapa: str | None = "aplicando_layout",
    caminho: Any = None,
    conteudo: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
    """`dados` de `layout.elemento`: onde o elemento caiu na folha, em mm reais."""
    if elemento not in ELEMENTOS:
        raise MotionInvalido(f"Elemento fora do contrato de layout: {elemento!r}.")
    jid = _job_id(job_id)
    seq = _inteiro(sequencia, "sequencia", minimo=1)
    tot = _inteiro(total, "total", minimo=1)
    if seq > tot:
        raise MotionInvalido(f"sequencia ({seq}) maior que total ({tot}).")

    formato = str((folha or {}).get("formato") or "").upper()
    if formato not in FORMATOS_FOLHA:
        raise MotionInvalido(f"folha.formato fora do contrato: {formato!r}.")
    orientacao = str((folha or {}).get("orientacao") or "").lower()
    if orientacao not in ORIENTACOES:
        raise MotionInvalido(f"folha.orientacao fora do contrato: {orientacao!r}.")
    largura_mm = _numero(folha.get("largura_mm"), "folha.largura_mm")
    altura_mm = _numero(folha.get("altura_mm"), "folha.altura_mm")
    if largura_mm <= 0 or altura_mm <= 0:
        raise MotionInvalido("folha com dimensão não positiva.")

    if isinstance(caixa_mm, dict):
        x0 = _numero(caixa_mm.get("x0"), "caixa_mm.x0")
        y0 = _numero(caixa_mm.get("y0"), "caixa_mm.y0")
        x1 = _numero(caixa_mm.get("x1"), "caixa_mm.x1")
        y1 = _numero(caixa_mm.get("y1"), "caixa_mm.y1")
    else:
        if len(tuple(caixa_mm)) != 4:
            raise MotionInvalido("caixa_mm tem de ter x0, y0, x1, y1.")
        x0, y0, x1, y1 = (_numero(v, "caixa_mm") for v in caixa_mm)
    if x1 <= x0 or y1 <= y0:
        raise MotionInvalido("caixa_mm com área zero ou invertida.")
    if x1 > largura_mm + 0.5 or y1 > altura_mm + 0.5:
        raise MotionInvalido("caixa_mm fora da folha.")

    return {
        "job_id": jid,
        "elemento": elemento,
        "sequencia": seq,
        "total": tot,
        "folha": {
            "formato": formato,
            "orientacao": orientacao,
            "largura_mm": round(largura_mm, 1),
            "altura_mm": round(altura_mm, 1),
        },
        "caixa_mm": {
            "x0": round(x0, 2),
            "y0": round(y0, 2),
            "x1": round(x1, 2),
            "y1": round(y1, 2),
        },
        "conteudo": _conteudo(conteudo),
        "caminho": caminho_de_palco(caminho, job_id=jid, exigido=False),
        "etapa": _etapa(etapa, job_id=jid),
    }


def _conteudo(conteudo: Any) -> dict[str, Any] | str | None:
    """`conteudo` é texto curto (título, linhas de metadados) ou dicionário pequeno.

    Teto de tamanho porque este dado vai no SSE: mandar a legenda inteira do mapa num evento é
    o mesmo erro de mandar o GeoJSON (AW-04) — o desenho do elemento vem do `caminho`.
    """
    if conteudo is None:
        return None
    if isinstance(conteudo, str):
        return conteudo[:500]
    if isinstance(conteudo, dict):
        bruto = repr(conteudo)
        if len(bruto) > 2000:
            raise MotionInvalido("'conteudo' de layout.elemento passou de 2 kB.")
        return conteudo
    raise MotionInvalido(f"'conteudo' tem de ser texto, dicionário ou nulo, veio {type(conteudo)}.")
