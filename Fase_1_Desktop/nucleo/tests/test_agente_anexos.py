from __future__ import annotations

import base64
from pathlib import Path

import pytest

from mapasfacil_nucleo.agente.anexos import LIMITE_ANEXO_BYTES, validar_anexos
from mapasfacil_nucleo.conversas.repositorio import RepositorioConversas
from mapasfacil_nucleo.erros import ErroNucleo


def test_validar_anexo_base64_e_limite() -> None:
    dados = b"PNG"
    anexos = validar_anexos(
        [
            {
                "nome": r"C:\capturas\mapa.png",
                "mime": "image/png",
                "bytes": len(dados),
                "base64": base64.b64encode(dados).decode("ascii"),
            }
        ]
    )
    assert anexos[0].nome == "mapa.png"
    assert anexos[0].dados == dados

    with pytest.raises(ErroNucleo) as exc:
        validar_anexos(
            [
                {
                    "nome": "grande.png",
                    "mime": "image/png",
                    "bytes": LIMITE_ANEXO_BYTES + 1,
                    "base64": "",
                }
            ]
        )
    assert exc.value.codigo == "CH-004"


def test_repositorio_persiste_anexo_e_contexto_so_recebe_metadados(tmp_path: Path) -> None:
    repo = RepositorioConversas(tmp_path / "chats")
    cid = repo.criar_conversa()["conversation_id"]
    mensagem = repo.adicionar_mensagem(cid, papel="usuario", conteudo="Veja o print")
    salvo = repo.adicionar_anexo(
        cid,
        message_id=mensagem["message_id"],
        indice=1,
        nome_original="mapa.png",
        mime="image/png",
        dados=b"PNG",
    )

    caminho = tmp_path / "chats" / "anexos" / salvo["caminho_local"]
    assert caminho.read_bytes() == b"PNG"
    aberto = repo.abrir_conversa(cid)
    assert aberto["mensagens"][0]["conteudo"] == "Veja o print"
    assert aberto["mensagens"][0]["anexos"][0]["nome_original"] == "mapa.png"
    contexto = repo.contexto_para_turno(cid)
    assert "modelo atual é somente texto" in contexto.mensagens[0]["conteudo"]
    assert "UE5H" not in contexto.mensagens[0]["conteudo"]
    repo.fechar()
