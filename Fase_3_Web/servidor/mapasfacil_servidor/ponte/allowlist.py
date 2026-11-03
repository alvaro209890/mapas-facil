"""O que o servidor pode pedir ao núcleo — e o que ele nunca pede (W-04 §allowlist).

Método fora da lista levanta `SV-201` **antes** de chegar ao worker. A lista é
fechada de propósito: cada método novo do núcleo obriga a uma decisão explícita
(ver `tests/test_allowlist.py`, que lê os métodos registrados no `__main__` do
núcleo quando ele está instalado).
"""

from __future__ import annotations

from ..erros import ErroServidor

PERMITIDOS: frozenset[str] = frozenset(
    {
        # handshake do worker
        "ping",
        # workspace
        "workspace.abrir",
        "workspace.inspecionar",
        "workspace.reindexar",
        # conversa (uma principal por projeto — D25)
        "chat.criar_conversa",
        "chat.abrir_conversa",
        "chat.carregar_anteriores",
        "chat.enviar",
        "chat.cancelar",
        "chat.renomear",
        "chat.listar_conversas",
        "chat.buscar",
        # geração
        "mapa.gerar",
        "mapa.cancelar",
        "analise.executar",
        "mapspec.validar",
        "mapspec.diff",
        "quantitativos.calcular",
        "quantitativos.exportar_xlsx",
        "quantitativos.renderizar_png",
        "galeria.listar",
        "galeria.detalhar",
        "galeria.montar_mapspec",
        "catalogo.listar",
        "doctor.rodar",
    }
)

# Bloqueados com motivo escrito: o servidor tem a própria versão (conta, segredo) ou
# lê o arquivo direto (artefato).
BLOQUEADOS: dict[str, str] = {
    "cofre.definir": "o cofre do servidor é o servidor.env, não o keyring (NU-060)",
    "conta.criar": "contas do site vivem no banco do servidor (W3)",
    "conta.entrar": "contas do site vivem no banco do servidor (W3)",
    "conta.sair": "contas do site vivem no banco do servidor (W3)",
    "sessao.definir": "a sessão vem do banco do servidor (AUTH-090)",
    "sessao.estado": "a sessão vem do banco do servidor (AUTH-090)",
    "chat.apagar": "conversa não se apaga pela web (D26)",
    "chat.arquivar": "conversa não se arquiva pela web (D26)",
    "chat.ramificar": "ramificação é do desktop (D26)",
    "chat.gravar_mensagem": "a mensagem é gravada pelo próprio núcleo no turno",
    "artefato.ler": "o servidor lê arquivo direto, com allowlist de prefixos",
    "camada.resolver": "resolução de camada passa por catalogo.listar",
    "conta.estado": "contas do site vivem no banco do servidor (W3)",
    "car.ler_recibo": "o recibo é lido na importação, que é do servidor (W4)",
    "zip.listar": "o ZIP é importado pelo servidor (W4)",
    "zip.extrair": "o ZIP é importado pelo servidor (W4)",
    "template.listar": "o servidor lê o MANIFEST direto; o catálogo vem de galeria.listar",
    "template.verificar": "verificação de template é do núcleo na geração",
    "validacao.comparar_pdf": "a validação roda dentro de mapa.gerar",
    "cofre.existe": "o cofre do servidor é o servidor.env",
    "cofre.testar": "o cofre do servidor é o servidor.env",
}


def verificar(metodo: str) -> None:
    """Levanta `SV-201` se o método não for permitido. Chamado antes do worker."""
    if metodo in PERMITIDOS:
        return
    motivo = BLOQUEADOS.get(metodo)
    raise ErroServidor(
        "SV-201",
        f"O método {metodo!r} não é permitido pela ponte.",
        status_http=403,
        porque=motivo or "Método fora da allowlist do servidor (W-04).",
        o_que_fazer="Se o método deveria existir na web, inclua-o em "
        "`ponte/allowlist.py` e no plano W-04 antes de chamar.",
        detalhes={"metodo": metodo},
    )


def permitido(metodo: str) -> bool:
    return metodo in PERMITIDOS
