// `tela-login` — criar conta ou entrar com e-mail + senha locais (F1-14 / M5).
// Sem Google. Dados só neste PC.

import { type FormEvent, useState } from "react";

import {
  criarConta,
  entrarConta,
  useAuth,
  type SnapshotAuth,
} from "../estado/auth.js";
import { CenaMapaLogin } from "./CenaMapaLogin.js";
import estilos from "./Login.module.css";

type Modo = "entrar" | "criar";

export interface PropsLogin {
  onConectado?: (snap: SnapshotAuth) => void;
}

export function Login({ onConectado }: PropsLogin) {
  const auth = useAuth();
  const [modo, setModo] = useState<Modo>("criar");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [nome, setNome] = useState("");
  const [lembrar, setLembrar] = useState(true);
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    setEnviando(true);
    try {
      const snap =
        modo === "criar"
          ? await criarConta({ email, senha, nome: nome.trim() || undefined })
          : await entrarConta({ email, senha, lembrar_neste_pc: lembrar });
      if (snap.estado === "conectado") onConectado?.(snap);
    } finally {
      setEnviando(false);
    }
  }

  const ocupado = enviando || auth.estado === "conectando";

  return (
    <main id="tela-login" className={estilos.tela} aria-label="entrar no Mapas Fácil">
      <CenaMapaLogin />

      <div className={estilos.cartao}>
        <span className={estilos.selo}>Mapas Fácil · desktop</span>
        <h1 className={estilos.marca}>
          Do shapefile ao mapa
          <em>sem abrir o ArcMap na mão.</em>
        </h1>
        <p className={estilos.nota}>
          Acesso completo, sem limites · conta e dados ficam só neste PC
        </p>

        <div className={estilos.abas} role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={modo === "criar"}
            className={estilos.aba}
            data-ativa={modo === "criar" ? "sim" : "nao"}
            onClick={() => setModo("criar")}
          >
            Criar conta
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={modo === "entrar"}
            className={estilos.aba}
            data-ativa={modo === "entrar" ? "sim" : "nao"}
            onClick={() => setModo("entrar")}
          >
            Entrar
          </button>
        </div>

        <form className={estilos.form} onSubmit={(e) => void enviar(e)}>
          {modo === "criar" && (
            <label className={estilos.campo}>
              <span>Nome (opcional)</span>
              <input
                type="text"
                autoComplete="name"
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                disabled={ocupado}
              />
            </label>
          )}
          <label className={estilos.campo}>
            <span>E-mail</span>
            <input
              name="email"
              type="email"
              required
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={ocupado}
            />
          </label>
          <label className={estilos.campo}>
            <span>Senha</span>
            <input
              name="senha"
              type="password"
              required
              minLength={8}
              autoComplete={modo === "criar" ? "new-password" : "current-password"}
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              disabled={ocupado}
            />
          </label>
          {modo === "entrar" && (
            <label className={estilos.check}>
              <input
                type="checkbox"
                checked={lembrar}
                onChange={(e) => setLembrar(e.target.checked)}
                disabled={ocupado}
              />
              Lembrar neste PC
            </label>
          )}

          {auth.erro && (
            <p className={estilos.erro} role="alert">
              <span className={estilos.codigo}>{auth.erro.codigo}</span> {auth.erro.mensagem}
            </p>
          )}

          <button type="submit" className={estilos.primario} disabled={ocupado}>
            {ocupado ? "Aguarde…" : modo === "criar" ? "Criar e entrar" : "Entrar"}
          </button>
        </form>

        <p className={estilos.rodape}>
          Sem nuvem, sem mensalidade. Os mapas e as conversas ficam neste
          computador.
        </p>
      </div>
    </main>
  );
}
