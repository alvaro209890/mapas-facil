/** `tempoRelativo`: relativo até uma semana, absoluto depois, nunca ISO na tela. */

import { describe, expect, it } from 'vitest';

import { dataCurta, seloFolha, tempoRelativo } from './tempo';

const AGORA = Date.parse('2026-11-03T15:00:00-03:00');

describe('tempoRelativo', () => {
  it('menos de um minuto é "agora"', () => {
    expect(tempoRelativo('2026-11-03T14:59:30-03:00', AGORA)).toBe('agora');
  });

  it('minutos e horas', () => {
    expect(tempoRelativo('2026-11-03T14:35:00-03:00', AGORA)).toBe('há 25 min');
    expect(tempoRelativo('2026-11-03T11:00:00-03:00', AGORA)).toBe('há 4 h');
  });

  it('ontem e até seis dias', () => {
    expect(tempoRelativo('2026-11-02T15:00:00-03:00', AGORA)).toBe('ontem');
    expect(tempoRelativo('2026-10-31T15:00:00-03:00', AGORA)).toBe('há 3 dias');
  });

  it('mais de uma semana vira data curta', () => {
    expect(tempoRelativo('2026-10-12T15:00:00-03:00', AGORA)).toBe(dataCurta('2026-10-12T15:00:00-03:00'));
    expect(tempoRelativo('2026-10-12T15:00:00-03:00', AGORA)).toBe('12/10/2026');
  });

  it('data inválida não vira "Invalid Date" na tela', () => {
    expect(tempoRelativo('nada', AGORA)).toBe('');
    expect(dataCurta('nada')).toBe('');
  });
});

describe('seloFolha', () => {
  it('junta formato e orientação', () => {
    expect(seloFolha({ formato: 'A3', orientacao: 'paisagem' })).toBe('A3 · paisagem');
    expect(seloFolha({ formato: 'A4' })).toBe('A4 · retrato');
    expect(seloFolha(undefined)).toBe('');
  });
});
