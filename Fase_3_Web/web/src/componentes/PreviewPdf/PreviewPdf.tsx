/**
 * Visualizador de Preview de PDF seguro (W-16 / planos/06-agente-pdf-first.md).
 *
 * Utiliza exclusivamente caminhos relativos sanitizados e API autenticada por versão/projeto,
 * nunca navegando caminhos absolutos ou strings arbitrárias.
 */

import { Download, ExternalLink, FileText } from 'lucide-react';
import estilos from './PreviewPdf.module.css';

interface PropriedadesPreviewPdf {
  projetoId: string;
  caminho: string;
  pagina?: number | undefined;
  titulo?: string | undefined;
}

/**
 * Remove tentativas de path traversal (../) ou barras iniciais para garantir
 * que apenas o caminho relativo sob o workspace do projeto seja consumido.
 */
function sanitizarCaminhoRelativo(caminho: string): string {
  return caminho
    .replace(/^([a-zA-Z]:)?[/\\]+/, '') // remove C:\ ou barras iniciais
    .split(/[/\\]+/)
    .filter((segmento) => segmento && segmento !== '..' && segmento !== '.')
    .join('/');
}

export function PreviewPdf({ projetoId, caminho, pagina, titulo }: PropriedadesPreviewPdf) {
  const caminhoLimpo = sanitizarCaminhoRelativo(caminho);
  const partes = caminhoLimpo.split('/').map(encodeURIComponent).join('/');
  const baseApi = `/api/v1/projetos/${encodeURIComponent(projetoId)}/arquivos/${partes}`;
  const urlVisualizacao = pagina ? `${baseApi}#page=${pagina}` : baseApi;
  const rotulo = titulo ?? caminhoLimpo;

  return (
    <div className={estilos.container} role="region" aria-label={`Pré-visualização de ${rotulo}`}>
      <div className={estilos.barraFerramentas}>
        <div className={estilos.info} title={caminhoLimpo}>
          <FileText size={16} aria-hidden="true" />
          <span>{rotulo}</span>
          {typeof pagina === 'number' && <span>(página {pagina})</span>}
        </div>

        <div className={estilos.acoes}>
          <a
            className={estilos.botaoLink}
            href={urlVisualizacao}
            target="_blank"
            rel="noreferrer"
            aria-label="Abrir em nova aba"
          >
            <ExternalLink size={13} aria-hidden="true" />
            <span>Abrir</span>
          </a>

          <a
            className={estilos.botaoLink}
            href={`${baseApi}?anexo=true`}
            download
            aria-label="Baixar PDF"
          >
            <Download size={13} aria-hidden="true" />
            <span>Baixar</span>
          </a>
        </div>
      </div>

      <iframe
        className={estilos.visualizador}
        src={urlVisualizacao}
        title={`Visualização do PDF: ${rotulo}`}
      />
    </div>
  );
}
