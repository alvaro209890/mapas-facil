from __future__ import annotations

from pathlib import Path
import uuid
from typing import Any

import pymupdf

from mapasfacil_nucleo.agente.registro import RegistroFerramentas, _erro, _ok
from mapasfacil_nucleo.agente.tools_workspace import _obter_workspace, _resolver_caminho_seguro, _resolver_saida_nova
from mapasfacil_nucleo.protocolo import Emissor


def registrar_tools_pdf(registro: RegistroFerramentas) -> None:
    @registro.ferramenta(
        nome="pdf_preview",
        descricao="Gera preview em imagem (PNG) de uma página específica de um arquivo PDF.",
        categoria="pdf",
        parametros={
            "type": "object",
            "properties": {
                "caminho_pdf": {
                    "type": "string",
                    "description": "Caminho relativo do arquivo PDF.",
                },
                "pagina": {
                    "type": "integer",
                    "description": "Número da página (1-indexado, padrão: 1).",
                },
                "dpi": {
                    "type": "integer",
                    "description": "Resolução da imagem em DPI (padrão: 150).",
                },
            },
            "required": ["caminho_pdf"],
            "additionalProperties": False,
        },
    )
    def tool_pdf_preview(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        try:
            ws_root = _obter_workspace(ctx)
            alvo = _resolver_caminho_seguro(args["caminho_pdf"], ws_root)
            if not alvo.exists():
                return _erro("PDF-001", f"Arquivo PDF '{alvo.name}' não existe.")

            num_pagina = int(args.get("pagina", 1))
            dpi = max(36, min(200, int(args.get("dpi", 150))))
            fator_zoom = dpi / 72.0

            doc = pymupdf.open(str(alvo))
            total_pags = len(doc)
            if num_pagina < 1 or num_pagina > total_pags:
                doc.close()
                return _erro(
                    "PDF-002",
                    f"Página {num_pagina} inválida. O PDF possui {total_pags} página(s).",
                )

            page = doc[num_pagina - 1]
            mat = pymupdf.Matrix(fator_zoom, fator_zoom)
            pix = page.get_pixmap(matrix=mat)

            pasta_preview = ws_root / "Mapas" / "previews"
            pasta_preview.mkdir(parents=True, exist_ok=True)
            nome_preview = f"{alvo.stem}_p{num_pagina}_{uuid.uuid4().hex[:12]}.png"
            caminho_img = _resolver_saida_nova(f"Mapas/previews/{nome_preview}", ws_root)
            pix.save(str(caminho_img))
            doc.close()

            rel_preview = caminho_img.relative_to(ws_root).as_posix()
            emissor: Emissor | None = ctx.get("emissor")
            if emissor is not None:
                emissor.emitir(
                    "agente.preview",
                    {"caminho": rel_preview, "pagina": num_pagina},
                )

            return _ok(
                {
                    "preview_caminho": rel_preview,
                    "pagina": num_pagina,
                    "total_paginas": total_pags,
                    "largura": pix.width,
                    "altura": pix.height,
                }
            )
        except Exception as exc:
            return _erro("PDF-003", f"Falha ao gerar preview do PDF: {exc}")

    @registro.ferramenta(
        nome="pdf_texto",
        descricao="Extrai o conteúdo textual estruturado de uma ou todas as páginas de um PDF.",
        categoria="pdf",
        parametros={
            "type": "object",
            "properties": {
                "caminho_pdf": {"type": "string", "description": "Caminho relativo do PDF."},
                "pagina": {
                    "type": "integer",
                    "description": "Página específica (opcional, padrão todas).",
                },
            },
            "required": ["caminho_pdf"],
            "additionalProperties": False,
        },
    )
    def tool_pdf_texto(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        try:
            ws_root = _obter_workspace(ctx)
            alvo = _resolver_caminho_seguro(args["caminho_pdf"], ws_root)
            if not alvo.exists():
                return _erro("PDF-001", f"Arquivo PDF '{alvo.name}' não existe.")

            doc = pymupdf.open(str(alvo))
            pag_especifica = args.get("pagina")
            paginas = []

            if pag_especifica is not None:
                p_idx = int(pag_especifica) - 1
                if 0 <= p_idx < len(doc):
                    paginas.append({"pagina": int(pag_especifica), "texto": doc[p_idx].get_text()})
            else:
                for idx, page in enumerate(doc, start=1):
                    paginas.append({"pagina": idx, "texto": page.get_text()})

            total = len(doc)
            doc.close()
            return _ok(
                {
                    "caminho": alvo.relative_to(ws_root).as_posix(),
                    "total_paginas": total,
                    "paginas": paginas,
                }
            )
        except Exception as exc:
            return _erro("PDF-004", f"Falha ao extrair texto do PDF: {exc}")

    @registro.ferramenta(
        nome="pdf_unir",
        descricao="Combina múltiplos arquivos PDF em um único documento unificado.",
        categoria="pdf",
        parametros={
            "type": "object",
            "properties": {
                "caminhos": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de caminhos relativos dos PDFs a unir na ordem desejada.",
                },
                "caminho_saida": {
                    "type": "string",
                    "description": "Caminho relativo do arquivo PDF compilado.",
                },
            },
            "required": ["caminhos", "caminho_saida"],
            "additionalProperties": False,
        },
    )
    def tool_pdf_unir(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        try:
            ws_root = _obter_workspace(ctx)
            caminhos = args.get("caminhos", [])
            if not caminhos:
                return _erro("PDF-005", "Lista de arquivos para unir está vazia.")

            p_saida = _resolver_saida_nova(args["caminho_saida"], ws_root)
            p_saida.parent.mkdir(parents=True, exist_ok=True)

            doc_unido = pymupdf.open()
            for c in caminhos:
                p_arq = _resolver_caminho_seguro(c, ws_root)
                if not p_arq.exists():
                    doc_unido.close()
                    return _erro("PDF-001", f"Arquivo PDF '{c}' não existe.")
                doc_parte = pymupdf.open(str(p_arq))
                doc_unido.insert_pdf(doc_parte)
                doc_parte.close()

            doc_unido.save(str(p_saida))
            total = len(doc_unido)
            doc_unido.close()

            rel_saida = p_saida.relative_to(ws_root).as_posix()
            emissor: Emissor | None = ctx.get("emissor")
            if emissor is not None:
                emissor.emitir("agente.arquivo", {"caminho": rel_saida, "acao": "criacao"})

            return _ok({"caminho_saida": rel_saida, "total_paginas": total})
        except Exception as exc:
            return _erro("PDF-006", f"Falha ao unir PDFs: {exc}")
