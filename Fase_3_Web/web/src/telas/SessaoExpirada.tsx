/**
 * Modal de sessão expirada (W6-09).
 *
 * Aparece quando qualquer requisição volta `401` (o cliente avisa a store uma vez só). A regra
 * do plano é **não perder o que o usuário digitou**: o modal é uma camada, não uma troca de
 * tela — o chat continua montado atrás dele, com o texto no campo, e o modal só pede a senha
 * para reabrir a mesma sessão.
 */

import { useState } from 'react';

import { ErroHttp } from '../api/cliente';
import { useSessao } from '../estado/sessao';
import estilos from './SessaoExpirada.module.css';

export function SessaoExpirada() {
  const { estado, usuario, entrar, carregando } = useSessao();
  const [senha, setSenha] = useState('');
  const [erro, setErro] = useState<string | null>(null);

  if (estado !== 'expirada') return null;

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    setErro(null);
    try {
      await entrar(usuario?.email ?? '', senha);
      setSenha('');
    } catch (e) {
      setErro(e instanceof ErroHttp ? `${e.codigo}: ${e.texto}` : 'Não foi possível entrar.');
    }
  }

  return (
    <div className={estilos.fundo} role="dialog" aria-modal="true" aria-labelledby="mf-titulo-expirada">
      <section className={estilos.caixa}>
        <h2 id="mf-titulo-expirada">Sua sessão expirou</h2>
        <p className={estilos.texto}>
          O que você escreveu continua aqui. Entre de novo para mandar a mensagem — nada foi
          perdido.
        </p>

        {usuario?.email ? (
          <form className={estilos.formulario} onSubmit={enviar}>
            <label htmlFor="mf-senha-expirada">Senha de {usuario.email}</label>
            <input
              id="mf-senha-expirada"
              type="password"
              autoComplete="current-password"
              autoFocus
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              required
            />
            {erro && (
              <div className={estilos.erro} role="alert">
                {erro}
              </div>
            )}
            <button type="submit" className={estilos.principal} disabled={!senha || carregando}>
              Entrar de novo
            </button>
          </form>
        ) : (
          <p className={estilos.texto}>Recarregue a página para entrar de novo.</p>
        )}
      </section>
    </div>
  );
}
