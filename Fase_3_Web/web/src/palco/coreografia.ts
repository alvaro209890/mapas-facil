/**
 * Coreografia do palco (W8-05 / W-07 §Coreografia) — módulo **puro**.
 *
 * Sem React, sem DOM, sem zustand, sem relógio próprio: entram os eventos que o núcleo já
 * emitiu e sai uma lista de **passos** de animação, cada um com começo e duração. É isso que
 * deixa o palco testável sem navegador — `coreografia.test.ts` roda os roteiros gravados em
 * `servidor/tests/roteiros/`.
 *
 * ## Por que a compressão existe
 *
 * Os eventos chegam **mais rápido** que as animações: uma camada local sai em milissegundos e
 * um voo de câmera dura 2 s. Sem compressão, o palco ficaria minutos atrás do job e a animação
 * "contaria uma história" que já acabou. Por isso a fila é medida e o que sobrou é encurtado.
 *
 * ## Critério de compressão (o contrato testado)
 *
 * 1. Um evento virou passo com a **duração-alvo** da tabela de tokens.
 * 2. Mede-se o **atraso**: quantos eventos chegaram enquanto o passo anterior ainda estava
 *    tocando (`chegou_ms` do evento < fim do passo anterior na grade sem compressão). Esse
 *    número é a fila pendente. Sem relógio de chegada (ex.: leitura de um `.ndjson` gravado),
 *    a fila pendente é o tamanho da própria lista — mesma conta, sem inventar tempo.
 * 3. `pendentes ≤ 4` → duração-alvo inteira. `5..10` → **metade**. `> 10` → **um quarto**, com
 *    piso por tipo (`voo_min_ms`, `camada_intervalo_min_ms`, `elemento_intervalo_min_ms`).
 * 4. Com `> 10`, os **voos intermediários viram salto** (duração 0, `pulado: true`): o palco vai
 *    direto do primeiro ao último `viewport.foco` pendente; só o primeiro e o último animam.
 *    Os acendimentos entram em **ondas de 3** (três camadas no mesmo instante).
 * 5. Consequência que o teste prova: a duração total cresce no **piso** (~180 ms por camada em
 *    rajada), não na duração-alvo (~520 ms) — e **nenhum passo some**: o estado final é sempre
 *    o mesmo, com ou sem compressão (W-07 §Fila, "nenhum evento é descartado do estado").
 *
 * Nada aqui escreve no DOM nem agenda temporizador: quem executa os passos é o `Palco.tsx` (W8-01),
 * com o relógio dele. O módulo só diz **o quê**, **quando** e **por quanto tempo**.
 */

/** `[oeste, sul, leste, norte]` em EPSG:4326 — o mesmo formato de `mapasfacil_nucleo/motion.py`. */
export type Bbox4326 = [number, number, number, number];

/** Espelho de `motion.NIVEIS_VIEWPORT` (ordem de descida da câmera). */
export type NivelViewport = 'estado' | 'municipio' | 'imovel' | 'enquadramento' | 'folha';

export const NIVEIS_VIEWPORT: readonly NivelViewport[] = [
  'estado',
  'municipio',
  'imovel',
  'enquadramento',
  'folha',
];

/** `foco` = câmera, `camada` = acendimento vetorial/raster, `elemento` = peça da folha. */
export type TipoPasso = 'foco' | 'camada' | 'elemento';

/** Os quatro modos do palco (W-07 §Modos e transições). */
export type ModoPalco = 'ocioso' | 'mapa' | 'folha' | 'resultado';

/** Um passo de animação, pronto para o executor. */
export interface Passo {
  /** Único e determinístico: `<tipo>:<seq do evento>` (serve de `key` no React). */
  id: string;
  tipo: TipoPasso;
  /** `nivel` (foco), `camada_id` (camada) ou `elemento` (elemento). */
  alvo: string;
  inicio_ms: number;
  duracao_ms: number;
  /** O `dados` do evento, intacto — o executor lê bbox, estilo, caixa_mm etc. daqui. */
  dados: Record<string, unknown>;
  /** `true` quando a animação foi suprimida (salto da compressão ou `reduzir_movimento`). */
  pulado: boolean;
}

/**
 * O que a coreografia consome. É um recorte estrutural de `api/tipos.Evento` (que é o que o SSE
 * entrega) mais o relógio de chegada, que o despachante injeta.
 */
export interface EventoCoreografia {
  seq: number;
  evento: string;
  dados: Record<string, unknown>;
  /**
   * Relógio monotônico de chegada, em ms desde o começo do job. **Injetado por quem despacha**:
   * é o que permite saber se um evento chegou atrasado. Ausente = sem relógio (replay de arquivo).
   */
  chegou_ms?: number | undefined;
}

/** Durações-alvo de W-07 §Coreografia (os mesmos nomes de token do plano). */
export interface TokensCoreografia {
  voo_estado_ms: number;
  voo_municipio_ms: number;
  voo_imovel_ms: number;
  voo_enquadramento_ms: number;
  voo_folha_ms: number;
  voo_min_ms: number;
  voo_max_ms: number;
  camada_acende_ms: number;
  camada_intervalo_min_ms: number;
  raster_revela_ms: number;
  elemento_entra_ms: number;
  elemento_intervalo_min_ms: number;
  resultado_crossfade_ms: number;
}

export const TOKENS_COREOGRAFIA: TokensCoreografia = {
  voo_estado_ms: 1600,
  voo_municipio_ms: 1800,
  voo_imovel_ms: 2200,
  voo_enquadramento_ms: 900,
  voo_folha_ms: 1100,
  voo_min_ms: 500,
  voo_max_ms: 2400,
  camada_acende_ms: 520,
  camada_intervalo_min_ms: 180,
  raster_revela_ms: 700,
  elemento_entra_ms: 360,
  elemento_intervalo_min_ms: 120,
  resultado_crossfade_ms: 240,
};

/** Teto do fator de feições: uma camada com 1.000 polígonos não pode durar 10× uma com 1. */
export const FATOR_FEICOES_MAX = 2;
/** Até este número de passos pendentes, nada é comprimido. */
export const LIMITE_COMPRESSAO_LEVE = 4;
/** Acima deste número, os voos intermediários viram salto e os acendimentos entram em ondas. */
export const LIMITE_COMPRESSAO_FORTE = 10;
export const FATOR_COMPRESSAO_LEVE = 0.5;
export const FATOR_COMPRESSAO_FORTE = 0.25;
/** Fração final do voo em que um acendimento já pode começar (W-07 §Fila item 2). */
export const SOBREPOSICAO_VOO = 0.3;
/** Quantas camadas acendem juntas quando a fila está estourada (W-07 §Fila item 3). */
export const CAMADAS_POR_ONDA = 3;

export interface OpcoesCoreografia {
  /** `prefers-reduced-motion: reduce` (ou o usuário desligou a animação): durações viram 0. */
  reduzir_movimento?: boolean | undefined;
  /** Sobrescreve tokens — usado por teste e por folha maior. */
  tokens?: Partial<TokensCoreografia> | undefined;
}

// ------------------------------------------------------------------ utilidades

function numero(valor: unknown): number | null {
  return typeof valor === 'number' && Number.isFinite(valor) ? valor : null;
}

function texto(valor: unknown): string {
  return typeof valor === 'string' ? valor.trim() : '';
}

function bboxDe(valor: unknown): Bbox4326 | null {
  if (!Array.isArray(valor) || valor.length !== 4) return null;
  const o = numero(valor[0]);
  const s = numero(valor[1]);
  const l = numero(valor[2]);
  const n = numero(valor[3]);
  if (o === null || s === null || l === null || n === null) return null;
  if (o < -180 || l > 180 || s < -90 || n > 90) return null;
  if (o >= l || s >= n) return null;
  return [o, s, l, n];
}

function ehNivel(valor: unknown): valor is NivelViewport {
  return typeof valor === 'string' && (NIVEIS_VIEWPORT as readonly string[]).includes(valor);
}

function duracaoVoo(nivel: NivelViewport, tokens: TokensCoreografia): number {
  switch (nivel) {
    case 'estado':
      return tokens.voo_estado_ms;
    case 'municipio':
      return tokens.voo_municipio_ms;
    case 'imovel':
      return tokens.voo_imovel_ms;
    case 'enquadramento':
      return tokens.voo_enquadramento_ms;
    case 'folha':
      return tokens.voo_folha_ms;
  }
}

/**
 * Duração do acendimento, proporcional ao tamanho da geometria pelo número de feições.
 *
 * É log e não linear de propósito: 1 → 100 feições tem de aparecer na duração, 1.000 → 10.000
 * não. E é `n_feicoes` (contado pelo núcleo) e não a área medida aqui — o navegador não calcula
 * área nem escala para mostrar em rótulo (anti-padrão de W-07).
 */
function duracaoCamada(dados: Record<string, unknown>, tokens: TokensCoreografia): number {
  if (texto(dados.geometria) === 'raster') return tokens.raster_revela_ms;
  const feicoes = Math.max(0, numero(dados.n_feicoes) ?? 0);
  const fator = Math.min(FATOR_FEICOES_MAX, 1 + Math.log10(1 + feicoes));
  return Math.round(tokens.camada_acende_ms * fator);
}

// ------------------------------------------------------------------ passos-alvo

interface PassoAlvo {
  id: string;
  tipo: TipoPasso;
  alvo: string;
  seq: number;
  dados: Record<string, unknown>;
  chegou_ms: number | undefined;
  dur_alvo: number;
}

/**
 * Converte os eventos em passos-alvo, **descartando em silêncio** o que está fora do contrato.
 *
 * Evento de outro tipo (`job.progresso`, `job.log`, `chat.*`...) não vira passo: o palco não
 * anima o que não é dele. Evento do contrato mas sem campo obrigatório (camada sem id, elemento
 * sem nome, `nivel` desconhecido) também não: melhor não animar do que animar errado. Nada disso
 * levanta exceção — uma linha estranha no SSE não pode derrubar a tela.
 */
function passosAlvo(eventos: readonly EventoCoreografia[], tokens: TokensCoreografia): PassoAlvo[] {
  const alvos: PassoAlvo[] = [];
  const vistos = new Set<string>();

  for (const evento of eventos) {
    if (!evento || !Number.isFinite(evento.seq)) continue;
    const dados = evento.dados ?? {};
    const id = `${evento.evento}:${evento.seq}`;
    if (vistos.has(id)) continue;

    if (evento.evento === 'viewport.foco') {
      const bbox = bboxDe(dados.bbox_4326);
      const legado = numero(dados.x) !== null && numero(dados.y) !== null;
      let alvo: string;
      let dur: number;
      if (dados.nivel === undefined || dados.nivel === null) {
        // Formato do desktop M8 (`x`/`y`/`motivo`), mantido só para não quebrar o roteiro do W6.
        if (!bbox && !legado) continue;
        alvo = 'foco';
        dur = tokens.voo_estado_ms;
      } else if (ehNivel(dados.nivel)) {
        alvo = dados.nivel;
        dur = duracaoVoo(dados.nivel, tokens);
      } else {
        continue; // nível fora do contrato
      }
      vistos.add(id);
      alvos.push({ id, tipo: 'foco', alvo, seq: evento.seq, dados, chegou_ms: evento.chegou_ms, dur_alvo: dur });
      continue;
    }

    if (evento.evento === 'camada.renderizada') {
      const alvo = texto(dados.camada_id) || texto(dados.nome);
      if (!alvo) continue;
      vistos.add(id);
      alvos.push({
        id,
        tipo: 'camada',
        alvo,
        seq: evento.seq,
        dados,
        chegou_ms: evento.chegou_ms,
        dur_alvo: duracaoCamada(dados, tokens),
      });
      continue;
    }

    if (evento.evento === 'layout.elemento') {
      const alvo = texto(dados.elemento) || texto(dados.nome);
      if (!alvo) continue;
      vistos.add(id);
      alvos.push({
        id,
        tipo: 'elemento',
        alvo,
        seq: evento.seq,
        dados,
        chegou_ms: evento.chegou_ms,
        dur_alvo: tokens.elemento_entra_ms,
      });
      continue;
    }
    // Evento de outro tipo: não é do palco.
  }
  return alvos;
}

// ------------------------------------------------------------------ agenda

/**
 * Agenda os passos-alvo na grade de tempo.
 *
 * Regras (W-07 §Fila):
 * * **voos não se sobrepõem** — cada `foco` começa quando o anterior termina;
 * * **acendimento pode começar antes do voo acabar**: a partir dos últimos 30% dele;
 * * **intervalo mínimo** entre dois acendimentos do mesmo tipo;
 * * com `pularVoos`, os voos que não são o primeiro nem o último viram salto (duração 0) e as
 *   camadas entram em ondas de `CAMADAS_POR_ONDA`.
 */
function agendar(
  alvos: readonly PassoAlvo[],
  tokens: TokensCoreografia,
  fator: number,
  pularVoos: boolean,
): Passo[] {
  const passos: Passo[] = [];
  const indicesFoco = alvos.map((a, i) => (a.tipo === 'foco' ? i : -1)).filter((i) => i >= 0);
  const primeiroFoco = indicesFoco[0] ?? -1;
  const ultimoFoco = indicesFoco[indicesFoco.length - 1] ?? -1;

  let fimVoo = 0;
  let durVoo = 0;
  let baseCamada = 0;
  let quantasCamadas = 0;
  let baseElemento = 0;
  let quantosElementos = 0;

  alvos.forEach((alvo, indice) => {
    // Quando o último voo já "entrega" o assunto: faltando 30% dele para terminar.
    const liberado = Math.max(0, fimVoo - Math.round(durVoo * SOBREPOSICAO_VOO));

    if (alvo.tipo === 'foco') {
      const alvoComprimido = Math.round(alvo.dur_alvo * fator);
      let duracao = Math.min(tokens.voo_max_ms, Math.max(tokens.voo_min_ms, alvoComprimido));
      let pulado = false;
      if (pularVoos && indice !== primeiroFoco && indice !== ultimoFoco) {
        duracao = 0;
        pulado = true;
      }
      passos.push({
        id: alvo.id,
        tipo: alvo.tipo,
        alvo: alvo.alvo,
        inicio_ms: fimVoo,
        duracao_ms: duracao,
        dados: alvo.dados,
        pulado,
      });
      fimVoo += duracao;
      durVoo = duracao;
      return;
    }

    const piso =
      alvo.tipo === 'camada' ? tokens.camada_intervalo_min_ms : tokens.elemento_intervalo_min_ms;
    const duracao = Math.max(piso, Math.round(alvo.dur_alvo * fator));

    let inicio: number;
    if (alvo.tipo === 'camada') {
      if (quantasCamadas === 0) baseCamada = liberado;
      const onda = pularVoos ? Math.floor(quantasCamadas / CAMADAS_POR_ONDA) : quantasCamadas;
      inicio = Math.max(liberado, baseCamada + onda * tokens.camada_intervalo_min_ms);
      quantasCamadas += 1;
    } else {
      if (quantosElementos === 0) baseElemento = liberado;
      inicio = Math.max(liberado, baseElemento + quantosElementos * tokens.elemento_intervalo_min_ms);
      quantosElementos += 1;
    }

    passos.push({
      id: alvo.id,
      tipo: alvo.tipo,
      alvo: alvo.alvo,
      inicio_ms: inicio,
      duracao_ms: duracao,
      dados: alvo.dados,
      pulado: false,
    });
  });

  return passos;
}

/**
 * Quantos eventos chegaram enquanto o passo anterior ainda estava tocando.
 *
 * Sem relógio de chegada no lote (replay de arquivo, teste de rajada sem tempo), o atraso é o
 * tamanho da própria fila: todo evento menos o primeiro já chegou "junto".
 */
function contarPendentes(alvos: readonly PassoAlvo[], semCompressao: readonly Passo[]): number {
  const temRelogio = alvos.some((alvo) => alvo.chegou_ms !== undefined);
  if (!temRelogio) return alvos.length;
  let pendentes = 0;
  for (let i = 1; i < alvos.length; i += 1) {
    const chegou = alvos[i]?.chegou_ms ?? 0;
    const anterior = semCompressao[i - 1];
    if (anterior && chegou < anterior.inicio_ms + anterior.duracao_ms) pendentes += 1;
  }
  return pendentes;
}

/**
 * A coreografia: eventos do núcleo → passos ordenados.
 *
 * A ordem de saída é **a ordem de chegada dos eventos** (nunca uma ordem própria): o palco mostra
 * a mesma sequência que o PDF vai desenhar. Só o **tempo** é ajustado.
 */
export function coreografar(
  eventos: readonly EventoCoreografia[],
  opcoes: OpcoesCoreografia = {},
): Passo[] {
  const tokens: TokensCoreografia = { ...TOKENS_COREOGRAFIA, ...(opcoes.tokens ?? {}) };
  const alvos = passosAlvo(eventos, tokens);
  if (alvos.length === 0) return [];

  if (opcoes.reduzir_movimento === true) {
    // Tudo instantâneo, ordem intacta: nenhum voo e nenhuma entrada acima de ~0 ms.
    return alvos.map((alvo) => ({
      id: alvo.id,
      tipo: alvo.tipo,
      alvo: alvo.alvo,
      inicio_ms: 0,
      duracao_ms: 0,
      dados: alvo.dados,
      pulado: true,
    }));
  }

  const semCompressao = agendar(alvos, tokens, 1, false);
  const pendentes = contarPendentes(alvos, semCompressao);
  const fator =
    pendentes <= LIMITE_COMPRESSAO_LEVE
      ? 1
      : pendentes <= LIMITE_COMPRESSAO_FORTE
        ? FATOR_COMPRESSAO_LEVE
        : FATOR_COMPRESSAO_FORTE;
  return agendar(alvos, tokens, fator, pendentes > LIMITE_COMPRESSAO_FORTE);
}

/** Fim do último passo — é a "duração total" que o teste de compressão compara. */
export function duracaoTotal(passos: readonly Passo[]): number {
  return passos.reduce((fim, passo) => Math.max(fim, passo.inicio_ms + passo.duracao_ms), 0);
}

// ------------------------------------------------------------------ estado final

export interface FocoFinal {
  nivel: NivelViewport | null;
  bbox_4326: Bbox4326 | null;
  rotulo: string;
  escala: number | null;
  crs_mapa: string | null;
  quadro_mm: { largura: number; altura: number } | null;
  /** Centro do `bbox` (ou `x` do formato legado) — o que o executor usa para posicionar. */
  x: number;
  y: number;
  motivo: string;
}

export interface CamadaFinal {
  camada_id: string;
  papel: string;
  nome: string;
  geometria: string;
  sequencia: number;
  total: number;
  caminho: string | null;
  bbox_4326: Bbox4326 | null;
  estilo: Record<string, unknown> | null;
  n_feicoes: number;
  area_ha: number | null;
  estado: 'renderizando' | 'ok' | 'falhou';
}

export interface ElementoFinal {
  elemento: string;
  sequencia: number;
  total: number;
  folha: Record<string, unknown> | null;
  caixa_mm: Record<string, unknown> | null;
  conteudo: Record<string, unknown> | string | null;
  caminho: string | null;
  visivel: boolean;
}

export interface VersaoFinal {
  numero: number;
  conforme: boolean;
}

export interface EstadoPalco {
  modo: ModoPalco;
  foco: FocoFinal | null;
  camadas: Record<string, CamadaFinal>;
  elementos: Record<string, ElementoFinal>;
  versao: VersaoFinal | null;
  resultado: boolean;
  erro: string | null;
  ultimo_seq: number;
}

/**
 * Escolhe o modo do palco a partir do estado (W-07 §Modos e transições).
 *
 * `resultado` ganha de tudo (foi uma versão que nasceu); depois vem `folha` (a câmera recuou ou
 * o primeiro elemento encaixou); depois `mapa`; sem nada, `ocioso`.
 */
export function selecionarModo(estado: {
  foco: FocoFinal | null;
  camadas: Record<string, CamadaFinal>;
  elementos: Record<string, ElementoFinal>;
  resultado: boolean;
}): ModoPalco {
  if (estado.resultado) return 'resultado';
  if (estado.foco?.nivel === 'folha' || Object.keys(estado.elementos).length > 0) return 'folha';
  if (estado.foco !== null || Object.keys(estado.camadas).length > 0) return 'mapa';
  return 'ocioso';
}

function objetoOrdenado<T>(mapa: Map<string, T>): Record<string, T> {
  const pares = [...mapa.entries()].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
  return Object.fromEntries(pares) as Record<string, T>;
}

function focoDe(dados: Record<string, unknown>): FocoFinal {
  const bbox = bboxDe(dados.bbox_4326);
  const rotulo = texto(dados.rotulo) || texto(dados.motivo);
  const escala = numero(dados.escala);
  const quadro = dados.quadro_mm;
  const largura = quadro && typeof quadro === 'object' ? numero((quadro as Record<string, unknown>).largura) : null;
  const altura = quadro && typeof quadro === 'object' ? numero((quadro as Record<string, unknown>).altura) : null;
  return {
    nivel: ehNivel(dados.nivel) ? dados.nivel : null,
    bbox_4326: bbox,
    rotulo,
    escala,
    crs_mapa: texto(dados.crs_mapa) || null,
    quadro_mm: largura !== null && altura !== null ? { largura, altura } : null,
    x: bbox ? (bbox[0] + bbox[2]) / 2 : (numero(dados.x) ?? 0),
    y: bbox ? (bbox[1] + bbox[3]) / 2 : (numero(dados.y) ?? 0),
    motivo: texto(dados.motivo) || rotulo,
  };
}

function camadaDe(dados: Record<string, unknown>, anterior: CamadaFinal | undefined): CamadaFinal {
  const nome = texto(dados.nome);
  const camadaId = texto(dados.camada_id) || nome || anterior?.camada_id || '';
  const estadoBruto = texto(dados.estado);
  const estado: CamadaFinal['estado'] =
    estadoBruto === 'falhou' || estadoBruto === 'renderizando' ? estadoBruto : 'ok';
  return {
    camada_id: camadaId,
    papel: texto(dados.papel) || anterior?.papel || '',
    nome: nome || anterior?.nome || camadaId,
    geometria: texto(dados.geometria) || anterior?.geometria || '',
    sequencia: numero(dados.sequencia) ?? anterior?.sequencia ?? 0,
    total: numero(dados.total) ?? anterior?.total ?? 0,
    caminho: texto(dados.caminho) || anterior?.caminho || null,
    bbox_4326: bboxDe(dados.bbox_4326) ?? anterior?.bbox_4326 ?? null,
    estilo:
      dados.estilo && typeof dados.estilo === 'object'
        ? (dados.estilo as Record<string, unknown>)
        : (anterior?.estilo ?? null),
    n_feicoes: numero(dados.n_feicoes) ?? anterior?.n_feicoes ?? 0,
    area_ha: numero(dados.area_ha) ?? anterior?.area_ha ?? null,
    estado,
  };
}

function elementoDe(dados: Record<string, unknown>): ElementoFinal {
  const elemento = texto(dados.elemento) || texto(dados.nome);
  const conteudo = dados.conteudo;
  return {
    elemento,
    sequencia: numero(dados.sequencia) ?? 0,
    total: numero(dados.total) ?? 0,
    folha: dados.folha && typeof dados.folha === 'object' ? (dados.folha as Record<string, unknown>) : null,
    caixa_mm:
      dados.caixa_mm && typeof dados.caixa_mm === 'object'
        ? (dados.caixa_mm as Record<string, unknown>)
        : null,
    conteudo:
      typeof conteudo === 'string' || (conteudo && typeof conteudo === 'object')
        ? (conteudo as Record<string, unknown> | string)
        : null,
    caminho: texto(dados.caminho) || null,
    visivel: dados.visivel !== false,
  };
}

/**
 * Estado final do palco depois de aplicar a lista de eventos — **determinístico**.
 *
 * Mesma entrada ⇒ mesma saída, byte a byte no JSON: as chaves de `camadas` e `elementos` saem
 * ordenadas, não há relógio nem id aleatório em campo nenhum. É o que `replay()` promete.
 */
export function estadoFinal(eventos: readonly EventoCoreografia[]): EstadoPalco {
  const camadas = new Map<string, CamadaFinal>();
  const elementos = new Map<string, ElementoFinal>();
  let foco: FocoFinal | null = null;
  let versao: VersaoFinal | null = null;
  let resultado = false;
  let erro: string | null = null;
  let ultimoSeq = 0;

  for (const evento of eventos) {
    if (!evento || !Number.isFinite(evento.seq)) continue;
    const dados = evento.dados ?? {};
    ultimoSeq = Math.max(ultimoSeq, evento.seq);

    switch (evento.evento) {
      case 'viewport.foco': {
        const candidato = focoDe(dados);
        // Evento inválido (sem nível, sem bbox e sem o par legado) não muda o foco.
        if (candidato.nivel === null && candidato.bbox_4326 === null && candidato.x === 0 && candidato.y === 0) {
          break;
        }
        foco = candidato;
        break;
      }
      case 'camada.renderizada': {
        const chave = texto(dados.camada_id) || texto(dados.nome);
        if (!chave) break;
        camadas.set(chave, camadaDe(dados, camadas.get(chave)));
        break;
      }
      case 'layout.elemento': {
        const chave = texto(dados.elemento) || texto(dados.nome);
        if (!chave) break;
        elementos.set(chave, elementoDe(dados));
        break;
      }
      case 'versao.criada': {
        const bruta = dados.versao;
        if (bruta && typeof bruta === 'object') {
          const v = bruta as Record<string, unknown>;
          versao = { numero: numero(v.numero) ?? 0, conforme: v.conforme !== false };
          resultado = true;
        }
        break;
      }
      case 'nucleo.res': {
        if (dados.ok === true) {
          resultado = true;
          break;
        }
        if (dados.ok === false) {
          // O palco para onde está, escurece e mostra o código — não vira "resultado".
          const erroBruto = dados.erro;
          const codigo =
            erroBruto && typeof erroBruto === 'object'
              ? texto((erroBruto as Record<string, unknown>).codigo)
              : '';
          const mensagem =
            erroBruto && typeof erroBruto === 'object'
              ? texto((erroBruto as Record<string, unknown>).mensagem)
              : '';
          erro = [codigo, mensagem].filter(Boolean).join(': ') || 'a geração falhou';
        }
        break;
      }
      default:
        break;
    }
  }

  const estado: EstadoPalco = {
    modo: 'ocioso',
    foco,
    camadas: objetoOrdenado(camadas),
    elementos: objetoOrdenado(elementos),
    versao,
    resultado,
    erro,
    ultimo_seq: ultimoSeq,
  };
  estado.modo = selecionarModo(estado);
  return estado;
}

// ------------------------------------------------------------------ replay

export interface ResultadoReplay {
  estado: EstadoPalco;
  passos: Passo[];
  duracao_total_ms: number;
}

/**
 * Lê um NDJSON de eventos (uma linha = um evento; linha vazia, comentário `#` e JSON quebrado são
 * ignorados) e devolve os eventos utilizáveis.
 */
export function parsearNdjson(linhas: string | readonly string[]): EventoCoreografia[] {
  const fonte = typeof linhas === 'string' ? linhas : linhas.join('\n');
  const eventos: EventoCoreografia[] = [];
  let indice = 0;
  for (const bruta of fonte.split(/\r?\n/)) {
    indice += 1;
    const linha = bruta.trim();
    if (!linha || linha.startsWith('#')) continue;
    let bruto: unknown;
    try {
      bruto = JSON.parse(linha);
    } catch {
      continue; // linha quebrada não derruba o replay
    }
    if (!bruto || typeof bruto !== 'object' || Array.isArray(bruto)) continue;
    const evento = bruto as Record<string, unknown>;
    const nome = texto(evento.evento);
    if (!nome) continue;
    const dados =
      evento.dados && typeof evento.dados === 'object' && !Array.isArray(evento.dados)
        ? (evento.dados as Record<string, unknown>)
        : {};
    eventos.push({ seq: numero(evento.seq) ?? indice, evento: nome, dados });
  }
  return eventos;
}

/**
 * Reconstrói o palco a partir de um roteiro gravado (reconexão com `desde=0`, teste, depuração).
 *
 * Determinístico: a mesma lista de linhas devolve o mesmo JSON, na mesma ordem de chaves. Não há
 * relógio de chegada aqui — a compressão então usa o tamanho da fila (ver `contarPendentes`).
 */
export function replay(linhas: string | readonly string[]): ResultadoReplay {
  const eventos = parsearNdjson(linhas);
  const passos = coreografar(eventos);
  return {
    estado: estadoFinal(eventos),
    passos,
    duracao_total_ms: duracaoTotal(passos),
  };
}
