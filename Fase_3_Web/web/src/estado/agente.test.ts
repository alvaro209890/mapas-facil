/**
 * Testes da store do Agente v2 PDF-first (src/estado/agente.ts).
 *
 * Contrato testado:
 * 1. Eventos SSE: agente.plano, agente.passo, agente.arquivo, agente.preview,
 *    agente.aprovacao, agente.fim.
 * 2. Status: pendente, em_andamento, concluido, erro, cancelado.
 * 3. Recuperação via GET /api/v1/projetos/:id/agente no reload.
 * 4. Botão Parar / cancelamento: cancela via API e preserva histórico.
 * 5. Aprovação: requer endpoint seguro/token confiável; bloqueia e explica se indisponível,
 *    nunca autoautoriza via texto.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Evento } from '../api/tipos';
import { useAgente } from './agente';

let proximoSeq = 1;

function evtAgente(nome: string, dados: Record<string, unknown>): Evento {
  return {
    seq: proximoSeq++,
    ts: '2026-11-06T12:00:00Z',
    origem: 'servidor',
    evento: nome,
    dados,
  };
}

const fetchFalso = vi.fn();

beforeEach(() => {
  vi.stubGlobal('fetch', fetchFalso);
  fetchFalso.mockReset();
  proximoSeq = 1;
  useAgente.getState().limpar();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonResposta(corpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(corpo), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('useAgente — eventos SSE', () => {
  it('inicializa em estado ocioso e limpo', () => {
    const estado = useAgente.getState();
    expect(estado.status).toBe('ocioso');
    expect(estado.passos).toEqual([]);
    expect(estado.arquivos).toEqual([]);
    expect(estado.previews).toEqual([]);
    expect(estado.aprovacao).toBeNull();
    expect(estado.previewAtivo).toBeNull();
  });

  it('aplica agente.plano registrando os passos e definindo status em_andamento', () => {
    const e = evtAgente('agente.plano', {
      passos: [
        { id: 'p1', titulo: 'Ler shapefiles e perímetro', status: 'pendente' },
        { id: 'p2', titulo: 'Gerar PDF padrão IMAP', status: 'pendente' },
      ],
    });

    useAgente.getState().aplicarEvento(e);
    const estado = useAgente.getState();

    expect(estado.status).toBe('em_andamento');
    expect(estado.passos).toHaveLength(2);
    expect(estado.passos[0]?.id).toBe('p1');
    expect(estado.passos[0]?.status).toBe('pendente');
  });

  it('aplica agente.passo atualizando status e resumo do passo', () => {
    useAgente.getState().aplicarEvento(
      evtAgente('agente.plano', {
        passos: [{ id: 'p1', titulo: 'Ler dados', status: 'pendente' }],
      }),
    );

    useAgente.getState().aplicarEvento(
      evtAgente('agente.passo', {
        id: 'p1',
        titulo: 'Ler dados',
        status: 'em_andamento',
        resumo: 'Indexando 4 shapefiles',
      }),
    );

    let estado = useAgente.getState();
    expect(estado.passos[0]?.status).toBe('em_andamento');
    expect(estado.passos[0]?.resumo).toBe('Indexando 4 shapefiles');

    useAgente.getState().aplicarEvento(
      evtAgente('agente.passo', {
        id: 'p1',
        titulo: 'Ler dados',
        status: 'concluido',
        resumo: 'Perímetro identificado com sucesso',
      }),
    );

    estado = useAgente.getState();
    expect(estado.passos[0]?.status).toBe('concluido');
    expect(estado.passos[0]?.resumo).toBe('Perímetro identificado com sucesso');
  });

  it('aplica agente.arquivo acumulando caminhos relativos e ações', () => {
    useAgente.getState().aplicarEvento(
      evtAgente('agente.arquivo', {
        caminho: 'Mapas/v001/mapa_dinamica.pdf',
        acao: 'criado',
      }),
    );
    useAgente.getState().aplicarEvento(
      evtAgente('agente.arquivo', {
        caminho: 'SHP/perimetro_utm.shp',
        acao: 'modificado',
      }),
    );

    const estado = useAgente.getState();
    expect(estado.arquivos).toHaveLength(2);
    expect(estado.arquivos[0]).toEqual({
      caminho: 'Mapas/v001/mapa_dinamica.pdf',
      acao: 'criado',
      ts: '2026-11-06T12:00:00Z',
    });
  });

  it('aplica agente.preview atualizando lista e selecionando preview ativo', () => {
    useAgente.getState().aplicarEvento(
      evtAgente('agente.preview', {
        caminho: 'Mapas/v001/preview_p1.pdf',
        pagina: 1,
      }),
    );

    const estado = useAgente.getState();
    expect(estado.previews).toHaveLength(1);
    expect(estado.previews[0]?.caminho).toBe('Mapas/v001/preview_p1.pdf');
    expect(estado.previews[0]?.pagina).toBe(1);
    expect(estado.previewAtivo?.caminho).toBe('Mapas/v001/preview_p1.pdf');
  });

  it('aplica agente.aprovacao guardando requisição destrutiva', () => {
    useAgente.getState().aplicarEvento(
      evtAgente('agente.aprovacao', {
        acao: 'sobrescrever_arquivo',
        caminho: 'Mapas/v001/mapa_final.pdf',
        motivo: 'Regeneração com novo enquadramento solicitado',
        token: 'tok-aprov-123',
      }),
    );

    const estado = useAgente.getState();
    expect(estado.aprovacao).toEqual({
      acao: 'sobrescrever_arquivo',
      caminho: 'Mapas/v001/mapa_final.pdf',
      motivo: 'Regeneração com novo enquadramento solicitado',
      token: 'tok-aprov-123',
      resolvida: false,
    });
  });

  it('aplica agente.fim marcando concluido com resumo e versao', () => {
    useAgente.getState().aplicarEvento(
      evtAgente('agente.fim', {
        status: 'concluido',
        resumo: 'PDF padrão IMAP gerado com sucesso.',
        versao: 2,
      }),
    );

    const estado = useAgente.getState();
    expect(estado.status).toBe('concluido');
    expect(estado.resumoFim).toBe('PDF padrão IMAP gerado com sucesso.');
    expect(estado.versaoGerada).toBe(2);
  });
});

describe('useAgente — carga no reload (GET /api/v1/projetos/:id/agente)', () => {
  it('carrega o estado completo retornado pela API', async () => {
    fetchFalso.mockImplementation((url: string) => {
      if (url.includes('/agente')) {
        return Promise.resolve(
          jsonResposta({
            status: 'em_andamento',
            passos: [
              { id: '1', titulo: 'Passo 1', status: 'concluido', resumo: 'ok' },
              { id: '2', titulo: 'Passo 2', status: 'em_andamento' },
            ],
            arquivos: [{ caminho: 'Mapas/v001/mapa.pdf', acao: 'criado' }],
            previews: [{ caminho: 'Mapas/v001/mapa.pdf', pagina: 1 }],
            aprovacao: null,
          }),
        );
      }
      return Promise.resolve(jsonResposta({}));
    });

    await useAgente.getState().carregar('proj-123');

    const estado = useAgente.getState();
    expect(estado.status).toBe('em_andamento');
    expect(estado.passos).toHaveLength(2);
    expect(estado.arquivos).toHaveLength(1);
    expect(estado.previews).toHaveLength(1);
    expect(estado.previewAtivo?.caminho).toBe('Mapas/v001/mapa.pdf');
  });

  it('lida graciosamente com 404 (endpoint ainda não implementado no servidor)', async () => {
    fetchFalso.mockImplementation(() =>
      Promise.resolve(
        jsonResposta({ erro: { codigo: 'SV-404', mensagem: 'não encontrado' } }, 404),
      ),
    );

    await useAgente.getState().carregar('proj-inexistente');

    const estado = useAgente.getState();
    expect(estado.status).toBe('ocioso');
    expect(estado.passos).toEqual([]);
    expect(estado.erro).toBeNull();
  });
});

describe('useAgente — botão Parar / cancelamento', () => {
  it('cancela via API preservando os passos e arquivos já executados', async () => {
    useAgente.getState().aplicarEvento(
      evtAgente('agente.plano', {
        passos: [
          { id: 'p1', titulo: 'Passo concluído', status: 'concluido' },
          { id: 'p2', titulo: 'Passo em andamento', status: 'em_andamento' },
          { id: 'p3', titulo: 'Passo pendente', status: 'pendente' },
        ],
      }),
    );
    useAgente.getState().aplicarEvento(
      evtAgente('agente.arquivo', { caminho: 'SHP/teste.shp', acao: 'criado' }),
    );

    fetchFalso.mockImplementation((url: string, init?: RequestInit) => {
      if (url.includes('/cancelar') && init?.method === 'POST') {
        return Promise.resolve(jsonResposta({ ok: true }));
      }
      return Promise.resolve(jsonResposta({}));
    });

    await useAgente.getState().cancelar('proj-123');

    const estado = useAgente.getState();
    expect(estado.status).toBe('cancelado');
    // Passo 1 concluído permanece concluído
    expect(estado.passos[0]?.status).toBe('concluido');
    // Passo 2 que estava em andamento é marcado como cancelado
    expect(estado.passos[1]?.status).toBe('cancelado');
    // Arquivo preservado
    expect(estado.arquivos).toHaveLength(1);
  });
});

describe('useAgente — aprovação explícita e segurança', () => {
  it('bloqueia e exibe explicação quando endpoint de aprovação segura estiver indisponível, sem enviar texto no chat', async () => {
    useAgente.getState().aplicarEvento(
      evtAgente('agente.aprovacao', {
        acao: 'apagar_camada',
        caminho: 'SHP/reserva.shp',
        motivo: 'Remoção de camada sobreposta',
        token: 'tok-destrutivo',
      }),
    );

    // Endpoint retorna 404/501 (não suportado)
    fetchFalso.mockImplementation((url: string) => {
      if (url.includes('/aprovacao')) {
        return Promise.resolve(
          jsonResposta({ erro: { codigo: 'SV-404', mensagem: 'Endpoint não implementado' } }, 404),
        );
      }
      return Promise.resolve(jsonResposta({}));
    });

    await useAgente.getState().decidirAprovacao('proj-123', true);

    const estado = useAgente.getState();
    // Não auto-autorizou nem marcou aprovado
    expect(estado.aprovacao?.resolvida).toBe(false);
    expect(estado.bloqueioAprovacao).toContain('não suportada');
  });

  it('aprova com sucesso quando endpoint seguro responde 200', async () => {
    useAgente.getState().aplicarEvento(
      evtAgente('agente.aprovacao', {
        acao: 'sobrescrever',
        caminho: 'Mapas/v001/mapa.pdf',
        motivo: 'Atualização',
        token: 'tok-valido',
      }),
    );

    fetchFalso.mockImplementation((url: string, init?: RequestInit) => {
      if (url.includes('/aprovacao') && init?.method === 'POST') {
        return Promise.resolve(jsonResposta({ ok: true, aprovado: true }));
      }
      if (url.endsWith('/agente')) {
        return Promise.resolve(jsonResposta({ agente: { aprovacao: { acao: 'sobrescrever', caminho: 'Mapas/v001/mapa.pdf', motivo: 'Atualização', token: 'tok-valido' } } }));
      }
      return Promise.resolve(jsonResposta({}));
    });

    await useAgente.getState().decidirAprovacao('proj-123', true);

    const estado = useAgente.getState();
    expect(estado.aprovacao?.resolvida).toBe(true);
    expect(estado.aprovacao?.aprovado).toBe(true);
    expect(estado.bloqueioAprovacao).toBeNull();
  });
});
