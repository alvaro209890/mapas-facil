/**
 * Data legível para cartão de projeto.
 *
 * A regra é a do resto do produto: data **relativa** até uma semana, absoluta depois, sempre
 * no fuso local de quem está olhando. Nada de "3 days ago" nem de ISO cru na tela.
 */

const MINUTO = 60_000;
const HORA = 60 * MINUTO;
const DIA = 24 * HORA;

/**
 * @param iso data ISO do servidor (`2026-11-03T12:00:00-03:00` ou em UTC)
 * @param agora referência (default: `Date.now()`); passar fixo deixa o teste determinístico
 */
export function tempoRelativo(iso: string, agora: number = Date.now()): string {
  const quando = Date.parse(iso);
  if (Number.isNaN(quando)) return '';

  const diferenca = agora - quando;
  if (diferenca < 0) return 'agora';
  if (diferenca < MINUTO) return 'agora';
  if (diferenca < HORA) {
    const min = Math.floor(diferenca / MINUTO);
    return `há ${min} min`;
  }
  if (diferenca < DIA) {
    const horas = Math.floor(diferenca / HORA);
    return `há ${horas} h`;
  }
  const dias = Math.floor(diferenca / DIA);
  if (dias === 1) return 'ontem';
  if (dias < 7) return `há ${dias} dias`;
  return dataCurta(iso);
}

/** `03/11/2026` no fuso de quem olha. */
export function dataCurta(iso: string): string {
  const quando = new Date(iso);
  if (Number.isNaN(quando.getTime())) return '';
  return quando.toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

/** `A3 · paisagem` — o selo de folha do cartão. */
export function seloFolha(folha: { formato?: string; orientacao?: string } | undefined): string {
  const formato = folha?.formato ?? '';
  const orientacao = folha?.orientacao ?? 'retrato';
  return formato ? `${formato} · ${orientacao}` : '';
}
