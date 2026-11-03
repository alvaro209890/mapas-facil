"""Upload por partes (W-02 §Upload por partes).

O navegador manda 8 MiB por vez porque a Cloudflare corta corpo acima de 100 MB no
plano gratuito. A integridade é conferida **sem** carregar o arquivo inteiro em
memória: cada parte tem seu SHA-256 no header, e `hash_partes` é o sha256 da
concatenação dos hex, na ordem — recalcular esse hash prova que a montagem está
completa e na ordem certa.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from ..erros import ErroServidor

PARTE_PADRAO_MB = 8
FOLGA_PARTE = 1024  # o corpo pode passar 1 KiB do tamanho nominal
EXPIRA_HORAS = 24


@dataclass(frozen=True)
class Upload:
    id: str
    nome: str
    tamanho: int
    parte_bytes: int
    total_partes: int
    pasta: Path

    def para_json(self) -> dict:
        return {
            "upload_id": self.id,
            "nome": self.nome,
            "tamanho": self.tamanho,
            "parte_bytes": self.parte_bytes,
            "total_partes": self.total_partes,
            "partes_ok": self.partes_ok(),
            "faltam": self.faltam(),
        }

    def partes_ok(self) -> list[int]:
        if not self.pasta.is_dir():
            return []
        oks = []
        for numero in range(self.total_partes):
            if (self.pasta / f"{numero}.part").is_file():
                oks.append(numero)
        return oks

    def faltam(self) -> list[int]:
        prontas = set(self.partes_ok())
        return [n for n in range(self.total_partes) if n not in prontas]


def _meta_caminho(pasta: Path) -> Path:
    return pasta / "upload.json"


def calcular_total(tamanho: int, parte_bytes: int) -> int:
    if tamanho <= 0:
        raise ErroServidor(
            "SV-100",
            "Arquivo vazio.",
            status_http=400,
            o_que_fazer="Envie o .zip do imóvel.",
        )
    return max(1, (tamanho + parte_bytes - 1) // parte_bytes)


def criar(
    raiz_uploads: Path,
    *,
    nome: str,
    tamanho: int,
    parte_mb: int = PARTE_PADRAO_MB,
    tamanho_max_bytes: int,
) -> Upload:
    if tamanho > tamanho_max_bytes:
        raise ErroServidor(
            "SV-103",
            f"Arquivo de {tamanho / 1024**3:.1f} GB passa do limite de upload.",
            status_http=413,
            o_que_fazer="Divida o pacote ou suba só os arquivos do imóvel.",
            detalhes={"limite_bytes": tamanho_max_bytes},
        )
    parte_bytes = parte_mb * 1024 * 1024
    total = calcular_total(tamanho, parte_bytes)
    upload_id = uuid.uuid4().hex
    pasta = raiz_uploads / upload_id
    pasta.mkdir(parents=True, exist_ok=False)
    upload = Upload(
        id=upload_id,
        nome=Path(nome or "entrada.zip").name,
        tamanho=tamanho,
        parte_bytes=parte_bytes,
        total_partes=total,
        pasta=pasta,
    )
    _meta_caminho(pasta).write_text(
        json.dumps(
            {
                "id": upload.id,
                "nome": upload.nome,
                "tamanho": upload.tamanho,
                "parte_bytes": parte_bytes,
                "total_partes": total,
            }
        ),
        encoding="utf-8",
    )
    return upload


def abrir(raiz_uploads: Path, upload_id: str) -> Upload:
    if not upload_id or any(c not in "0123456789abcdef" for c in upload_id):
        raise ErroServidor("SV-100", "Identificador de upload inválido.", status_http=400)
    pasta = raiz_uploads / upload_id
    meta = _meta_caminho(pasta)
    if not meta.is_file():
        raise ErroServidor(
            "SV-100",
            "Upload não encontrado (ou expirado).",
            status_http=404,
            porque="Partes não usadas são apagadas em 24 h.",
            o_que_fazer="Comece o envio de novo.",
        )
    dados = json.loads(meta.read_text(encoding="utf-8"))
    return Upload(
        id=dados["id"],
        nome=dados["nome"],
        tamanho=int(dados["tamanho"]),
        parte_bytes=int(dados["parte_bytes"]),
        total_partes=int(dados["total_partes"]),
        pasta=pasta,
    )


def gravar_parte(
    upload: Upload,
    numero: int,
    dados: bytes,
    *,
    sha256_declarado: str | None,
) -> None:
    """Grava a parte validando tamanho e hash. Repetir a mesma parte é idempotente."""
    if numero < 0 or numero >= upload.total_partes:
        raise ErroServidor(
            "SV-100",
            f"Parte fora da faixa: {numero}.",
            status_http=400,
            detalhes={"total_partes": upload.total_partes},
        )
    if len(dados) > upload.parte_bytes + FOLGA_PARTE:
        raise ErroServidor(
            "SV-103",
            "Parte maior que o combinado.",
            status_http=413,
            detalhes={"parte_bytes": upload.parte_bytes, "recebido": len(dados)},
        )
    if not sha256_declarado:
        raise ErroServidor(
            "SV-101",
            "Falta o header X-Parte-SHA256.",
            status_http=400,
        )
    real = hashlib.sha256(dados).hexdigest()
    if real.lower() != sha256_declarado.strip().lower():
        raise ErroServidor(
            "SV-101",
            "A parte chegou corrompida.",
            status_http=400,
            porque="O SHA-256 recebido não confere com o conteúdo da parte.",
            o_que_fazer="Reenvie esta parte.",
            detalhes={"parte": numero},
        )
    destino = upload.pasta / f"{numero}.part"
    temporario = upload.pasta / f"{numero}.part.tmp"
    temporario.write_bytes(dados)
    os.replace(temporario, destino)


def hash_partes(upload: Upload) -> str:
    """sha256(concatenação dos hex das partes, na ordem) — o mesmo cálculo do navegador."""
    acumulado = hashlib.sha256()
    for numero in range(upload.total_partes):
        parte = upload.pasta / f"{numero}.part"
        if not parte.is_file():
            raise ErroServidor(
                "SV-102",
                "Ainda faltam partes para montar o arquivo.",
                status_http=409,
                detalhes={"faltam": upload.faltam()[:20]},
            )
        acumulado.update(hashlib.sha256(parte.read_bytes()).hexdigest().encode("ascii"))
    return acumulado.hexdigest()


def concluir(
    upload: Upload,
    *,
    hash_partes_declarado: str,
    destino: Path,
) -> dict:
    """Confere a montagem e grava o arquivo final, devolvendo o sha256 dele."""
    esperado = hash_partes(upload)
    if esperado.lower() != (hash_partes_declarado or "").strip().lower():
        raise ErroServidor(
            "SV-102",
            "A montagem do arquivo não confere.",
            status_http=400,
            porque="O hash das partes recebidas é diferente do informado pelo navegador.",
            o_que_fazer="Recomece o envio do arquivo.",
        )
    destino.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    escrito = 0
    with open(destino, "wb") as saida:
        for numero in range(upload.total_partes):
            parte = upload.pasta / f"{numero}.part"
            with open(parte, "rb") as origem:
                while True:
                    bloco = origem.read(1024 * 1024)
                    if not bloco:
                        break
                    escrito += len(bloco)
                    digest.update(bloco)
                    saida.write(bloco)
    if escrito != upload.tamanho:
        raise ErroServidor(
            "SV-102",
            "O arquivo montado tem tamanho diferente do declarado.",
            status_http=400,
            detalhes={"esperado": upload.tamanho, "montado": escrito},
        )
    return {"sha256": digest.hexdigest(), "tamanho": escrito}


def descartar(upload: Upload) -> None:
    shutil.rmtree(upload.pasta, ignore_errors=True)
