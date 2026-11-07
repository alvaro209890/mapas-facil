/**
 * Leitura humana dos cartões de tool (divergência da web em relação ao desktop).
 *
 * O payload `chat.tool` traz `args_resumo`/`resultado_resumo` como JSON em texto. Aqui ele vira
 * o que o usuário entende: nome da ferramenta em português, argumentos em etiquetas curtas,
 * o "porquê" que o modelo deu e — quando falha — a mensagem de erro, sem JSON cru na frente.
 */

const NOMES: Record<string, string> = {
  estado_do_projeto: 'Ler o estado do projeto',
  listar_arquivos: 'Listar arquivos',
  inspecionar_shapefile: 'Inspecionar shapefile',
  ler_recibo_car: 'Ler recibo do CAR',
  listar_zip: 'Listar o .zip',
  listar_catalogo: 'Consultar catálogo',
  consultar_sema: 'Consultar SEMA',
  distancia_ate: 'Medir distância',
  calcular_quantitativos: 'Calcular quantitativos',
  listar_modelos_galeria: 'Listar modelos da galeria',
  usar_modelo_da_galeria: 'Usar modelo da galeria',
  criar_mapa: 'Criar mapa',
  definir_imovel: 'Definir dados do imóvel',
  adicionar_camada: 'Adicionar camada',
  remover_camada: 'Remover camada',
  editar_camada: 'Editar camada',
  definir_basemap: 'Definir imagem de fundo',
  definir_escala: 'Definir escala',
  definir_tabela: 'Definir tabela',
  editar_metadados: 'Editar metadados',
  ajustar_elemento: 'Ajustar elemento do layout',
  alternar_elemento: 'Mostrar/ocultar elemento',
  definir_titulo: 'Definir título',
  validar_mapspec: 'Validar o mapa',
  gerar_mapa: 'Gerar mapa',
  gerar_planilha: 'Gerar planilha',
  analisar_referencia: 'Analisar referência',
  definir_folha: 'Definir folha',
  sugerir_enquadramento: 'Sugerir enquadramento',
  listar_versoes: 'Listar versões',
  restaurar_versao: 'Restaurar versão',
  explicar_validacao: 'Explicar validação',
  perguntar: 'Perguntar ao usuário',
  comparar_com_modelo: 'Comparar com o modelo',
};

/** Chaves que o modelo usa para justificar a chamada — viram legenda, não etiqueta. */
const CHAVES_MOTIVO = new Set(['reason', 'motivo', 'porque', 'justificativa']);

export function nomeAmigavel(tool: string): string {
  return NOMES[tool] ?? tool.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
}

function parseObjeto(texto: string | undefined): Record<string, unknown> | null {
  if (!texto) return null;
  try {
    const valor: unknown = JSON.parse(texto);
    return valor && typeof valor === 'object' && !Array.isArray(valor)
      ? (valor as Record<string, unknown>)
      : null;
  } catch {
    return null; // resumo truncado pelo núcleo: não é JSON válido, cai no texto puro
  }
}

function ehMapSpec(valor: unknown): boolean {
  if (!valor || typeof valor !== 'object' || Array.isArray(valor)) return false;
  const obj = valor as Record<string, unknown>;
  return (
    'contract_version' in obj ||
    ('folha' in obj && 'camadas' in obj) ||
    ('imovel' in obj && 'camadas' in obj)
  );
}

function resumirMapSpec(valor: unknown): string {
  if (!valor || typeof valor !== 'object') return 'especificação do mapa';
  const obj = valor as Record<string, unknown>;
  const titulo = typeof obj.titulo === 'string' && obj.titulo ? obj.titulo : null;
  const imovel =
    obj.imovel && typeof obj.imovel === 'object'
      ? (obj.imovel as Record<string, unknown>).nome
      : null;
  const nome = titulo || (typeof imovel === 'string' ? imovel : 'padrão IMAP');
  return `especificação (${nome})`;
}

function valorCurto(valor: unknown): string {
  if (valor === null || valor === undefined) return '—';
  if (typeof valor === 'string') {
    if (valor.includes('contract_version') && valor.includes('camadas')) {
      return 'especificação do mapa';
    }
    return valor;
  }
  if (ehMapSpec(valor)) {
    return resumirMapSpec(valor);
  }
  if (typeof valor === 'number' || typeof valor === 'boolean') return String(valor);
  if (Array.isArray(valor)) return valor.map(valorCurto).join(', ');
  return JSON.stringify(valor);
}

export interface ArgsLegiveis {
  etiquetas: { chave: string; valor: string }[];
  motivo: string | null;
}

export function lerArgs(argsResumo: string | undefined): ArgsLegiveis {
  const objeto = parseObjeto(argsResumo);
  if (!objeto) {
    const bruto = (argsResumo ?? '').trim();
    if (bruto.includes('contract_version') && bruto.includes('camadas')) {
      return { etiquetas: [{ chave: 'mapa', valor: 'especificação do mapa' }], motivo: null };
    }
    return {
      etiquetas: bruto && bruto !== '{}' ? [{ chave: '', valor: bruto }] : [],
      motivo: null,
    };
  }
  let motivo: string | null = null;
  const etiquetas: { chave: string; valor: string }[] = [];
  for (const [chave, valor] of Object.entries(objeto)) {
    if (CHAVES_MOTIVO.has(chave) && typeof valor === 'string') {
      motivo = valor;
      continue;
    }
    if (chave === 'mapspec' || ehMapSpec(valor)) {
      etiquetas.push({ chave: 'mapa', valor: resumirMapSpec(valor) });
      continue;
    }
    etiquetas.push({ chave: chave.replace(/_/g, ' '), valor: valorCurto(valor) });
  }
  return { etiquetas, motivo };
}

export interface ResultadoLegivel {
  /** Mensagem de erro do núcleo (`{ok:false, mensagem}`), quando houver. */
  erro: string | null;
  codigo: string | null;
  /** JSON indentado (ou o texto original, se truncado). */
  formatado: string;
}

export function lerResultado(resultadoResumo: string | undefined): ResultadoLegivel | null {
  if (!resultadoResumo) return null;
  const objeto = parseObjeto(resultadoResumo);
  if (!objeto) return { erro: null, codigo: null, formatado: resultadoResumo };
  const falhou = objeto.ok === false;
  const mensagem = typeof objeto.mensagem === 'string' ? objeto.mensagem : null;
  const erros = Array.isArray(objeto.erros)
    ? objeto.erros
        .map((e) =>
          e && typeof e === 'object' && typeof (e as { mensagem?: unknown }).mensagem === 'string'
            ? (e as { mensagem: string }).mensagem
            : null,
        )
        .filter((e): e is string => e !== null)
    : [];
  const erro = falhou ? [mensagem, ...erros].filter(Boolean).join(' — ') || 'falhou' : null;

  let formatado = JSON.stringify(objeto, null, 2);
  if (ehMapSpec(objeto)) {
    formatado = JSON.stringify({ mapa: resumirMapSpec(objeto) }, null, 2);
  } else if (ehMapSpec(objeto.mapspec)) {
    const clone = { ...objeto, mapspec: resumirMapSpec(objeto.mapspec) };
    formatado = JSON.stringify(clone, null, 2);
  }

  return {
    erro,
    codigo: falhou && typeof objeto.codigo === 'string' ? objeto.codigo : null,
    formatado,
  };
}
