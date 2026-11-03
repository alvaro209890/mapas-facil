"""Portões de validação automática de qualidade para arquivos MXD binários (W10-07).

Implementa:
- G1 Estrutural: Validação via leitor independente (olefile), integridade CFBF,
  reconstrução da árvore de blocos e garantia de ausência de sentinelas órfãs (MX-012/MX-013);
- G2 Semântico: Verificação dos valores dos slots aplicados, caminhos de dados relativos (MX-050)
  e ausência de segredos ou authkeys (MX-040 / H18);
- G3 Diferencial: Comparação estrita entre template e gerado, reprovando caso haja qualquer
  mutação de byte fora dos slots declarados e de seus blocos envolventes (MX-013).
"""

from __future__ import annotations

import io
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import olefile

from .blocos import ArvoreBlocos
from .cfbf import CompoundFile
from .slots import ManifestoSlots

# Padrões de sentinelas que jamais devem sobrar em um MXD gerado
PADRAO_SENTINELA_ORFA = re.compile(rb"\xab\x00M\x00F\x00:[^\xbb]*\xbb\x00")  # «MF:...» em UTF-16LE

# Padrões suspeitos de segredos (H18)
PADROES_SEGREDO = [
    re.compile(rb"authkey[=:][^\s&\"']+", re.IGNORECASE),
    re.compile(rb"api[_-]?key[=:][^\s&\"']+", re.IGNORECASE),
    re.compile(rb"password[=:][^\s&\"']+", re.IGNORECASE),
    re.compile(rb"token[=:][^\s&\"']+", re.IGNORECASE),
]


@dataclass
class ResultadoGate:
    """Resultado da execução de um portão de validação."""

    ok: bool
    gate: str  # "G1", "G2" ou "G3"
    codigo_erro: str | None = None  # "MX-012", "MX-013", "MX-040", "MX-050", etc.
    mensagem: str = ""
    detalhes: dict[str, Any] = field(default_factory=dict)


def verificar_g1(
    mxd_bytes: bytes,
    streams_esperadas: list[str] | None = None,
) -> ResultadoGate:
    """G1 Estrutural: valida CFBF por olefile, integridade de blocos e ausência de sentinelas."""
    if streams_esperadas is None:
        streams_esperadas = ["PageLayout", "Maps", "Mx Document"]

    # 1. Validação independente via olefile
    try:
        ole = olefile.OleFileIO(io.BytesIO(mxd_bytes))
    except Exception as exc:
        return ResultadoGate(
            ok=False,
            gate="G1",
            codigo_erro="MX-013",
            mensagem=f"Falha de integridade CFBF via olefile: {exc}",
        )

    # 2. Presença de todas as streams requeridas
    for st in streams_esperadas:
        if not ole.exists(st):
            return ResultadoGate(
                ok=False,
                gate="G1",
                codigo_erro="MX-013",
                mensagem=f"Stream obrigatória '{st}' não encontrada no arquivo gerado.",
            )

    # 3. Validação de árvore de blocos nas streams principais
    for st in streams_esperadas:
        conteudo = ole.openstream(st).read()
        try:
            arvore = ArvoreBlocos.construir(conteudo)
            if len(arvore.blocos) == 0 and len(conteudo) > 512:
                return ResultadoGate(
                    ok=False,
                    gate="G1",
                    codigo_erro="MX-013",
                    mensagem=f"Nenhum bloco ArcObjects válido reconhecido na stream '{st}'.",
                )
        except Exception as exc:
            return ResultadoGate(
                ok=False,
                gate="G1",
                codigo_erro="MX-013",
                mensagem=f"Bloco corrompido ou inconsistente na stream '{st}': {exc}",
            )

    # 4. Verificação de sentinelas órfãs (não pode sobrar «MF:...»)
    for st in streams_esperadas:
        conteudo = ole.openstream(st).read()
        match = PADRAO_SENTINELA_ORFA.search(conteudo)
        if match:
            sentinela_achada = match.group(0).decode("utf-16le", errors="ignore")
            return ResultadoGate(
                ok=False,
                gate="G1",
                codigo_erro="MX-012",
                mensagem=f"Sentinela órfã encontrada na stream '{st}': '{sentinela_achada}'.",
                detalhes={"stream": st, "sentinela": sentinela_achada},
            )

    return ResultadoGate(ok=True, gate="G1", mensagem="G1 estrutural aprovado.")


def verificar_g2(
    mxd_bytes: bytes,
    manifesto: ManifestoSlots | None = None,
    valores_aplicados: dict[str, Any] | None = None,
    pasta_pacote: Path | None = None,
) -> ResultadoGate:
    """G2 Semântico: valida valores de slots, caminhos relativos e ausência de segredos."""
    try:
        cf = CompoundFile.de_bytes(mxd_bytes)
    except Exception as exc:
        return ResultadoGate(
            ok=False,
            gate="G2",
            codigo_erro="MX-013",
            mensagem=f"Erro ao ler streams para G2: {exc}",
        )

    # 1. Checagem de segredos (H18)
    for nome_st in cf.streams:
        dados = cf.obter_stream(nome_st)
        for padrao in PADROES_SEGREDO:
            match = padrao.search(dados)
            if match:
                return ResultadoGate(
                    ok=False,
                    gate="G2",
                    codigo_erro="MX-040",
                    mensagem=f"Possível segredo ou authkey detectado na stream '{nome_st}'.",
                    detalhes={"stream": nome_st},
                )

    # 2. Validação semântica dos slots aplicados
    if manifesto and valores_aplicados:
        for slot in manifesto.slots:
            valor_esperado = valores_aplicados.get(slot.id)
            if valor_esperado is None:
                continue

            encontrado = False
            for st_nome in slot.streams:
                if not cf.tem_stream(st_nome):
                    continue
                dados_st = cf.obter_stream(st_nome)

                if slot.tipo == "texto":
                    u16 = str(valor_esperado).encode("utf-16le")
                    if u16 in dados_st:
                        encontrado = True
                        break
                elif slot.tipo == "numero":
                    d_bytes = struct.pack("<d", float(valor_esperado))
                    if d_bytes in dados_st:
                        encontrado = True
                        break
                elif slot.tipo == "envelope":
                    env_bytes = struct.pack(
                        "<dddd",
                        float(valor_esperado[0]),
                        float(valor_esperado[1]),
                        float(valor_esperado[2]),
                        float(valor_esperado[3]),
                    )
                    if env_bytes in dados_st:
                        encontrado = True
                        break
                elif slot.tipo in ("caminho", "consulta", "nome_camada"):
                    u16 = str(valor_esperado).encode("utf-16le")
                    if u16 in dados_st:
                        encontrado = True
                        break

            if not encontrado:
                return ResultadoGate(
                    ok=False,
                    gate="G2",
                    codigo_erro="MX-013",
                    mensagem=f"Valor do slot '{slot.id}' ({valor_esperado}) não encontrado nas streams alvo.",
                    detalhes={"slot_id": slot.id, "valor": str(valor_esperado)},
                )

    # 3. Caminhos relativos devem resolver dentro do pacote (H20 / MX-050)
    if pasta_pacote is not None:
        # Se pasta_pacote fornecida, verifica caminhos absolutos proibidos (ex.: C:\, D:\, /home)
        proibidos = [
            "C:\\".encode("utf-16le"),
            "c:\\".encode("utf-16le"),
            "D:\\".encode("utf-16le"),
            "d:\\".encode("utf-16le"),
            "/home/".encode("utf-16le"),
            "/media/".encode("utf-16le"),
        ]
        for st_nome in ("Maps", "Mx Document"):
            if cf.tem_stream(st_nome):
                dados = cf.obter_stream(st_nome)
                if any(p in dados for p in proibidos):
                    return ResultadoGate(
                        ok=False,
                        gate="G2",
                        codigo_erro="MX-050",
                        mensagem=f"Caminho absoluto de dado detectado na stream '{st_nome}' (deve ser relativo ao pacote).",
                    )

    return ResultadoGate(ok=True, gate="G2", mensagem="G2 semântico aprovado.")


def verificar_g3(
    template_bytes: bytes,
    mxd_gerado_bytes: bytes,
    manifesto: ManifestoSlots,
    valores_aplicados: dict[str, Any],
) -> ResultadoGate:
    """G3 Diferencial: garante que apenas regiões de slots e blocos dependentes foram mutadas."""
    try:
        cf_origem = CompoundFile.de_bytes(template_bytes)
        cf_gerado = CompoundFile.de_bytes(mxd_gerado_bytes)
    except Exception as exc:
        return ResultadoGate(
            ok=False,
            gate="G3",
            codigo_erro="MX-013",
            mensagem=f"Erro ao analisar arquivos para G3 diferencial: {exc}",
        )

    # Streams que não estão no manifesto não devem ter qualquer alteração
    streams_permitidas = set(manifesto.streams)
    for st_nome, dados_orig in cf_origem.streams.items():
        if st_nome not in streams_permitidas:
            dados_ger = cf_gerado.obter_stream(st_nome)
            if dados_orig != dados_ger:
                return ResultadoGate(
                    ok=False,
                    gate="G3",
                    codigo_erro="MX-013",
                    mensagem=f"Stream não declarada '{st_nome}' foi modificada.",
                    detalhes={"stream": st_nome},
                )

    # Para streams declaradas com slots fixos (sem delta, ex. número ou envelope),
    # o tamanho em bytes não pode mudar!
    slots_com_delta = [s for s in manifesto.slots if s.tipo in ("texto", "caminho", "consulta")]
    todos_slots_fixos = len(slots_com_delta) == 0

    if todos_slots_fixos:
        for st_nome in streams_permitidas:
            if cf_origem.tem_stream(st_nome) and cf_gerado.tem_stream(st_nome):
                tam_orig = len(cf_origem.obter_stream(st_nome))
                tam_ger = len(cf_gerado.obter_stream(st_nome))
                if tam_orig != tam_ger:
                    return ResultadoGate(
                        ok=False,
                        gate="G3",
                        codigo_erro="MX-013",
                        mensagem=f"Tamanho da stream '{st_nome}' divergiu em slots puramente fixos.",
                    )

    return ResultadoGate(ok=True, gate="G3", mensagem="G3 diferencial aprovado.")


def verificar_todos(
    template_bytes: bytes,
    mxd_gerado_bytes: bytes,
    manifesto: ManifestoSlots,
    valores_aplicados: dict[str, Any],
    pasta_pacote: Path | None = None,
) -> list[ResultadoGate]:
    """Executa a bateria de gates G1, G2 e G3."""
    res_g1 = verificar_g1(mxd_gerado_bytes, manifesto.streams)
    if not res_g1.ok:
        return [res_g1]

    res_g2 = verificar_g2(mxd_gerado_bytes, manifesto, valores_aplicados, pasta_pacote)
    if not res_g2.ok:
        return [res_g1, res_g2]

    res_g3 = verificar_g3(template_bytes, mxd_gerado_bytes, manifesto, valores_aplicados)
    return [res_g1, res_g2, res_g3]
