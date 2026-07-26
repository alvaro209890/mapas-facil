# F1-07 — cliente do modelo de visão. Chamada única (sem streaming): manda o
# print/raster + o prompt com as medidas já feitas, espera um JSON de volta.
#
# P1 (fechada 2026-07-26): a API oficial DeepSeek V4 **não** aceita imagem.
# `GET /models` só lista `deepseek-v4-pro` e `deepseek-v4-flash`; ambos rejeitam
# `content` com `image_url` (`400` — "unknown variant image_url, expected text").
# O cliente multimodal fica pronto para quando a DeepSeek publicar um modelo com
# visão na API; até lá, `IA-060` é o caminho esperado. Sobrescreva o nome com
# `MAPASFACIL_MODELO_VISAO` se um dia existir id multimodal.

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Protocol

from mapasfacil_nucleo.agente import limites
from mapasfacil_nucleo.erros import ErroNucleo

ENDPOINT_PADRAO = "https://api.deepseek.com/chat/completions"
# Placeholder histórico — nenhum id atual da API aceita imagem (teste live 2026-07-26).
MODELO_VISAO_PADRAO = "deepseek-vl"


def modelo_visao_configurado() -> str:
    return os.environ.get("MAPASFACIL_MODELO_VISAO", "").strip() or MODELO_VISAO_PADRAO


class ProvedorVisao(Protocol):
    def analisar(self, *, imagem_base64: str, mime: str, prompt: str) -> str:
        """Devolve o texto bruto da resposta do modelo — deve ser JSON (não parseado aqui)."""


class DeepSeekVisaoProvedor:
    def __init__(
        self,
        chave: str,
        *,
        endpoint: str = ENDPOINT_PADRAO,
        modelo: str | None = None,
        timeout: float = 60.0,
        urlopen: Any | None = None,
    ) -> None:
        self.chave = chave
        self.endpoint = endpoint
        self.modelo = modelo or modelo_visao_configurado()
        self.timeout = timeout
        self._urlopen = urlopen or urllib.request.urlopen

    def analisar(self, *, imagem_base64: str, mime: str, prompt: str) -> str:
        corpo = {
            "model": self.modelo,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{imagem_base64}"},
                        },
                    ],
                }
            ],
            "stream": False,
            "max_tokens": limites.SAIDA_MAX_TOKENS,
        }
        dados = json.dumps(corpo).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=dados,
            headers={
                "Authorization": f"Bearer {self.chave}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            resp = self._urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            detalhe = exc.read().decode(errors="replace")[:400]
            raise ErroNucleo(
                limites.CODIGO_VISAO_INDISPONIVEL,
                f"Modelo de visão indisponível (HTTP {exc.code}).",
                {"detalhe": detalhe},
            ) from exc
        except urllib.error.URLError as exc:
            raise ErroNucleo(
                limites.CODIGO_VISAO_INDISPONIVEL,
                f"Modelo de visão inacessível: {exc.reason}",
            ) from exc

        try:
            corpo_resp = resp.read()
        finally:
            try:
                resp.close()
            except Exception:  # noqa: BLE001 — fechar não pode mascarar erro real
                pass

        try:
            payload = json.loads(corpo_resp.decode("utf-8"))
            texto = payload["choices"][0]["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError, UnicodeDecodeError) as exc:
            raise ErroNucleo(
                limites.CODIGO_VISAO_INDISPONIVEL,
                "Resposta do modelo de visão em formato inesperado.",
            ) from exc
        return str(texto)


class ProvedorVisaoFixo:
    """Test double: devolve um texto fixo (ou uma sequência) sem rede — VCR simples."""

    def __init__(self, respostas: str | list[str]) -> None:
        self._respostas = [respostas] if isinstance(respostas, str) else list(respostas)
        self._indice = 0
        self.chamadas: list[dict[str, Any]] = []

    def analisar(self, *, imagem_base64: str, mime: str, prompt: str) -> str:
        self.chamadas.append(
            {"mime": mime, "prompt": prompt, "tamanho_imagem_base64": len(imagem_base64)}
        )
        if self._indice >= len(self._respostas):
            resposta = self._respostas[-1]
        else:
            resposta = self._respostas[self._indice]
            self._indice += 1
        return resposta


class ProvedorVisaoFalha:
    """Test double: sempre levanta erro — prova o caminho de degrade honesto."""

    def __init__(self, erro: ErroNucleo | None = None) -> None:
        self.erro = erro or ErroNucleo(limites.CODIGO_VISAO_INDISPONIVEL, "falha simulada")

    def analisar(self, *, imagem_base64: str, mime: str, prompt: str) -> str:
        del imagem_base64, mime, prompt
        raise self.erro
