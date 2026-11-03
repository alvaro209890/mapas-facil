/**
 * Conta (W6-08) — trocar senha, tema e sair.
 *
 * Nada de campo que o servidor não tem: aqui só senha (com a regra mostrada antes de enviar),
 * tema (preferência local do navegador) e sair.
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';

import { ErroHttp } from '../api/cliente';
import { useSessao } from '../estado/sessao';
import { problemasSenha } from './Entrar';
import estilos from './Conta.module.css';

type Tema = 'escuro' | 'claro';

function temaAtual(): Tema {
  return document.documentElement.dataset.tema === 'claro' ? 'claro' : 'escuro';
}

export function Conta() {
  const { usuario, trocarSenha, sair } = useSessao();
  const [atual, setAtual] = useState('');
  const [nova, setNova] = useState('');
  const [erro, setErro] = useState<string | null>(null);
  const [feito, setFeito] = useState(false);
  const [tema, setTema] = useState<Tema>(temaAtual);

  const problema = problemasSenha(nova);

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    setErro(null);
    setFeito(false);
    try {
      await trocarSenha(atual, nova);
      setFeito(true);
      setAtual('');
      setNova('');
    } catch (e) {
      setErro(e instanceof ErroHttp ? `${e.codigo}: ${e.texto}` : 'Não foi possível trocar a senha.');
    }
  }

  function mudarTema(novo: Tema) {
    setTema(novo);
    // Preferência do navegador: o servidor não guarda tema (D15/AP-08).
    document.documentElement.dataset.tema = novo;
    try {
      localStorage.setItem('mf-tema', novo);
    } catch {
      // modo privado pode bloquear localStorage — o app continua no tema escolhido na sessão
    }
  }

  return (
    <main className={estilos.tela}>
      <header className={estilos.cabecalho}>
        <div>
          <Link to="/projetos" className={estilos.voltar}>
            ← Projetos
          </Link>
          <h1 className={estilos.titulo}>Sua conta</h1>
          <p className={estilos.subtitulo}>
            {usuario?.nome} · {usuario?.email} · {usuario?.papel === 'admin' ? 'administrador' : 'usuário'}
          </p>
        </div>
      </header>

      <section className={estilos.bloco}>
        <h2>Trocar a senha</h2>
        <form className={estilos.formulario} onSubmit={enviar}>
          <label htmlFor="mf-atual-conta">Senha atual</label>
          <input
            id="mf-atual-conta"
            type="password"
            autoComplete="current-password"
            value={atual}
            onChange={(e) => setAtual(e.target.value)}
            required
          />
          <label htmlFor="mf-nova-conta">Senha nova</label>
          <input
            id="mf-nova-conta"
            type="password"
            autoComplete="new-password"
            aria-describedby="mf-dica-conta"
            value={nova}
            onChange={(e) => setNova(e.target.value)}
            required
          />
          <small id="mf-dica-conta" className={problema ? estilos.dicaErro : estilos.dica}>
            {problema ?? 'Mínimo 10 caracteres, nada de sequência óbvia.'}
          </small>
          {erro && (
            <div className={estilos.erro} role="alert">
              {erro}
            </div>
          )}
          {feito && (
            <div className={estilos.ok} role="status">
              Senha alterada.
            </div>
          )}
          <button type="submit" className={estilos.principal} disabled={!atual || !nova || Boolean(problema)}>
            Salvar
          </button>
        </form>
      </section>

      <section className={estilos.bloco}>
        <h2>Tema</h2>
        <div className={estilos.abas} role="group" aria-label="Tema">
          {(['escuro', 'claro'] as Tema[]).map((opcao) => (
            <button
              key={opcao}
              type="button"
              aria-pressed={tema === opcao}
              className={tema === opcao ? `${estilos.aba} ${estilos.abaAtiva}` : estilos.aba}
              onClick={() => mudarTema(opcao)}
            >
              {opcao}
            </button>
          ))}
        </div>
        <p className={estilos.dica}>O escuro é o padrão do produto. A escolha fica neste navegador.</p>
      </section>

      <section className={estilos.bloco}>
        <h2>Sessão</h2>
        <button type="button" className={estilos.secundario} onClick={() => void sair()}>
          Sair deste navegador
        </button>
      </section>
    </main>
  );
}
