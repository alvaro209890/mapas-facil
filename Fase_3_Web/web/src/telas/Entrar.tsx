/**
 * Tela de entrada e cadastro (W6-04).
 *
 * Regras do W-06:
 * - duas abas (Entrar / Criar conta), cadastro aberto sem confirmação de e-mail (D27);
 * - erro sempre com o **código do servidor** e o "o que fazer" — nunca "erro ao entrar";
 * - `SV-005` mostra contagem regressiva **real** (`detalhes.espera_s`), não um relógio inventado;
 * - conta criada pela CLI do admin (`trocar_senha: true`) cai na troca obrigatória.
 *
 * A cena de fundo é decorativa (grade de MT se desenhando). Ela não finge progresso de job:
 * é a única animação sem evento permitida, e sai com `prefers-reduced-motion`.
 */

import { useEffect, useMemo, useState } from 'react';

import { ErroHttp } from '../api/cliente';
import { useSessao } from '../estado/sessao';
import estilos from './Entrar.module.css';

type Aba = 'entrar' | 'criar';

const SENHA_MIN = 10;

/** Regra de senha do servidor, resumida — o servidor é quem decide (SV-010). */
export function problemasSenha(senha: string): string | null {
  if (senha.length < SENHA_MIN) return `A senha precisa de pelo menos ${SENHA_MIN} caracteres.`;
  if (/^\d+$/.test(senha)) return 'A senha não pode ser só números.';
  if (/^(.)\1+$/.test(senha)) return 'A senha não pode ser um caractere repetido.';
  return null;
}

export interface EntrarProps {
  /** Para onde ir depois de entrar (vem de `?volta=`). */
  aoEntrar?: () => void;
}

export function Entrar({ aoEntrar }: EntrarProps) {
  const { entrar, cadastrar, carregando, estado, precisaTrocarSenha } = useSessao();
  const [aba, setAba] = useState<Aba>('entrar');
  const [nome, setNome] = useState('');
  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [repetir, setRepetir] = useState('');
  const [erro, setErro] = useState<{ codigo: string; texto: string } | null>(null);
  const [espera, setEspera] = useState(0);

  // Contagem regressiva do bloqueio de login (SV-005). Só anda se o servidor disse quanto.
  useEffect(() => {
    if (espera <= 0) return;
    const t = setInterval(() => setEspera((s) => (s > 0 ? s - 1 : 0)), 1000);
    return () => clearInterval(t);
  }, [espera]);

  useEffect(() => {
    if (estado === 'ativa' && !precisaTrocarSenha) aoEntrar?.();
  }, [estado, precisaTrocarSenha, aoEntrar]);

  const problemaDaSenha = useMemo(() => (aba === 'criar' ? problemasSenha(senha) : null), [aba, senha]);
  const senhasDiferentes = aba === 'criar' && repetir.length > 0 && repetir !== senha;
  const podeEnviar =
    !carregando &&
    espera === 0 &&
    email.includes('@') &&
    senha.length > 0 &&
    (aba === 'entrar' || (nome.trim().length > 0 && !problemaDaSenha && !senhasDiferentes));

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    setErro(null);
    try {
      if (aba === 'entrar') {
        await entrar(email.trim(), senha);
      } else {
        await cadastrar(nome.trim(), email.trim(), senha);
      }
    } catch (e) {
      if (e instanceof ErroHttp) {
        const segundos = Number((e.detalhes as { espera_s?: unknown } | undefined)?.espera_s ?? 0);
        if (e.codigo === 'SV-005' && segundos > 0) setEspera(segundos);
        setErro({ codigo: e.codigo, texto: e.texto });
      } else {
        setErro({ codigo: 'REDE', texto: 'Não foi possível falar com o servidor. Tente de novo.' });
      }
    }
  }

  if (precisaTrocarSenha) {
    return <TrocarSenhaObrigatoria email={email} />;
  }

  return (
    <main className={estilos.tela}>
      <div className={estilos.fundo} aria-hidden="true">
        <div className={estilos.grade} />
        <div className={estilos.contorno} />
      </div>

      <section className={estilos.painel}>
        <header className={estilos.cabecalho}>
          <h1 className={estilos.titulo}>Mapas Fácil</h1>
          <p className={estilos.subtitulo}>
            Diga o que você precisa e a IA monta o mapa do imóvel — PDF padrão IMAP, shapefiles e planilhas.
          </p>
        </header>

        <div className={estilos.abas} role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={aba === 'entrar'}
            className={aba === 'entrar' ? `${estilos.aba} ${estilos.abaAtiva}` : estilos.aba}
            onClick={() => {
              setAba('entrar');
              setErro(null);
            }}
          >
            Entrar
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={aba === 'criar'}
            className={aba === 'criar' ? `${estilos.aba} ${estilos.abaAtiva}` : estilos.aba}
            onClick={() => {
              setAba('criar');
              setErro(null);
            }}
          >
            Criar conta
          </button>
        </div>

        <form className={estilos.formulario} onSubmit={enviar} noValidate>
          {aba === 'criar' && (
            <div className={estilos.campo}>
              <label htmlFor="mf-nome">Nome</label>
              <input
                id="mf-nome"
                type="text"
                autoComplete="name"
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                required
              />
            </div>
          )}

          <div className={estilos.campo}>
            <label htmlFor="mf-email">E-mail</label>
            <input
              id="mf-email"
              type="email"
              autoComplete="email"
              inputMode="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className={estilos.campo}>
            <label htmlFor="mf-senha">Senha</label>
            <input
              id="mf-senha"
              type="password"
              aria-describedby={aba === 'criar' ? 'mf-dica-senha' : undefined}
              autoComplete={aba === 'entrar' ? 'current-password' : 'new-password'}
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              required
            />
            {aba === 'criar' && (
              <small
                id="mf-dica-senha"
                className={problemaDaSenha ? estilos.dicaErro : estilos.dica}
              >
                {problemaDaSenha ?? `Mínimo ${SENHA_MIN} caracteres, nada de sequência óbvia.`}
              </small>
            )}
          </div>

          {aba === 'criar' && (
            <div className={estilos.campo}>
              <label htmlFor="mf-repetir">Repetir a senha</label>
              <input
                id="mf-repetir"
                type="password"
                aria-describedby={senhasDiferentes ? 'mf-dica-repetir' : undefined}
                autoComplete="new-password"
                value={repetir}
                onChange={(e) => setRepetir(e.target.value)}
                required
              />
              {senhasDiferentes && (
                <small id="mf-dica-repetir" className={estilos.dicaErro}>
                  As senhas não conferem.
                </small>
              )}
            </div>
          )}

          {erro && (
            <div className={estilos.erro} role="alert">
              <strong>{erro.codigo}</strong>
              <span>{erro.texto}</span>
              {espera > 0 && <span className={estilos.espera}>Tente de novo em {espera}s</span>}
            </div>
          )}

          <button type="submit" className={estilos.botao} disabled={!podeEnviar}>
            {carregando ? 'Enviando…' : aba === 'entrar' ? 'Entrar' : 'Criar conta e entrar'}
          </button>
        </form>

        <p className={estilos.rodape}>
          Ainda não tem conta? O cadastro é aberto —{' '}
          <button
            type="button"
            className={estilos.link}
            onClick={() => {
              setAba(aba === 'entrar' ? 'criar' : 'entrar');
              setErro(null);
            }}
          >
            {aba === 'entrar' ? 'crie a sua' : 'entre com a sua'}
          </button>
          .
        </p>
      </section>
    </main>
  );
}

/**
 * Primeiro acesso de conta criada pela CLI do admin: troca de senha obrigatória.
 *
 * Não dá para pular: a senha temporária foi mostrada uma vez para o administrador, então
 * quem entrou com ela precisa definir a sua antes de usar o app.
 */
function TrocarSenhaObrigatoria({ email }: { email: string }) {
  const { trocarSenha, sair } = useSessao();
  const [atual, setAtual] = useState('');
  const [nova, setNova] = useState('');
  const [erro, setErro] = useState<string | null>(null);
  const problema = problemasSenha(nova);

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    setErro(null);
    try {
      await trocarSenha(atual, nova);
    } catch (e) {
      setErro(e instanceof ErroHttp ? e.texto : 'Não foi possível trocar a senha.');
    }
  }

  return (
    <main className={estilos.tela}>
      <section className={estilos.painel}>
        <header className={estilos.cabecalho}>
          <h1 className={estilos.titulo}>Defina sua senha</h1>
          <p className={estilos.subtitulo}>
            A conta {email || 'desta sessão'} foi criada pelo administrador. Escolha uma senha só sua
            para continuar.
          </p>
        </header>
        <form className={estilos.formulario} onSubmit={enviar}>
          <div className={estilos.campo}>
            <label htmlFor="mf-atual">Senha temporária</label>
            <input
              id="mf-atual"
              type="password"
              autoComplete="current-password"
              value={atual}
              onChange={(e) => setAtual(e.target.value)}
              required
            />
          </div>
          <div className={estilos.campo}>
            <label htmlFor="mf-nova">Nova senha</label>
            <input
              id="mf-nova"
              type="password"
              aria-describedby="mf-dica-nova"
              autoComplete="new-password"
              value={nova}
              onChange={(e) => setNova(e.target.value)}
              required
            />
            <small id="mf-dica-nova" className={problema ? estilos.dicaErro : estilos.dica}>
              {problema ?? `Mínimo ${SENHA_MIN} caracteres.`}
            </small>
          </div>
          {erro && (
            <div className={estilos.erro} role="alert">
              <span>{erro}</span>
            </div>
          )}
          <button type="submit" className={estilos.botao} disabled={!atual || !nova || Boolean(problema)}>
            Salvar e entrar
          </button>
          <button type="button" className={estilos.link} onClick={() => void sair()}>
            Sair
          </button>
        </form>
      </section>
    </main>
  );
}
