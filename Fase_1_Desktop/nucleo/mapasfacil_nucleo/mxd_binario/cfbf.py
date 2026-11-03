"""Módulo de manipulação do formato binário CFBF v3 (Compound File Binary Format / OLE2).

O formato CFBF (também conhecido como Microsoft Compound Document File ou OLE2) é uma
especificação de contêiner binário estruturado (MS-CFB) utilizado pelo ArcGIS Desktop
(versões 8.x até 10.8.2) para armazenar documentos de mapa (.mxd).

Estrutura física do CFBF v3:
- Setores regulares: blocos fixos de 512 bytes (2^9 bytes, sector_shift = 9).
- Mini-setores: blocos de 64 bytes (2^6 bytes, mini_sector_shift = 6) alocados
  dentro da Mini Stream (contêiner gerenciado pelo Root Entry).
- Corte da Mini Stream (cutoff): streams menores que 4.096 bytes (4 KB) são
  armazenadas na Mini Stream e indexadas pela MiniFAT. Streams de 4.096 bytes ou mais
  são armazenadas diretamente em setores regulares de 512 bytes e indexadas pela FAT principal.
- FAT (File Allocation Table): tabela de alocação encadeada de 32 bits por setor.
- DIFAT (Double Indirect FAT): tabela de ponteiros para os setores que compõem a FAT.
  Os primeiros 109 ponteiros residem no próprio cabeçalho (header); caso a FAT exceda
  109 setores, setores DIFAT adicionais encadeados são alocados no arquivo.
- Diretório: árvore balanceada rubro-negra de entradas de 128 bytes que descrevem cada
  storage, stream ou entrada raiz (Root Entry).

Por que este módulo existe:
Permite a leitura, inspeção, substituição de fluxos de dados (streams) e reempacotamento
completo de arquivos .mxd diretamente no servidor Linux e em qualquer ambiente Python 3 puro,
sem nenhuma dependência de bibliotecas externas em produção e sem necessidade
do ArcGIS Desktop (arcpy/ArcObjects).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Sequence

# --- Constantes do Formato MS-CFB v3 ---

TAMANHO_CABECALHO = 512
TAMANHO_SETOR = 512
TAMANHO_MINI_SETOR = 64
CORTE_MINI_STREAM = 4096
TAMANHO_ENTRADA_DIRETORIO = 128

ASSINATURA_MAGICA = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
BYTE_ORDER_LITTLE_ENDIAN = 0xFFFE
VERSAO_MAJOR_V3 = 3
VERSAO_MINOR_PADRAO = 0x003E

FAT_MAX_REGULAR = 0xFFFFFFFA
FAT_DIFAT = 0xFFFFFFFC
FAT_ESPECIAL = 0xFFFFFFFD
FAT_FIM = 0xFFFFFFFE
FAT_LIVRE = 0xFFFFFFFF

TIPO_VAZIO = 0
TIPO_STORAGE = 1
TIPO_STREAM = 2
TIPO_ROOT = 5

COR_VERMELHO = 0
COR_PRETO = 1
SID_NULO = 0xFFFFFFFF


# --- Exceções ---


class ErroCFBF(Exception):
    """Exceção base para erros relacionados ao formato CFBF/OLE2."""


class AssinaturaInvalidaError(ErroCFBF, ValueError):
    """Lançada quando a assinatura mágica inicial do arquivo não corresponde a CFBF."""


class VersaoNaoSuportadaError(ErroCFBF, ValueError):
    """Lançada quando a versão do CFBF não é v3 (setores de 512 bytes)."""


class CorrupcaoEstruturalError(ErroCFBF, ValueError):
    """Lançada quando a estrutura interna (FAT, diretório, offsets) está corrompida."""


class StreamNaoEncontradaError(ErroCFBF, KeyError):
    """Lançada quando uma stream solicitada não existe no contêiner CFBF."""


# --- Estruturas de Dados ---


@dataclass
class EntradaDiretorio:
    """Representa uma entrada de 128 bytes no diretório CFBF."""

    sid: int
    nome: str
    nome_bruto: bytes
    tamanho_nome: int
    tipo_entrada: int
    cor: int
    sid_esquerda: int
    sid_direita: int
    sid_filho: int
    clsid: bytes
    flags_usuario: int
    tempo_criacao: int
    tempo_modificacao: int
    setor_inicio: int
    tamanho: int

    def serializar(self) -> bytes:
        """Serializa a entrada nos 128 bytes canônicos da especificação MS-CFB."""
        raw = bytearray(TAMANHO_ENTRADA_DIRETORIO)
        raw[:64] = self.nome_bruto
        struct.pack_into(
            "<HBBIII",
            raw,
            64,
            self.tamanho_nome,
            self.tipo_entrada,
            self.cor,
            self.sid_esquerda,
            self.sid_direita,
            self.sid_filho,
        )
        raw[80:96] = self.clsid
        struct.pack_into(
            "<IQQIQ",
            raw,
            96,
            self.flags_usuario,
            self.tempo_criacao,
            self.tempo_modificacao,
            self.setor_inicio,
            self.tamanho,
        )
        return bytes(raw)


class CompoundFile:
    """Contêiner que representa um arquivo Compound File (CFBF v3 / OLE2) em memória."""

    def __init__(
        self,
        entradas: Sequence[EntradaDiretorio | None],
        streams_por_sid: dict[int, bytes],
        caminho_origem: Path | None = None,
    ) -> None:
        self.entradas: list[EntradaDiretorio | None] = list(entradas)
        self._streams_por_sid: dict[int, bytes] = dict(streams_por_sid)
        self.caminho_origem = caminho_origem

        self._sid_por_nome: dict[str, int] = {}
        self.streams: dict[str, bytes] = {}
        for entrada in self.entradas:
            if entrada and entrada.tipo_entrada == TIPO_STREAM:
                self._sid_por_nome[entrada.nome] = entrada.sid
                self.streams[entrada.nome] = self._streams_por_sid.get(entrada.sid, b"")

    @classmethod
    def abrir(cls, caminho: str | Path) -> CompoundFile:
        """Abre e decodifica um arquivo CFBF a partir do caminho informado."""
        return ler(caminho)

    def tem_stream(self, nome: str) -> bool:
        """Verifica se a stream informada existe no documento."""
        return nome in self.streams

    @classmethod
    def de_bytes(cls, dados: bytes) -> CompoundFile:
        """Decodifica um arquivo CFBF a partir de bytes em memória."""
        import io
        return ler(io.BytesIO(dados))

    def obter_stream(self, nome: str) -> bytes:
        """Obtém o conteúdo binário de uma stream pelo nome."""
        if nome not in self.streams:
            raise StreamNaoEncontradaError(f"Stream '{nome}' não encontrada no arquivo CFBF.")
        return self.streams[nome]

    def substituir(self, nome_do_stream: str, novos_bytes: bytes) -> int:
        """Substitui o conteúdo de uma stream e devolve o novo tamanho em bytes."""
        if nome_do_stream not in self._sid_por_nome:
            raise StreamNaoEncontradaError(
                f"Stream '{nome_do_stream}' não encontrada para substituição."
            )
        sid = self._sid_por_nome[nome_do_stream]
        self.streams[nome_do_stream] = novos_bytes
        self._streams_por_sid[sid] = novos_bytes
        return len(novos_bytes)

    def listar_streams(self) -> list[tuple[str, int]]:
        """Lista tuplas (nome_da_stream, tamanho_em_bytes) na ordem do diretório."""
        resultado: list[tuple[str, int]] = []
        for entrada in self.entradas:
            if entrada and entrada.tipo_entrada == TIPO_STREAM:
                dados = self.streams.get(entrada.nome, b"")
                resultado.append((entrada.nome, len(dados)))
        return resultado

    def __contains__(self, nome: str) -> bool:
        return nome in self.streams

    def __getitem__(self, nome: str) -> bytes:
        return self.obter_stream(nome)

    def __setitem__(self, nome: str, dados: bytes) -> None:
        self.substituir(nome, dados)

    def __len__(self) -> int:
        return len(self.streams)

    def __repr__(self) -> str:
        origem = f" de '{self.caminho_origem.name}'" if self.caminho_origem else ""
        return f"<CompoundFile{origem} com {len(self.streams)} streams>"

    def salvar(self, destino: str | Path) -> None:
        """Reempacota o contêiner CFBF v3 preservando streams e diretório."""
        # 0. Sincroniza eventuais alterações feitas diretamente no dict self.streams
        for nome, sid in self._sid_por_nome.items():
            if nome in self.streams:
                self._streams_por_sid[sid] = self.streams[nome]

        entradas_salvar: list[EntradaDiretorio | None] = [
            replace(e) if e is not None else None for e in self.entradas
        ]

        mini_dados = bytearray()
        minifat: list[int] = []

        # 1. Aloca streams pequenas (< 4096 bytes) na Mini Stream
        for sid, entrada in enumerate(entradas_salvar):
            if entrada is None or entrada.tipo_entrada != TIPO_STREAM:
                continue
            dados = self._streams_por_sid.get(sid, b"")
            entrada.tamanho = len(dados)
            if len(dados) == 0:
                entrada.setor_inicio = FAT_FIM
            elif len(dados) < CORTE_MINI_STREAM:
                inicio_mini = len(minifat)
                entrada.setor_inicio = inicio_mini
                num_mini = (len(dados) + TAMANHO_MINI_SETOR - 1) // TAMANHO_MINI_SETOR
                for i in range(num_mini):
                    minifat.append(inicio_mini + i + 1 if i < num_mini - 1 else FAT_FIM)
                preenchido = dados.ljust(num_mini * TAMANHO_MINI_SETOR, b"\x00")
                mini_dados.extend(preenchido)

        root = entradas_salvar[0]
        if root is None:
            raise CorrupcaoEstruturalError("Root Entry (SID 0) ausente no contêiner CFBF.")
        root.tamanho = len(mini_dados)

        # 2. Prepara alocações na FAT regular (Ministream e streams >= 4096 bytes)
        alocacoes_grandes: list[tuple[str | int, bytes]] = []
        if len(mini_dados) > 0:
            alocacoes_grandes.append(("ministream", bytes(mini_dados)))

        for sid, entrada in enumerate(entradas_salvar):
            if entrada is None or entrada.tipo_entrada != TIPO_STREAM:
                continue
            dados = self._streams_por_sid.get(sid, b"")
            if len(dados) >= CORTE_MINI_STREAM:
                alocacoes_grandes.append((sid, dados))

        setores_principais: list[bytes] = []
        fat: list[int] = []

        def alocar_cadeia(dados_bytes: bytes) -> tuple[int, int]:
            inicio = len(setores_principais)
            num = (len(dados_bytes) + TAMANHO_SETOR - 1) // TAMANHO_SETOR
            for i in range(num):
                bloco = dados_bytes[i * TAMANHO_SETOR : (i + 1) * TAMANHO_SETOR]
                if len(bloco) < TAMANHO_SETOR:
                    bloco = bloco.ljust(TAMANHO_SETOR, b"\x00")
                setores_principais.append(bloco)
                fat.append(inicio + i + 1 if i < num - 1 else FAT_FIM)
            return inicio, num

        for chave_item, dados in alocacoes_grandes:
            inicio, _ = alocar_cadeia(dados)
            if chave_item == "ministream":
                root.setor_inicio = inicio
            else:
                entradas_salvar[chave_item].setor_inicio = inicio  # type: ignore[index]

        if len(mini_dados) == 0:
            root.setor_inicio = FAT_FIM

        # 3. Aloca MiniFAT
        if minifat:
            minifat_bytes = struct.pack(f"<{len(minifat)}I", *minifat)
            setor_minifat, num_setores_minifat = alocar_cadeia(minifat_bytes)
        else:
            setor_minifat, num_setores_minifat = FAT_FIM, 0

        # 4. Aloca Directory Stream
        dir_bytes = bytearray()
        for entrada in entradas_salvar:
            if entrada is None:
                dir_bytes.extend(b"\x00" * TAMANHO_ENTRADA_DIRETORIO)
            else:
                dir_bytes.extend(entrada.serializar())

        setor_diretorio, _ = alocar_cadeia(bytes(dir_bytes))

        # 5. Calcula setores FAT (F) e DIFAT (D)
        num_fat = 1
        while True:
            num_difat = 0 if num_fat <= 109 else (num_fat - 109 + 126) // 127
            total_setores = len(setores_principais) + num_fat + num_difat
            if num_fat * 128 >= total_setores:
                break
            num_fat += 1

        inicio_fat = len(setores_principais)
        for _ in range(num_fat):
            fat.append(FAT_ESPECIAL)

        inicio_difat = FAT_FIM
        if num_difat > 0:
            inicio_difat = len(setores_principais) + num_fat
            for _ in range(num_difat):
                fat.append(FAT_DIFAT)

        while len(fat) < num_fat * 128:
            fat.append(FAT_LIVRE)

        difat_cabecalho = [FAT_LIVRE] * 109
        for i in range(min(num_fat, 109)):
            difat_cabecalho[i] = inicio_fat + i

        setores_difat: list[bytes] = []
        if num_difat > 0:
            fat_restante = list(range(inicio_fat + 109, inicio_fat + num_fat))
            for i in range(num_difat):
                sec = [FAT_LIVRE] * 128
                pedaco = fat_restante[i * 127 : (i + 1) * 127]
                for j, s_idx in enumerate(pedaco):
                    sec[j] = s_idx
                sec[127] = inicio_difat + i + 1 if i < num_difat - 1 else FAT_FIM
                setores_difat.append(struct.pack("<128I", *sec))

        setores_fat: list[bytes] = []
        for i in range(num_fat):
            pedaco = fat[i * 128 : (i + 1) * 128]
            setores_fat.append(struct.pack("<128I", *pedaco))

        # 6. Monta o cabeçalho de 512 bytes
        cabecalho = bytearray(TAMANHO_CABECALHO)
        cabecalho[:8] = ASSINATURA_MAGICA
        struct.pack_into(
            "<HHHHHHIIIIIIIIII",
            cabecalho,
            24,
            VERSAO_MINOR_PADRAO,
            VERSAO_MAJOR_V3,
            BYTE_ORDER_LITTLE_ENDIAN,
            9,
            6,
            0,
            0,
            0,
            num_fat,
            setor_diretorio,
            0,
            CORTE_MINI_STREAM,
            setor_minifat,
            num_setores_minifat,
            inicio_difat if num_difat > 0 else FAT_FIM,
            num_difat,
        )
        struct.pack_into("<109I", cabecalho, 76, *difat_cabecalho)

        def _gravar_conteudo(f):
            f.write(cabecalho)
            for s in setores_principais:
                f.write(s)
            for s in setores_fat:
                f.write(s)
            for s in setores_difat:
                f.write(s)

        if hasattr(destino, "write"):
            _gravar_conteudo(destino)
        else:
            caminho_dest = Path(destino)
            caminho_dest.parent.mkdir(parents=True, exist_ok=True)
            with open(caminho_dest, "wb") as f:
                _gravar_conteudo(f)


# --- Função de Leitura ---


def ler(origem: str | Path | Any) -> CompoundFile:
    """Lê um arquivo CFBF v3 (.mxd) a partir de arquivo ou buffer BytesIO.

    Returns:
        Instância de CompoundFile com streams decodificadas e hierarquia preservada.
    """
    import io
    if isinstance(origem, (str, Path)):
        p = Path(origem)
        if not p.is_file():
            raise FileNotFoundError(f"Arquivo não encontrado: {p}")
        f_ctx = open(p, "rb")
        nome_arqv = p.name
        caminho_origem = p
    elif hasattr(origem, "read"):
        f_ctx = origem
        nome_arqv = getattr(origem, "name", "memoria.mxd")
        caminho_origem = None
    elif isinstance(origem, bytes):
        f_ctx = io.BytesIO(origem)
        nome_arqv = "memoria.mxd"
        caminho_origem = None
    else:
        raise ValueError(f"Origem inválida para leitura CFBF: {type(origem)}")

    def _processar(f):
        cabecalho = f.read(TAMANHO_CABECALHO)
        if len(cabecalho) < TAMANHO_CABECALHO:
            raise AssinaturaInvalidaError(
                f"Arquivo '{p.name}' é menor que o cabeçalho CFBF de 512 bytes ({len(cabecalho)} bytes lidos); "
                f"assinatura inválida ou arquivo corrompido."
            )
        if cabecalho[:8] != ASSINATURA_MAGICA:
            raise AssinaturaInvalidaError(
                f"Arquivo '{p.name}' não possui assinatura CFBF válida. "
                f"Esperado: {ASSINATURA_MAGICA.hex(' ').upper()}, "
                f"Encontrado: {cabecalho[:8].hex(' ').upper()}."
            )

        minor, major, byte_order, sec_shift, mini_shift = struct.unpack_from("<HHHHH", cabecalho, 24)
        if byte_order != BYTE_ORDER_LITTLE_ENDIAN:
            raise VersaoNaoSuportadaError(
                f"Byte order 0x{byte_order:04X} não suportado (apenas Little Endian 0xFFFE)."
            )
        if sec_shift != 9 or major != VERSAO_MAJOR_V3:
            raise VersaoNaoSuportadaError(
                f"Apenas CFBF v3 com setores de 512 bytes (sector_shift=9, major=3) é suportado. "
                f"Encontrado: major={major}, sector_shift={sec_shift}."
            )
        if mini_shift != 6:
            raise VersaoNaoSuportadaError(
                f"Mini sector shift inesperado: {mini_shift} (esperado 6 para blocos de 64 bytes)."
            )

        num_fat_sectors = struct.unpack_from("<I", cabecalho, 0x2C)[0]
        first_dir_sector = struct.unpack_from("<I", cabecalho, 0x30)[0]
        mini_cutoff = struct.unpack_from("<I", cabecalho, 0x38)[0]
        first_minifat_sector = struct.unpack_from("<I", cabecalho, 0x3C)[0]
        num_minifat_sectors = struct.unpack_from("<I", cabecalho, 0x40)[0]
        first_difat_sector = struct.unpack_from("<I", cabecalho, 0x44)[0]
        num_difat_sectors = struct.unpack_from("<I", cabecalho, 0x48)[0]

        # 1. Monta lista de setores da FAT a partir do cabeçalho e da DIFAT
        difat_inicial = list(struct.unpack_from("<109I", cabecalho, 0x4C))
        setores_fat = [s for s in difat_inicial[:num_fat_sectors] if s != FAT_LIVRE]

        setor_difat_atual = first_difat_sector
        for _ in range(num_difat_sectors):
            if setor_difat_atual > FAT_MAX_REGULAR:
                break
            f.seek((setor_difat_atual + 1) * TAMANHO_SETOR)
            bloco_difat = struct.unpack("<128I", f.read(TAMANHO_SETOR))
            for s in bloco_difat[:127]:
                if s != FAT_LIVRE and len(setores_fat) < num_fat_sectors:
                    setores_fat.append(s)
            setor_difat_atual = bloco_difat[127]

        # 2. Lê todos os setores da FAT
        fat: list[int] = []
        for s in setores_fat:
            f.seek((s + 1) * TAMANHO_SETOR)
            fat.extend(struct.unpack("<128I", f.read(TAMANHO_SETOR)))

        def ler_cadeia_fat(setor_inicio: int, tamanho_exato: int | None = None) -> bytes:
            if setor_inicio in (FAT_FIM, FAT_LIVRE):
                return b""
            buf = bytearray()
            atual = setor_inicio
            visitados = set()
            while atual <= FAT_MAX_REGULAR:
                if atual in visitados:
                    raise CorrupcaoEstruturalError(f"Ciclo detectado na FAT no setor {atual}.")
                visitados.add(atual)
                f.seek((atual + 1) * TAMANHO_SETOR)
                bloco = f.read(TAMANHO_SETOR)
                buf.extend(bloco)
                if tamanho_exato is not None and len(buf) >= tamanho_exato:
                    return bytes(buf[:tamanho_exato])
                if atual >= len(fat):
                    break
                atual = fat[atual]
            if tamanho_exato is not None:
                return bytes(buf[:tamanho_exato])
            return bytes(buf)

        # 3. Lê Directory Stream
        dir_bytes = ler_cadeia_fat(first_dir_sector)
        num_entradas = len(dir_bytes) // TAMANHO_ENTRADA_DIRETORIO
        entradas: list[EntradaDiretorio | None] = []
        for sid in range(num_entradas):
            offset_dir = sid * TAMANHO_ENTRADA_DIRETORIO
            raw = dir_bytes[offset_dir : offset_dir + TAMANHO_ENTRADA_DIRETORIO]
            if raw == b"\x00" * TAMANHO_ENTRADA_DIRETORIO:
                entradas.append(None)
                continue
            nome_bruto = raw[:64]
            namelen, entry_type, color, sid_left, sid_right, sid_child = struct.unpack_from(
                "<HBBIII", raw, 64
            )
            clsid = raw[80:96]
            dw_user_flags, create_time, modify_time, isect_start, size = struct.unpack_from(
                "<IQQIQ", raw, 96
            )
            nome = (
                nome_bruto[: namelen - 2].decode("utf-16le")
                if namelen >= 2
                else ""
            )
            entradas.append(
                EntradaDiretorio(
                    sid=sid,
                    nome=nome,
                    nome_bruto=nome_bruto,
                    tamanho_nome=namelen,
                    tipo_entrada=entry_type,
                    cor=color,
                    sid_esquerda=sid_left,
                    sid_direita=sid_right,
                    sid_filho=sid_child,
                    clsid=clsid,
                    flags_usuario=dw_user_flags,
                    tempo_criacao=create_time,
                    tempo_modificacao=modify_time,
                    setor_inicio=isect_start,
                    tamanho=size,
                )
            )

        if not entradas or entradas[0] is None or entradas[0].tipo_entrada != TIPO_ROOT:
            raise CorrupcaoEstruturalError("Root Entry (SID 0) ausente ou inválida no diretório.")

        root = entradas[0]

        # 4. Lê a Mini Stream (container do Root Entry)
        mini_stream_bytes = ler_cadeia_fat(root.setor_inicio, root.tamanho)

        # 5. Lê a MiniFAT
        minifat_bytes = ler_cadeia_fat(first_minifat_sector)
        minifat: list[int] = (
            list(struct.unpack(f"<{len(minifat_bytes) // 4}I", minifat_bytes))
            if minifat_bytes
            else []
        )

        # 6. Lê as Streams
        streams_por_sid: dict[int, bytes] = {}
        for entrada in entradas:
            if entrada is None or entrada.tipo_entrada != TIPO_STREAM:
                continue
            tam = entrada.tamanho
            if tam == 0:
                streams_por_sid[entrada.sid] = b""
            elif tam < mini_cutoff:
                # Alocada em mini-setores da Mini Stream
                buf = bytearray()
                atual = entrada.setor_inicio
                visitados_mini = set()
                while atual <= FAT_MAX_REGULAR and len(buf) < tam:
                    if atual in visitados_mini:
                        raise CorrupcaoEstruturalError(
                            f"Ciclo detectado na MiniFAT no mini-setor {atual}."
                        )
                    visitados_mini.add(atual)
                    offset_mini = atual * TAMANHO_MINI_SETOR
                    bloco = mini_stream_bytes[offset_mini : offset_mini + TAMANHO_MINI_SETOR]
                    buf.extend(bloco)
                    if atual >= len(minifat):
                        break
                    atual = minifat[atual]
                streams_por_sid[entrada.sid] = bytes(buf[:tam])
            else:
                # Alocada em setores normais da FAT regular
                streams_por_sid[entrada.sid] = ler_cadeia_fat(entrada.setor_inicio, tam)

        return CompoundFile(entradas, streams_por_sid, caminho_origem=caminho_origem)

    if hasattr(f_ctx, "__enter__"):
        with f_ctx as f:
            return _processar(f)
    else:
        return _processar(f_ctx)
