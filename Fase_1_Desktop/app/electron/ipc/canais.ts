// Nomes dos canais IPC, num lugar só — o preload e o main importam daqui.
// Nenhum canal expõe segredo nem caminho absoluto do disco do usuário: o
// renderer fala com o núcleo só por método NDJSON (fronteira 1 de F1-01).
export const CANAL_CHAMAR = "nucleo:chamar";
export const CANAL_ESTADO = "nucleo:estado";
// Pull do estado atual. O push de `CANAL_ESTADO` acontece em `did-finish-load`,
// que é **antes** de o React assinar no `useEffect` — sozinho ele se perde e a
// tela fica presa em "núcleo iniciando" (e a guarda de login nunca roda).
export const CANAL_ESTADO_ATUAL = "nucleo:estado-atual";
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

// Auto-update (F1-11 P2). O main empurra o estado por `CANAL_ATUALIZACAO` e o
// renderer pede as ações — nada baixa nem instala sem clique do usuário.
export const CANAL_ATUALIZACAO = "atualizacao:estado";
export const CANAL_ATUALIZACAO_ATUAL = "atualizacao:estado-atual";
export const CANAL_ATUALIZACAO_BAIXAR = "atualizacao:baixar";
export const CANAL_ATUALIZACAO_INSTALAR = "atualizacao:instalar";

// Menu nativo e tray (main) → renderer. Carrega só o **id do comando** já
// existente na paleta `Ctrl+K`, para menu e paleta nunca divergirem de
// comportamento. Nenhum dado do disco trafega por aqui.
export const CANAL_COMANDO_MENU = "menu:comando";
