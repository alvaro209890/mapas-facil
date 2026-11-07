"""Projetos: repositório e máquina de estados (W-03 §Projetos, `SV-090`)."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass

from .auth import sessoes
from .erros import ErroServidor

ESTADOS = (
    "aguardando_zip",
    "importando",
    "indexando",
    "pronto",
    "gerando",
    "erro",
    "lixeira",
)

# Transições permitidas. Qualquer outra → `SV-090`.
TRANSICOES: dict[str, frozenset[str]] = {
    "aguardando_zip": frozenset({"importando", "lixeira"}),
    "importando": frozenset({"indexando", "erro", "lixeira"}),
    "indexando": frozenset({"pronto", "erro", "lixeira"}),
    "pronto": frozenset({"gerando", "importando", "erro", "lixeira"}),
    "gerando": frozenset({"pronto", "erro", "lixeira"}),
    "erro": frozenset({"aguardando_zip", "importando", "lixeira"}),
    "lixeira": frozenset({"pronto", "aguardando_zip"}),
}

FORMATOS = frozenset({"A4", "A3", "A2", "A1", "A0"})
ORIENTACOES = frozenset({"retrato", "paisagem"})


@dataclass(frozen=True)
class Projeto:
    id: str
    usuario_id: str
    nome: str
    estado: str
    folha: dict
    imovel: dict
    versao_atual: int
    miniatura: str | None
    erro_codigo: str | None
    criado_em: str
    atualizado_em: str

    def resumo(self) -> dict:
        return {
            "id": self.id,
            "nome": self.nome,
            "estado": self.estado,
            "folha": self.folha,
            "imovel": self.imovel,
            "versao_atual": self.versao_atual,
            "miniatura": self.miniatura,
            "atualizado_em": self.atualizado_em,
        }

    def completo(self) -> dict:
        dados = self.resumo()
        dados.update(
            {
                "criado_em": self.criado_em,
                "erro_codigo": self.erro_codigo,
            }
        )
        return dados


def _de_linha(linha: sqlite3.Row) -> Projeto:
    return Projeto(
        id=linha["id"],
        usuario_id=linha["usuario_id"],
        nome=linha["nome"],
        estado=linha["estado"],
        folha={
            "formato": linha["folha_formato"],
            "orientacao": linha["folha_orientacao"],
        },
        imovel={
            "nome": linha["imovel_nome"],
            "car": linha["imovel_car"],
            "municipio": linha["imovel_municipio"],
            "uf": linha["imovel_uf"],
        },
        versao_atual=int(linha["versao_atual"]),
        miniatura=linha["miniatura"],
        erro_codigo=linha["erro_codigo"],
        criado_em=linha["criado_em"],
        atualizado_em=linha["atualizado_em"],
    )


def _agora() -> str:
    return sessoes.iso(sessoes.agora())


def validar_folha(folha: dict | None) -> dict:
    if not isinstance(folha, dict):
        raise ErroServidor(
            "SV-091",
            "Informe a folha do projeto.",
            status_http=400,
            o_que_fazer="Escolha o formato (A4 a A0) e a orientação.",
        )
    formato = folha.get("formato")
    orientacao = folha.get("orientacao", "retrato")
    if formato not in FORMATOS:
        raise ErroServidor(
            "SV-091",
            f"Formato de folha inválido: {formato!r}.",
            status_http=400,
            detalhes={"formatos": sorted(FORMATOS)},
        )
    if orientacao not in ORIENTACOES:
        raise ErroServidor(
            "SV-091",
            f"Orientação inválida: {orientacao!r}.",
            status_http=400,
            detalhes={"orientacoes": sorted(ORIENTACOES)},
        )
    return {"formato": formato, "orientacao": orientacao}


def criar(
    con: sqlite3.Connection,
    *,
    usuario_id: str,
    nome: str,
    folha: dict,
) -> Projeto:
    nome = (nome or "").strip()
    if not nome or len(nome) > 120:
        raise ErroServidor(
            "SV-092",
            "O nome do projeto precisa ter de 1 a 120 caracteres.",
            status_http=400,
        )
    folha_ok = validar_folha(folha)
    projeto_id = uuid.uuid4().hex
    momento = _agora()
    con.execute(
        "INSERT INTO projetos (id, usuario_id, nome, estado, folha_formato, folha_orientacao,"
        " versao_atual, criado_em, atualizado_em) VALUES (?,?,?,?,?,?,0,?,?)",
        (
            projeto_id,
            usuario_id,
            nome,
            "aguardando_zip",
            folha_ok["formato"],
            folha_ok["orientacao"],
            momento,
            momento,
        ),
    )
    projeto = obter(con, projeto_id, usuario_id=usuario_id)
    assert projeto is not None
    return projeto


def obter(
    con: sqlite3.Connection, projeto_id: str, *, usuario_id: str, admin: bool = False
) -> Projeto | None:
    """Projeto do dono (ou qualquer um, para admin em leitura). Alheio = `SV-031`."""
    linha = con.execute("SELECT * FROM projetos WHERE id = ?", (projeto_id,)).fetchone()
    if linha is None:
        return None
    if not admin and linha["usuario_id"] != usuario_id:
        raise ErroServidor(
            "SV-031",
            "Projeto não encontrado.",
            status_http=404,
            porque="Projeto de outra conta é indistinguível de projeto inexistente.",
        )
    return _de_linha(linha)


def exigir(
    con: sqlite3.Connection, projeto_id: str, *, usuario_id: str, admin: bool = False
) -> Projeto:
    projeto = obter(con, projeto_id, usuario_id=usuario_id, admin=admin)
    if projeto is None:
        raise ErroServidor("SV-031", "Projeto não encontrado.", status_http=404)
    return projeto


def listar(
    con: sqlite3.Connection,
    *,
    usuario_id: str,
    admin: bool = False,
    busca: str | None = None,
    estado: str | None = None,
    antes: str | None = None,
    limite: int = 50,
) -> dict:
    limite = max(1, min(int(limite or 50), 200))
    where = ["1=1"]
    params: list[object] = []
    if not admin:
        where.append("usuario_id = ?")
        params.append(usuario_id)
    if estado:
        if estado not in ESTADOS:
            raise ErroServidor("SV-093", f"Estado inválido: {estado!r}.", status_http=400)
        where.append("estado = ?")
        params.append(estado)
    else:
        where.append("estado <> 'lixeira'")
    if busca:
        where.append("(nome LIKE ? OR imovel_nome LIKE ? OR imovel_car LIKE ?)")
        alvo = f"%{busca.strip()}%"
        params.extend([alvo, alvo, alvo])
    if antes:
        linha = con.execute(
            "SELECT atualizado_em FROM projetos WHERE id = ?", (antes,)
        ).fetchone()
        if linha is not None:
            # Cursor estável: vários projetos criados no mesmo segundo não somem
            # nem repetem (ordem por atualizado_em DESC, id DESC).
            where.append("(atualizado_em < ? OR (atualizado_em = ? AND id < ?))")
            params.extend([linha["atualizado_em"], linha["atualizado_em"], antes])

    sql = (
        "SELECT * FROM projetos WHERE "
        + " AND ".join(where)
        + " ORDER BY atualizado_em DESC, id DESC LIMIT ?"
    )
    params.append(limite + 1)
    linhas = con.execute(sql, params).fetchall()
    itens = [_de_linha(linha).resumo() for linha in linhas[:limite]]
    # `proximo` é o id do **último item entregue** — o cursor de `?antes=` é
    # exclusivo, então tem de apontar para o fim da página, não para o começo da próxima.
    proximo = linhas[limite - 1]["id"] if len(linhas) > limite else None
    return {"itens": itens, "proximo": proximo}


def transicionar(
    con: sqlite3.Connection,
    projeto: Projeto,
    novo: str,
    *,
    erro_codigo: str | None = None,
) -> Projeto:
    if novo not in ESTADOS:
        raise ErroServidor("SV-093", f"Estado inválido: {novo!r}.", status_http=400)
    if novo not in TRANSICOES[projeto.estado]:
        raise ErroServidor(
            "SV-090",
            f"Transição de {projeto.estado!r} para {novo!r} não é permitida.",
            status_http=409,
            porque="O estado do projeto segue uma máquina fechada; pular etapa "
            "deixaria dado pela metade.",
            detalhes={"de": projeto.estado, "para": novo},
        )
    con.execute(
        "UPDATE projetos SET estado = ?, erro_codigo = ?, atualizado_em = ? WHERE id = ?",
        (novo, erro_codigo, _agora(), projeto.id),
    )
    atualizado = obter(con, projeto.id, usuario_id=projeto.usuario_id, admin=True)
    assert atualizado is not None
    return atualizado


def renomear(con: sqlite3.Connection, projeto: Projeto, nome: str) -> Projeto:
    nome = (nome or "").strip()
    if not nome or len(nome) > 120:
        raise ErroServidor("SV-092", "O nome do projeto precisa ter de 1 a 120 caracteres.", status_http=400)
    con.execute(
        "UPDATE projetos SET nome = ?, atualizado_em = ? WHERE id = ?",
        (nome, _agora(), projeto.id),
    )
    atualizado = obter(con, projeto.id, usuario_id=projeto.usuario_id, admin=True)
    assert atualizado is not None
    return atualizado


def atualizar_imovel(con: sqlite3.Connection, projeto: Projeto, imovel: dict) -> Projeto:
    con.execute(
        "UPDATE projetos SET imovel_nome = ?, imovel_car = ?, imovel_municipio = ?,"
        " imovel_uf = ?, atualizado_em = ? WHERE id = ?",
        (
            imovel.get("nome"),
            imovel.get("car"),
            imovel.get("municipio"),
            imovel.get("uf"),
            _agora(),
            projeto.id,
        ),
    )
    atualizado = obter(con, projeto.id, usuario_id=projeto.usuario_id, admin=True)
    assert atualizado is not None
    return atualizado


def registrar_versao(
    con: sqlite3.Connection,
    projeto: Projeto,
    *,
    numero: int,
    pasta: str,
    conforme: bool,
    miniatura: str | None,
    artefatos: dict,
    validacao: dict,
) -> None:
    """Grava a versão e atualiza `versao_atual`/`miniatura` do projeto (W2-05 → W3)."""
    con.execute(
        "INSERT OR REPLACE INTO versoes (projeto_id, numero, pasta, conforme, miniatura,"
        " artefatos, validacao, criada_em) VALUES (?,?,?,?,?,?,?,?)",
        (
            projeto.id,
            numero,
            pasta,
            1 if conforme else 0,
            miniatura,
            json.dumps(artefatos, ensure_ascii=False),
            json.dumps(validacao, ensure_ascii=False),
            _agora(),
        ),
    )
    con.execute(
        "UPDATE projetos SET versao_atual = ?, miniatura = ?, atualizado_em = ? WHERE id = ?",
        (numero, miniatura, _agora(), projeto.id),
    )


def versoes(con: sqlite3.Connection, projeto_id: str) -> list[dict]:
    linhas = con.execute(
        "SELECT * FROM versoes WHERE projeto_id = ? ORDER BY numero DESC", (projeto_id,)
    ).fetchall()
    return [
        {
            "numero": linha["numero"],
            "pasta": linha["pasta"],
            "conforme": bool(linha["conforme"]),
            "miniatura": linha["miniatura"],
            "artefatos": json.loads(linha["artefatos"] or "{}"),
            "criada_em": linha["criada_em"],
        }
        for linha in linhas
    ]


def salvar_imoveis(
    con: sqlite3.Connection,
    projeto_id: str,
    imoveis: list[dict],
) -> list[dict]:
    momento = _agora()
    salvos = []
    for idx, im in enumerate(imoveis, start=1):
        im_id = str(im.get("id") or f"imovel_{idx}")
        registro_id = f"{projeto_id}_{im_id}"
        nome = str(im.get("nome") or f"Imóvel {idx}")
        car = im.get("car")
        matricula = im.get("matricula")
        area = im.get("area")
        area_ha = float(area) if isinstance(area, (int, float)) else None
        atp = im.get("atp")
        principal = 1 if im.get("principal") else 0

        con.execute(
            "INSERT INTO imoveis_projeto (id, projeto_id, imovel_id, nome, car, matricula, area_ha, atp_fonte, principal, criado_em)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(projeto_id, imovel_id) DO UPDATE SET"
            "   nome=excluded.nome,"
            "   car=excluded.car,"
            "   matricula=excluded.matricula,"
            "   area_ha=excluded.area_ha,"
            "   atp_fonte=excluded.atp_fonte,"
            "   principal=excluded.principal",
            (
                registro_id,
                projeto_id,
                im_id,
                nome,
                car,
                matricula,
                area_ha,
                atp,
                principal,
                momento,
            ),
        )
        salvos.append({
            "id": im_id,
            "nome": nome,
            "car": car,
            "matricula": matricula,
            "area": area_ha,
            "atp": atp,
            "principal": bool(principal),
        })
    return salvos


def listar_imoveis(con: sqlite3.Connection, projeto_id: str) -> list[dict]:
    linhas = con.execute(
        "SELECT * FROM imoveis_projeto WHERE projeto_id = ? ORDER BY principal DESC, criado_em ASC",
        (projeto_id,),
    ).fetchall()
    return [
        {
            "id": linha["imovel_id"],
            "nome": linha["nome"],
            "car": linha["car"],
            "matricula": linha["matricula"],
            "area": linha["area_ha"],
            "atp": linha["atp_fonte"],
            "principal": bool(linha["principal"]),
        }
        for linha in linhas
    ]
