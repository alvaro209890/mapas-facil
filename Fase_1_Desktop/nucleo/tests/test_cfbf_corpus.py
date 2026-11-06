"""Testes de conformidade e round-trip do motor CFBF contra o corpus de arquivos MXD.

Valida a leitura e o reempacotamento sem alterações em todos os arquivos de:
- shared/templates/ (22 arquivos .mxd)
- Referencias_IMAP/MXD/ (26 arquivos: 24 .mxd válidos e 2 arquivos não-CFBF)

Utiliza o olefile como oráculo de validação independente nos testes para garantir
que o leitor/escritor puro stdlib em mapasfacil_nucleo.mxd_binario.cfbf funcione de
forma absolutamente fiel à especificação MS-CFB v3.
"""
from __future__ import annotations

from pathlib import Path

import olefile
import pytest

from mapasfacil_nucleo.config import raiz_repositorio
from mapasfacil_nucleo.mxd_binario import (
    AssinaturaInvalidaError,
    CompoundFile,
    StreamNaoEncontradaError,
    ler,
)

# Coleta de todos os arquivos do corpus
_RAIZ = raiz_repositorio()
_PASTA_TEMPLATES = _RAIZ / "shared" / "templates"
_PASTA_REFERENCIAS = _RAIZ / "Referencias_IMAP" / "MXD"

_ARQUIVOS_TEMPLATES = sorted(_PASTA_TEMPLATES.glob("*.mxd"))

# Cópia solta do MXD pré-projeto do Dinamica_retrato (dado local, não versionado;
# ver docs/fase3-rodada-2026-11-05-mxd-aline.md). Fica fora do corpus para a
# contagem ser a mesma no CI e numa máquina que tenha o arquivo.
FORA_DO_CORPUS = frozenset({"Dinamica_retrato_pre_projeto.mxd"})

_ARQUIVOS_REFERENCIAS = sorted(
    [f for f in _PASTA_REFERENCIAS.iterdir() if f.is_file() and f.name not in FORA_DO_CORPUS]
)
ARQUIVOS_CORPUS = _ARQUIVOS_TEMPLATES + _ARQUIVOS_REFERENCIAS


def id_arquivo(caminho: Path) -> str:
    pasta = caminho.parent.name
    return f"{pasta}/{caminho.name}"


def test_contagem_corpus() -> None:
    """Garante que o corpus cobre exatamente os 48 arquivos especificados (22 templates + 26 referências)."""
    assert len(_ARQUIVOS_TEMPLATES) == 22, (
        f"Esperado 22 templates em {_PASTA_TEMPLATES}, encontrado {len(_ARQUIVOS_TEMPLATES)}"
    )
    assert len(_ARQUIVOS_REFERENCIAS) == 26, (
        f"Esperado 26 arquivos em {_PASTA_REFERENCIAS}, encontrado {len(_ARQUIVOS_REFERENCIAS)}"
    )
    assert len(ARQUIVOS_CORPUS) == 48, (
        f"Esperado 48 arquivos no total do corpus, encontrado {len(ARQUIVOS_CORPUS)}"
    )


@pytest.mark.parametrize("caminho_arquivo", ARQUIVOS_CORPUS, ids=id_arquivo)
def test_cfbf_corpus_roundtrip(caminho_arquivo: Path, tmp_path: Path) -> None:
    """Para cada arquivo do corpus:

    - Se for CFBF válido (.mxd): lê com cfbf.ler(), compara streams com olefile,
      salva no tmp_path, relê o salvo com olefile e valida stream por stream.
    - Se for um arquivo não-CFBF (ex.: script .py ou doc .md presente na pasta):
      confirma que cfbf.ler() levanta AssinaturaInvalidaError explicitando o motivo.
    """
    assert caminho_arquivo.exists(), f"Arquivo do corpus não encontrado: {caminho_arquivo}"

    # Arquivos que não são CFBF (ex.: _chk_texts.py ou DOCUMENTACAO_MXD_HARMONIA.md)
    if not olefile.isOleFile(str(caminho_arquivo)):
        with pytest.raises(AssinaturaInvalidaError) as exc_info:
            ler(caminho_arquivo)
        msg_erro = str(exc_info.value)
        assert caminho_arquivo.name in msg_erro
        assert "assinatura" in msg_erro.lower() or "cabeçalho" in msg_erro.lower()
        return

    # 1. Leitura via leitor próprio puro stdlib
    cf = ler(caminho_arquivo)
    assert isinstance(cf, CompoundFile)
    assert len(cf.streams) > 0

    # 2. Leitura independente via olefile (oráculo de validação)
    ole_orig = olefile.OleFileIO(str(caminho_arquivo))
    ole_orig_streams = {e[0]: ole_orig.openstream(e).read() for e in ole_orig.listdir()}
    ole_orig.close()

    # Confere nomes das streams
    assert set(cf.streams.keys()) == set(ole_orig_streams.keys()), (
        f"Divergência nos nomes das streams em {caminho_arquivo.name}"
    )

    # Confere tamanho e conteúdo de cada stream lida
    for nome, dados_ole in ole_orig_streams.items():
        dados_cf = cf.obter_stream(nome)
        assert len(dados_cf) == len(dados_ole), (
            f"Tamanho divergiu na stream '{nome}' em {caminho_arquivo.name}: "
            f"{len(dados_cf)} vs {len(dados_ole)}"
        )
        assert dados_cf == dados_ole, (
            f"Conteúdo de bytes divergiu na stream '{nome}' em {caminho_arquivo.name}"
        )

    # 3. Salva cópia reempacotada sem alterações
    destino = tmp_path / f"repack_{caminho_arquivo.name}"
    cf.salvar(destino)
    assert destino.exists()
    assert destino.stat().st_size >= 512

    # 4. Relê o arquivo reempacotado com olefile
    ole_repack = olefile.OleFileIO(str(destino))
    ole_repack_streams = {e[0]: ole_repack.openstream(e).read() for e in ole_repack.listdir()}
    ole_repack.close()

    assert set(ole_repack_streams.keys()) == set(ole_orig_streams.keys()), (
        f"Streams no arquivo salvo divergiram em {caminho_arquivo.name}"
    )

    # 5. Confere byte a byte cada stream relida do arquivo salvo
    for nome, dados_originais in ole_orig_streams.items():
        dados_salvos = ole_repack_streams[nome]
        assert len(dados_salvos) == len(dados_originais), (
            f"Tamanho pós-reempacotamento divergiu na stream '{nome}' em {caminho_arquivo.name}: "
            f"{len(dados_salvos)} vs {len(dados_originais)}"
        )
        assert dados_salvos == dados_originais, (
            f"Conteúdo pós-reempacotamento divergiu na stream '{nome}' em {caminho_arquivo.name}"
        )


def test_substituir_streams_pequeno_e_grande(tmp_path: Path) -> None:
    """Substitui uma stream pequena (< 4096) e uma grande (>= 4096) e valida que só elas mudaram."""
    template_path = _PASTA_TEMPLATES / "Dinamica_2026.mxd"
    cf = ler(template_path)

    lista = cf.listar_streams()
    pequenas = [nome for nome, tam in lista if 0 < tam < 4096]
    grandes = [nome for nome, tam in lista if tam >= 4096]

    assert pequenas, "Deveria haver pelo menos uma stream pequena (< 4096 bytes)"
    assert grandes, "Deveria haver pelo menos uma stream grande (>= 4096 bytes)"

    nome_pequena = pequenas[0]
    nome_grande = grandes[0]

    # Novos bytes com padrão determinístico
    novos_pequena = b"[NOVO_PEQUENO]" + bytes(range(100))
    novos_grande = b"[NOVO_GRANDE]" + (b"MAPAS_FACIL_MXD_BINARIO_" * 300)

    tam_ret_p = cf.substituir(nome_pequena, novos_pequena)
    assert tam_ret_p == len(novos_pequena)
    assert cf.obter_stream(nome_pequena) == novos_pequena

    tam_ret_g = cf.substituir(nome_grande, novos_grande)
    assert tam_ret_g == len(novos_grande)
    assert cf.obter_stream(nome_grande) == novos_grande

    destino = tmp_path / "modificado.mxd"
    cf.salvar(destino)

    # Validação via olefile
    ole_mod = olefile.OleFileIO(str(destino))
    assert ole_mod.openstream([nome_pequena]).read() == novos_pequena
    assert ole_mod.openstream([nome_grande]).read() == novos_grande

    # Validação de que TODAS as outras streams permaneceram idênticas
    cf_orig = ler(template_path)
    for nome, tam in lista:
        if nome not in (nome_pequena, nome_grande):
            assert ole_mod.openstream([nome]).read() == cf_orig.obter_stream(nome), (
                f"Stream não alterada '{nome}' foi indevidamente modificada!"
            )
    ole_mod.close()


def test_substituir_redimensionamento_crossover(tmp_path: Path) -> None:
    """Testa crossover: stream pequena crescendo para >= 4096 e grande encolhendo para < 4096."""
    template_path = _PASTA_TEMPLATES / "Dinamica_2026.mxd"
    cf = ler(template_path)

    lista = cf.listar_streams()
    nome_pequena = [nome for nome, tam in lista if 0 < tam < 4096][0]
    nome_grande = [nome for nome, tam in lista if tam >= 4096][0]

    # Pequena vira grande (8192 bytes >= 4096)
    novos_dados_gigante = b"X" * 8192
    cf.substituir(nome_pequena, novos_dados_gigante)

    # Grande vira pequena (128 bytes < 4096)
    novos_dados_anani = b"Y" * 128
    cf.substituir(nome_grande, novos_dados_anani)

    destino = tmp_path / "crossover.mxd"
    cf.salvar(destino)

    ole = olefile.OleFileIO(str(destino))
    assert ole.openstream([nome_pequena]).read() == novos_dados_gigante
    assert ole.openstream([nome_grande]).read() == novos_dados_anani
    ole.close()


def test_substituir_stream_inexistente_levanta_erro() -> None:
    template_path = _PASTA_TEMPLATES / "Dinamica_2026.mxd"
    cf = ler(template_path)
    with pytest.raises(StreamNaoEncontradaError):
        cf.substituir("Stream_Que_Nao_Existe_12345", b"dados")


def test_arquivo_inexistente_levanta_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        ler(Path("caminho_inexistente_mapasfacil.mxd"))
