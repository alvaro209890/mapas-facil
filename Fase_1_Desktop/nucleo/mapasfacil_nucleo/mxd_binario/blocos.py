"""Parser e manipulador da hierarquia de blocos e serialização ArcObjects (.mxd).

Responsável por (W10-03 / W-08 §Contratos):
1. Construir a árvore de blocos delimitados por `0xFF 0xFF 0xFF 0xFF` + `uint64`;
2. Manter a hierarquia pai/filho para recalcular tamanhos ao expandir/encolher conteúdo;
3. Localizar strings UTF-16LE com prefixo `uint32` de comprimento;
4. Identificar elementos de texto no `PageLayout` e camadas/dataframes no `Maps`.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Any

# Marcador padrão de início de bloco serializado ArcObjects
MARCADOR_BLOCO = b"\xff\xff\xff\xff"


@dataclass
class Bloco:
    """Nó da árvore de blocos serializados ArcObjects."""

    offset_marcador: int
    offset_tamanho: int
    offset_payload: int
    tamanho_payload: int
    fim: int
    pai: Bloco | None = None
    filhos: list[Bloco] = field(default_factory=list)

    def contem(self, offset: int) -> bool:
        """Verifica se um determinado offset está contido dentro do payload deste bloco."""
        return self.offset_payload <= offset < self.fim


@dataclass
class ArvoreBlocos:
    """Árvore hierárquica de blocos de uma stream ArcObjects."""

    blocos: list[Bloco] = field(default_factory=list)
    tamanho_stream: int = 0

    @classmethod
    def construir(cls, dados: bytes | bytearray) -> ArvoreBlocos:
        """Varre os dados binários da stream e constrói a árvore de blocos."""
        n = len(dados)
        pos = 0
        blocos_planos: list[Bloco] = []

        while pos <= n - 12:
            idx = dados.find(MARCADOR_BLOCO, pos)
            if idx == -1 or idx + 12 > n:
                break
            # Lê uint64 little-endian (tamanho do payload do bloco)
            tam_payload = struct.unpack_from("<Q", dados, idx + 4)[0]
            # Validação de sanidade: tamanho positivo e não ultrapassa a stream
            if 0 < tam_payload <= (n - (idx + 12)):
                offset_payload = idx + 12
                fim = offset_payload + tam_payload
                bloco = Bloco(
                    offset_marcador=idx,
                    offset_tamanho=idx + 4,
                    offset_payload=offset_payload,
                    tamanho_payload=tam_payload,
                    fim=fim,
                )
                blocos_planos.append(bloco)
            pos = idx + 4

        # Constrói a hierarquia (ordenando por offset e tamanho)
        # Blocos maiores que englobam outros viram pais
        blocos_planos.sort(key=lambda b: (b.offset_marcador, -b.tamanho_payload))
        raizes: list[Bloco] = []
        pilha: list[Bloco] = []

        for b in blocos_planos:
            while pilha and (b.offset_marcador >= pilha[-1].fim):
                pilha.pop()
            if pilha:
                pai = pilha[-1]
                if b.fim <= pai.fim:
                    b.pai = pai
                    pai.filhos.append(b)
                else:
                    raizes.append(b)
            else:
                raizes.append(b)
            pilha.append(b)

        return cls(blocos=raizes, tamanho_stream=n)

    def ancestrais_de_offset(self, offset: int) -> list[Bloco]:
        """Devolve os blocos que contêm o offset, do mais interno para a raiz."""
        resultado: list[Bloco] = []

        def _buscar(nos: list[Bloco]) -> bool:
            for b in nos:
                if b.contem(offset):
                    resultado.append(b)
                    # Busca nos filhos para encontrar nós mais específicos
                    _buscar(b.filhos)
                    return True
            return False

        _buscar(self.blocos)
        resultado.reverse()  # Mais interno primeiro
        return resultado

    def ajustar_delta_tamanho(
        self,
        offset_modificado: int,
        delta_bytes: int,
        dados: bytearray,
    ) -> list[tuple[int, int, int]]:
        """Atualiza o uint64 de todos os blocos ancestrais do offset modificado.

        Devolve lista de (offset_tamanho, tamanho_antigo, novo_tamanho).
        """
        modificacoes: list[tuple[int, int, int]] = []
        if delta_bytes == 0:
            return modificacoes

        ancestrais = self.ancestrais_de_offset(offset_modificado)
        for b in ancestrais:
            antigo = b.tamanho_payload
            novo = antigo + delta_bytes
            struct.pack_into("<Q", dados, b.offset_tamanho, novo)
            b.tamanho_payload = novo
            b.fim += delta_bytes
            modificacoes.append((b.offset_tamanho, antigo, novo))

        return modificacoes


# ------------------------------------------------------------------ Varredura ArcObjects


def extrair_strings_utf16(
    dados: bytes | bytearray,
    min_chars: int = 2,
    max_chars: int = 500,
) -> list[tuple[int, int, str]]:
    """Localiza strings UTF-16LE precedidas por seu uint32 de comprimento em bytes.

    Retorna lista de (offset_uint32, offset_string, texto).
    """
    n = len(dados)
    strings_encontradas: list[tuple[int, int, str]] = []
    pos = 0

    while pos <= n - 6:
        # Lê comprimento declarado em bytes
        tam_bytes = struct.unpack_from("<I", dados, pos)[0]
        # Uma string UTF-16LE válida tem tamanho par, termina com \x00\x00 e cabe na stream
        if (
            (min_chars * 2) <= tam_bytes <= (max_chars * 2)
            and tam_bytes % 2 == 0
            and (pos + 4 + tam_bytes) <= n
        ):
            trecho = dados[pos + 4 : pos + 4 + tam_bytes]
            if trecho.endswith(b"\x00\x00"):
                try:
                    txt = trecho[:-2].decode("utf-16le")
                    # Aceita apenas textos compostos por caracteres legíveis
                    if txt and all(ord(c) >= 32 or c in "\r\n\t" for c in txt):
                        strings_encontradas.append((pos, pos + 4, txt))
                        pos += 4 + tam_bytes
                        continue
                except UnicodeDecodeError:
                    pass
        pos += 1

    return strings_encontradas


def inspecionar_textos_layout(page_layout_bytes: bytes | bytearray) -> list[str]:
    """Extrai os textos de layout contidos na stream PageLayout."""
    textos: list[str] = []
    pos = 0
    n = len(page_layout_bytes)

    # 1. Procura ocorrências de blocos formatados com tags XML (<FNT, <BOL, etc.)
    while pos < n - 8:
        idx = page_layout_bytes.find(b"<\x00F\x00N\x00T\x00", pos)
        if idx == -1:
            idx = page_layout_bytes.find(b"<\x00B\x00O\x00L\x00", pos)
        if idx == -1:
            break
        # Busca o terminador nulo duplo
        fim_idx = page_layout_bytes.find(b"\x00\x00\x00\x00", idx)
        if fim_idx != -1 and (fim_idx - idx) < 4000:
            chunk = page_layout_bytes[idx : fim_idx + 2]
            try:
                txt = chunk.decode("utf-16le", errors="ignore").strip("\x00")
                if txt and len(txt) >= 2 and txt not in textos:
                    textos.append(txt)
            except Exception:
                pass
        pos = idx + 8

    # 2. Varre strings com prefixo uint32 que se parecem com textos do layout
    todas = extrair_strings_utf16(page_layout_bytes, min_chars=2, max_chars=300)
    for _, _, txt in todas:
        txt_s = txt.strip()
        if (
            len(txt_s) >= 2
            and not txt_s.startswith("{")  # ignora GUIDs
            and not txt_s.startswith("esri")  # ignora nomes de biblioteca
            and not txt_s.endswith(".dll")
            and not txt_s.endswith(".ttf")
            and txt_s not in textos
        ):
            # Filtra fontes e propriedades comuns
            if txt_s not in ("Arial", "Times New Roman", "Cambria", "Calibri", "Regular", "Bold", "Italic"):
                textos.append(txt_s)

    return textos


def inspecionar_camadas_maps(maps_bytes: bytes | bytearray) -> list[str]:
    """Extrai os nomes de camadas registrados no TOC da stream Maps."""
    camadas: list[str] = []
    todas = extrair_strings_utf16(maps_bytes, min_chars=2, max_chars=120)

    # Nomes de camadas típicos não contêm pontuações de caminho nem GUIDs
    for _, _, txt in todas:
        txt_s = txt.strip()
        if (
            len(txt_s) >= 2
            and not txt_s.startswith("{")
            and not txt_s.startswith("esri")
            and not txt_s.endswith(".dll")
            and not txt_s.endswith(".shp")  # dataset, não nome no TOC
            and "\\" not in txt_s
            and "/" not in txt_s
            and txt_s not in ("MAPA", "MINIMAPA", "UF_INSET", "Layers")
            and txt_s not in camadas
        ):
            camadas.append(txt_s)

    return camadas


def inspecionar_dataframes_maps(maps_bytes: bytes | bytearray) -> list[str]:
    """Identifica nomes de DataFrames (esriCarto.Map) presentes em Maps."""
    candidatos = ["MAPA", "MINIMAPA", "UF_INSET", "Layers", "Camadas", "Localizacao"]
    encontrados: list[str] = []
    for cand in candidatos:
        cand_u16 = cand.encode("utf-16le")
        if cand_u16 in maps_bytes and cand not in encontrados:
            encontrados.append(cand)
    return encontrados
