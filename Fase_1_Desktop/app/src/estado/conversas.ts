// Store da barra de chats (M6 / F1-17) — consome chat.listar / criar / buscar / …

import { useCallback, useEffect, useState } from "react";

import { api } from "./ponte.js";

export interface ConversaResumo {
  conversation_id: string;
  title: string;
  updated_at: string;
  workspace_nome: string | null;
  arquivada: boolean;
  mensagens_total: number;
  ultimo_trecho: string;
}

export interface ResultadoBusca {
  conversation_id: string;
  message_id: string;
  seq: number;
  title: string;
  trecho_destacado: string;
  updated_at: string;
}

export function useConversas(workspacePath: string | null): {
  situacao: "idle" | "carregando" | "pronta" | "erro";
  conversas: ConversaResumo[];
  busca: string;
  resultadosBusca: ResultadoBusca[];
  filtrarPastaAtual: boolean;
  conversaAtiva: string | null;
  erro: { codigo: string; mensagem: string } | null;
  listar: () => Promise<void>;
  criar: () => Promise<string | null>;
  buscar: (termo: string) => Promise<void>;
  selecionar: (conversationId: string | null) => void;
  alternarFiltroPasta: () => void;
  definirBusca: (termo: string) => void;
  apagar: (conversationId: string) => Promise<void>;
  renomear: (conversationId: string, title: string) => Promise<void>;
} {
  const [situacao, setSituacao] = useState<"idle" | "carregando" | "pronta" | "erro">("idle");
  const [conversas, setConversas] = useState<ConversaResumo[]>([]);
  const [busca, setBusca] = useState("");
  const [resultadosBusca, setResultadosBusca] = useState<ResultadoBusca[]>([]);
  const [filtrarPastaAtual, setFiltrarPastaAtual] = useState(false);
  const [conversaAtiva, setConversaAtiva] = useState<string | null>(null);
  const [erro, setErro] = useState<{ codigo: string; mensagem: string } | null>(null);

  const listar = useCallback(async () => {
    const ponte = api();
    if (ponte === undefined) {
      setSituacao("erro");
      setErro({ codigo: "UI-001", mensagem: "Núcleo indisponível." });
      return;
    }
    setSituacao("carregando");
    setErro(null);
    const params: Record<string, unknown> = {};
    if (filtrarPastaAtual && workspacePath) params.workspace = workspacePath;
    const resposta = await ponte.chamar("chat.listar_conversas", params);
    if (!resposta.ok || typeof resposta.resultado !== "object" || resposta.resultado === null) {
      setSituacao("erro");
      setErro(resposta.erro ?? { codigo: "UI-001", mensagem: "Falha ao listar conversas." });
      return;
    }
    const bruto = resposta.resultado as { conversas?: ConversaResumo[] };
    setConversas(bruto.conversas ?? []);
    setSituacao("pronta");
  }, [filtrarPastaAtual, workspacePath]);

  useEffect(() => {
    void listar();
  }, [listar]);

  const criar = useCallback(async () => {
    const ponte = api();
    if (ponte === undefined) return null;
    const params: Record<string, unknown> = {};
    if (workspacePath) params.workspace = workspacePath;
    const resposta = await ponte.chamar("chat.criar_conversa", params);
    if (!resposta.ok || typeof resposta.resultado !== "object" || resposta.resultado === null) {
      setErro(resposta.erro ?? { codigo: "UI-001", mensagem: "Não foi possível criar a conversa." });
      return null;
    }
    const cid = (resposta.resultado as { conversation_id: string }).conversation_id;
    setConversaAtiva(cid);
    await listar();
    return cid;
  }, [listar, workspacePath]);

  const buscar = useCallback(async (termo: string) => {
    const ponte = api();
    if (ponte === undefined) return;
    const limpo = termo.trim();
    setBusca(limpo);
    if (limpo.length === 0) {
      setResultadosBusca([]);
      return;
    }
    const resposta = await ponte.chamar("chat.buscar", { termo: limpo });
    if (!resposta.ok || typeof resposta.resultado !== "object" || resposta.resultado === null) {
      setErro(resposta.erro ?? { codigo: "UI-001", mensagem: "Busca falhou." });
      return;
    }
    const bruto = resposta.resultado as { resultados?: ResultadoBusca[] };
    setResultadosBusca(bruto.resultados ?? []);
  }, []);

  const apagar = useCallback(
    async (conversationId: string) => {
      const ponte = api();
      if (ponte === undefined) return;
      await ponte.chamar("chat.apagar", { conversation_id: conversationId });
      setConversaAtiva((ativa) => (ativa === conversationId ? null : ativa));
      await listar();
    },
    [listar],
  );

  const renomear = useCallback(
    async (conversationId: string, title: string) => {
      const ponte = api();
      if (ponte === undefined) return;
      await ponte.chamar("chat.renomear", { conversation_id: conversationId, title });
      await listar();
    },
    [listar],
  );

  return {
    situacao,
    conversas,
    busca,
    resultadosBusca,
    filtrarPastaAtual,
    conversaAtiva,
    erro,
    listar,
    criar,
    buscar,
    selecionar: setConversaAtiva,
    alternarFiltroPasta: () => setFiltrarPastaAtual((v) => !v),
    definirBusca: setBusca,
    apagar,
    renomear,
  };
}

/** Agrupa conversas em Hoje / Ontem / 7 dias / Antes (F1-17). */
export function agruparPorData(
  conversas: ConversaResumo[],
  agora: Date = new Date(),
): { rotulo: string; itens: ConversaResumo[] }[] {
  const inicioHoje = new Date(agora);
  inicioHoje.setHours(0, 0, 0, 0);
  const inicioOntem = new Date(inicioHoje);
  inicioOntem.setDate(inicioOntem.getDate() - 1);
  const inicio7 = new Date(inicioHoje);
  inicio7.setDate(inicio7.getDate() - 7);

  const baldes: Record<string, ConversaResumo[]> = {
    Hoje: [],
    Ontem: [],
    "7 dias": [],
    Antes: [],
  };
  for (const c of conversas) {
    const t = Date.parse(c.updated_at);
    if (Number.isNaN(t)) {
      baldes.Antes.push(c);
      continue;
    }
    const d = new Date(t);
    if (d >= inicioHoje) baldes.Hoje.push(c);
    else if (d >= inicioOntem) baldes.Ontem.push(c);
    else if (d >= inicio7) baldes["7 dias"].push(c);
    else baldes.Antes.push(c);
  }
  return (["Hoje", "Ontem", "7 dias", "Antes"] as const)
    .filter((rotulo) => baldes[rotulo].length > 0)
    .map((rotulo) => ({ rotulo, itens: baldes[rotulo] }));
}
