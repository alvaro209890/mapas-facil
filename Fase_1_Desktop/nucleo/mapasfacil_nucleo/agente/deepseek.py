# Cliente DeepSeek (chat completions + stream SSE). temperature não é enviado
# (ignorado nos modelos de raciocínio — F1-06).

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Iterator

from mapasfacil_nucleo.agente import limites
from mapasfacil_nucleo.agente.provedor import DeltaStream, MensagemLLM
from mapasfacil_nucleo.erros import ErroNucleo

ENDPOINT_PADRAO = "https://api.deepseek.com/chat/completions"
MODELO_PRO = "deepseek-chat"  # alias estável; V4 Pro quando disponível na conta
MODELO_FLASH = "deepseek-chat"


class DeepSeekProvedor:
    def __init__(
        self,
        chave: str,
        *,
        endpoint: str = ENDPOINT_PADRAO,
        modelo: str = MODELO_PRO,
        timeout: float = 120.0,
        urlopen: Any | None = None,
    ) -> None:
        self.chave = chave
        self.endpoint = endpoint
        self.modelo = modelo
        self.timeout = timeout
        self._urlopen = urlopen or urllib.request.urlopen
        self._cancelado = False
        self._resposta: Any = None

    def cancelar(self) -> None:
        self._cancelado = True
        resp = self._resposta
        if resp is not None:
            try:
                resp.close()
            except Exception:
                pass

    def enviar_stream(
        self,
        mensagens: list[MensagemLLM],
        *,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = limites.SAIDA_MAX_TOKENS,
        modelo: str | None = None,
    ) -> Iterator[DeltaStream]:
        self._cancelado = False
        corpo: dict[str, Any] = {
            "model": modelo or self.modelo,
            "messages": [_msg_para_api(m) for m in mensagens],
            "stream": True,
            "max_tokens": max_tokens,
        }
        if tools:
            corpo["tools"] = tools
            corpo["tool_choice"] = "auto"
        dados = json.dumps(corpo).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=dados,
            headers={
                "Authorization": f"Bearer {self.chave}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            method="POST",
        )
        try:
            self._resposta = self._urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            detalhe = exc.read().decode(errors="replace")[:400]
            raise ErroNucleo(
                limites.CODIGO_PROVEDOR_INDISPONIVEL,
                f"DeepSeek HTTP {exc.code}.",
                {"detalhe": detalhe},
            ) from exc
        except urllib.error.URLError as exc:
            raise ErroNucleo(
                limites.CODIGO_PROVEDOR_INDISPONIVEL,
                f"DeepSeek inacessível: {exc.reason}",
            ) from exc

        tool_acc: dict[int, dict[str, Any]] = {}
        finish: str | None = None
        try:
            for linha_bruta in self._resposta:
                if self._cancelado:
                    break
                linha = linha_bruta.decode("utf-8", errors="replace").strip()
                if not linha or not linha.startswith("data:"):
                    continue
                payload = linha[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    evento = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                escolha = (evento.get("choices") or [{}])[0]
                delta = escolha.get("delta") or {}
                finish = escolha.get("finish_reason") or finish
                texto = delta.get("content") or ""
                raciocinio = delta.get("reasoning_content") or ""
                for tc in delta.get("tool_calls") or []:
                    idx = int(tc.get("index", 0))
                    atual = tool_acc.setdefault(
                        idx,
                        {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
                    )
                    if tc.get("id"):
                        atual["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        atual["function"]["name"] = fn["name"]
                    if fn.get("arguments"):
                        atual["function"]["arguments"] += fn["arguments"]
                yield DeltaStream(texto=texto, raciocinio=raciocinio)
        finally:
            try:
                self._resposta.close()
            except Exception:
                pass
            self._resposta = None

        calls = [tool_acc[i] for i in sorted(tool_acc)]
        truncado = finish == "length"
        yield DeltaStream(
            texto="",
            tool_calls=calls,
            finish_reason=finish or "stop",
            truncado=truncado,
        )


def _msg_para_api(m: MensagemLLM) -> dict[str, Any]:
    papel = m.papel
    if papel == "assistente":
        papel = "assistant"
    out: dict[str, Any] = {"role": papel, "content": m.conteudo}
    if m.tool_call_id:
        out["tool_call_id"] = m.tool_call_id
    if m.name:
        out["name"] = m.name
    if m.tool_calls:
        out["tool_calls"] = m.tool_calls
        out["content"] = m.conteudo or None
    return out
