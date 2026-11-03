"""Configuração do servidor — lida do ambiente, validada no boot (W-01 §Configuração).

Regras que este módulo garante:

- falta de obrigatória ⇒ `SV-000` com o **nome** da variável (nunca o valor);
- bind fora do loopback ⇒ `SV-001`;
- arquivo de segredos ausente, ilegível ou com modo frouxo ⇒ `SV-000` (falha de
  boot), citando o caminho;
- chave obrigatória faltando **dentro** do arquivo ⇒ `SV-002`, citando só o
  **nome** da chave;
- o valor de qualquer segredo nunca é logado, nunca entra em mensagem de erro.

Os defaults são os do plano W-01 e não mudam em produção sem atualizar o plano.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from .erros import ConfiguracaoInvalida, HostInvalido, SegredoAusente

HOSTS_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})

# Chaves que o `servidor.env` precisa ter (nomes, nunca valores).
#
# 🔴 Só a chave do provedor de IA é obrigatória. As duas chaves geo **não** são: sem elas o app
# sobe, gera mapa com as camadas locais do `.zip` e avisa; o que perde é o WFS autenticado da SEMA
# e o WMTS da Planet. Antes, a ausência das duas impedia o boot inteiro (`SV-002`) — e as chaves
# não existiam em cofre nenhum da frota (03/11/2026), o que travava deploy e piloto sem motivo.
CHAVES_OBRIGATORIAS_SEGREDOS: tuple[str, ...] = ("MAPASFACIL_PROVEDOR_CHAVE",)

# Chaves que mudam o que o app consegue fazer, mas não o boot.
CHAVES_OPCIONAIS_SEGREDOS: tuple[str, ...] = (
    "MAPASFACIL_SEMA_AUTHKEY",
    "MAPASFACIL_PLANET_API_KEY",
)

# Só quando o provedor alternativo é a DeepSeek direta (D33 permite).
CHAVE_OBRIGATORIA_DEEPSEEK = "MAPASFACIL_DEEPSEEK_API_KEY"


@dataclass(frozen=True)
class Config:
    raiz: Path
    host: str
    porta: int
    url_publica: str
    python_nucleo: Path
    max_workers: int
    max_jobs: int
    worker_ocioso_s: int
    timeout_req_s: int
    upload_max_mb: int
    upload_parte_mb: int
    extraido_max_mb: int
    segredos: Path
    admin_email: str | None = None
    provedor: str = "openai_compat"
    provedor_url: str = "http://100.104.255.35:20128/v1"
    modelo_chat: str = "ag/gemini-3.8-flash-high"
    modelo_rapido: str = "ag/gemini-3.8-flash-high"
    modelo_visao: str = "ag/gemini-3.8-flash-high"
    raciocinio: str = "high"
    # Chaves lidas do arquivo de segredos, por nome. Nunca logar este dicionário.
    segredos_lidos: dict[str, str] = field(default_factory=dict, repr=False)
    # Nomes das chaves opcionais que faltaram; nunca valores.
    segredos_ausentes: tuple[str, ...] = ()

    # Caminhos derivados -------------------------------------------------
    @property
    def dados(self) -> Path:
        return self.raiz / "dados"

    @property
    def projetos(self) -> Path:
        return self.dados / "projetos"

    @property
    def uploads(self) -> Path:
        return self.dados / "uploads"

    @property
    def vagas(self) -> Path:
        return self.dados / "vagas"

    @property
    def cache(self) -> Path:
        return self.dados / "cache"

    @property
    def banco(self) -> Path:
        return self.dados / "mapasfacil.sqlite"

    @property
    def logs(self) -> Path:
        return self.raiz / "logs"


def _inteiro(env: Mapping[str, str], nome: str, padrao: int) -> int:
    bruto = env.get(nome)
    if bruto is None or bruto.strip() == "":
        return padrao
    try:
        valor = int(bruto)
    except ValueError as exc:
        raise ConfiguracaoInvalida(
            f"{nome} precisa ser um número inteiro.",
            porque="O boot falha cedo em vez de usar um valor silenciosamente errado.",
            o_que_fazer=f"Corrija {nome} no ambiente ou no `servidor.env`.",
            detalhes={"variavel": nome},
        ) from exc
    if valor <= 0:
        raise ConfiguracaoInvalida(
            f"{nome} precisa ser maior que zero.",
            detalhes={"variavel": nome, "valor": valor},
        )
    return valor


def _obrigatoria(env: Mapping[str, str], nome: str) -> str:
    valor = env.get(nome)
    if valor is None or valor.strip() == "":
        raise ConfiguracaoInvalida(
            f"Falta a variável obrigatória {nome}.",
            porque="O servidor não sobe meio configurado: dado no lugar errado é "
            "pior que servidor parado.",
            o_que_fazer=f"Defina {nome} no ambiente da unit (ou rode com a variável).",
            detalhes={"variavel": nome},
        )
    return valor.strip()


def ler_segredos(caminho: Path) -> dict[str, str]:
    """Lê `chave=valor` do arquivo de segredos. Nunca imprime nada.

    Aceita linhas em branco, comentários (`#`) e aspas simples/duplas em volta do
    valor. Não faz expansão de variável — o arquivo é literal.
    """
    if not caminho.exists():
        raise ConfiguracaoInvalida(
            f"Arquivo de segredos não encontrado: {caminho}.",
            porque="Sem as chaves do provedor de IA e das APIs geo o servidor não trabalha.",
            o_que_fazer="Peça ao Álvaro para criar o arquivo (0600) com as chaves. "
            "O agente nunca lê nem imprime o valor.",
            detalhes={"arquivo": str(caminho), "variavel": "MF_SEGREDOS"},
        )
    if os.name == "posix":
        modo = caminho.stat().st_mode & 0o777
        if modo & 0o077:
            raise ConfiguracaoInvalida(
                f"O arquivo de segredos {caminho} está legível por outros usuários "
                f"(modo {modo:o}).",
                porque="Segredo compartilhado com o grupo/mundo vaza por qualquer conta "
                "no PC.",
                o_que_fazer=f"`chmod 600 {caminho}`.",
                detalhes={"arquivo": str(caminho), "modo": f"{modo:o}"},
            )

    lidos: dict[str, str] = {}
    try:
        texto = caminho.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfiguracaoInvalida(
            f"Não consegui ler o arquivo de segredos {caminho}.",
            detalhes={"arquivo": str(caminho)},
        ) from exc

    for linha in texto.splitlines():
        limpa = linha.strip()
        if not limpa or limpa.startswith("#") or "=" not in limpa:
            continue
        nome, _, valor = limpa.partition("=")
        nome = nome.strip()
        valor = valor.strip().strip("'\"")
        if nome:
            lidos[nome] = valor
    return lidos


def carregar(
    env: Mapping[str, str] | None = None,
    *,
    exigir_segredos: bool = True,
) -> Config:
    """Monta a `Config` a partir do ambiente, validando o que é obrigatório."""
    env = os.environ if env is None else env

    raiz = Path(_obrigatoria(env, "MF_RAIZ")).resolve()

    host = env.get("MF_HOST", "127.0.0.1").strip() or "127.0.0.1"
    if host not in HOSTS_LOOPBACK:
        raise HostInvalido(host)

    porta = _inteiro(env, "MF_PORTA", 3130)

    url_publica = env.get("MF_URL_PUBLICA", "https://mapasfacil-app.cursar.space").strip()
    if not url_publica.startswith("https://"):
        raise ConfiguracaoInvalida(
            "MF_URL_PUBLICA precisa começar com https://.",
            porque="Os cookies são `Secure` e o CORS é fechado nessa origem.",
            detalhes={"variavel": "MF_URL_PUBLICA"},
        )
    url_publica = url_publica.rstrip("/")

    python_nucleo = Path(
        env.get("MF_PYTHON_NUCLEO", "").strip() or (raiz / "venv" / "bin" / "python")
    )

    segredos = Path(
        env.get("MF_SEGREDOS", "").strip() or (raiz / "segredos" / "servidor.env")
    )

    provedor = env.get("MAPASFACIL_PROVEDOR", "openai_compat").strip() or "openai_compat"
    modelo_padrao = "ag/gemini-3.8-flash-high"

    cfg = Config(
        raiz=raiz,
        host=host,
        porta=porta,
        url_publica=url_publica,
        python_nucleo=python_nucleo,
        max_workers=_inteiro(env, "MF_MAX_WORKERS", 6),
        max_jobs=_inteiro(env, "MF_MAX_JOBS", 2),
        worker_ocioso_s=_inteiro(env, "MF_WORKER_OCIOSO_S", 900),
        timeout_req_s=_inteiro(env, "MF_TIMEOUT_REQ_S", 1800),
        upload_max_mb=_inteiro(env, "MF_UPLOAD_MAX_MB", 2048),
        upload_parte_mb=_inteiro(env, "MF_UPLOAD_PARTE_MB", 8),
        extraido_max_mb=_inteiro(env, "MF_EXTRAIDO_MAX_MB", 8192),
        segredos=segredos,
        admin_email=(env.get("MF_ADMIN_EMAIL") or "").strip() or None,
        provedor=provedor,
        provedor_url=(env.get("MAPASFACIL_PROVEDOR_URL") or "").strip()
        or "http://100.104.255.35:20128/v1",
        modelo_chat=(env.get("MAPASFACIL_MODELO_CHAT") or "").strip() or modelo_padrao,
        modelo_rapido=(env.get("MAPASFACIL_MODELO_RAPIDO") or "").strip() or modelo_padrao,
        modelo_visao=(env.get("MAPASFACIL_MODELO_VISAO") or "").strip() or modelo_padrao,
        raciocinio=(env.get("MAPASFACIL_RACIOCINIO") or "").strip() or "high",
    )

    if not exigir_segredos:
        return cfg

    lidos = ler_segredos(cfg.segredos)
    obrigatorias = list(CHAVES_OBRIGATORIAS_SEGREDOS)
    if cfg.provedor == "deepseek":
        obrigatorias.append(CHAVE_OBRIGATORIA_DEEPSEEK)

    faltando = [nome for nome in obrigatorias if not lidos.get(nome)]
    if faltando:
        raise SegredoAusente(
            "O arquivo de segredos existe, mas faltam chaves: "
            + ", ".join(faltando)
            + ".",
            detalhes={"arquivo": str(cfg.segredos), "faltando": faltando},
        )

    # Aviso só com NOMES: a tela de admin e o journal precisam saber qual fonte está fora.
    ausentes = tuple(nome for nome in CHAVES_OPCIONAIS_SEGREDOS if not lidos.get(nome))

    # `replace` porque a Config é frozen; o dicionário fica fora do repr.
    return Config(**{**cfg.__dict__, "segredos_lidos": lidos, "segredos_ausentes": ausentes})


def raiz_padrao_sugerida() -> str:
    """Ajuda de terminal (usada pelo `--ajuda-config` e pelo preflight)."""
    return "/home/server/mapasfacil"
