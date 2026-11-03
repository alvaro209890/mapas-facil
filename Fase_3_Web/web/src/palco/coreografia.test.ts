/**
 * W8-05 — coreografia do palco (`palco/coreografia.ts`).
 *
 * O módulo é puro, então o teste é só dado entrando e passo saindo — sem navegador, sem React,
 * sem timer. Roda os **roteiros gravados** de `servidor/tests/roteiros/` (o `palco_dinamica` é
 * gravação real de um job sintético; `serie_analise` e `dinamica_falha_hard` de palco ainda não
 * existem como gravação e entram aqui como fixture sintética coerente — os dois PNG/GeoJSON
 * daquele roteiro não são copiados, só as linhas de evento).
 *
 * O que este teste protege:
 *
 * 1. **Ordem** — o palco mostra a ordem dos eventos, nunca uma ordem própria (o PDF desenha
 *    nessa ordem).
 * 2. **Compressão** — rajada não acumula atraso, mas **nenhum passo some do estado**.
 * 3. **Replay determinístico** — mesma entrada, mesmo JSON, byte a byte.
 * 4. **Reduced motion** — nenhuma duração acima de 0.
 * 5. **Tolerância** — evento inválido/desconhecido é ignorado sem levantar.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  CAMADAS_POR_ONDA,
  TOKENS_COREOGRAFIA,
  coreografar,
  duracaoTotal,
  estadoFinal,
  parsearNdjson,
  replay,
  type EventoCoreografia,
  type Passo,
} from './coreografia';

const FIXTURES = join(__dirname, 'fixtures');

function lerFixture(nome: string): string {
  return readFileSync(join(FIXTURES, nome), 'utf8');
}

/**
 * Dá a cada evento um relógio de chegada bem espaçado — assim nada chegou "atrasado" e a
 * coreografia sai na duração-alvo (é o cenário de um job que emite devagar, como na vida real).
 */
function relogioLento(eventos: readonly EventoCoreografia[]): EventoCoreografia[] {
  return eventos.map((evento, indice) => ({ ...evento, chegou_ms: indice * 60_000 }));
}

/** Rajada: todos os eventos chegaram praticamente juntos (é o caso do núcleo local). */
function rajada(eventos: readonly EventoCoreografia[], chegada = 50): EventoCoreografia[] {
  return eventos.map((evento) => ({ ...evento, chegou_ms: chegada }));
}

function evento(
  seq: number,
  nome: string,
  dados: Record<string, unknown>,
): EventoCoreografia {
  return { seq, evento: nome, dados };
}

const BBOX_MT: [number, number, number, number] = [-61.6283, -18.0404, -50.2248, -7.3561];

const DINAMICA = lerFixture('palco_dinamica.ndjson');
const SERIE = lerFixture('serie_analise.ndjson');
const FALHA_HARD = lerFixture('dinamica_falha_hard.ndjson');

function alvos(passos: readonly Passo[]): string[] {
  return passos.map((passo) => passo.alvo);
}

function porTipo(passos: readonly Passo[], tipo: Passo['tipo']): Passo[] {
  return passos.filter((passo) => passo.tipo === tipo);
}

// ------------------------------------------------------------------ roteiro real

describe('roteiro dinâmica (gravação real do núcleo)', () => {
  const eventos = relogioLento(parsearNdjson(DINAMICA));
  const passos = coreografar(eventos);

  it('lê os 33 eventos e produz 13 passos, na ordem dos eventos', () => {
    expect(parsearNdjson(DINAMICA)).toHaveLength(33);
    expect(passos).toHaveLength(13);
    expect(alvos(passos)).toEqual([
      'estado',
      'municipio',
      'imovel',
      'perimetro',
      'avn',
      'enquadramento',
      'folha',
      'grade',
      'titulo_caixa',
      'norte',
      'metadados',
      'legenda',
      'logo',
    ]);
    expect(passos.map((p) => p.tipo)).toEqual([
      'foco',
      'foco',
      'foco',
      'camada',
      'camada',
      'foco',
      'foco',
      'elemento',
      'elemento',
      'elemento',
      'elemento',
      'elemento',
      'elemento',
    ]);
  });

  it('cada passo tem id único, alvo preenchido e os dados do evento intactos', () => {
    const nomeDoEvento: Record<Passo['tipo'], string> = {
      foco: 'viewport.foco',
      camada: 'camada.renderizada',
      elemento: 'layout.elemento',
    };
    expect(new Set(passos.map((p) => p.id)).size).toBe(passos.length);
    for (const passo of passos) {
      expect(passo.alvo).not.toBe('');
      // O id é `<evento>:<seq>` — dá para voltar ao evento que gerou o passo.
      expect(passo.id.startsWith(`${nomeDoEvento[passo.tipo]}:`)).toBe(true);
    }
    // O caminho do GeoJSON vem no `dados` — a coreografia não reescreve nem inventa arquivo.
    const perimetro = passos.find((p) => p.alvo === 'perimetro');
    expect(perimetro?.dados.caminho).toBe(
      'Mapas/.preview/01JOBPALCO0000000000000000/camadas/perimetro.geojson',
    );
    expect(perimetro?.dados.estilo).toMatchObject({ contorno: '#FFFF00', padrao: 'vazado' });
  });

  it('voos de câmera não se sobrepõem e acendimento começa antes do voo acabar', () => {
    const focos = porTipo(passos, 'foco');
    for (let i = 1; i < focos.length; i += 1) {
      const anterior = focos[i - 1];
      const atual = focos[i];
      expect(atual?.inicio_ms).toBeGreaterThanOrEqual(
        (anterior?.inicio_ms ?? 0) + (anterior?.duracao_ms ?? 0),
      );
    }
    // O perímetro acende nos últimos 30% do voo do imóvel (W-07 §Fila item 2).
    const imovel = passos.find((p) => p.alvo === 'imovel');
    const perimetro = passos.find((p) => p.alvo === 'perimetro');
    const fimImovel = (imovel?.inicio_ms ?? 0) + (imovel?.duracao_ms ?? 0);
    expect(perimetro?.inicio_ms).toBeGreaterThanOrEqual(
      fimImovel - Math.round((imovel?.duracao_ms ?? 0) * 0.3),
    );
    expect(perimetro?.inicio_ms).toBeLessThan(fimImovel);
  });

  it('a duração-alvo por tipo sai da tabela de tokens', () => {
    const porAlvo = new Map(passos.map((p) => [p.alvo, p]));
    expect(porAlvo.get('estado')?.duracao_ms).toBe(TOKENS_COREOGRAFIA.voo_estado_ms);
    expect(porAlvo.get('municipio')?.duracao_ms).toBe(TOKENS_COREOGRAFIA.voo_municipio_ms);
    expect(porAlvo.get('imovel')?.duracao_ms).toBe(TOKENS_COREOGRAFIA.voo_imovel_ms);
    expect(porAlvo.get('enquadramento')?.duracao_ms).toBe(
      TOKENS_COREOGRAFIA.voo_enquadramento_ms,
    );
    expect(porAlvo.get('folha')?.duracao_ms).toBe(TOKENS_COREOGRAFIA.voo_folha_ms);
    expect(porAlvo.get('grade')?.duracao_ms).toBe(TOKENS_COREOGRAFIA.elemento_entra_ms);
    // Nada comprimido: cada evento chegou depois do fim do passo anterior.
    expect(passos.every((p) => !p.pulado)).toBe(true);
  });

  it('o estado final fica na folha (montada) — quem vira `resultado` é `versao.criada`', () => {
    const resultado = replay(DINAMICA);
    // O roteiro real grava o job até o fim da exportação: nenhuma versão nasceu ainda.
    expect(resultado.estado.modo).toBe('folha');
    expect(resultado.estado.resultado).toBe(false);
    expect(resultado.estado.versao).toBeNull();
    expect(resultado.estado.foco?.nivel).toBe('folha');
    expect(resultado.estado.foco?.rotulo).toBe('A4 retrato');
    expect(Object.keys(resultado.estado.camadas)).toEqual(['avn', 'perimetro']);
    expect(Object.keys(resultado.estado.elementos)).toHaveLength(6);
    expect(resultado.estado.camadas.perimetro?.n_feicoes).toBe(1);
    expect(resultado.estado.camadas.avn?.estilo).toMatchObject({ padrao: 'hachura' });
    expect(resultado.estado.erro).toBeNull();
    expect(resultado.estado.ultimo_seq).toBe(33);
  });
});

// ------------------------------------------------------------------ compressão

describe('compressão sob rajada', () => {
  const eventos = parsearNdjson(DINAMICA);

  it('a rajada encurta a duração total e NÃO tira passo nenhum do estado', () => {
    const rapido = coreografar(rajada(eventos));
    const devagar = coreografar(relogioLento(eventos));

    expect(duracaoTotal(rapido)).toBeLessThan(duracaoTotal(devagar));
    expect(rapido.map((p) => p.id)).toEqual(devagar.map((p) => p.id));
    expect(rapido.map((p) => p.alvo)).toEqual(devagar.map((p) => p.alvo));
    // O estado final é o mesmo: compressão é tempo, não conteúdo.
    expect(JSON.stringify(estadoFinal(eventos))).toBe(
      JSON.stringify(estadoFinal(rajada(eventos))),
    );
  });

  it('fila curta (até 4 pendentes) não comprime; 5–10 cai pela metade', () => {
    const focos = (quantos: number): EventoCoreografia[] =>
      ['estado', 'municipio', 'imovel', 'enquadramento', 'folha']
        .slice(0, quantos)
        .map((nivel, indice) => evento(indice + 1, 'viewport.foco', { nivel, bbox_4326: BBOX_MT }));

    const curta = coreografar(rajada(focos(3)));
    // Pendentes ≤ 4: nada comprime — cada voo sai na duração-alvo do seu nível.
    expect(curta.map((p) => p.duracao_ms)).toEqual([
      TOKENS_COREOGRAFIA.voo_estado_ms,
      TOKENS_COREOGRAFIA.voo_municipio_ms,
      TOKENS_COREOGRAFIA.voo_imovel_ms,
    ]);
    expect(curta.every((p) => !p.pulado)).toBe(true);

    const meia = coreografar(
      rajada([
        ...focos(5),
        evento(6, 'camada.renderizada', { camada_id: 'perimetro', geometria: 'poligono', n_feicoes: 0 }),
      ]),
    );
    expect(meia).toHaveLength(6);
    // 5 pendentes caem para a metade da duração-alvo (piso não alcançado).
    expect(meia[0]?.duracao_ms).toBe(Math.round(TOKENS_COREOGRAFIA.voo_estado_ms * 0.5));
    expect(meia[5]?.duracao_ms).toBe(Math.round(TOKENS_COREOGRAFIA.camada_acende_ms * 0.5));
    expect(meia.every((p) => !p.pulado)).toBe(true);
  });

  it('fila estourada (>10) pula voos intermediários e agrupa acendimentos em ondas de 3', () => {
    const eventos: EventoCoreografia[] = [
      ...['estado', 'municipio', 'imovel', 'enquadramento', 'folha'].map((nivel, indice) =>
        evento(indice + 1, 'viewport.foco', { nivel, bbox_4326: BBOX_MT }),
      ),
      ...Array.from({ length: 8 }, (_, indice) =>
        evento(indice + 6, 'camada.renderizada', {
          camada_id: `c${String(indice)}`,
          geometria: 'poligono',
          n_feicoes: 0,
        }),
      ),
    ];
    const passos = coreografar(rajada(eventos));

    const focos = porTipo(passos, 'foco');
    expect(focos.map((p) => p.pulado)).toEqual([false, true, true, true, false]);
    expect(focos[0]?.duracao_ms).toBe(TOKENS_COREOGRAFIA.voo_min_ms);
    expect(focos[4]?.duracao_ms).toBe(TOKENS_COREOGRAFIA.voo_min_ms);

    const camadas = porTipo(passos, 'camada');
    expect(camadas).toHaveLength(8);
    expect(camadas.every((p) => p.duracao_ms === TOKENS_COREOGRAFIA.camada_intervalo_min_ms)).toBe(
      true,
    );
    // Onda: as 3 primeiras no mesmo instante, a quarta 180 ms depois.
    expect(camadas[1]?.inicio_ms).toBe(camadas[0]?.inicio_ms);
    expect(camadas[2]?.inicio_ms).toBe(camadas[0]?.inicio_ms);
    expect(camadas[CAMADAS_POR_ONDA]?.inicio_ms).toBe(
      (camadas[0]?.inicio_ms ?? 0) + TOKENS_COREOGRAFIA.camada_intervalo_min_ms,
    );
  });

  it('o tempo total cresce no piso, não na duração-alvo (não acumula atraso sem limite)', () => {
    const camadas = (quantas: number): EventoCoreografia[] =>
      Array.from({ length: quantas }, (_, indice) =>
        evento(indice + 1, 'camada.renderizada', {
          camada_id: `c${String(indice)}`,
          geometria: 'poligono',
          n_feicoes: 0,
        }),
      );
    const dez = duracaoTotal(coreografar(rajada(camadas(10))));
    const vinte = duracaoTotal(coreografar(rajada(camadas(20))));
    const cem = duracaoTotal(coreografar(rajada(camadas(100))));
    // Cada camada nova custa no máximo o intervalo mínimo (180 ms), nunca os 520 ms-alvo.
    expect(vinte - dez).toBeLessThanOrEqual(10 * TOKENS_COREOGRAFIA.camada_intervalo_min_ms);
    expect(cem - vinte).toBeLessThanOrEqual(80 * TOKENS_COREOGRAFIA.camada_intervalo_min_ms);
    expect(cem).toBeLessThan(100 * TOKENS_COREOGRAFIA.camada_acende_ms);
  });
});

// ------------------------------------------------------------------ reduced motion

describe('reduzir_movimento', () => {
  it('colapsa todas as durações para 0 mantendo a ordem', () => {
    const eventos = parsearNdjson(DINAMICA);
    const normal = coreografar(eventos);
    const reduzido = coreografar(eventos, { reduzir_movimento: true });

    expect(reduzido).toHaveLength(normal.length);
    expect(reduzido.map((p) => p.alvo)).toEqual(normal.map((p) => p.alvo));
    expect(reduzido.every((p) => p.duracao_ms === 0)).toBe(true);
    expect(reduzido.every((p) => p.inicio_ms === 0)).toBe(true);
    expect(reduzido.every((p) => p.pulado)).toBe(true);
    expect(duracaoTotal(reduzido)).toBe(0);
  });
});

// ------------------------------------------------------------------ proporção

describe('duração proporcional ao tamanho da geometria', () => {
  function duracaoDe(nFeicoes: number, geometria = 'poligono'): number {
    const passos = coreografar([
      evento(1, 'camada.renderizada', { camada_id: 'x', geometria, n_feicoes: nFeicoes }),
    ]);
    return passos[0]?.duracao_ms ?? -1;
  }

  it('mais feições, mais tempo — com teto (log, não linear)', () => {
    const zero = duracaoDe(0);
    const uma = duracaoDe(1);
    const muitas = duracaoDe(5_000);
    expect(zero).toBe(TOKENS_COREOGRAFIA.camada_acende_ms);
    expect(uma).toBeGreaterThan(zero);
    expect(muitas).toBeGreaterThan(uma);
    expect(muitas).toBeLessThanOrEqual(TOKENS_COREOGRAFIA.camada_acende_ms * 2);
  });

  it('raster usa a revela da máscara, não o acendimento vetorial', () => {
    expect(duracaoDe(0, 'raster')).toBe(TOKENS_COREOGRAFIA.raster_revela_ms);
  });
});

// ------------------------------------------------------------------ tolerância

describe('evento inválido ou desconhecido é ignorado sem quebrar', () => {
  it('nível fora do contrato, camada sem id, elemento sem nome e evento de outro módulo', () => {
    const passos = coreografar([
      evento(1, 'viewport.foco', { nivel: 'globo' }),
      evento(2, 'camada.renderizada', { papel: 'perimetro' }),
      evento(3, 'layout.elemento', { sequencia: 1 }),
      evento(4, 'job.progresso', { etapa: 'validando_spec', pct: 3 }),
      evento(5, 'chat.delta', { texto: 'oi' }),
      evento(6, 'viewport.foco', { nivel: 'estado', bbox_4326: BBOX_MT }),
    ]);
    expect(passos).toHaveLength(1);
    expect(passos[0]?.alvo).toBe('estado');

    const estado = estadoFinal([
      evento(1, 'viewport.foco', { nivel: 'globo' }),
      evento(2, 'camada.renderizada', {}),
      evento(3, 'layout.elemento', {}),
      evento(4, 'viewport.foco', { nivel: 'imovel', bbox_4326: BBOX_MT }),
    ]);
    expect(estado.foco?.nivel).toBe('imovel');
    expect(Object.keys(estado.camadas)).toEqual([]);
    expect(Object.keys(estado.elementos)).toEqual([]);
  });

  it('bbox malformado não vira foco, mas o par legado (x/y) ainda vira', () => {
    expect(coreografar([evento(1, 'viewport.foco', { bbox_4326: [1, 2, 3] })])).toHaveLength(0);
    const legado = coreografar([evento(2, 'viewport.foco', { x: 600_000, y: 8_300_000 })]);
    expect(legado).toHaveLength(1);
    expect(legado[0]?.alvo).toBe('foco');
  });

  it('parsearNdjson ignora comentário, linha vazia, JSON quebrado e evento sem nome', () => {
    const bruto = [
      '# cabeçalho',
      '',
      '{"seq": 2, "evento": "viewport.foco", "dados": {"nivel": "estado"}}',
      '{ isto não é json',
      '{"evento": "camada.renderizada", "dados": {"camada_id": "x"}}',
      '[]',
      '{"seq": 7}',
    ].join('\n');
    const eventos = parsearNdjson(bruto);
    expect(eventos.map((e) => e.seq)).toEqual([2, 5]);
    expect(eventos[1]?.evento).toBe('camada.renderizada');
  });
});

// ------------------------------------------------------------------ replay

describe('replay determinístico', () => {
  it('mesma entrada ⇒ mesma saída, byte a byte no JSON', () => {
    for (const linha of [DINAMICA, SERIE, FALHA_HARD]) {
      const primeira = JSON.stringify(replay(linha));
      const segunda = JSON.stringify(replay(linha));
      expect(segunda).toBe(primeira);
    }
  });

  it('a série sintética monta 4 mapas no mesmo job e termina em resultado', () => {
    const resultado = replay(SERIE);
    expect(resultado.estado.modo).toBe('resultado');
    expect(resultado.estado.versao).toEqual({ numero: 4, conforme: true });
    expect(resultado.estado.foco?.nivel).toBe('folha');
    expect(Object.keys(resultado.estado.camadas).sort()).toEqual(['ac', 'avn', 'perimetro']);
    expect(Object.keys(resultado.estado.elementos)).toHaveLength(6);

    const focos = porTipo(resultado.passos, 'foco');
    expect(focos).toHaveLength(17); // 1 estado + 4 × (município, imóvel, enquadramento, folha)
    expect(porTipo(resultado.passos, 'camada')).toHaveLength(12);
    expect(porTipo(resultado.passos, 'elemento')).toHaveLength(24);
    expect(resultado.passos).toHaveLength(53);
    // Cada tipo sai em ordem de tempo (um voo não volta atrás; acendimento não volta atrás).
    // Entre tipos, a sobreposição é o esperado: os elementos do mapa 1 entram enquanto a câmera
    // do mapa 2 já está se movendo.
    for (const tipo of ['foco', 'camada', 'elemento'] as const) {
      const inicios = porTipo(resultado.passos, tipo).map((p) => p.inicio_ms);
      expect([...inicios].sort((a, b) => a - b)).toEqual(inicios);
    }
    expect(resultado.passos[0]?.inicio_ms).toBe(0);
  });

  it('erro HARD termina em `resultado` NÃO conforme, guardando o código — sem animação de sucesso', () => {
    const resultado = replay(FALHA_HARD);
    expect(resultado.estado.modo).toBe('resultado');
    expect(resultado.estado.versao).toEqual({ numero: 1, conforme: false });
    expect(resultado.estado.erro).toContain('NU-500');
    expect(resultado.estado.erro).toContain('HARD');
    // O palco para onde estava: a folha montada continua lá.
    expect(resultado.estado.foco?.nivel).toBe('folha');
    expect(Object.keys(resultado.estado.elementos)).toHaveLength(6);

    const semErro = replay(DINAMICA);
    expect(duracaoTotal(resultado.passos)).toBeLessThanOrEqual(
      duracaoTotal(semErro.passos) + 1,
    );
  });

  it('nucleo.res com falha não vira resultado: o palco fica onde estava', () => {
    const eventos = [
      evento(1, 'viewport.foco', { nivel: 'imovel', bbox_4326: BBOX_MT }),
      evento(2, 'camada.renderizada', { camada_id: 'perimetro', geometria: 'poligono' }),
      evento(3, 'nucleo.res', { ok: false, erro: { codigo: 'NU-500', mensagem: 'HARD' } }),
    ];
    const estado = estadoFinal(eventos);
    expect(estado.modo).toBe('mapa');
    expect(estado.resultado).toBe(false);
    expect(estado.erro).toBe('NU-500: HARD');
    expect(Object.keys(estado.camadas)).toEqual(['perimetro']);
  });
});
