/**
 * Casca do app web — Fase 3.
 *
 * W0 entrega só o esqueleto: o shell de verdade (rotas, login, projetos, palco)
 * chega no W6. Não há spinner nem dado inventado aqui.
 */
export function App() {
  return (
    <main
      style={{
        display: "grid",
        placeItems: "center",
        minHeight: "100%",
        padding: "2rem",
      }}
    >
      <div style={{ maxWidth: "32rem", textAlign: "center" }}>
        <h1 style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>Mapas Fácil</h1>
        <p style={{ color: "#8b949e", lineHeight: 1.5 }}>
          O app web está sendo construído. A API responde em{" "}
          <code>/api/v1/saude</code> a partir do marco W3.
        </p>
      </div>
    </main>
  );
}
