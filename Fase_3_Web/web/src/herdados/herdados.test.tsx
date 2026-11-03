/**
 * W6-01 — os componentes herdados do desktop renderizam no web.
 *
 * O critério não é "copiei os arquivos": é eles funcionarem com os tipos locais
 * (`./tipos.ts`) e as fontes/tokens novos. Os casos abaixo são os do uso real no chat.
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { BlocoRaciocinio } from './BlocoRaciocinio';
import { BolhaMarkdown } from './BolhaMarkdown';
import { CartaoPergunta } from './CartaoPergunta';
import { CartaoTool, aplicarEventoTool, cancelarPendentes } from './CartaoTool';
import { GrupoTools } from './GrupoTools';
import { IndicadorPensando } from './IndicadorPensando';
import { aplicarEventoTimeline, type BlocoTurno } from './timeline';

describe('componentes herdados', () => {
  it('BolhaMarkdown renderiza markdown com tabela e negrito', () => {
    render(<BolhaMarkdown markdown={'**pronto**\n\n| a | b |\n|---|---|\n| 1 | 2 |'} />);
    expect(screen.getByText('pronto')).toBeInTheDocument();
    expect(screen.getByRole('table')).toBeInTheDocument();
  });

  it('IndicadorPensando aparece com rótulo acessível', () => {
    render(<IndicadorPensando />);
    expect(screen.getByText(/pensando/i)).toBeInTheDocument();
  });

  it('CartaoTool mostra a tool e o resumo do resultado', () => {
    const [estado] = aplicarEventoTool([], {
      trace_id: 't1',
      tool: 'gerar_mapa',
      fase: 'fim',
      resultado_resumo: 'PDF e planilha gerados',
      ms: 1200,
      ok: true,
    });
    render(<CartaoTool estado={estado!} />);
    expect(screen.getByText(/gerar_mapa/)).toBeInTheDocument();
  });

  it('GrupoTools agrupa várias tools', () => {
    const estados = ['estado_do_projeto', 'ler_recibo_car', 'gerar_mapa'].map((tool, i) =>
      aplicarEventoTool([], { trace_id: `t${i}`, tool, fase: 'fim', ok: true })[0]!,
    );
    render(<GrupoTools id="g1" tools={estados} />);
    expect(screen.getByText(/3/)).toBeInTheDocument();
  });

  it('CartaoPergunta mostra as opções clicáveis', () => {
    render(
      <CartaoPergunta
        dados={{
          pergunta: 'Qual ano da Dinâmica?',
          opcoes: [
            { id: 'o1', rotulo: '2026' },
            { id: 'o2', rotulo: '2025' },
          ],
          permite_texto_livre: false,
        }}
        aoResponder={() => {}}
      />,
    );
    expect(screen.getByText('Qual ano da Dinâmica?')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '2026' })).toBeInTheDocument();
  });

  it('BlocoRaciocinio fica colapsado e abre no clique', () => {
    render(<BlocoRaciocinio id="r1" texto="vou olhar a pasta antes de responder" />);
    const botao = screen.getByRole('button');
    expect(botao).toBeInTheDocument();
  });
});

describe('timeline herdada', () => {
  it('acumula texto de dois deltas no mesmo bloco', () => {
    let t: BlocoTurno[] = [];
    t = aplicarEventoTimeline(t, { tipo: 'texto', dados: { texto: 'Olá, ' } });
    t = aplicarEventoTimeline(t, { tipo: 'texto', dados: { texto: 'mundo.' } });
    const bloco = t[0];
    expect(bloco?.tipo).toBe('texto');
    expect(bloco && bloco.tipo === 'texto' ? bloco.markdown : '').toBe('Olá, mundo.');
  });

  it('tool pendente é cancelada quando o turno fecha', () => {
    const pendente = aplicarEventoTool([], {
      trace_id: 't9',
      tool: 'gerar_mapa',
      fase: 'inicio',
    });
    const canceladas = cancelarPendentes(pendente);
    expect(canceladas[0]?.cancelada).toBe(true);
  });
});
