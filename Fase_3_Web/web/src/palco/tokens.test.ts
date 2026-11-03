/**
 * Testes unitários dos tokens de motion e utilitários de redução de movimento (W8-08).
 */

import { describe, expect, it } from 'vitest';
import {
  CROSSFADE_REDUZIDO_MS,
  duracaoEfetiva,
  EASINGS,
  TOKENS_MOTION,
} from './tokens';

describe('tokens de motion do palco (W8-08)', () => {
  it('contém todas as durações canônicas do plano W-07', () => {
    expect(TOKENS_MOTION.voo_estado_ms).toBe(1600);
    expect(TOKENS_MOTION.voo_municipio_ms).toBe(1800);
    expect(TOKENS_MOTION.voo_imovel_ms).toBe(2200);
    expect(TOKENS_MOTION.voo_enquadramento_ms).toBe(900);
    expect(TOKENS_MOTION.voo_folha_ms).toBe(1100);
    expect(TOKENS_MOTION.voo_min_ms).toBe(500);
    expect(TOKENS_MOTION.voo_max_ms).toBe(2400);
    expect(TOKENS_MOTION.camada_acende_ms).toBe(520);
    expect(TOKENS_MOTION.camada_intervalo_min_ms).toBe(180);
    expect(TOKENS_MOTION.raster_revela_ms).toBe(700);
    expect(TOKENS_MOTION.folha_recuo_ms).toBe(1100);
    expect(TOKENS_MOTION.elemento_entra_ms).toBe(360);
    expect(TOKENS_MOTION.elemento_intervalo_min_ms).toBe(120);
    expect(TOKENS_MOTION.resultado_crossfade_ms).toBe(240);
  });

  it('define as curvas de aceleração e aproximação de câmera', () => {
    expect(EASINGS.vooCurva).toBe(1.6);
    expect(EASINGS.saida).toContain('cubic-bezier');
    expect(EASINGS.ambos).toContain('cubic-bezier');
    expect(EASINGS.entrada).toContain('cubic-bezier');
  });

  describe('duracaoEfetiva', () => {
    it('mantém a duração padrão quando reduzirMovimento é false', () => {
      expect(duracaoEfetiva(TOKENS_MOTION.voo_imovel_ms, false)).toBe(2200);
      expect(duracaoEfetiva(TOKENS_MOTION.camada_acende_ms, false)).toBe(520);
    });

    it('zera a duração de voos e acendimentos quando reduzirMovimento é true', () => {
      expect(duracaoEfetiva(TOKENS_MOTION.voo_estado_ms, true)).toBe(0);
      expect(duracaoEfetiva(TOKENS_MOTION.voo_imovel_ms, true)).toBe(0);
      expect(duracaoEfetiva(TOKENS_MOTION.camada_acende_ms, true)).toBe(0);
      expect(duracaoEfetiva(TOKENS_MOTION.elemento_entra_ms, true)).toBe(0);
    });

    it('limita crossfades a no máximo 150 ms quando reduzirMovimento é true', () => {
      expect(duracaoEfetiva(TOKENS_MOTION.resultado_crossfade_ms, true, true)).toBe(
        CROSSFADE_REDUZIDO_MS,
      );
      expect(duracaoEfetiva(100, true, true)).toBe(100);
    });
  });
});
