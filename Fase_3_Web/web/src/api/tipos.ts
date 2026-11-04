/**
 * Tipos da API do Mapas Fácil (W6-02).
 *
 * Escritos à mão a partir de W-03 (`03-api-http-e-eventos.md`) e conferidos contra o
 * código do servidor: `projetos_repo.Projeto`, `api/mensajes`, `eventos/log.py`
 * (envelope) e o vocabulário fechado de `eventos/vocabulario.py`. O teste
 * `api/tipos.test.ts` compara este vocabulário com a lista do servidor, para os dois
 * lados não divergirem em silêncio.
 */

export type FormatoFolha = 'A4' | 'A3' | 'A2' | 'A1' | 'A0';
export type Orientacao = 'retrato' | 'paisagem';

/** Estados do projeto, na ordem em que a vida dele acontece. */
export type EstadoProjeto =
  | 'aguardando_zip'
  | 'importando'
  | 'indexando'
  | 'pronto'
  | 'gerando'
  | 'erro'
  | 'lixeira';

export interface Folha {
  formato: FormatoFolha;
  orientacao: Orientacao;
  escala_elementos?: 'proporcional' | 'fixa';
}

export interface Imovel {
  nome?: string | null;
  car?: string | null;
  municipio?: string | null;
  uf?: string | null;
}

export interface Projeto {
  id: string;
  nome: string;
  estado: EstadoProjeto;
  folha: Folha;
  imovel: Imovel;
  versao_atual: number;
  miniatura: string | null;
  atualizado_em: string;
  criado_em?: string;
  erro_codigo?: string | null;
}

export interface Versao {
  numero: number;
  pasta: string;
  conforme: boolean;
  miniatura: string | null;
  artefatos: Record<string, string>;
  validacao: Validacao;
  criada_em: string;
}

/** Checks da validação: `hard` reprova o mapa, `soft` só avisa. */
export interface Validacao {
  motor?: string;
  confianca?: string;
  checks?: {
    hard?: CheckValidacao[];
    soft?: CheckValidacao[];
  };
}

export interface CheckValidacao {
  id: string;
  ok: boolean;
  mensagem?: string;
}

export interface Usuario {
  id: string;
  nome: string;
  email: string;
  papel: 'admin' | 'usuario';
  bloqueado?: boolean;
  /** Conta criada pelo admin: o primeiro acesso exige senha nova. */
  trocar_senha?: boolean;
  criado_em?: string;
}

/** Corpo de `/auth/eu`, `/auth/entrar` e `/auth/cadastrar`. */
export interface Sessao {
  usuario: Usuario;
  csrf: string;
  /** Legado: o servidor manda a flag dentro de `usuario`. */
  trocar_senha?: boolean;
}

/** Corpo de erro padrão do servidor — `erro` em toda resposta não-2xx. */
export interface ErroApi {
  codigo: string;
  mensagem: string;
  /** `undefined` explícito: o projeto usa `exactOptionalPropertyTypes`. */
  porque?: string | undefined;
  o_que_fazer?: string | undefined;
  detalhes?: Record<string, unknown> | undefined;
}

/** Envelope de evento, igual ao gravado em `eventos.log.registrar()`. */
export interface Evento {
  seq: number;
  ts: string;
  origem: 'nucleo' | 'servidor';
  evento: string;
  req_id?: string | null;
  job_id?: string | null;
  dados: Record<string, unknown>;
}

export interface Mensagem {
  message_id: string;
  seq: number;
  papel: 'usuario' | 'assistente' | 'sistema';
  texto: string;
  criada_em: string;
  /** Tools que o agente chamou neste turno (volta no `GET /mensagens`). */
  tool_traces?: TraceMensagem[];
}

/** Tool de um turno passado, como o servidor devolve no histórico. */
export interface TraceMensagem {
  trace_id: string;
  tool: string;
  args_resumo?: string | null;
  resultado_resumo?: string | null;
  ok?: boolean;
  ms?: number | null;
}

export interface Sugestao {
  id: string;
  texto: string;
  porque: string;
}

export interface ResumoProjeto {
  projeto_id: string;
  estado: EstadoProjeto;
  resumo: Record<string, unknown> | null;
}

export interface PaginaProjetos {
  itens: Projeto[];
  proximo?: string | null;
}

export interface SaudeResposta {
  ok: boolean;
  versao: string;
  nucleo?: string;
  upload_max_mb?: number;
}

/** Eventos do vocabulário fechado do servidor (`eventos/vocabulario.py`). */
export const EVENTOS_NUCLEO = [
  'job.progresso',
  'job.log',
  'job.artefato_parcial',
  'workspace.mudou',
  'chat.delta',
  'chat.raciocinio',
  'chat.tool',
  'chat.pergunta',
  'mapspec.atualizado',
  'aviso',
  // palco (W7)
  'viewport.foco',
  'camada.renderizada',
  'layout.elemento',
  'revisao.visual',
] as const;

export const EVENTOS_SERVIDOR = [
  'projeto.estado',
  'importacao.progresso',
  'worker.estado',
  'mensagem.criada',
  'versao.criada',
  'nucleo.res',
  'sse.heartbeat',
] as const;

export type EventoConhecido = (typeof EVENTOS_NUCLEO)[number] | (typeof EVENTOS_SERVIDOR)[number];
