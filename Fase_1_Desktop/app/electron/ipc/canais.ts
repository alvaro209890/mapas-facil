// Nomes dos canais IPC, num lugar só — o preload e o main importam daqui.
// Nenhum canal expõe segredo nem caminho absoluto do disco do usuário: o
// renderer fala com o núcleo só por método NDJSON (fronteira 1 de F1-01).
export const CANAL_CHAMAR = "nucleo:chamar";
export const CANAL_ESTADO = "nucleo:estado";
export const CANAL_REINICIAR = "nucleo:reiniciar";
export const CANAL_EVENTO = "nucleo:evt";
export const CANAL_PREFERENCIAS_LER = "preferencias:ler";
export const CANAL_PREFERENCIAS_GRAVAR = "preferencias:gravar";

// C7 — conectar pasta. O diálogo nativo é do processo main (só ele tem `dialog`),
// e é o main que chama `workspace.abrir`: assim o caminho escolhido não precisa
// passear pelo renderer para virar I/O. Projeto recente é reaberto **por índice**,
// nunca por caminho vindo da tela.
export const CANAL_WORKSPACE_CONECTAR = "workspace:conectar";
export const CANAL_WORKSPACE_RECENTES = "workspace:recentes";
export const CANAL_WORKSPACE_ABRIR_RECENTE = "workspace:abrir-recente";
