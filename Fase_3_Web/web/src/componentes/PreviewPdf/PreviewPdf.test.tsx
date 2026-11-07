/**
 * Testes do componente PreviewPdf.
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { PreviewPdf } from './PreviewPdf';

describe('PreviewPdf', () => {
  it('renderiza o iframe e o link de download autenticado com caminho relativo seguro', () => {
    render(
      <PreviewPdf
        projetoId="proj-1"
        caminho="Mapas/v001/mapa_dinamica.pdf"
        pagina={2}
        titulo="Mapa de Dinâmica 2026"
      />,
    );

    const linkNovaAba = screen.getByRole('link', { name: /abrir em nova aba/i });
    expect(linkNovaAba).toHaveAttribute(
      'href',
      '/api/v1/projetos/proj-1/arquivos/Mapas/v001/mapa_dinamica.pdf#page=2',
    );

    const iframe = screen.getByTitle('Visualização do PDF: Mapa de Dinâmica 2026');
    expect(iframe).toHaveAttribute(
      'src',
      '/api/v1/projetos/proj-1/arquivos/Mapas/v001/mapa_dinamica.pdf#page=2',
    );
  });

  it('sanitiza caminhos absolutos ou inseguros para caminhos relativos seguros', () => {
    render(
      <PreviewPdf
        projetoId="proj-1"
        caminho="../../secreto.pdf"
        titulo="Tentativa de traversal"
      />,
    );

    const link = screen.getByRole('link', { name: /abrir em nova aba/i });
    expect(link.getAttribute('href')).toBe('/api/v1/projetos/proj-1/arquivos/secreto.pdf');
    expect(link.getAttribute('href')).not.toContain('..');
  });
});
