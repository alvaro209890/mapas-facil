// F6 / F1-17 — `barra-chats`: lista do histórico, busca e menu de contexto.
//
// O que esta barra **não** faz: enviar mensagem, chamar IA, mostrar spinner de
// coisa que não está acontecendo (AP-07). Estado vazio é honesto e diferencia os
// três casos que o usuário confunde: nunca conversou, o filtro escondeu tudo, ou o
// núcleo não respondeu.

import { MessageSquarePlus, RefreshCw } from "lucide-react";

import { EstadoVazio } from "../componentes/EstadoVazio.js";
import { BuscaChats } from "../componentes/BuscaChats.js";
import { ItemChat } from "../componentes/ItemChat.js";
import type { AcoesConversas, EstadoConversas } from "../estado/conversas.js";
import { agruparPorData } from "../estado/conversas.js";
import estilos from "./BarraChats.module.css";

export interface PropsBarraChats {
  estado: EstadoConversas & AcoesConversas;
  /** Nome da pasta conectada; `null` quando nenhuma está aberta. */
  pastaAberta: string | null;
  /** Contador que `Ctrl+F` incrementa para focar o campo de busca. */
  focoBusca: number;
}

export function BarraChats({ estado, pastaAberta, focoBusca }: PropsBarraChats) {
  const buscando = estado.resultados !== null;
  const grupos = agruparPorData(estado.lista);
  const abertaId = estado.aberta?.conversa.conversation_id ?? null;

  return (
    <div className={estilos.raiz}>
      <div className={estilos.acoes}>
        <button
          type="button"
          className={estilos.novo}
          onClick={() => void estado.criar()}
          title="Novo chat (Ctrl+N)"
        >
          <MessageSquarePlus size={14} aria-hidden="true" /> Novo chat
        </button>
        <button
          type="button"
          className={estilos.iconeAcao}
          onClick={() => void estado.recarregar()}
          aria-label="recarregar histórico"
        >
          <RefreshCw size={13} aria-hidden="true" />
        </button>
      </div>

      <BuscaChats
        termo={estado.termo}
        resultados={estado.resultados}
        foco={focoBusca}
        aoDigitar={(termo) => void estado.buscar(termo)}
        aoLimpar={estado.limparBusca}
        aoEscolher={(conversationId, seq) => void estado.abrir(conversationId, seq)}
      />

      {!buscando && (
        <div className={estilos.filtros}>
          <button
            type="button"
            data-ativo={estado.soDestaPasta || undefined}
            aria-pressed={estado.soDestaPasta}
            disabled={pastaAberta === null}
            title={
              pastaAberta === null ? "Conecte uma pasta para filtrar por ela" : undefined
            }
            onClick={estado.alternarSoDestaPasta}
          >
            {estado.soDestaPasta ? "Só desta pasta" : "Todos os chats"}
          </button>
          <button
            type="button"
            data-ativo={estado.incluirArquivadas || undefined}
            aria-pressed={estado.incluirArquivadas}
            onClick={estado.alternarArquivadas}
          >
            Arquivadas
          </button>
        </div>
      )}

      {!buscando && estado.situacao === "erro" && (
        <EstadoVazio
          tom="erro"
          codigo={estado.erro?.codigo ?? "UI-001"}
          titulo="Não foi possível ler o histórico"
          descricao={
            estado.erro?.mensagem ??
            "O núcleo não respondeu ao listar as conversas guardadas neste PC."
          }
          saidas={[
            "Reinicie o núcleo pelo banner do topo",
            "Confira o diagnóstico do ambiente (F1)",
          ]}
          acoes={[
            { rotulo: "tentar de novo", aoAcionar: () => void estado.recarregar(), primaria: true },
          ]}
        />
      )}

      {!buscando && estado.situacao === "pronta" && estado.lista.length === 0 && (
        <EstadoVazio
          titulo={
            estado.soDestaPasta || estado.incluirArquivadas
              ? "Nada com este filtro"
              : "Nenhuma conversa ainda"
          }
          descricao={
            estado.soDestaPasta
              ? "Esta pasta ainda não tem conversa. Tire o filtro para ver as de outras pastas."
              : "O histórico fica só neste PC (D20). Comece uma conversa para ela aparecer aqui."
          }
          acoes={[{ rotulo: "novo chat", aoAcionar: () => void estado.criar(), primaria: true }]}
        />
      )}

      {!buscando && estado.lista.length > 0 && (
        <div className={estilos.lista}>
          {grupos.map(({ grupo, itens }) => (
            <section key={grupo} className={estilos.grupo}>
              <h3 className={estilos.tituloGrupo}>{grupo}</h3>
              <ul>
                {itens.map((conversa) => (
                  <ItemChat
                    key={conversa.conversation_id}
                    conversa={conversa}
                    ativa={conversa.conversation_id === abertaId}
                    pastaAberta={pastaAberta}
                    aoAbrir={() => void estado.abrir(conversa.conversation_id)}
                    aoRenomear={(title) => void estado.renomear(conversa.conversation_id, title)}
                    aoArquivar={(arquivada) =>
                      void estado.arquivar(conversa.conversation_id, arquivada)
                    }
                    aoRamificar={() =>
                      void estado.ramificar(conversa.conversation_id, conversa.mensagens_total)
                    }
                    aoApagar={() => void estado.apagar(conversa.conversation_id)}
                  />
                ))}
              </ul>
            </section>
          ))}
          {estado.temMais && (
            <button
              type="button"
              className={estilos.maisAntigas}
              onClick={() => void estado.carregarMais()}
            >
              Carregar conversas mais antigas
            </button>
          )}
        </div>
      )}
    </div>
  );
}
