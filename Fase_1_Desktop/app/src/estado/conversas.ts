// F6 / F1-17 — estado do histórico de conversas no renderer.
//
// Espelha os métodos `chat.*` do núcleo (`nucleo/.../conversas/servico.py`). Nada
// aqui inventa conversa: sem núcleo, `situacao` vira `erro` com `UI-001` e a barra
// mostra isso — não uma lista vazia que parece "você ainda não conversou".
//
// Paginação em dois eixos, como o plano manda: a LISTA pagina por `updated_at`
// (`antes_de`) e a CONVERSA aberta pagina por `seq` (`carregar_anteriores`). As
// conversas já abertas ficam num cache por id, para reabrir não pagar ida e volta.

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "./ponte.js";

export interface ItemConversa {
  conversation_id: string;
  title: string;
  updated_at: string;
  workspace_nome: string | null;
  mensagens_total: number;
  ultimo_trecho: string | null;
  arquivada: boolean;
  ramificada: boolean;
}

export interface MensagemConversa {
  message_id: string;
  seq: number;
  papel: "usuario" | "assistente" | "sistema" | "tool";
  conteudo: string;
  criado_em: string;
  mapspec_id: string | null;
  mapspec_versao: number | null;
  cancelada: boolean;
}

export interface TracoTool {
  trace_id: string;
  message_id: string | null;
  tool: string;
  args_resumo: string | null;
  resultado_resumo: string | null;
  ms: number | null;
  ok: boolean;
  erro_codigo: string | null;
  criado_em: string;
}

export interface CabecalhoConversa {
  conversation_id: string;
  title: string;
  title_manual: boolean;
  created_at: string;
  updated_at: string;
  workspace_nome: string | null;
  workspace_fingerprint: string;
  workspace_path: string | null;
  conta_id: string | null;
  arquivada: boolean;
  parent_conversation_id: string | null;
  parent_message_seq: number | null;
  modelo: string | null;
  tokens_entrada: number;
  tokens_saida: number;
  compact_ate_seq: number | null;
}

export interface ConversaAberta {
  conversa: CabecalhoConversa;
  mensagens: MensagemConversa[];
  compact_summary: string | null;
  total: number;
  tem_anteriores: boolean;
  tool_traces: TracoTool[];
  mapspecs: { mapspec_id: string; versao: number; criado_em: string }[];
  /** `seq` que a busca encontrou — a transcrição rola até ele ao abrir. */
  focoSeq?: number;
}

export interface ResultadoBusca {
  conversation_id: string;
  message_id: string;
  seq: number;
  title: string;
  workspace_nome: string | null;
  trecho_destacado: string;
  updated_at: string;
}

export interface ErroUi {
  codigo: string;
  mensagem: string;
}

export type SituacaoConversas = "idle" | "carregando" | "pronta" | "erro";

const LIMITE_LISTA = 50;
const LIMITE_MENSAGENS = 30;
const LIMITE_ANTERIORES = 50;

const SEM_NUCLEO: ErroUi = {
  codigo: "UI-001",
  mensagem: "O núcleo não respondeu; o histórico local não pôde ser lido.",
};

export interface EstadoConversas {
  situacao: SituacaoConversas;
  lista: ItemConversa[];
  temMais: boolean;
  incluirArquivadas: boolean;
  soDestaPasta: boolean;
  aberta: ConversaAberta | null;
  carregandoAberta: boolean;
  termo: string;
  resultados: ResultadoBusca[] | null;
  erro: ErroUi | null;
}

const INICIAL: EstadoConversas = {
  situacao: "idle",
  lista: [],
  temMais: false,
  incluirArquivadas: false,
  soDestaPasta: false,
  aberta: null,
  carregandoAberta: false,
  termo: "",
  resultados: null,
  erro: null,
};

export interface AcoesConversas {
  recarregar: () => Promise<void>;
  carregarMais: () => Promise<void>;
  alternarSoDestaPasta: () => void;
  alternarArquivadas: () => void;
  criar: () => Promise<string | null>;
  abrir: (conversationId: string, focoSeq?: number) => Promise<void>;
  fechar: () => void;
  carregarAnteriores: () => Promise<void>;
  renomear: (conversationId: string, title: string) => Promise<void>;
  arquivar: (conversationId: string, arquivada: boolean) => Promise<void>;
  apagar: (conversationId: string) => Promise<void>;
  ramificar: (conversationId: string, aPartirDoSeq: number) => Promise<void>;
  buscar: (termo: string) => Promise<void>;
  limparBusca: () => void;
}

/** `workspaceRaiz` é o caminho que o núcleo devolveu em `workspace.abrir`. */
export function useConversas(workspaceRaiz: string | null): EstadoConversas & AcoesConversas {
  const [estado, setEstado] = useState<EstadoConversas>(INICIAL);
  // Refs para não recriar cada ação a cada tecla digitada na busca.
  const raizRef = useRef(workspaceRaiz);
  raizRef.current = workspaceRaiz;
  const filtrosRef = useRef({ soDestaPasta: false, incluirArquivadas: false });
  filtrosRef.current = {
    soDestaPasta: estado.soDestaPasta,
    incluirArquivadas: estado.incluirArquivadas,
  };
  const cache = useRef(new Map<string, ConversaAberta>());

  const chamar = useCallback(
    async (metodo: string, params: Record<string, unknown> = {}): Promise<unknown | null> => {
      const ponte = api();
      if (ponte === undefined) {
        setEstado((a) => ({ ...a, situacao: "erro", erro: SEM_NUCLEO }));
        return null;
      }
      const resposta = await ponte.chamar(metodo, params);
      if (!resposta.ok || typeof resposta.resultado !== "object" || resposta.resultado === null) {
        setEstado((a) => ({ ...a, erro: resposta.erro ?? SEM_NUCLEO }));
        return null;
      }
      return resposta.resultado;
    },
    [],
  );

  const recarregar = useCallback(async () => {
    setEstado((a) => ({ ...a, situacao: "carregando", erro: null }));
    const { soDestaPasta, incluirArquivadas } = filtrosRef.current;
    const resultado = (await chamar("chat.listar_conversas", {
      limite: LIMITE_LISTA,
      incluir_arquivadas: incluirArquivadas,
      ...(soDestaPasta && raizRef.current !== null ? { workspace: raizRef.current } : {}),
    })) as { conversas?: ItemConversa[]; tem_mais?: boolean } | null;
    if (resultado === null) {
      setEstado((a) => ({ ...a, situacao: "erro" }));
      return;
    }
    setEstado((a) => ({
      ...a,
      situacao: "pronta",
      lista: resultado.conversas ?? [],
      temMais: resultado.tem_mais ?? false,
      erro: null,
    }));
  }, [chamar]);

  useEffect(() => {
    void recarregar();
  }, [recarregar]);

  const carregarMais = useCallback(async () => {
    const ultima = estado.lista[estado.lista.length - 1];
    if (ultima === undefined || !estado.temMais) return;
    const { soDestaPasta, incluirArquivadas } = filtrosRef.current;
    const resultado = (await chamar("chat.listar_conversas", {
      limite: LIMITE_LISTA,
      antes_de: ultima.updated_at,
      incluir_arquivadas: incluirArquivadas,
      ...(soDestaPasta && raizRef.current !== null ? { workspace: raizRef.current } : {}),
    })) as { conversas?: ItemConversa[]; tem_mais?: boolean } | null;
    if (resultado === null) return;
    setEstado((a) => ({
      ...a,
      lista: [...a.lista, ...(resultado.conversas ?? [])],
      temMais: resultado.tem_mais ?? false,
    }));
  }, [chamar, estado.lista, estado.temMais]);

  const abrir = useCallback(
    async (conversationId: string, focoSeq?: number) => {
      const guardada = cache.current.get(conversationId);
      if (guardada !== undefined) {
        setEstado((a) => ({ ...a, aberta: { ...guardada, focoSeq }, erro: null }));
        return;
      }
      setEstado((a) => ({ ...a, carregandoAberta: true, erro: null }));
      const resultado = (await chamar("chat.abrir_conversa", {
        conversation_id: conversationId,
        limite: LIMITE_MENSAGENS,
      })) as ConversaAberta | null;
      if (resultado === null) {
        setEstado((a) => ({ ...a, carregandoAberta: false }));
        return;
      }
      cache.current.set(conversationId, resultado);
      setEstado((a) => ({
        ...a,
        carregandoAberta: false,
        aberta: { ...resultado, focoSeq },
      }));
    },
    [chamar],
  );

  const fechar = useCallback(() => setEstado((a) => ({ ...a, aberta: null })), []);

  const carregarAnteriores = useCallback(async () => {
    const aberta = estado.aberta;
    if (aberta === null || !aberta.tem_anteriores) return;
    const primeiro = aberta.mensagens[0];
    if (primeiro === undefined) return;
    const resultado = (await chamar("chat.carregar_anteriores", {
      conversation_id: aberta.conversa.conversation_id,
      antes_de_seq: primeiro.seq,
      limite: LIMITE_ANTERIORES,
    })) as { mensagens?: MensagemConversa[]; tem_mais?: boolean } | null;
    if (resultado === null) return;
    const juntas = [...(resultado.mensagens ?? []), ...aberta.mensagens];
    const atualizada: ConversaAberta = {
      ...aberta,
      mensagens: juntas,
      tem_anteriores: resultado.tem_mais ?? false,
    };
    cache.current.set(aberta.conversa.conversation_id, atualizada);
    setEstado((a) => ({ ...a, aberta: atualizada }));
  }, [chamar, estado.aberta]);

  const criar = useCallback(async () => {
    const raiz = raizRef.current;
    const resultado = (await chamar("chat.criar_conversa", {
      ...(raiz !== null ? { workspace: raiz } : {}),
    })) as { conversation_id?: string } | null;
    if (resultado?.conversation_id === undefined) return null;
    await recarregar();
    await abrir(resultado.conversation_id);
    return resultado.conversation_id;
  }, [abrir, chamar, recarregar]);

  const renomear = useCallback(
    async (conversationId: string, title: string) => {
      const ok = await chamar("chat.renomear", { conversation_id: conversationId, title });
      if (ok === null) return;
      // O cache guarda o cabeçalho com o título antigo; invalidar e reabrir é mais
      // honesto do que remendar o título em memória e divergir do banco.
      cache.current.delete(conversationId);
      await recarregar();
      if (estado.aberta?.conversa.conversation_id === conversationId) await abrir(conversationId);
    },
    [abrir, chamar, estado.aberta, recarregar],
  );

  const arquivar = useCallback(
    async (conversationId: string, arquivada: boolean) => {
      const ok = await chamar("chat.arquivar", {
        conversation_id: conversationId,
        arquivada,
      });
      if (ok === null) return;
      await recarregar();
    },
    [chamar, recarregar],
  );

  const apagar = useCallback(
    async (conversationId: string) => {
      const ok = await chamar("chat.apagar", { conversation_id: conversationId });
      if (ok === null) return;
      cache.current.delete(conversationId);
      if (estado.aberta?.conversa.conversation_id === conversationId) fechar();
      await recarregar();
    },
    [chamar, estado.aberta, fechar, recarregar],
  );

  const ramificar = useCallback(
    async (conversationId: string, aPartirDoSeq: number) => {
      const resultado = (await chamar("chat.ramificar", {
        conversation_id: conversationId,
        a_partir_do_seq: aPartirDoSeq,
      })) as { conversation_id?: string } | null;
      if (resultado?.conversation_id === undefined) return;
      await recarregar();
      await abrir(resultado.conversation_id);
    },
    [abrir, chamar, recarregar],
  );

  const buscar = useCallback(
    async (termo: string) => {
      setEstado((a) => ({ ...a, termo }));
      if (termo.trim().length === 0) {
        setEstado((a) => ({ ...a, resultados: null }));
        return;
      }
      const soDestaPasta = filtrosRef.current.soDestaPasta;
      const resultado = (await chamar("chat.buscar", {
        termo,
        ...(soDestaPasta && raizRef.current !== null ? { workspace: raizRef.current } : {}),
      })) as { resultados?: ResultadoBusca[] } | null;
      if (resultado === null) return;
      setEstado((a) => ({ ...a, resultados: resultado.resultados ?? [] }));
    },
    [chamar],
  );

  const limparBusca = useCallback(
    () => setEstado((a) => ({ ...a, termo: "", resultados: null })),
    [],
  );

  const alternarSoDestaPasta = useCallback(() => {
    setEstado((a) => ({ ...a, soDestaPasta: !a.soDestaPasta }));
  }, []);

  const alternarArquivadas = useCallback(() => {
    setEstado((a) => ({ ...a, incluirArquivadas: !a.incluirArquivadas }));
  }, []);

  // Trocar de filtro ou de pasta relista — a lista mostrada é sempre a do filtro atual.
  const filtroAssinatura = `${estado.soDestaPasta}|${estado.incluirArquivadas}|${workspaceRaiz ?? ""}`;
  const assinaturaAnterior = useRef(filtroAssinatura);
  useEffect(() => {
    if (assinaturaAnterior.current === filtroAssinatura) return;
    assinaturaAnterior.current = filtroAssinatura;
    void recarregar();
  }, [filtroAssinatura, recarregar]);

  return {
    ...estado,
    recarregar,
    carregarMais,
    alternarSoDestaPasta,
    alternarArquivadas,
    criar,
    abrir,
    fechar,
    carregarAnteriores,
    renomear,
    arquivar,
    apagar,
    ramificar,
    buscar,
    limparBusca,
  };
}

export type GrupoData = "Hoje" | "Ontem" | "7 dias" | "Antes";

/** Agrupa como a sidebar do plano: Hoje · Ontem · 7 dias · Antes. */
export function agruparPorData(
  conversas: ItemConversa[],
  agora: Date = new Date(),
): { grupo: GrupoData; itens: ItemConversa[] }[] {
  const inicioDeHoje = new Date(agora.getFullYear(), agora.getMonth(), agora.getDate()).getTime();
  const umDia = 86_400_000;
  const grupos: Record<GrupoData, ItemConversa[]> = {
    Hoje: [],
    Ontem: [],
    "7 dias": [],
    Antes: [],
  };
  for (const conversa of conversas) {
    const instante = Date.parse(conversa.updated_at);
    if (Number.isNaN(instante)) {
      grupos.Antes.push(conversa);
    } else if (instante >= inicioDeHoje) {
      grupos.Hoje.push(conversa);
    } else if (instante >= inicioDeHoje - umDia) {
      grupos.Ontem.push(conversa);
    } else if (instante >= inicioDeHoje - 7 * umDia) {
      grupos["7 dias"].push(conversa);
    } else {
      grupos.Antes.push(conversa);
    }
  }
  return (["Hoje", "Ontem", "7 dias", "Antes"] as GrupoData[])
    .map((grupo) => ({ grupo, itens: grupos[grupo] }))
    .filter((bloco) => bloco.itens.length > 0);
}

/** `true` quando a conversa é de outra pasta que não a aberta (faixa do plano). */
export function deOutraPasta(
  conversa: Pick<CabecalhoConversa, "workspace_nome">,
  workspaceAberto: string | null,
): boolean {
  if (conversa.workspace_nome === null) return false;
  if (workspaceAberto === null) return true;
  return conversa.workspace_nome !== workspaceAberto;
}
