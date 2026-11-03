#!/usr/bin/env python3
"""Smoke ao vivo do provedor de IA da web (W5-16 / W5-20).

O que ele prova, sem passar pelo chat e sem gravar nada do cliente:

| Bloco | Prova |
|---|---|
| `tools` | As **32** tools viajam, o modelo responde `finish_reason=tool_calls` e os argumentos são JSON válido com os campos obrigatórios do schema. |
| `paralelo` | O modelo pede **duas** tools no mesmo turno (a UI mostra as duas juntas). |
| `longo` | Um resultado de tool de ~6 kB volta ao modelo e ele usa um dado do meio do texto (sentinela). |
| `raciocinio` | `reasoning_content` chega pelo 9Router (vira `chat.raciocinio` na tela). |
| `stream` | Texto longo em stream: pedaços > 20, `finish_reason=stop`, nada truncado. |
| `contexto` | (opcional, `--contexto`) Qual o maior prompt que o pool aceita de verdade — é o número que vai em `MAPASFACIL_CONTEXTO_MAX`. |
| `visao` | (opcional, `--visao`) O modelo recebe `image_url` (print de mapa **sem dado de cliente**) e descreve o que vê — é o W5-20. |

A chave **nunca** é impressa: ou vem de `--env` (arquivo ou `-` para stdin, uso recomendado por
pipe de SSH), ou do ambiente.

    # no server, com a chave em arquivo 600:
    python3 ferramentas/provedor_smoke.py --env /home/server/segredos-mapasfacil/servidor.env

    # daqui, sem copiar a chave para o disco local:
    ssh sd 'cat /home/server/segredos-mapasfacil/servidor.env' | python ferramentas/provedor_smoke.py --env -
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Fase_1_Desktop" / "nucleo"))

from mapasfacil_nucleo.agente import limites, tools  # noqa: E402
from mapasfacil_nucleo.agente.openai_compat import (  # noqa: E402
    ENV_CHAVE,
    ENV_MODELO_CHAT,
    ENV_MODELO_VISAO,
    ENV_RACIOCINIO,
    ENV_URL,
    MODELO_PADRAO,
    RACIOCINIO_PADRAO,
    OpenAICompatProvedor,
    endpoint_de,
)
from mapasfacil_nucleo.agente.provedor import MensagemLLM  # noqa: E402

SENTINELA = "ZQ-7731-CAMADA"


# --------------------------------------------------------------------- entrada
def carregar_env(caminho: str) -> dict[str, str]:
    """Lê um `servidor.env` (KEY=valor por linha) ou o próprio ambiente."""
    if caminho == "-":
        texto = sys.stdin.read()
    else:
        p = Path(caminho)
        if not p.exists():
            raise SystemExit(f"arquivo de segredos não encontrado: {p}")
        texto = p.read_text(encoding="utf-8")
    env: dict[str, str] = {}
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        env[chave.strip()] = valor.strip().strip('"').strip("'")
    return {**os.environ, **env}


def provedor(env: dict[str, str], modelo: str | None = None) -> OpenAICompatProvedor:
    chave = (env.get(ENV_CHAVE) or "").strip()
    if not chave:
        raise SystemExit(f"sem {ENV_CHAVE} — nada a testar")
    return OpenAICompatProvedor(
        chave,
        base_url=(env.get(ENV_URL) or "http://100.104.255.35:20128/v1").strip(),
        modelo=modelo or (env.get(ENV_MODELO_CHAT) or MODELO_PADRAO).strip(),
        reasoning_effort=(env.get(ENV_RACIOCINIO) or RACIOCINIO_PADRAO).strip(),
        timeout=240.0,
    )


def falar(
    prov: OpenAICompatProvedor,
    mensagens: list[MensagemLLM],
    *,
    com_tools: bool = False,
    modelo: str | None = None,
    max_tokens: int = 1500,
) -> dict[str, Any]:
    """Um turno; devolve texto, raciocínio, tool_calls, finish e tempo."""
    inicio = time.monotonic()
    texto: list[str] = []
    raciocinio: list[str] = []
    pedacos = 0
    final = None
    esquemas = tools.schemas_openai() if com_tools else None
    for delta in prov.enviar_stream(
        mensagens, tools=esquemas, max_tokens=max_tokens, modelo=modelo
    ):
        if delta.texto:
            texto.append(delta.texto)
            pedacos += 1
        if delta.raciocinio:
            raciocinio.append(delta.raciocinio)
        if delta.finish_reason:
            final = delta
    return {
        "texto": "".join(texto),
        "raciocinio": "".join(raciocinio),
        "chunks": pedacos,
        "tool_calls": (final.tool_calls if final else []) or [],
        "finish_reason": (final.finish_reason if final else None),
        "truncado": bool(final.truncado) if final else False,
        "segundos": round(time.monotonic() - inicio, 1),
    }


# --------------------------------------------------------------------- blocos
def bloco_tools(prov: OpenAICompatProvedor) -> dict[str, Any]:
    """Uma tool obrigatória: nome válido, argumentos JSON e campos obrigatórios presentes."""
    esquemas = tools.schemas_openai()
    resposta = falar(
        prov,
        [
            MensagemLLM(
                "system",
                "Você opera mapas. Responda SEMPRE chamando uma ferramenta — nunca em texto.",
            ),
            MensagemLLM(
                "user",
                "Quais versões deste projeto já foram geradas? Consulte com a ferramenta certa.",
            ),
        ],
        com_tools=True,
        max_tokens=600,
    )
    nomes = {e["function"]["name"] for e in esquemas}
    problemas: list[str] = []
    if resposta["finish_reason"] != "tool_calls":
        problemas.append(f"finish_reason={resposta['finish_reason']} (esperado tool_calls)")
    if not resposta["tool_calls"]:
        problemas.append("nenhum tool_call")
    for call in resposta["tool_calls"]:
        nome = call.get("function", {}).get("name")
        if nome not in nomes:
            problemas.append(f"tool fora do catálogo: {nome}")
        bruto = call.get("function", {}).get("arguments") or "{}"
        try:
            args = json.loads(bruto)
        except json.JSONDecodeError as exc:
            problemas.append(f"argumentos não são JSON ({nome}): {exc}")
            continue
        obrig = next(
            (e["function"]["parameters"].get("required") or [] for e in esquemas if e["function"]["name"] == nome),
            [],
        )
        faltando = [c for c in obrig if c not in args]
        if faltando:
            problemas.append(f"{nome} sem obrigatórios: {faltando}")
    return {
        "ok": not problemas,
        "problemas": problemas,
        "schemas": len(esquemas),
        "tool_calls": [
            {"nome": c.get("function", {}).get("name"), "argumentos": c.get("function", {}).get("arguments")}
            for c in resposta["tool_calls"]
        ],
        "finish_reason": resposta["finish_reason"],
        "segundos": resposta["segundos"],
    }


def bloco_paralelo(prov: OpenAICompatProvedor) -> dict[str, Any]:
    """Duas tools no mesmo turno — é o que permite a UI mostrar as duas juntas."""
    resposta = falar(
        prov,
        [
            MensagemLLM(
                "system",
                "Você opera mapas. Use as ferramentas, sempre em paralelo quando fizer sentido.",
            ),
            MensagemLLM(
                "user",
                "Preciso do estado do projeto e da lista de versões ao mesmo tempo. "
                "Chame as duas ferramentas numa única resposta.",
            ),
        ],
        com_tools=True,
        max_tokens=800,
    )
    nomes = [c.get("function", {}).get("name") for c in resposta["tool_calls"]]
    return {
        "ok": len(nomes) >= 2 and resposta["finish_reason"] == "tool_calls",
        "tools": nomes,
        "finish_reason": resposta["finish_reason"],
        "segundos": resposta["segundos"],
    }


def bloco_resultado_longo(prov: OpenAICompatProvedor) -> dict[str, Any]:
    """Resultado de tool com ~6 kB: o modelo tem de achar a sentinela no meio."""
    linhas = [f"camada_{i:03d}: {i * 7} feições, tipo=polígono" for i in range(1, 160)]
    linhas.insert(80, f"camada_{80:03d}: {SENTINELA} — 42 feições, tipo=polígono")
    carga = "\n".join(linhas)
    resposta = falar(
        prov,
        [
            MensagemLLM("system", "Você lê resultados de ferramenta com atenção."),
            MensagemLLM("user", "Liste as camadas do projeto."),
            MensagemLLM(
                "assistant",
                "",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "listar_camadas", "arguments": "{}"},
                    }
                ],
            ),
            MensagemLLM("tool", carga, tool_call_id="call_1", name="listar_camadas"),
            MensagemLLM(
                "user",
                "Qual camada tem a marcação especial? Responda com o nome exato da camada.",
            ),
        ],
        max_tokens=400,
    )
    texto = resposta["texto"]
    return {
        "ok": SENTINELA in texto or "camada_080" in texto.lower(),
        "achou_sentinela": SENTINELA in texto,
        "resposta": texto[:200],
        "caracteres_enviados": len(carga),
        "segundos": resposta["segundos"],
    }


def bloco_raciocinio(prov: OpenAICompatProvedor) -> dict[str, Any]:
    resposta = falar(
        prov,
        [
            MensagemLLM(
                "user",
                "Um imóvel de 12,1 km de largura precisa caber em 28,5 cm de quadro com 15% de "
                "margem. Qual escala redonda? Mostre a conta.",
            )
        ],
        max_tokens=1200,
    )
    return {
        "ok": bool(resposta["raciocinio"]) and "50.000" in resposta["texto"].replace("50000", "50.000"),
        "caracteres_raciocinio": len(resposta["raciocinio"]),
        "resposta": resposta["texto"][:160],
        "finish_reason": resposta["finish_reason"],
        "segundos": resposta["segundos"],
    }


def bloco_stream(prov: OpenAICompatProvedor) -> dict[str, Any]:
    resposta = falar(
        prov,
        [
            MensagemLLM(
                "user",
                "Explique em 12 parágrafos numerados como montar um pacote de entrega de mapa "
                "(MXD, SHP, Mapas) que abra em outro computador. Texto corrido, sem ferramentas.",
            )
        ],
        max_tokens=limites.SAIDA_MAX_TOKENS,
    )
    return {
        "ok": resposta["chunks"] >= 20 and resposta["finish_reason"] == "stop" and not resposta["truncado"],
        "chunks": resposta["chunks"],
        "caracteres": len(resposta["texto"]),
        "finish_reason": resposta["finish_reason"],
        "truncado": resposta["truncado"],
        "segundos": resposta["segundos"],
    }


def bloco_visao(prov: OpenAICompatProvedor, imagem: Path, modelo_visao: str) -> dict[str, Any]:
    """W5-20 — o 9Router repassa `image_url` ao modelo de visão?"""
    if not imagem.exists():
        return {"ok": False, "erro": f"imagem não encontrada: {imagem}"}
    dados = base64.b64encode(imagem.read_bytes()).decode("ascii")
    sufixo = imagem.suffix.lower().lstrip(".") or "png"
    corpo = {
        "model": modelo_visao,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "O que aparece nesta imagem? Responda em uma frase."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/{sufixo};base64,{dados}"},
                    },
                ],
            }
        ],
        "max_tokens": 300,
    }
    req = urllib.request.Request(
        endpoint_de(prov.base_url),
        data=json.dumps(corpo).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {prov.chave}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    inicio = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "erro": f"HTTP {exc.code}",
            "detalhe": exc.read().decode(errors="replace")[:400],
            "modelo": modelo_visao,
        }
    except urllib.error.URLError as exc:
        return {"ok": False, "erro": f"rede: {exc.reason}", "modelo": modelo_visao}
    escolha = (payload.get("choices") or [{}])[0]
    texto = (escolha.get("message") or {}).get("content") or ""
    return {
        "ok": bool(texto.strip()),
        "modelo": modelo_visao,
        "resposta": texto[:300],
        "bytes_imagem": imagem.stat().st_size,
        "segundos": round(time.monotonic() - inicio, 1),
    }


def bloco_contexto(prov: OpenAICompatProvedor, tamanhos: list[int]) -> dict[str, Any]:
    """Maior prompt aceito de verdade — a medida que vai para `MAPASFACIL_CONTEXTO_MAX`."""
    resultados: list[dict[str, Any]] = []
    for tokens_alvo in tamanhos:
        # ~1 token por caractere de enchimento é ordem de grandeza suficiente para achar o teto.
        enchimento = ("camada de vegetação nativa em área consolidada. " * (tokens_alvo // 12 + 1))[
            : tokens_alvo
        ]
        corpo = {
            "model": prov.modelo,
            "messages": [
                {"role": "user", "content": enchimento + "\n\nQuantas palavras tem o texto acima?"}
            ],
            "max_tokens": 16,
            "stream": False,
            "stream_options": {"include_usage": True},
        }
        req = urllib.request.Request(
            endpoint_de(prov.base_url),
            data=json.dumps(corpo).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {prov.chave}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        inicio = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
            uso = payload.get("usage") or {}
            resultados.append(
                {
                    "pedido_tokens": tokens_alvo,
                    "ok": True,
                    "prompt_tokens": uso.get("prompt_tokens"),
                    "total_tokens": uso.get("total_tokens"),
                    "segundos": round(time.monotonic() - inicio, 1),
                }
            )
        except urllib.error.HTTPError as exc:
            detalhe = exc.read().decode(errors="replace")[:200]
            resultados.append({"pedido_tokens": tokens_alvo, "ok": False, "http": exc.code, "detalhe": detalhe})
            break
        except urllib.error.URLError as exc:
            resultados.append({"pedido_tokens": tokens_alvo, "ok": False, "erro": str(exc.reason)})
            break
    aceitos = [r for r in resultados if r["ok"]]
    return {
        "ok": bool(aceitos),
        # ⚠️ `prompt_tokens` do 9Router/pool é INFLADO e não serve de medida: um prompt de
        # ~900 tokens reais voltou como 14.842. O que vale é o **maior prompt que passou sem
        # erro** (medido pelo tamanho enviado) e o primeiro que falhou, se falhou.
        "maior_chars_aceitos": max((r["pedido_tokens"] for r in aceitos), default=0),
        "prompt_tokens_declarados": [r.get("prompt_tokens") for r in aceitos],
        "tentativas": resultados,
        "primeira_falha": next((r for r in resultados if not r["ok"]), None),
        "aviso_uso": "prompt_tokens do pool não é confiável; use maior_chars_aceitos",
    }


# ----------------------------------------------------------------------- main
BLOCOS = ("tools", "paralelo", "longo", "raciocinio", "stream")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Smoke do provedor de IA da web (W5-16/W5-20).")
    ap.add_argument("--env", dest="env", default=None, help="arquivo servidor.env ou '-' (stdin)")
    ap.add_argument("--modelo", default=None, help=f"modelo de chat (padrão {MODELO_PADRAO})")
    ap.add_argument("--blocos", default=",".join(BLOCOS), help=f"quais rodar ({', '.join(BLOCOS)})")
    ap.add_argument("--contexto", action="store_true", help="mede o contexto real (gasta muitos tokens)")
    ap.add_argument("--contexto-tamanhos", default="8000,32000", help="tamanhos de prompt a testar")
    ap.add_argument("--visao", default=None, help="arquivo de imagem para o teste W5-20")
    ap.add_argument("--json", dest="saida", default=None, help="grava o resultado em JSON")
    args = ap.parse_args(argv)

    env = carregar_env(args.env) if args.env else dict(os.environ)
    prov = provedor(env, args.modelo)
    modelo_visao = (env.get(ENV_MODELO_VISAO) or MODELO_PADRAO).strip()

    print(f"modelo={prov.modelo} raciocinio={prov.reasoning_effort} base={prov.base_url}")
    print(f"tools no catálogo: {len(tools.nomes_tools())}")

    resultado: dict[str, Any] = {
        "modelo": prov.modelo,
        "raciocinio": prov.reasoning_effort,
        "base_url": prov.base_url,
        "quando": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    falhas: list[str] = []
    escolhidos = [b.strip() for b in args.blocos.split(",") if b.strip()]
    for nome in escolhidos:
        if nome == "tools":
            r = bloco_tools(prov)
        elif nome == "paralelo":
            r = bloco_paralelo(prov)
        elif nome == "longo":
            r = bloco_resultado_longo(prov)
        elif nome == "raciocinio":
            r = bloco_raciocinio(prov)
        elif nome == "stream":
            r = bloco_stream(prov)
        else:
            print(f"bloco desconhecido: {nome}")
            continue
        resultado[nome] = r
        marca = "OK  " if r.get("ok") else "FALHA"
        print(f"[{marca}] {nome}: {json.dumps({k: v for k, v in r.items() if k != 'ok'}, ensure_ascii=False)[:220]}")
        if not r.get("ok"):
            falhas.append(nome)

    if args.contexto:
        tamanhos = [int(t) for t in args.contexto_tamanhos.split(",") if t.strip()]
        r = bloco_contexto(prov, tamanhos)
        resultado["contexto"] = r
        print(f"[{'OK  ' if r['ok'] else 'FALHA'}] contexto: maior prompt aceito={r['maior_chars_aceitos']} chars; tokens declarados={r['prompt_tokens_declarados']}")
        if not r["ok"]:
            falhas.append("contexto")

    if args.visao:
        r = bloco_visao(prov, Path(args.visao), modelo_visao)
        resultado["visao"] = r
        print(f"[{'OK  ' if r['ok'] else 'FALHA'}] visao ({modelo_visao}): {json.dumps({k: v for k, v in r.items() if k != 'ok'}, ensure_ascii=False)[:220]}")
        if not r["ok"]:
            falhas.append("visao")

    if args.saida:
        Path(args.saida).write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"resultado em {args.saida}")

    print("RESUMO:", "tudo verde" if not falhas else f"falhas em {falhas}")
    return 0 if not falhas else 1


if __name__ == "__main__":
    raise SystemExit(main())
