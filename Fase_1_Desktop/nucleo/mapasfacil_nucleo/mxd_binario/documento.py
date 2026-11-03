"""API de alto nível para manipulação de documentos MXD binários.

Responsável por (W10-06 / W-08 §Documento):
`DocumentoMxd.abrir(template) -> aplicar(valores, manifesto) -> salvar(destino)`
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from .blocos import ArvoreBlocos
from .cfbf import CompoundFile
from .slots import (
    DefinicaoSlot,
    ErroSlot,
    ManifestoSlots,
    aplicar_slot_consulta,
    aplicar_slot_envelope,
    aplicar_slot_numero,
    aplicar_slot_texto,
)


class DocumentoMxd:
    """Documento MXD manipulado diretamente no nível de streams binárias."""

    def __init__(self, cf: CompoundFile, caminho_origem: Path | None = None) -> None:
        self.cf = cf
        self.caminho_origem = caminho_origem
        self._streams_modificadas: dict[str, bytearray] = {}
        self._arvores_blocos: dict[str, ArvoreBlocos] = {}

    @classmethod
    def abrir(cls, caminho: str | Path) -> DocumentoMxd:
        """Abre um documento MXD existente."""
        p = Path(caminho)
        cf = CompoundFile.abrir(p)
        return cls(cf, caminho_origem=p)

    @classmethod
    def de_bytes(cls, dados: bytes) -> DocumentoMxd:
        """Abre um documento MXD a partir de bytes em memória."""
        cf = CompoundFile.de_bytes(dados)
        return cls(cf)

    def _obter_buffer_stream(self, nome_stream: str) -> bytearray:
        """Obtém buffer mutável de uma stream, carregando-a se necessário."""
        if nome_stream not in self._streams_modificadas:
            dados = self.cf.obter_stream(nome_stream)
            self._streams_modificadas[nome_stream] = bytearray(dados)
        return self._streams_modificadas[nome_stream]

    def _obter_arvore_stream(self, nome_stream: str) -> ArvoreBlocos:
        """Obtém ou constrói a árvore de blocos de uma stream."""
        if nome_stream not in self._arvores_blocos:
            buf = self._obter_buffer_stream(nome_stream)
            self._arvores_blocos[nome_stream] = ArvoreBlocos.construir(buf)
        return self._arvores_blocos[nome_stream]

    def aplicar(
        self,
        valores: dict[str, Any],
        manifesto: ManifestoSlots | None = None,
    ) -> DocumentoMxd:
        """Aplica valores de slots no documento.

        Se manifesto for informado, valida obrigatoriedade e usa sentinelas declaradas.
        Caso contrário, infere as sentinelas padrão «MF:<slot_id>».
        """
        if manifesto is not None:
            for slot_def in manifesto.slots:
                valor = valores.get(slot_def.id)
                if valor is None:
                    if slot_def.obrigatorio:
                        raise ErroSlot(f"Slot obrigatório não fornecido: {slot_def.id}")
                    continue
                self._aplicar_slot_individual(slot_def, valor)
        else:
            # Aplicação direta com inferência básica
            for slot_id, valor in valores.items():
                slot_def = self._inferir_slot(slot_id, valor)
                self._aplicar_slot_individual(slot_def, valor)

        return self

    def _inferir_slot(self, slot_id: str, valor: Any) -> DefinicaoSlot:
        """Infere uma definição de slot a partir da chave e do valor."""
        if isinstance(valor, (list, tuple)) and len(valor) == 4:
            return DefinicaoSlot(
                id=slot_id,
                tipo="envelope",
                sentinela=valor,
                streams=["Maps", "Mx Document"],
            )
        elif isinstance(valor, (int, float)):
            return DefinicaoSlot(
                id=slot_id,
                tipo="numero",
                sentinela=float(valor),
                streams=["Maps", "Mx Document"],
            )
        elif slot_id.startswith("ws_") or slot_id.startswith("caminho_"):
            return DefinicaoSlot(
                id=slot_id,
                tipo="caminho",
                sentinela=f"«MF:{slot_id}»",
                streams=["Maps", "Mx Document"],
            )
        else:
            return DefinicaoSlot(
                id=slot_id,
                tipo="texto",
                sentinela=f"«MF:{slot_id}»",
                streams=["PageLayout", "Mx Document"],
            )

    def _aplicar_slot_individual(self, slot_def: DefinicaoSlot, valor: Any) -> int:
        """Aplica uma definição de slot em todas as streams configuradas."""
        total_subst = 0

        for nome_stream in slot_def.streams:
            if not self.cf.tem_stream(nome_stream):
                continue

            buf = self._obter_buffer_stream(nome_stream)
            arvore = self._obter_arvore_stream(nome_stream)

            if slot_def.tipo in ("texto", "nome_camada", "caminho"):
                n = aplicar_slot_texto(buf, str(slot_def.sentinela), str(valor), arvore)
                total_subst += n
            elif slot_def.tipo == "consulta":
                n = aplicar_slot_consulta(buf, str(slot_def.sentinela), str(valor), arvore)
                total_subst += n
            elif slot_def.tipo == "numero":
                n = aplicar_slot_numero(buf, float(slot_def.sentinela), float(valor))
                total_subst += n
            elif slot_def.tipo == "envelope":
                n = aplicar_slot_envelope(buf, slot_def.sentinela, valor)
                total_subst += n

        return total_subst

    def salvar(self, destino: str | Path) -> None:
        """Grava o documento alterado no caminho de destino."""
        p = Path(destino)
        # Atualiza as streams modificadas no CompoundFile
        for nome_stream, dados_modificados in self._streams_modificadas.items():
            self.cf.substituir(nome_stream, bytes(dados_modificados))
        self.cf.salvar(p)

    def obter_bytes(self) -> bytes:
        """Retorna os bytes completos do documento MXD empacotado."""
        for nome_stream, dados_modificados in self._streams_modificadas.items():
            self.cf.substituir(nome_stream, bytes(dados_modificados))
        buf = io.BytesIO()
        self.cf.salvar(buf)
        return buf.getvalue()
