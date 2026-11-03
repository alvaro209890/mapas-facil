"""Verificação e extração segura do ZIP de entrada (W-02 §Verificação e extração).

Ordem fixa, parando no primeiro erro. O que não é erro (extensão fora da allowlist,
`.mxd` com `authkey`) vira **aviso**, não falha — o usuário precisa saber, mas não pode
perder o trabalho por isso.

Códigos: `SV-104` zip-slip · `SV-105` symlink · `SV-106` zip-bomba/teto ·
`SV-107` razão de compressão · `SV-108` entradas demais · `SV-110` ZIP inválido ·
`SV-120` extensão ignorada · `SV-121` chave removida de `.mxd`.
"""

from __future__ import annotations

import shutil
import unicodedata
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..erros import ErroServidor

EXTENSOES_OK = frozenset(
    {
        ".shp", ".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx", ".qix", ".xml",
        ".zip", ".pdf", ".tif", ".tiff", ".tfw", ".jpg", ".jpeg", ".jgw", ".png",
        ".pgw", ".kml", ".kmz", ".geojson", ".json", ".csv", ".txt", ".xlsx", ".mxd",
    }
)
MAX_ENTRADAS = 5000
RAZAO_MAX = 200
RAZAO_TAMANHO_MIN = 50 * 1024 * 1024
FLAG_UTF8 = 0x800

Progresso = Callable[[dict], None]


@dataclass
class ResultadoExtracao:
    destino: Path
    arquivos: list[str] = field(default_factory=list)
    ignorados: list[str] = field(default_factory=list)
    avisos: list[dict] = field(default_factory=list)
    bytes_extraidos: int = 0

    @property
    def total(self) -> int:
        return len(self.arquivos)


def _nome_seguro(nome: str) -> str:
    """Normaliza e recusa caminho que sai da pasta de destino (zip-slip)."""
    if "\x00" in nome:
        raise ErroServidor(
            "SV-104",
            "O ZIP tem nome de arquivo com byte nulo.",
            status_http=400,
            porque="Nome inválido é sinal de ZIP montado para enganar o extrator.",
        )
    normalizado = nome.replace("\\", "/")
    if normalizado.startswith("/") or (len(normalizado) > 1 and normalizado[1] == ":"):
        raise ErroServidor(
            "SV-104",
            f"Caminho absoluto no ZIP: {nome!r}.",
            status_http=400,
            detalhes={"entrada": nome},
        )
    partes = [p for p in normalizado.split("/") if p not in ("", ".")]
    if any(p == ".." for p in partes) or not partes:
        raise ErroServidor(
            "SV-104",
            f"Caminho com '..' no ZIP: {nome!r}.",
            status_http=400,
            o_que_fazer="Recompacte o ZIP sem caminhos relativos para fora da pasta.",
            detalhes={"entrada": nome},
        )
    return "/".join(partes)


def _decodificar_nome(info: zipfile.ZipInfo) -> str:
    """ZIP do Windows sem flag UTF-8 vem em cp437/cp850 — decodificar antes de usar."""
    if info.flag_bits & FLAG_UTF8:
        return unicodedata.normalize("NFC", info.filename)
    bruto = info.filename
    try:
        texto = bruto.encode("cp437").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        texto = bruto
    return unicodedata.normalize("NFC", texto)


def _eh_symlink(info: zipfile.ZipInfo) -> bool:
    return (info.external_attr >> 16) & 0o170000 == 0o120000


def verificar(
    caminho_zip: Path,
    *,
    max_extraido_bytes: int,
) -> tuple[zipfile.ZipFile, list[zipfile.ZipInfo]]:
    """Abre o ZIP e valida estrutura, nomes, symlinks, contagem e tamanhos."""
    if not caminho_zip.is_file():
        raise ErroServidor(
            "SV-110",
            "Arquivo de entrada não encontrado.",
            status_http=400,
        )
    if not zipfile.is_zipfile(caminho_zip):
        raise ErroServidor(
            "SV-110",
            "O arquivo enviado não é um ZIP válido.",
            status_http=400,
            porque="O diretório central do ZIP está ausente ou corrompido.",
            o_que_fazer="Recompacte o pacote; se o download falhou, baixe de novo do SIMCAR.",
        )
    try:
        zf = zipfile.ZipFile(caminho_zip)
    except (zipfile.BadZipFile, OSError) as exc:
        raise ErroServidor(
            "SV-110",
            "Não foi possível abrir o ZIP.",
            status_http=400,
            detalhes={"motivo": str(exc)},
        ) from exc

    infos = zf.infolist()
    if len(infos) > MAX_ENTRADAS:
        zf.close()
        raise ErroServidor(
            "SV-108",
            f"O ZIP tem {len(infos)} arquivos; o limite é {MAX_ENTRADAS}.",
            status_http=400,
            o_que_fazer="Envie só os arquivos do imóvel, sem o acervo inteiro.",
        )

    soma = 0
    for info in infos:
        _nome_seguro(_decodificar_nome(info))
        if _eh_symlink(info):
            zf.close()
            raise ErroServidor(
                "SV-105",
                f"O ZIP contém link simbólico: {info.filename!r}.",
                status_http=400,
                porque="Symlink dentro de pacote é tentativa de escrever fora da pasta.",
            )
        if info.is_dir():
            continue
        soma += info.file_size
        if (
            info.file_size > RAZAO_TAMANHO_MIN
            and info.compress_size > 0
            and info.file_size / info.compress_size > RAZAO_MAX
        ):
            zf.close()
            raise ErroServidor(
                "SV-107",
                "O ZIP tem compressão suspeita (possível zip-bomba).",
                status_http=400,
                detalhes={"entrada": info.filename},
            )
    if soma > max_extraido_bytes:
        zf.close()
        raise ErroServidor(
            "SV-106",
            "O conteúdo do ZIP passa do limite configurado.",
            status_http=400,
            porque="Proteção contra zip-bomba e contra encher o disco do servidor.",
            detalhes={"bytes": soma, "limite": max_extraido_bytes},
        )
    return zf, infos


def extrair(
    caminho_zip: Path,
    destino: Path,
    *,
    max_extraido_bytes: int,
    ao_progresso: Progresso | None = None,
) -> ResultadoExtracao:
    """Extrai arquivo a arquivo, contando bytes **reais** (o declarado pode mentir)."""
    zf, infos = verificar(caminho_zip, max_extraido_bytes=max_extraido_bytes)
    resultado = ResultadoExtracao(destino=destino)
    destino.mkdir(parents=True, exist_ok=True)
    total = len([i for i in infos if not i.is_dir()])

    try:
        for indice, info in enumerate(infos, start=1):
            nome = _nome_seguro(_decodificar_nome(info))
            if info.is_dir():
                continue
            sufixo = Path(nome).suffix.lower()
            alvo = destino / nome
            if sufixo not in EXTENSOES_OK:
                resultado.ignorados.append(nome)
                resultado.avisos.append(
                    {
                        "codigo": "SV-120",
                        "mensagem": f"Arquivo ignorado (extensão não suportada): {nome}",
                    }
                )
                continue
            alvo.parent.mkdir(parents=True, exist_ok=True)
            if alvo.exists():
                # Entrada duplicada no ZIP: mantém a primeira (é a que o ArcMap usaria).
                resultado.avisos.append(
                    {
                        "codigo": "SV-122",
                        "mensagem": f"Entrada duplicada ignorada: {nome}",
                    }
                )
                continue
            escrito = 0
            with zf.open(info) as origem, open(alvo, "xb") as saida:
                while True:
                    bloco = origem.read(1024 * 1024)
                    if not bloco:
                        break
                    escrito += len(bloco)
                    resultado.bytes_extraidos += len(bloco)
                    if resultado.bytes_extraidos > max_extraido_bytes:
                        raise ErroServidor(
                            "SV-106",
                            "O conteúdo extraído passou do limite durante a extração.",
                            status_http=400,
                            detalhes={"arquivo": nome, "limite": max_extraido_bytes},
                        )
                    saida.write(bloco)
            resultado.arquivos.append(nome)
            if ao_progresso is not None:
                ao_progresso(
                    {
                        "fase": "extraindo",
                        "arquivo": nome,
                        "indice": indice,
                        "total": total,
                        "bytes": resultado.bytes_extraidos,
                    }
                )
    finally:
        zf.close()

    return resultado


def marcar_somente_leitura(caminho: Path) -> None:
    """`entrada/` é imutável para o núcleo: 0440 e pasta 0550."""
    for alvo in caminho.rglob("*"):
        try:
            alvo.chmod(0o440 if alvo.is_file() else 0o550)
        except OSError:  # pragma: no cover - FS sem permissão POSIX
            continue
    try:
        caminho.chmod(0o550)
    except OSError:  # pragma: no cover
        pass


def copiar_zip(caminho_zip: Path, destino: Path) -> Path:
    """Copia o original para `entrada.zip` (0440) antes de extrair."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(caminho_zip, destino)
    try:
        destino.chmod(0o440)
    except OSError:  # pragma: no cover
        pass
    return destino
