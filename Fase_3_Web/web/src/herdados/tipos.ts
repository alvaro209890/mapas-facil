/**
 * Tipos que os componentes herdados do desktop usam.
 *
 * Os componentes de `herdados/` foram copiados de `Fase_1_Desktop/app/src/componentes/`
 * (W6-01) e antes importavam de `../estado/*`. Aqui ficam **só os tipos** — a web não
 * herda as stores do desktop (isso é o W6-03), então o mínimo é declarado localmente e
 * coberto pela guarda de contrato de `api/tipos.test.ts`.
 */

/** Payload de `chat.tool`. */
export interface DadosChatTool {
  trace_id: string;
  tool: string;
  fase: 'inicio' | 'fim';
  args_resumo?: string;
  resultado_resumo?: string;
  ms?: number;
  ok?: boolean;
}

/** Payload de `chat.raciocinio`. */
export interface DadosChatRaciocinio {
  texto: string;
  streaming?: boolean;
}

/** Opção clicável de uma pergunta do agente. */
export interface OpcaoPergunta {
  id: string;
  rotulo: string;
}

/** Payload de `chat.pergunta`. */
export interface DadosChatPergunta {
  pergunta: string;
  opcoes: OpcaoPergunta[];
  permite_texto_livre: boolean;
}

/** Diff estrutural do MapSpec — mesma forma de `mapspec/diff.py::diff`. */
export interface DiffMapspec {
  operacoes: { op: 'adicionar' | 'remover' | 'alterar'; caminho: string; antes?: unknown; depois?: unknown }[];
  total?: number;
  id_antes?: string | null;
  id_depois?: string | null;
  versao_antes?: number | null;
  versao_depois?: number | null;
  /** Linhas prontas para exibir — `agente/edicao.py::descrever_diff`. */
  resumo: string[];
}

/** Versão do MapSpec como a `LinhaVersoes` a desenha. */
export interface VersaoMapspec {
  id: string;
  versao: number;
  diff: DiffMapspec;
  /** Ordem de chegada — chave estável para animação (crossfade/flash). */
  chave: string;
}
