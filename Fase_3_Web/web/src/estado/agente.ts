/**
 * Store do Agente v2 PDF-first (W-16 / planos/06-agente-pdf-first.md).
 *
 * Responsável pelo acompanhamento estruturado da execução do agente:
 * - Checklist do plano e passos ({id, titulo, status, resumo});
 * - Arquivos tocados ({caminho, acao});
 * - Previews de PDF emitidos ({caminho, pagina});
 * - Aprovação destrutiva explícita ({acao, caminho, motivo, token});
 * - Cancelamento seguro via API existente preservando o histórico produzido;
 * - Hidratação no reload via GET /api/v1/projetos/{id}/agente e SSE contínuo.
 */

import { create } from 'zustand';
import { useChat } from './chat';
import { api, ErroHttp } from '../api/cliente';
import type {
  AprovacaoAgente,
  ArquivoAgente,
  EstadoAgenteApi,
  Evento,
  PassoAgente,
  PreviewAgente,
  StatusAgente,
  StatusPasso,
} from '../api/tipos';

export interface LojaAgente {
  passos: PassoAgente[];
  arquivos: ArquivoAgente[];
  previews: PreviewAgente[];
  aprovacao: AprovacaoAgente | null;
  status: StatusAgente;
  resumoFim: string | null;
  versaoGerada: number | null;
  previewAtivo: PreviewAgente | null;
  bloqueioAprovacao: string | null;
  carregando: boolean;
  erro: string | null;

  aplicarEvento: (evento: Evento) => void;
  carregar: (projetoId: string) => Promise<void>;
  cancelar: (projetoId: string) => Promise<void>;
  decidirAprovacao: (projetoId: string, aprovado: boolean) => Promise<void>;
  selecionarPreview: (preview: PreviewAgente | null) => void;
  limpar: () => void;
}

const ESTADO_INICIAL = {
  passos: [],
  arquivos: [],
  previews: [],
  aprovacao: null,
  status: 'ocioso' as StatusAgente,
  resumoFim: null,
  versaoGerada: null,
  previewAtivo: null,
  bloqueioAprovacao: null,
  carregando: false,
  erro: null,
};

export const useAgente = create<LojaAgente>((set, get) => ({
  ...ESTADO_INICIAL,

  aplicarEvento: (evento: Evento) => {
    switch (evento.evento) {
      case 'agente.plano': {
        const dados = evento.dados as { passos?: unknown };
        if (Array.isArray(dados.passos)) {
          const passosNovos: PassoAgente[] = dados.passos.map((p, idx) => {
            const item = p as Partial<PassoAgente>;
            return {
              id: String(item.id ?? `passo-${idx + 1}`),
              titulo: String(item.titulo ?? `Passo ${idx + 1}`),
              status: (item.status as StatusPasso) ?? 'pendente',
              ...(item.resumo ? { resumo: String(item.resumo) } : {}),
            };
          });
          set((atual) => ({
            passos: passosNovos,
            status: atual.status === 'ocioso' || atual.status === 'pendente' ? 'em_andamento' : atual.status,
          }));
        }
        return;
      }

      case 'agente.passo': {
        const dados = evento.dados as Partial<PassoAgente>;
        if (!dados.id) return;
        const id = String(dados.id);
        const status = (dados.status as StatusPasso) ?? 'em_andamento';
        const titulo = dados.titulo ? String(dados.titulo) : undefined;
        const resumo = dados.resumo !== undefined ? String(dados.resumo) : undefined;

        set((atual) => {
          const existe = atual.passos.some((p) => p.id === id);
          const passos = existe
            ? atual.passos.map((p) =>
                p.id === id
                  ? {
                      ...p,
                      status,
                      ...(titulo ? { titulo } : {}),
                      ...(resumo !== undefined ? { resumo } : {}),
                    }
                  : p,
              )
            : [
                ...atual.passos,
                {
                  id,
                  titulo: titulo ?? id,
                  status,
                  ...(resumo !== undefined ? { resumo } : {}),
                },
              ];
          return {
            passos,
            status: atual.status === 'ocioso' ? 'em_andamento' : atual.status,
          };
        });
        return;
      }

      case 'agente.arquivo': {
        const dados = evento.dados as Partial<ArquivoAgente>;
        if (!dados.caminho) return;
        const caminho = String(dados.caminho);
        const acao = String(dados.acao ?? 'modificado');
        const ts = String(evento.ts ?? new Date().toISOString());

        set((atual) => ({
          arquivos: [...atual.arquivos, { caminho, acao, ts }],
        }));
        return;
      }

      case 'agente.preview': {
        const dados = evento.dados as Partial<PreviewAgente>;
        if (!dados.caminho) return;
        const caminho = String(dados.caminho);
        const ts = String(evento.ts ?? new Date().toISOString());
        const novoPreview: PreviewAgente = {
          caminho,
          ts,
          ...(typeof dados.pagina === 'number' ? { pagina: dados.pagina } : {}),
        };

        set((atual) => ({
          previews: [...atual.previews, novoPreview],
          previewAtivo: novoPreview,
        }));
        return;
      }

      case 'agente.aprovacao': {
        const dados = evento.dados as Partial<AprovacaoAgente>;
        if (!dados.acao || !dados.caminho) return;
        const aprovacao: AprovacaoAgente = {
          acao: String(dados.acao),
          caminho: String(dados.caminho),
          motivo: String(dados.motivo ?? ''),
          ...(dados.token ? { token: String(dados.token) } : {}),
          resolvida: false,
        };
        set({ aprovacao, bloqueioAprovacao: null });
        return;
      }

      case 'agente.fim': {
        const dados = evento.dados as {
          status?: unknown;
          resumo?: unknown;
          versao?: unknown;
        };
        const statusFim = (dados.status as StatusPasso) ?? 'concluido';
        const resumo = typeof dados.resumo === 'string' ? dados.resumo : null;
        const versao = typeof dados.versao === 'number' ? dados.versao : null;

        set((atual) => {
          let passosAtualizados = atual.passos;
          if (statusFim === 'cancelado' || statusFim === 'erro') {
            passosAtualizados = atual.passos.map((p) =>
              p.status === 'em_andamento' || p.status === 'pendente'
                ? { ...p, status: statusFim }
                : p,
            );
          }
          return {
            status: statusFim,
            resumoFim: resumo,
            versaoGerada: versao,
            passos: passosAtualizados,
          };
        });
        return;
      }

      default:
        return;
    }
  },

  carregar: async (projetoId: string) => {
    if (!projetoId) return;
    set({ carregando: true, erro: null });
    try {
      const res = await api.get<EstadoAgenteApi | { agente: EstadoAgenteApi }>(
        `/projetos/${encodeURIComponent(projetoId)}/agente`,
      );
      const dados: EstadoAgenteApi = 'agente' in res && res.agente ? res.agente : (res as EstadoAgenteApi);

      const passos = Array.isArray(dados.passos) ? dados.passos : [];
      const arquivos = Array.isArray(dados.arquivos) ? dados.arquivos : [];
      const previews = Array.isArray(dados.previews) ? dados.previews : [];
      const aprovacao = dados.aprovacao ?? null;
      const status = dados.status ?? (passos.length > 0 ? 'em_andamento' : 'ocioso');
      const resumo = dados.resumo ?? null;
      const versao = dados.versao ?? null;

      set({
        passos,
        arquivos,
        previews,
        aprovacao,
        status,
        resumoFim: resumo,
        versaoGerada: versao,
        previewAtivo: previews.at(-1) ?? null,
        bloqueioAprovacao: null,
        carregando: false,
        erro: null,
      });
    } catch (err) {
      // 404 é normal enquanto o endpoint do servidor está sendo construído por outro agente
      if (err instanceof ErroHttp && err.status === 404) {
        set({ carregando: false, erro: null });
        return;
      }
      set({
        carregando: false,
        erro: err instanceof Error ? err.message : 'Falha ao carregar estado do agente',
      });
    }
  },

  cancelar: async (projetoId: string) => {
    if (!projetoId) return;
    try {
      // API existente de cancelamento do projeto
      await api.post(`/projetos/${encodeURIComponent(projetoId)}/cancelar`, { req_id: useChat.getState().turnoEmCurso ?? '' });
    } catch (err) {
      set({ erro: err instanceof Error ? err.message : 'Servidor não confirmou o cancelamento.' });
      return;
    }

    // Preserva passos concluídos e arquivos; marca em andamento como cancelado
    set((atual) => ({
      status: 'cancelado',
      passos: atual.passos.map((p) =>
        p.status === 'em_andamento' ? { ...p, status: 'cancelado' } : p,
      ),
    }));
  },

  decidirAprovacao: async (projetoId: string, aprovado: boolean) => {
    const atual = get();
    if (!atual.aprovacao || !projetoId) return;

    try {
      // Token só vem do GET autenticado, nunca é obtido pelo modelo/SSE.
      const resposta = await api.get<EstadoAgenteApi | { agente: EstadoAgenteApi }>(`/projetos/${encodeURIComponent(projetoId)}/agente`);
      const seguro = 'agente' in resposta ? resposta.agente : resposta;
      const pedido = seguro.aprovacao;
      if (!pedido?.token || pedido.acao !== atual.aprovacao.acao || pedido.caminho !== atual.aprovacao.caminho) {
        throw new Error('Pedido de aprovação ausente ou alterado; recarregue antes de decidir.');
      }
      const corpo = {
        acao: aprovado ? 'aprovar' : 'rejeitar',
        token: pedido.token,
        action: pedido.acao,
        path: pedido.caminho,
      };

      const res = await api.post<{ ok?: boolean; aprovado?: boolean }>(
        `/projetos/${encodeURIComponent(projetoId)}/agente/aprovacao`,
        corpo,
      );

      if (res?.ok === true) {
        set({
          aprovacao: {
            ...atual.aprovacao,
            resolvida: true,
            aprovado,
          },
          bloqueioAprovacao: null,
        });
        return;
      }
      throw new Error('Servidor não confirmou a decisão de aprovação.');
    } catch (err) {
      // Endpoint indisponível ou erro seguro.
      // REGRA: "Aprovação precisa endpoint seguro/token confiável; se indisponível mostre bloqueio
      // e explique não suportado em vez de autoautorizar via texto."
      set({
        bloqueioAprovacao:
          `Aprovação remota segura não suportada ou recusada; ação bloqueada. ${err instanceof Error ? err.message : ''}`, 
      });
    }
  },

  selecionarPreview: (preview: PreviewAgente | null) => {
    set({ previewAtivo: preview });
  },

  limpar: () => {
    set({ ...ESTADO_INICIAL });
  },
}));
