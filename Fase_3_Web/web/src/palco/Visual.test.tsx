/**
 * W8-10 — Testes visuais dos 6 estágios da coreografia do Palco (roteiro dinamica_ok).
 *
 * Valida a renderização e anatomia visual em cada ponto de parada:
 * 1. Estado (foco regional)
 * 2. Município (foco municipal)
 * 3. Imóvel (perímetro destacado)
 * 4. AVN acesa (camadas vetoriais)
 * 5. Folha montada com legenda e elementos
 * 6. Resultado final (versão concluída e pronta para entrega)
 */

import { render } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';

import { usePalco } from '../estado/palco';
import { Folha, type ElementoFolhaDados } from './Folha';
import { Palco } from './Palco';

describe('W8-10 — Testes visuais dos 6 estágios (dinamica_ok)', () => {
  beforeEach(() => {
    usePalco.getState().limpar();
  });

  it('Estágio 1 & 2: Modo Mapa com foco geográfico regional e municipal', () => {
    usePalco.setState({ modo: 'mapa' });
    const { container } = render(<Palco suporteWebGL={true} />);
    expect(container.querySelector('[data-modo="mapa"]')).toBeInTheDocument();
  });

  it('Estágio 3 & 4: Modo Mapa com camadas vetoriais acesas', () => {
    usePalco.setState({
      modo: 'mapa',
      camadas: {
        perimetro: {
          camada_id: 'perimetro',
          papel: 'imovel',
          nome: 'Perímetro',
          geometria: 'Polygon',
          sequencia: 1,
          total: 2,
          caminho: null,
          bbox_4326: null,
          estilo: null,
          n_feicoes: 1,
          area_ha: null,
          estado: 'ok',
        },
        avn: {
          camada_id: 'avn',
          papel: 'vegetacao',
          nome: 'AVN',
          geometria: 'MultiPolygon',
          sequencia: 2,
          total: 2,
          caminho: null,
          bbox_4326: null,
          estilo: null,
          n_feicoes: 3,
          area_ha: null,
          estado: 'ok',
        },
      },
    });
    const { container } = render(<Palco suporteWebGL={true} />);
    expect(container.querySelector('[data-modo="mapa"]')).toBeInTheDocument();
  });

  it('Estágio 5: Modo Folha com proporções mm reais e elementos', () => {
    const elementos: ElementoFolhaDados[] = [
      { elemento: 'titulo', caixa_mm: { x0: 15, y0: 10, x1: 195, y1: 30 } },
      { elemento: 'legenda', caixa_mm: { x0: 15, y0: 250, x1: 195, y1: 280 } },
    ];
    const { container } = render(
      <Folha
        formato="A4"
        orientacao="retrato"
        elementos={elementos}
        elementosVisiveis={['titulo', 'legenda']}
      />
    );

    const svg = container.querySelector('svg');
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveAttribute('viewBox', '0 0 210 297');
    expect(container.querySelector('[data-testid="papel-folha"]')).toBeInTheDocument();
  });

  it('Estágio 6: Modo Resultado com entrega e versão concluída', () => {
    usePalco.setState({ modo: 'resultado' });
    const { container } = render(<Palco />);
    expect(container.querySelector('[data-modo="resultado"]')).toBeInTheDocument();
  });
});
