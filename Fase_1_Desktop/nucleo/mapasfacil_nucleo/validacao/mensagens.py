"""Catálogo de mensagens humanas e ações recomendadas para os checks de validação (W11-07).

A IA não redige o diagnóstico do zero: ela consulta este catálogo para
obter a explicação oficial do escritório e a orientação ('o_que_fazer').
"""

from __future__ import annotations

from typing import Any

CATALOGO_CHECKS: dict[str, dict[str, str]] = {
    # CHECKS HARD (H01–H22)
    "H01": {
        "nome": "Perímetro Fechado",
        "severidade": "hard",
        "explicacao": "A geometria do imóvel deve ser um polígono fechado e válido.",
        "o_que_fazer": "Verifique o arquivo shapefile ou reprocesse o polígono do perímetro com buffer(0).",
    },
    "H02": {
        "nome": "CRS Definido",
        "severidade": "hard",
        "explicacao": "O sistema de coordenadas do projeto deve estar explicitamente definido.",
        "o_que_fazer": "Inclua o arquivo .prj no shapefile ou defina o CRS do projeto para EPSG:31982/31981/31980.",
    },
    "H03": {
        "nome": "Camadas Mínimas",
        "severidade": "hard",
        "explicacao": "O mapa exige ao menos a camada de perímetro do imóvel.",
        "o_que_fazer": "Importe o perímetro do imóvel no arquivo .zip do projeto.",
    },
    "H04": {
        "nome": "Título Presente",
        "severidade": "hard",
        "explicacao": "O layout do mapa exige um título identificador.",
        "o_que_fazer": "Defina o nome da fazenda ou título do mapa na barra lateral ou pelo chat.",
    },
    "H05": {
        "nome": "Escala Numérica Válida",
        "severidade": "hard",
        "explicacao": "A escala do mapa deve ser um valor numérico positivo.",
        "o_que_fazer": "Solicite o reenquadramento automático ou informe uma escala válida.",
    },
    "H15": {
        "nome": "PDF Válido e Abrível",
        "severidade": "hard",
        "explicacao": "O arquivo PDF exportado deve ser um documento PDF válido e sem corrupção.",
        "o_que_fazer": "Gere novamente a versão pelo motor nativo ou binário.",
    },
    "H16": {
        "nome": "Página Única",
        "severidade": "hard",
        "explicacao": "Cada mapa individual deve conter exatamente uma página.",
        "o_que_fazer": "Verifique se a configuração do layout não gerou páginas adicionais no documento.",
    },
    "H17": {
        "nome": "Área Coincidente com o CAR",
        "severidade": "hard",
        "explicacao": "A área do perímetro calculada em SIRGAS 2000 UTM deve coincidir com a área declarada do CAR dentro da tolerância oficial.",
        "o_que_fazer": "Verifique se o shapefile do perímetro é a versão oficial retificada aprovada no CAR.",
    },
    "H18": {
        "nome": "Documento Livre de Segredos",
        "severidade": "hard",
        "explicacao": "O arquivo .mxd não pode conter chaves de API, senhas ou tokens em texto puro.",
        "o_que_fazer": "Limpe as URLs WMS/WMTS com chaves privadas antes de gerar a entrega.",
    },
    "H19": {
        "nome": "Integridade Estrutural do MXD",
        "severidade": "hard",
        "explicacao": "O .mxd deve abrir perfeitamente sem sentinelas órfãs nos slots de texto e atributos.",
        "o_que_fazer": "Regenere o MXD garantindo o preenchimento de todos os slots de layout.",
    },
    "H20": {
        "nome": "Fontes de Dados Relativas ao Pacote",
        "severidade": "hard",
        "explicacao": "Todas as camadas do .mxd devem apontar para a pasta relativa ..\\SHP dentro do pacote .zip.",
        "o_que_fazer": "Utilize a ferramenta de substituição de workspace relativo antes de empacotar.",
    },

    # CHECKS SOFT (S01–S25)
    "S12": {
        "nome": "Divergência Leve de Área",
        "severidade": "soft",
        "explicacao": "Pequena divergência entre a área calculada e a área cadastral do recibo.",
        "o_que_fazer": "Aviso informativo; não impede a entrega do mapa nem a homologação.",
    },
    "S20": {
        "nome": "Escala Não Redonda",
        "severidade": "soft",
        "explicacao": "A escala escolhida não pertence aos degraus redondos padronizados do escritório.",
        "o_que_fazer": "Se desejar um mapa padrão de prateleira, use 1:40.000 ou 1:50.000.",
    },
    "S21": {
        "nome": "Texto Sobre Linha Vetorial",
        "severidade": "soft",
        "explicacao": "Foi detectado texto ou rótulo sobreposto à linha de shapefile (APP, ARL ou Perímetro).",
        "o_que_fazer": "Desloque o rótulo para fora do polígono ou reduza o tamanho da fonte.",
    },
    "S22": {
        "nome": "Elemento Fora da Folha",
        "severidade": "soft",
        "explicacao": "Um elemento gráfico ou textual ultrapassou as margens da folha.",
        "o_que_fazer": "Reposicione o elemento dentro da área útil da página.",
    },
    "S23": {
        "nome": "Inconsistência na Legenda",
        "severidade": "soft",
        "explicacao": "A legenda contém itens de camadas que não estão visíveis no mapa ou omite camadas ativas.",
        "o_que_fazer": "Ajuste a lista de itens da legenda para refletir as camadas visíveis.",
    },
    "S24": {
        "nome": "Minimapa sem Centroide",
        "severidade": "soft",
        "explicacao": "O indicador de localização do minimapa não engloba o centroide do imóvel.",
        "o_que_fazer": "Reenquadre o quadro de localização regional.",
    },
    "S25": {
        "nome": "Sobreposição de Elementos de Layout",
        "severidade": "soft",
        "explicacao": "Dois elementos de layout (como norte, barra de escala ou legenda) colidiram.",
        "o_que_fazer": "Separe os elementos arrastando-os no palco ou ajustando suas posições.",
    },
}


def obter_mensagem_check(check_id: str) -> dict[str, str]:
    """Retorna a explicação oficial e orientação para o check especificado."""
    return CATALOGO_CHECKS.get(
        check_id.upper(),
        {
            "nome": f"Check {check_id}",
            "severidade": "soft",
            "explicacao": f"Validação referente ao check {check_id}.",
            "o_que_fazer": "Consulte o checklist de validação em planos/01-padrao-imap-harmonia.md.",
        },
    )
