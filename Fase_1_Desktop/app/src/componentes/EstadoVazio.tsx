// C9 — estados vazios, de carregamento e de erro (F1-02 §Estados vazios).
//
// Regra da casa para erro: **o que aconteceu, por quê, o que fazer** — nunca só o
// código. Por isso `saidas` é uma lista de próximos passos, e o código aparece ao
// lado do título, em monoespaçada, para o usuário copiar no suporte.
//
// Estado nunca é comunicado só por cor (F1-16 §Acessibilidade): todo tom tem
// ícone + texto.

import type { ReactNode } from "react";
import { CircleAlert, FolderOpen, Info, Plug, TriangleAlert } from "lucide-react";

import estilos from "./EstadoVazio.module.css";

export type TomEstado = "neutro" | "info" | "aviso" | "erro";

export interface AcaoEstadoVazio {
  rotulo: string;
  aoAcionar: () => void;
  primaria?: boolean;
}

export interface PropsEstadoVazio {
  titulo: string;
  descricao: ReactNode;
  tom?: TomEstado;
  /** Código estável (`NU-`, `UI-`, `AG-`…) quando o estado veio de um erro. */
  codigo?: string;
  /** O que fazer a seguir, em ordem de recomendação. */
  saidas?: string[];
  acoes?: AcaoEstadoVazio[];
  icone?: ReactNode;
}

const ICONE_PADRAO: Record<TomEstado, ReactNode> = {
  neutro: <FolderOpen size={18} aria-hidden="true" />,
  info: <Info size={18} aria-hidden="true" />,
  aviso: <TriangleAlert size={18} aria-hidden="true" />,
  erro: <CircleAlert size={18} aria-hidden="true" />,
};

export function EstadoVazio({
  titulo,
  descricao,
  tom = "neutro",
  codigo,
  saidas,
  acoes,
  icone,
}: PropsEstadoVazio) {
  return (
    <div className={estilos.bloco} data-tom={tom} role={tom === "erro" ? "alert" : undefined}>
      <div className={estilos.cabecalho}>
        <span className={estilos.icone} data-tom={tom}>
          {icone ?? ICONE_PADRAO[tom]}
        </span>
        <span className={estilos.titulo}>{titulo}</span>
        {codigo !== undefined && <span className={estilos.codigo}>{codigo}</span>}
      </div>
      <p className={estilos.descricao}>{descricao}</p>
      {saidas !== undefined && saidas.length > 0 && (
        <div className={estilos.saidas}>
          {saidas.map((saida) => (
            <span key={saida} className={estilos.saida}>
              {saida}
            </span>
          ))}
        </div>
      )}
      {acoes !== undefined && acoes.length > 0 && (
        <div className={estilos.acoes}>
          {acoes.map((acao) => (
            <button
              key={acao.rotulo}
              type="button"
              className={estilos.acao}
              data-primaria={acao.primaria === true}
              onClick={acao.aoAcionar}
            >
              {acao.rotulo}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- casos de F1-02
// Cada função abaixo é uma linha da tabela de estados do plano. Só existem os
// casos que a UI consegue mostrar hoje com dado real; login, sessão expirada e
// "sem internet" chegam com os marcos deles (M5, camadas externas).

export function SemPastaConectada({ aoConectar }: { aoConectar: () => void }) {
  return (
    <EstadoVazio
      titulo="Nenhuma pasta conectada"
      descricao={
        <>
          Conecte a pasta do projeto para o Mapas Fácil indexar os shapefiles, ler o recibo do CAR
          e mostrar as áreas. Nada sai do seu computador.
        </>
      }
      acoes={[{ rotulo: "Conectar pasta", aoAcionar: aoConectar, primaria: true }]}
      icone={<FolderOpen size={18} aria-hidden="true" />}
    />
  );
}

export function PastaSemShapefile({ aoConectarOutra }: { aoConectarOutra: () => void }) {
  return (
    <EstadoVazio
      tom="aviso"
      titulo="A pasta não tem shapefile"
      descricao={
        <>
          O app procura <code>.shp</code> (com <code>.prj</code>, <code>.dbf</code> e{" "}
          <code>.shx</code> ao lado) para montar as camadas. Se o material veio do SIMCAR, o{" "}
          <code>.zip</code> serve: arraste-o para a pasta e reindexe.
        </>
      }
      saidas={[
        "Conferir se você apontou para a pasta do imóvel, e não para a pasta que a contém",
        "Colocar o .zip do SIMCAR na pasta e clicar em reindexar",
      ]}
      acoes={[{ rotulo: "Conectar outra pasta", aoAcionar: aoConectarOutra }]}
    />
  );
}

export function NucleoCaido({ aoReiniciar }: { aoReiniciar: () => void }) {
  return (
    <EstadoVazio
      tom="erro"
      codigo="UI-001"
      titulo="O núcleo do Mapas Fácil parou"
      descricao={
        <>
          O processo que lê os shapefiles e gera os mapas não está respondendo. O app tentou
          reiniciá-lo três vezes sozinho antes de mostrar isto.
        </>
      }
      saidas={[
        "Reiniciar o núcleo e tentar de novo",
        "Se voltar a cair, abrir o doctor e copiar o diagnóstico",
      ]}
      acoes={[{ rotulo: "Reiniciar o núcleo", aoAcionar: aoReiniciar, primaria: true }]}
      icone={<Plug size={18} aria-hidden="true" />}
    />
  );
}

export function ErroDoNucleo({
  codigo,
  mensagem,
  aoTentarDeNovo,
}: {
  codigo: string;
  mensagem: string;
  aoTentarDeNovo?: () => void;
}) {
  const saidas =
    codigo === "NU-010"
      ? ["Escolher uma pasta dentro do projeto — o app só lê o que você conectou"]
      : ["Conferir se a pasta ainda existe e se você tem permissão de leitura nela"];
  return (
    <EstadoVazio
      tom="erro"
      codigo={codigo}
      titulo="Não deu para abrir essa pasta"
      descricao={mensagem}
      saidas={saidas}
      acoes={
        aoTentarDeNovo === undefined
          ? undefined
          : [{ rotulo: "Tentar de novo", aoAcionar: aoTentarDeNovo, primaria: true }]
      }
    />
  );
}

export function SemChaveDeepSeek() {
  return (
    <EstadoVazio
      tom="info"
      codigo="IA-001"
      titulo="Sem chave da DeepSeek"
      descricao={
        <>
          O chat com o agente fica indisponível, mas o app continua inteiro: conectar pasta, ler o
          recibo, calcular quantitativos e gerar mapa pela galeria não dependem de IA.
        </>
      }
      saidas={["Configurar a chave depois, em preferências — nada aqui fica bloqueado"]}
    />
  );
}

export function SemArcMap({ motor }: { motor: string }) {
  return (
    <EstadoVazio
      tom="info"
      titulo="Sem ArcMap neste computador"
      descricao={
        <>
          O <code>.mxd</code> sai pelo caminho de template e o PDF pelo motor nativo. O motor
          escolhido agora é <code>{motor}</code>.
        </>
      }
      saidas={["Para paridade total com o padrão Harmonia, gerar num PC com ArcMap 10.6–10.8"]}
    />
  );
}

export function SemInternet() {
  return (
    <EstadoVazio
      tom="aviso"
      titulo="Sem internet"
      descricao={
        <>
          O app continua local: pasta, chats, galeria e geração nativa não dependem de rede.
          Camadas externas (SEMA, INCRA, mosaicos) usam o cache quando houver — com a idade que o
          núcleo gravou na última consulta.
        </>
      }
      saidas={[
        "Reconecte para atualizar camadas externas além do TTL do cache",
        "Geração pela galeria e o chat com chave local seguem disponíveis",
      ]}
    />
  );
}
