/**
 * Roteiro de eventos gravado (critério de aceite do W-06).
 *
 * Este é o fluxo inteiro de um projeto — upload, indexação, conversa, versão e palco — e o
 * estado esperado no fim. Se um dia o servidor renomear um evento ou mudar um campo, o
 * teste quebra aqui, não no navegador do Álvaro.
 *
 * O roteiro é uma gravação real do servidor com `fake_nucleo` (`tests/roteiros/chat_ok.ndjson`
 * + os eventos de importação), transcrita para JSON — nada inventado à mão.
 */

import { beforeEach, describe, expect, it } from 'vitest';

import { despachar } from '../api/ponteWeb';
import type { Evento } from '../api/tipos';
import { useConexao } from './conexao';
import { useChat } from './chat';
import { useJob } from './job';
import { usePalco } from './palco';
import { useProjetoAtivo } from './projetoAtivo';

const ROTEIRO: Evento[] = [
  { seq: 1, ts: '2026-11-03T12:00:00Z', origem: 'servidor', evento: 'projeto.estado', dados: { projeto_id: 'p1', estado: 'importando' } },
  { seq: 2, ts: '2026-11-03T12:00:01Z', origem: 'servidor', evento: 'importacao.progresso', dados: { projeto_id: 'p1', etapa: 'extraindo', pct: 40 } },
  { seq: 3, ts: '2026-11-03T12:00:02Z', origem: 'servidor', evento: 'projeto.estado', dados: { projeto_id: 'p1', estado: 'indexando' } },
  { seq: 4, ts: '2026-11-03T12:00:03Z', origem: 'servidor', evento: 'projeto.estado', dados: { projeto_id: 'p1', estado: 'pronto', resumo: { area_ha: 512.4, camadas: 4 } } },
  { seq: 5, ts: '2026-11-03T12:00:04Z', origem: 'servidor', evento: 'mensagem.criada', dados: { mensagem: { message_id: 'm1', seq: 1, papel: 'usuario', texto: 'faz a dinâmica 2023', criada_em: '2026-11-03T12:00:04Z' } } },
  { seq: 6, ts: '2026-11-03T12:00:05Z', origem: 'nucleo', evento: 'chat.raciocinio', dados: { texto: 'preciso da camada de dinâmica' } },
  { seq: 7, ts: '2026-11-03T12:00:06Z', origem: 'nucleo', evento: 'chat.tool', dados: { trace_id: 't1', tool: 'gerar_mapa', fase: 'inicio' } },
  { seq: 8, ts: '2026-11-03T12:00:07Z', origem: 'nucleo', evento: 'job.progresso', job_id: 'j1', dados: { etapa: 'camadas', pct: 30 } },
  { seq: 9, ts: '2026-11-03T12:00:08Z', origem: 'nucleo', evento: 'job.log', job_id: 'j1', dados: { mensagem: 'camada de dinâmica ok' } },
  { seq: 10, ts: '2026-11-03T12:00:09Z', origem: 'nucleo', evento: 'viewport.foco', dados: { x: 600000, y: 8300000, escala: 1, motivo: 'zoom na camada' } },
  { seq: 11, ts: '2026-11-03T12:00:10Z', origem: 'nucleo', evento: 'camada.renderizada', dados: { nome: 'dinamica', estado: 'ok' } },
  { seq: 12, ts: '2026-11-03T12:00:11Z', origem: 'nucleo', evento: 'job.progresso', job_id: 'j1', dados: { etapa: 'pdf', pct: 100 } },
  { seq: 13, ts: '2026-11-03T12:00:12Z', origem: 'nucleo', evento: 'chat.tool', dados: { trace_id: 't1', tool: 'gerar_mapa', fase: 'fim', ok: true } },
  { seq: 14, ts: '2026-11-03T12:00:13Z', origem: 'nucleo', evento: 'chat.delta', dados: { texto: 'Pronto: versão 1 gerada.' } },
  { seq: 15, ts: '2026-11-03T12:00:14Z', origem: 'nucleo', evento: 'nucleo.res', dados: { ok: true, req_id: 'req1' } },
  { seq: 16, ts: '2026-11-03T12:00:15Z', origem: 'servidor', evento: 'versao.criada', dados: { versao: { numero: 1, pasta: 'Mapas/v001', conforme: true, miniatura: 'Mapas/v001/mini.png', artefatos: { pdf: 'Mapas/v001/mapa.pdf', mxd: 'Mapas/v001/mapa.mxd' }, validacao: { hard_ok: true }, criada_em: '2026-11-03T12:00:15Z' } } },
];

function replay(eventos: Evento[]): void {
  for (const e of eventos) despachar(e);
}

beforeEach(() => {
  useConexao.setState({ ultimoSeq: 0, estado: 'parado' });
  useChat.getState().limpar();
  useJob.getState().limpar();
  usePalco.getState().limpar();
  useProjetoAtivo.getState().limpar();
});

describe('roteiro gravado do projeto', () => {
  it('aplica os 16 eventos e chega ao estado esperado', () => {
    useProjetoAtivo.setState({
      projeto: {
        id: 'p1',
        nome: 'Boa Vista',
        estado: 'aguardando_zip',
        folha: { formato: 'A3', orientacao: 'paisagem' },
        imovel: {},
        versao_atual: 0,
        miniatura: null,
        atualizado_em: '',
      },
    });
    useChat.getState().enviarLocal('faz a dinâmica 2023', 'req1');

    replay(ROTEIRO);

    const chat = useChat.getState();
    expect(chat.blocos.length).toBeGreaterThan(0);
    expect(chat.turnoEmCurso).toBeNull();
    expect(chat.mensagens.map((m) => m.texto)).toEqual(['faz a dinâmica 2023']);
    // o delta final virou texto na tela
    expect(JSON.stringify(chat.blocos)).toContain('versão 1 gerada');

    const projeto = useProjetoAtivo.getState();
    expect(projeto.projeto?.estado).toBe('pronto');
    expect(projeto.resumo?.area_ha).toBe(512.4);
    expect(projeto.versoes.map((v) => v.numero)).toEqual([1]);
    expect(projeto.projeto?.versao_atual).toBe(1);

    const job = useJob.getState();
    expect(job.jobId).toBe('j1');
    expect(job.pct).toBe(100);
    expect(job.log).toContain('camada de dinâmica ok');

    const palco = usePalco.getState();
    expect(palco.foco?.x).toBe(600000);
    expect(palco.camadas.dinamica?.estado).toBe('ok');

    expect(useConexao.getState().ultimoSeq).toBe(16);
  });

  it('replay do mesmo roteiro (reconexão) não duplica nada', () => {
    replay(ROTEIRO);
    const depoisDoPrimeiro = {
      camadas: usePalco.getState().camadas,
      versoes: useProjetoAtivo.getState().versoes.length,
      log: useJob.getState().log.length,
      blocos: JSON.stringify(useChat.getState().blocos),
    };

    replay(ROTEIRO);

    expect(useProjetoAtivo.getState().versoes).toHaveLength(depoisDoPrimeiro.versoes);
    expect(useJob.getState().log).toHaveLength(depoisDoPrimeiro.log);
    expect(JSON.stringify(useChat.getState().blocos)).toBe(depoisDoPrimeiro.blocos);
    expect(useConexao.getState().ultimoSeq).toBe(16);
  });

  it('seq repetido pontual é ignorado e o despachante diz que descartou', () => {
    const evento = ROTEIRO[4]!; // mensagem.criada
    expect(despachar(evento)).toBe(false);
    expect(despachar(evento)).toBe(true);
    expect(useChat.getState().mensagens).toHaveLength(1);
  });

  it('buraco no seq não é inventado: evento novo depois do buraco é aplicado', () => {
    despachar(ROTEIRO[0]!);
    const salto = { ...ROTEIRO[15]!, seq: 40 };
    expect(despachar(salto)).toBe(false);
    expect(useProjetoAtivo.getState().versoes).toHaveLength(1);
    expect(useConexao.getState().ultimoSeq).toBe(40);
  });
});
