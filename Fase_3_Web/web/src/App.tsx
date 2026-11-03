/**
 * Casca do app web — rotas do W-06.
 *
 * | URL | Tela | Sessão |
 * |---|---|---|
 * | `/entrar` | Entrar | não |
 * | `/` | redireciona para `/projetos` | sim |
 * | `/projetos` | lista | sim |
 * | `/projetos/novo` | assistente | sim |
 * | `/projetos/:id` | projeto (chat + palco) | sim |
 * | `/projetos/:id/versoes/:n` | projeto na versão `n` | sim |
 * | `/conta` | conta | sim |
 * | `/admin` | admin | papel admin |
 *
 * Sem sessão → `/entrar?volta=<url>`. A sessão é perguntada **uma vez** no boot
 * (`GET /auth/eu`); enquanto não se sabe, a tela não pisca login nem projeto.
 */

import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import { useSessao } from "./estado/sessao";
import { EmBreve } from "./telas/EmBreve";
import { Entrar } from "./telas/Entrar";
import { Projetos } from "./telas/Projetos";

function Carregando() {
  return (
    <main
      style={{
        display: "grid",
        placeItems: "center",
        minHeight: "100vh",
        color: "var(--mf-texto-3)",
        fontSize: "0.875rem",
      }}
    >
      Carregando…
    </main>
  );
}

/** Guarda de sessão: mantém a URL para voltar depois do login. */
function Protegido({ children }: { children: React.ReactNode }) {
  const estado = useSessao((s) => s.estado);
  const local = useLocation();
  if (estado === "desconhecida") return <Carregando />;
  if (estado === "expirada") {
    const volta = `${local.pathname}${local.search}`;
    return <Navigate to={`/entrar?volta=${encodeURIComponent(volta)}`} replace />;
  }
  return <>{children}</>;
}

/** Só admin: papel conferido no dado do servidor, nunca no localStorage. */
function SoAdmin({ children }: { children: React.ReactNode }) {
  const usuario = useSessao((s) => s.usuario);
  if (usuario?.papel !== "admin") return <Navigate to="/projetos" replace />;
  return <>{children}</>;
}

/** Destino depois do login: só caminho interno (`volta=//evil.com` viraria redirect aberto). */
export function depoisDoLogin(busca: string): string {
  const volta = new URLSearchParams(busca).get("volta");
  if (!volta || !volta.startsWith("/") || volta.startsWith("//")) return "/projetos";
  return volta;
}

function TelaEntrar() {
  const navegar = useNavigate();
  const local = useLocation();
  return <Entrar aoEntrar={() => navegar(depoisDoLogin(local.search), { replace: true })} />;
}

function Rotas() {
  const estado = useSessao((s) => s.estado);
  const carregar = useSessao((s) => s.carregar);

  useEffect(() => {
    if (estado === "desconhecida") void carregar();
  }, [estado, carregar]);

  return (
    <Routes>
      <Route path="/entrar" element={<TelaEntrar />} />
      <Route path="/" element={<Navigate to="/projetos" replace />} />
      <Route
        path="/projetos"
        element={
          <Protegido>
            <Projetos />
          </Protegido>
        }
      />
      <Route
        path="/projetos/novo"
        element={
          <Protegido>
            <EmBreve titulo="Novo mapa" marco="W6-06" />
          </Protegido>
        }
      />
      <Route
        path="/projetos/:id"
        element={
          <Protegido>
            <EmBreve titulo="Projeto" marco="W6-07" />
          </Protegido>
        }
      />
      <Route
        path="/projetos/:id/versoes/:numero"
        element={
          <Protegido>
            <EmBreve titulo="Projeto" marco="W6-07" />
          </Protegido>
        }
      />
      <Route
        path="/conta"
        element={
          <Protegido>
            <EmBreve titulo="Conta" marco="W6-08" />
          </Protegido>
        }
      />
      <Route
        path="/admin"
        element={
          <Protegido>
            <SoAdmin>
              <EmBreve titulo="Administração" marco="W6-08" />
            </SoAdmin>
          </Protegido>
        }
      />
      <Route path="*" element={<Navigate to="/entrar" replace />} />
    </Routes>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <Rotas />
    </BrowserRouter>
  );
}
