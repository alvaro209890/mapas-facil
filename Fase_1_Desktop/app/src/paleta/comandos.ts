// Catálogo da paleta `Ctrl+K` (F1-02 §Acessibilidade e atalhos).
//
// Comandos cujo marco ainda não existe ficam listados, mas `disponivel: false` —
// a paleta explica o porquê em vez de fingir que a ação rodou.

export type IdComando =
  | "conectar-pasta"
  | "reindexar-pasta"
  | "verificar-ambiente"
  | "preferencias"
  | "alternar-tema"
  | "gerar-mapa-serie"
  | "nova-conversa"
  | "buscar-chats";

export type GrupoComando = "pasta" | "ambiente" | "aparencia" | "conversas" | "em-breve";

export interface Comando {
  id: IdComando;
  grupo: GrupoComando;
  rotulo: string;
  descricao: string;
  /** Atalho mostrado à direita; a captura real fica em `useAtalhosGlobais`. */
  atalho?: string;
  disponivel: boolean;
  /** Por que o comando ainda não age — só quando `disponivel` é false. */
  motivo?: string;
}

export interface ContextoComandos {
  temPasta: boolean;
}

const ROTULO_GRUPO: Record<GrupoComando, string> = {
  pasta: "Pasta",
  ambiente: "Ambiente",
  aparencia: "Aparência",
  conversas: "Conversas",
  "em-breve": "Em breve",
};

export function rotuloDoGrupo(grupo: GrupoComando): string {
  return ROTULO_GRUPO[grupo];
}

/** Monta a lista na ordem em que a paleta mostra. */
export function listarComandos(contexto: ContextoComandos): Comando[] {
  return [
    {
      id: "conectar-pasta",
      grupo: "pasta",
      rotulo: "Conectar pasta",
      descricao: "Abre o diálogo nativo e indexa a pasta no núcleo",
      atalho: "Ctrl+O",
      disponivel: true,
    },
    {
      id: "reindexar-pasta",
      grupo: "pasta",
      rotulo: "Reindexar pasta",
      descricao: "Varre de novo a pasta já conectada (sem watcher ainda)",
      disponivel: contexto.temPasta,
      motivo: contexto.temPasta ? undefined : "Conecte uma pasta antes",
    },
    {
      id: "verificar-ambiente",
      grupo: "ambiente",
      rotulo: "Verificar ambiente (doctor)",
      descricao: "Roda doctor.rodar e abre o diagnóstico no painel da pasta",
      atalho: "F1",
      disponivel: true,
    },
    {
      id: "preferencias",
      grupo: "aparencia",
      rotulo: "Preferências",
      descricao: "Tema escuro/claro e opções locais (sem segredo)",
      atalho: "Ctrl+,",
      disponivel: true,
    },
    {
      id: "alternar-tema",
      grupo: "aparencia",
      rotulo: "Alternar tema escuro/claro",
      descricao: "Escuro continua sendo o default do produto (D15)",
      disponivel: true,
    },
    {
      id: "gerar-mapa-serie",
      grupo: "pasta",
      rotulo: "Gerar mapa da série",
      descricao: "Abre a galeria de modelos no painel direito",
      disponivel: true,
    },
    {
      id: "nova-conversa",
      grupo: "conversas",
      rotulo: "Nova conversa",
      descricao: "Cria um chat vazio na barra de conversas (histórico local, M6)",
      atalho: "Ctrl+N",
      disponivel: true,
    },
    {
      id: "buscar-chats",
      grupo: "conversas",
      rotulo: "Buscar nas conversas",
      descricao: "Foca a busca do histórico local (FTS5, sem acento importar)",
      atalho: "Ctrl+F",
      disponivel: true,
    },
  ];
}

export function filtrarComandos(comandos: Comando[], consulta: string): Comando[] {
  const termo = consulta.trim().toLocaleLowerCase("pt-BR");
  if (termo.length === 0) return comandos;
  return comandos.filter((comando) => {
    const haystack = `${comando.rotulo} ${comando.descricao} ${comando.atalho ?? ""}`.toLocaleLowerCase(
      "pt-BR",
    );
    return haystack.includes(termo);
  });
}
