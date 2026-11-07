/**
 * Painel do Agente v2 PDF-first (W-16 / planos/06-agente-pdf-first.md).
 *
 * Exibe:
 * 1. Checklist do plano / passos / status;
 * 2. Ferramentas e arquivos tocados com caminhos relativos seguros;
 * 3. Previews de PDF autenticados;
 * 4. Aprovação destrutiva explícita (sem autoenvio de texto, com proteção de canal seguro);
 * 5. Botão Parar / cancelamento seguro preservando os artefatos já gerados.
 */

import {
  CheckCircle2,
  Circle,
  CircleSlash,
  ExternalLink,
  FileCheck2,
  FileText,
  Loader2,
  ShieldAlert,
  XCircle,
} from 'lucide-react';
import type { PassoAgente, StatusAgente, StatusPasso } from '../../api/tipos';
import { useAgente } from '../../estado/agente';
import estilos from './PainelAgente.module.css';

interface PropriedadesPainelAgente {
  projetoId: string;
}

const ROTULO_STATUS_AGENTE: Record<StatusAgente, string> = {
  ocioso: 'Ocioso',
  pendente: 'Na fila',
  em_andamento: 'Executando',
  concluido: 'Concluído',
  erro: 'Erro',
  cancelado: 'Cancelado',
};

const CLASSE_STATUS_AGENTE: Record<StatusAgente, string | undefined> = {
  ocioso: estilos.badgeOcioso,
  pendente: estilos.badgePendente,
  em_andamento: estilos.badgeEmAndamento,
  concluido: estilos.badgeConcluido,
  erro: estilos.badgeErro,
  cancelado: estilos.badgeCancelado,
};

function IconePasso({ status }: { status: StatusPasso }) {
  switch (status) {
    case 'concluido':
      return <CheckCircle2 size={16} color="#22c55e" aria-hidden="true" />;
    case 'em_andamento':
      return <Loader2 size={16} color="#38bdf8" className="anim-spin" aria-hidden="true" />;
    case 'erro':
      return <XCircle size={16} color="#ef4444" aria-hidden="true" />;
    case 'cancelado':
      return <CircleSlash size={16} color="#94a3b8" aria-hidden="true" />;
    case 'pendente':
    default:
      return <Circle size={16} color="#8b949e" aria-hidden="true" />;
  }
}

export function PainelAgente({ projetoId }: PropriedadesPainelAgente) {
  const {
    passos,
    arquivos,
    aprovacao,
    status,
    resumoFim,
    previewAtivo,
    bloqueioAprovacao,
    cancelar,
    decidirAprovacao,
  } = useAgente();

  const ocupado = status === 'em_andamento';

  return (
    <section
      className={estilos.painel}
      role="region"
      aria-label="Plano de execução do agente"
      aria-busy={ocupado}
    >
      <header className={estilos.cabecalho}>
        <div className={estilos.titulo}>
          <FileText size={18} aria-hidden="true" />
          <span>Plano do Agente</span>
          <span
            className={`${estilos.badgeStatus} ${CLASSE_STATUS_AGENTE[status] ?? estilos.badgeOcioso}`}
          >
            {ROTULO_STATUS_AGENTE[status] ?? status}
          </span>
        </div>

        {ocupado && (
          <button
            type="button"
            className={estilos.botaoParar}
            onClick={() => void cancelar(projetoId)}
            aria-label="Parar agente"
          >
            Parar agente
          </button>
        )}
      </header>

      {/* ---------------------------------- Aprovação Destrutiva Explícita */}
      {aprovacao && !aprovacao.resolvida && (
        <div className={estilos.caixaAprovacao} role="alert" aria-live="assertive">
          <div className={estilos.aprovacaoTitulo}>
            <ShieldAlert size={18} aria-hidden="true" />
            <span>Aprovação Necessária: Ação Destrutiva</span>
          </div>

          <div className={estilos.aprovacaoDados}>
            <div className={estilos.dadoLinha}>
              <span className={estilos.dadoChave}>Ação:</span>
              <strong className={estilos.dadoValor}>{aprovacao.acao}</strong>
            </div>
            <div className={estilos.dadoLinha}>
              <span className={estilos.dadoChave}>Alvo:</span>
              <span className={estilos.dadoValor}>{aprovacao.caminho}</span>
            </div>
            {aprovacao.motivo && (
              <div className={estilos.dadoLinha}>
                <span className={estilos.dadoChave}>Motivo:</span>
                <span className={estilos.dadoValor}>{aprovacao.motivo}</span>
              </div>
            )}
          </div>

          <p className={estilos.avisoSeguranca}>
            Atenção: esta ação altera arquivos do projeto. A autorização é enviada
            estritamente por canal autenticado seguro e nunca via texto automático no chat.
          </p>

          {bloqueioAprovacao && (
            <div className={estilos.bloqueioMensagem} role="alert">
              {bloqueioAprovacao}
            </div>
          )}

          <div className={estilos.aprovacaoAcoes}>
            <button
              type="button"
              className={estilos.botaoAprovar}
              onClick={() => void decidirAprovacao(projetoId, true)}
            >
              Aprovar ação
            </button>
            <button
              type="button"
              className={estilos.botaoRecusar}
              onClick={() => void decidirAprovacao(projetoId, false)}
            >
              Recusar
            </button>
          </div>
        </div>
      )}

      {/* ---------------------------------- Checklist de Passos */}
      {passos.length > 0 && (
        <div className={estilos.secaoPassos}>
          <h3 className={estilos.subtitulo}>Etapas planejadas</h3>
          <ul className={estilos.listaPassos} role="list">
            {passos.map((passo: PassoAgente) => (
              <li key={passo.id} className={estilos.itemPasso} role="listitem">
                <span className={estilos.iconePasso}>
                  <IconePasso status={passo.status} />
                </span>
                <div className={estilos.passoConteudo}>
                  <span className={estilos.passoTitulo}>{passo.titulo}</span>
                  {passo.resumo && (
                    <span className={estilos.passoResumo}>{passo.resumo}</span>
                  )}
                </div>
                <span
                  className={`${estilos.badgeStatus} ${CLASSE_STATUS_AGENTE[passo.status] ?? estilos.badgeOcioso}`}
                >
                  {ROTULO_STATUS_AGENTE[passo.status] ?? passo.status}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ---------------------------------- Resumo de Conclusão */}
      {resumoFim && (
        <div className={estilos.resumoFinal} role="status">
          <strong>Resumo da entrega:</strong> {resumoFim}
        </div>
      )}

      {/* ---------------------------------- Arquivos Tocados */}
      {arquivos.length > 0 && (
        <div className={estilos.secaoArquivos}>
          <h3 className={estilos.subtitulo}>Arquivos tocados</h3>
          <ul className={estilos.listaArquivos} role="list">
            {arquivos.map((arq, i) => (
              <li key={`${arq.caminho}-${i}`} className={estilos.itemArquivo} role="listitem">
                <span className={estilos.caminhoArquivo}>{arq.caminho}</span>
                <span className={estilos.tagAcao}>{arq.acao}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ---------------------------------- Preview PDF */}
      {previewAtivo && (
        <div className={estilos.secaoPreview}>
          <h3 className={estilos.subtitulo}>Preview do Documento</h3>
          <div className={estilos.cartaoPreview}>
            <div className={estilos.infoPreview}>
              <span className={estilos.nomePreview}>
                <FileCheck2 size={14} style={{ display: 'inline', marginRight: 4 }} />
                {previewAtivo.caminho}
              </span>
              {typeof previewAtivo.pagina === 'number' && (
                <span className={estilos.paginaPreview}>Página {previewAtivo.pagina}</span>
              )}
            </div>

            <a
              className={estilos.linkPreview}
              href={`/api/v1/projetos/${encodeURIComponent(projetoId)}/arquivos/${previewAtivo.caminho
                .split('/')
                .map(encodeURIComponent)
                .join('/')}`}
              target="_blank"
              rel="noreferrer"
            >
              <span>Abrir PDF</span>
              <ExternalLink size={13} aria-hidden="true" />
            </a>
          </div>
        </div>
      )}
    </section>
  );
}
