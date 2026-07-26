# F1-07 §"O que vai para o modelo" — só interpretação; o prompt recebe a imagem
# **e as medidas já feitas**, instruído a não contradizê-las. Vocabulário
# fechado (estilos/série) no próprio prompt — não impede o modelo de inventar,
# mas `mapear.sanitizar_resposta` descarta o que vier fora da lista (AP-04).

from __future__ import annotations

import json
from typing import Any

INSTRUCAO = """Você está olhando um print ou PDF de um mapa florestal (padrão IMAP/Harmonia,
Mato Grosso — CAR, SIMCAR, embargos, terras indígenas, unidades de conservação).

Já medimos o que dá para medir sem você (orientação, proporção, cores dominantes, moldura). Não
contradiga essas medidas — sua função é só interpretar o que exige julgamento: qual mapa da série
é este, o que cada entrada de legenda significa, e qual estilo do catálogo mais se aproxima de
cada cor.

Responda SÓ com um objeto JSON válido, sem markdown, sem texto fora do JSON, neste formato:

{
  "mapa_da_serie": "<um destes: %(series)s, ou null se não souber>",
  "ano": <inteiro ou null>,
  "template_sugerido": "<id de template do padrão Harmonia, ou null>",
  "confianca": <0.0 a 1.0 — confiança geral na leitura>,
  "camadas": [
    {"legenda_lida": "<texto>", "cor_amostrada": "#RRGGBB",
     "estilo_sugerido": "<um destes: %(estilos)s>", "confianca": <0.0 a 1.0>}
  ],
  "metadados_lidos": [{"rotulo": "<texto>", "valor": "<texto>"}],
  "tabela_presente": <true ou false>,
  "observacoes": ["<texto livre, o que fugiu do padrão>"]
}

Seja honesto com a confiança — abaixo de 0.7 é normal e esperado quando o print é ruim ou a
legenda é ambígua. Nunca invente `estilo_sugerido` ou `mapa_da_serie` fora das listas acima."""


def montar_prompt(
    *,
    medidas: dict[str, Any],
    estilos_permitidos: list[str],
    mapas_serie: list[str],
) -> str:
    cabecalho = INSTRUCAO % {
        "series": ", ".join(sorted(mapas_serie)),
        "estilos": ", ".join(sorted(estilos_permitidos)),
    }
    medidas_json = json.dumps(medidas, ensure_ascii=False, indent=2, sort_keys=True)
    return f"{cabecalho}\n\nMEDIDAS JÁ FEITAS (determinístico, não contradiga):\n{medidas_json}"
