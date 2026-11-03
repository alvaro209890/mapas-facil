/**
 * Tela provisória de rota ainda não construída (W6).
 *
 * Existe para o roteador ter destino honesto: diz **o que** vai nascer ali e em qual marco,
 * em vez de mostrar tela vazia ou conteúdo de mentira.
 */

import estilos from './EmBreve.module.css';

export interface EmBreveProps {
  titulo: string;
  marco: string;
}

export function EmBreve({ titulo, marco }: EmBreveProps) {
  return (
    <main className={estilos.tela}>
      <h1 className={estilos.titulo}>{titulo}</h1>
      <p className={estilos.texto}>
        Esta tela entra no marco <strong>{marco}</strong>. A rota já existe para o app não
        precisar de remendo depois.
      </p>
    </main>
  );
}
