/**
 * Administração (W6-08) — usuários, auditoria e saúde.
 *
 * Só aparece para `papel === "admin"`, e o papel vem do **servidor** (`/auth/eu`), nunca de
 * `localStorage`. A senha temporária de um usuário novo aparece **uma vez**, em vermelho, com
 * botão de copiar: depois disso o servidor não devolve mais.
 */

import { useEffect, useState } from 'react';

import { api, ErroHttp } from '../api/cliente';
import type { Usuario } from '../api/tipos';
import { tempoRelativo } from '../utilitarios/tempo';
import estilos from './Admin.module.css';

interface EventoAuditoria {
  id: number | string;
  acao: string;
  usuario_id: string | null;
  alvo: string | null;
  criada_em: string;
}

interface Saude {
  workers: { workers?: number; ociosos?: number; projetos?: string[] };
  vagas_livres: number | null;
  disco_livre_gb: number | null;
  schema: number;
  nucleo: string | null;
}

export function Admin() {
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [auditoria, setAuditoria] = useState<EventoAuditoria[]>([]);
  const [saude, setSaude] = useState<Saude | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<{ email: string; senha: string } | null>(null);
  const [form, setForm] = useState({ nome: '', email: '', papel: 'usuario' });

  async function recarregar() {
    setErro(null);
    try {
      const [lista, aud, s] = await Promise.all([
        api.get<{ itens: Usuario[] }>('/admin/usuarios'),
        api.get<{ itens: EventoAuditoria[] }>('/admin/auditoria?limite=30').catch(() => ({ itens: [] })),
        api.get<Saude>('/admin/saude').catch(() => null),
      ]);
      setUsuarios(lista.itens);
      setAuditoria(aud.itens);
      setSaude(s);
    } catch (e) {
      setErro(e instanceof ErroHttp ? `${e.codigo}: ${e.texto}` : 'Não foi possível carregar.');
    }
  }

  useEffect(() => {
    void recarregar();
  }, []);

  async function criar(evento: React.FormEvent) {
    evento.preventDefault();
    setErro(null);
    try {
      const criado = await api.post<{ usuario: Usuario; senha_temporaria: string }>(
        '/admin/usuarios',
        { nome: form.nome.trim(), email: form.email.trim(), papel: form.papel },
      );
      setAviso({ email: criado.usuario.email, senha: criado.senha_temporaria });
      setForm({ nome: '', email: '', papel: 'usuario' });
      await recarregar();
    } catch (e) {
      setErro(e instanceof ErroHttp ? `${e.codigo}: ${e.texto}` : 'Não foi possível criar a conta.');
    }
  }

  async function alternar(usuario: Usuario) {
    setErro(null);
    try {
      await api.patch(`/admin/usuarios/${usuario.id}`, { ativo: usuario.bloqueado ?? false });
      await recarregar();
    } catch (e) {
      setErro(e instanceof ErroHttp ? `${e.codigo}: ${e.texto}` : 'Não foi possível alterar a conta.');
    }
  }

  async function redefinir(usuario: Usuario) {
    setErro(null);
    try {
      const resposta = await api.patch<{ senha_temporaria?: string }>(
        `/admin/usuarios/${usuario.id}`,
        { redefinir_senha: true },
      );
      if (resposta.senha_temporaria) {
        setAviso({ email: usuario.email, senha: resposta.senha_temporaria });
      }
      await recarregar();
    } catch (e) {
      setErro(e instanceof ErroHttp ? `${e.codigo}: ${e.texto}` : 'Não foi possível redefinir.');
    }
  }

  return (
    <main className={estilos.tela}>
      <header className={estilos.cabecalho}>
        <div>
          <h1 className={estilos.titulo}>Administração</h1>
          <p className={estilos.subtitulo}>
            Contas, auditoria e saúde do servidor. Só o administrador vê esta tela.
          </p>
        </div>
      </header>

      {erro && (
        <div className={estilos.erro} role="alert">
          {erro}
        </div>
      )}

      {aviso && (
        <div className={estilos.destaque} role="status">
          <p>
            Senha temporária de <strong>{aviso.email}</strong> — aparece uma vez só:
          </p>
          <code className={estilos.senha}>{aviso.senha}</code>
          <button type="button" className={estilos.secundario} onClick={() => setAviso(null)}>
            Já anotei
          </button>
        </div>
      )}

      {saude && (
        <section className={estilos.cartoes}>
          <article className={estilos.cartao}>
            <span className={estilos.rotulo}>Disco livre</span>
            <strong>{saude.disco_livre_gb ?? '—'} GB</strong>
          </article>
          <article className={estilos.cartao}>
            <span className={estilos.rotulo}>Workers</span>
            <strong>{saude.workers?.workers ?? 0}</strong>
          </article>
          <article className={estilos.cartao}>
            <span className={estilos.rotulo}>Vagas livres</span>
            <strong>{saude.vagas_livres ?? 'sem limite'}</strong>
          </article>
          <article className={estilos.cartao}>
            <span className={estilos.rotulo}>Schema</span>
            <strong>v{saude.schema}</strong>
          </article>
        </section>
      )}

      <section className={estilos.bloco}>
        <h2>Nova conta</h2>
        <form className={estilos.formulario} onSubmit={criar}>
          <label htmlFor="mf-admin-nome">Nome</label>
          <input
            id="mf-admin-nome"
            value={form.nome}
            onChange={(e) => setForm({ ...form, nome: e.target.value })}
            required
          />
          <label htmlFor="mf-admin-email">E-mail</label>
          <input
            id="mf-admin-email"
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            required
          />
          <label htmlFor="mf-admin-papel">Papel</label>
          <select
            id="mf-admin-papel"
            value={form.papel}
            onChange={(e) => setForm({ ...form, papel: e.target.value })}
          >
            <option value="usuario">usuário</option>
            <option value="admin">administrador</option>
          </select>
          <button type="submit" className={estilos.principal}>
            Criar conta e gerar senha
          </button>
        </form>
      </section>

      <section className={estilos.bloco}>
        <h2>Contas ({usuarios.length})</h2>
        <table className={estilos.tabela}>
          <thead>
            <tr>
              <th>Nome</th>
              <th>E-mail</th>
              <th>Papel</th>
              <th>Situação</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {usuarios.map((u) => (
              <tr key={u.id}>
                <td>{u.nome}</td>
                <td className={estilos.mono}>{u.email}</td>
                <td>{u.papel}</td>
                <td className={u.bloqueado ? estilos.ruim : estilos.ok}>
                  {u.bloqueado ? 'bloqueada' : 'ativa'}
                </td>
                <td className={estilos.acoes}>
                  <button type="button" onClick={() => void alternar(u)}>
                    {u.bloqueado ? 'desbloquear' : 'bloquear'}
                  </button>
                  <button type="button" onClick={() => void redefinir(u)}>
                    nova senha
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className={estilos.bloco}>
        <h2>Auditoria recente</h2>
        {auditoria.length === 0 ? (
          <p className={estilos.dica}>Nada registrado ainda.</p>
        ) : (
          <ul className={estilos.auditoria}>
            {auditoria.map((evento) => (
              <li key={evento.id}>
                <span className={estilos.mono}>{evento.acao}</span>
                <span className={estilos.dica}>{tempoRelativo(evento.criada_em)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
