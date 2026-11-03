"""Varredura de PII (W12-20) — CPF em banco, eventos e logs.

O CPF do proprietário **não pode ser persistido**: o parser do recibo descarta o dado e o PDF
original fica só dentro do `entrada.zip` do projeto. Esta varredura existe para provar isso e
para pegar regressão (alguém logou o recibo, gravou o CPF no evento, etc.).

Regras:

- valida os **dígitos verificadores** antes de acusar — `123.456.789-00` (inválido) é ruído;
- devolve **arquivo e linha**, nunca o valor encontrado (o alerta não pode ser a própria fuga);
- `000.000.000-00` e sequências repetidas são ignoradas (não são CPF).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# CPF com ou sem máscara. Sem máscara exige limite de dígitos dos dois lados para não casar
# dentro de um identificador maior (CAR, matrícula, coordenada).
PADRAO_CPF = re.compile(r"(?<!\d)(\d{3}\.?\d{3}\.?\d{3}-?\d{2})(?!\d)")

IGNORADOS = {"00000000000", "11111111111", "22222222222", "33333333333", "44444444444",
             "55555555555", "66666666666", "77777777777", "88888888888", "99999999999"}


def digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


def cpf_valido(texto: str) -> bool:
    """CPF de verdade: 11 dígitos, não repetido, com os dois verificadores certos."""
    numeros = digitos(texto)
    if len(numeros) != 11 or numeros in IGNORADOS:
        return False
    if len(set(numeros)) == 1:
        return False
    for tamanho in (9, 10):
        soma = sum(int(numeros[i]) * (tamanho + 1 - i) for i in range(tamanho))
        resto = (soma * 10) % 11
        verificador = 0 if resto == 10 else resto
        if verificador != int(numeros[tamanho]):
            return False
    return True


@dataclass(frozen=True)
class Achado:
    arquivo: str
    linha: int
    # Só para o operador saber o que procurar; nunca vai para log.
    tipo: str = "cpf"

    def publico(self) -> dict[str, object]:
        return {"arquivo": self.arquivo, "linha": self.linha, "tipo": self.tipo}


def varrer_texto(texto: str, arquivo: str) -> list[Achado]:
    achados: list[Achado] = []
    for numero_linha, linha in enumerate(texto.splitlines(), start=1):
        for casamento in PADRAO_CPF.finditer(linha):
            if cpf_valido(casamento.group(1)):
                achados.append(Achado(arquivo=arquivo, linha=numero_linha))
                break  # uma linha com vários CPFs conta uma vez
    return achados


def varrer_arquivo(caminho: Path, *, limite_bytes: int | None = None) -> list[Achado]:
    """Lê como texto tolerante (banco e log têm byte binário no meio)."""
    try:
        dados = caminho.read_bytes()
    except OSError:
        return []
    if limite_bytes is not None:
        dados = dados[:limite_bytes]
    texto = dados.decode("utf-8", errors="ignore")
    return varrer_texto(texto, str(caminho))


def varrer(caminhos: Iterable[Path], *, globs: tuple[str, ...] = ()) -> list[Achado]:
    """Varre arquivos e, opcionalmente, globs de diretório (ex.: `projetos/*/eventos.ndjson`)."""
    achados: list[Achado] = []
    for caminho in caminhos:
        if caminho.is_dir():
            for padrao in globs:
                for alvo in sorted(caminho.glob(padrao)):
                    if alvo.is_file():
                        achados.extend(varrer_arquivo(alvo))
        elif caminho.is_file():
            achados.extend(varrer_arquivo(caminho))
    return achados
