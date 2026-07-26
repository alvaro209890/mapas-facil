// C5 — `AppShell`: os quatro painéis de F1-02, redimensionáveis, com as larguras
// persistidas em `config.json` pelo IPC de preferências.
//
// C10: paleta `Ctrl+K`, atalhos globais e preferências de tema. O `painel-workspace`
// é real (C7); doctor no rodapé (C8). `barra-chats` (M6) e `painel-chat` (M7) são reais;
// preview em construção ainda espera M8.

import { useCallback, useState, type ReactNode } from "react";
import { Map as MapaIcone, PanelLeftClose, PanelLeftOpen } from "lucide-react";

import { AvisoAtalho } from "../componentes/AvisoAtalho.js";
import { BarraProgressoJob } from "../componentes/BarraProgressoJob.js";
import { DoctorResumoPuro } from "../componentes/DoctorResumo.js";
import { EstadoVazio, SemArcMap, SemChaveDeepSeek } from "../componentes/EstadoVazio.js";
import { LinhaVersoes } from "../componentes/LinhaVersoes.js";
import { Preferencias, alternarTema } from "../componentes/Preferencias.js";
import { useAuth, sairConta } from "../estado/auth.js";
import { useConversas } from "../estado/conversas.js";
import { useDoctor } from "../estado/doctor.js";
import { useGaleria } from "../estado/galeria.js";
import { useMapspecVersoes } from "../estado/mapspecVersoes.js";
import type { PainelLateral } from "../estado/preferencias.js";
import { usePaineis } from "../estado/preferencias.js";
import type { EstadoNucleo } from "../estado/ponte.js";
import { api } from "../estado/ponte.js";
import { useProgressoJob } from "../estado/progressoJob.js";
import { nomeDoProjeto, useWorkspace } from "../estado/workspace.js";
import { BarraChats } from "../paineis/BarraChats.js";
import { Galeria } from "../paineis/Galeria.js";
import { GaleriaDetalhe } from "../paineis/GaleriaDetalhe.js";
import { PainelChat } from "../paineis/PainelChat.js";
import { Preview } from "../paineis/Preview.js";
import { Workspace } from "../paineis/Workspace.js";
import type { IdComando } from "../paleta/comandos.js";
import { PaletaComandos } from "../paleta/PaletaComandos.js";
import { useAtalhosGlobais } from "../paleta/useAtalhosGlobais.js";
import { Divisor } from "./Divisor.js";
import { TopoApp } from "./TopoApp.js";
import estilos from "./AppShell.module.css";

export interface PropsAppShell {
  nucleo: EstadoNucleo;
  /** Banner de `UI-001` e afins, renderizado entre o topo e os painéis. */
  banner?: ReactNode;
}

interface PropsPainel {
  id: string;
  titulo: string;
  largura?: number;
  className?: string;
  aoColapsar?: () => void;
  children: ReactNode;
}

function Painel({ id, titulo, largura, className, aoColapsar, children }: PropsPainel) {
  const classe = className === undefined ? estilos.painel : `${estilos.painel} ${className}`;
  return (
    <section
      id={id}
      className={classe}
      aria-label={titulo}
      style={largura === undefined ? undefined : { flex: `0 0 ${largura}px`, width: largura }}
    >
      <div className={estilos.cabecalho}>
        <span className={estilos.titulo}>{titulo}</span>
        {aoColapsar !== undefined && (
          <button
            type="button"
            className={estilos.botaoColapso}
            onClick={aoColapsar}
            aria-label={`colapsar ${titulo}`}
          >
            <PanelLeftClose size={14} aria-hidden="true" />
          </button>
        )}
      </div>
      <div className={estilos.conteudo}>{children}</div>
    </section>
  );
}

function Trilho({ titulo, aoAbrir }: { titulo: string; aoAbrir: () => void }) {
  return (
    <button type="button" className={estilos.trilho} onClick={aoAbrir} aria-label={`abrir ${titulo}`}>
      <PanelLeftOpen size={16} aria-hidden="true" />
    </button>
  );
}

function focarDoctor(): void {
  const doctor = document.getElementById("doctor-resumo");
  if (doctor instanceof HTMLDetailsElement) doctor.open = true;
  if (doctor !== null && typeof doctor.scrollIntoView === "function") {
    doctor.scrollIntoView({ block: "nearest" });
  }
}

export function AppShell({ nucleo, banner }: PropsAppShell) {
  const { paineis, definirLargura, alternarColapso, gravar } = usePaineis();
  const { larguras, colapsados } = paineis;
  const workspace = useWorkspace();
  const doctor = useDoctor();
  const auth = useAuth();
  const galeria = useGaleria();
  const conversas = useConversas(workspace.indice?.raiz ?? null);
  const progressoJob = useProgressoJob();
  const mapspecVersoes = useMapspecVersoes();
  const [montando, setMontando] = useState(false);
  const [paletaAberta, setPaletaAberta] = useState(false);
  const [preferenciasAbertas, setPreferenciasAbertas] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const [focoGaleria, setFocoGaleria] = useState(0);
  const [abaDireita, setAbaDireita] = useState<"preview" | "galeria">("galeria");

  const abrirPaleta = useCallback(() => setPaletaAberta(true), []);
  const fecharPaleta = useCallback(() => setPaletaAberta(false), []);
  const abrirPreferencias = useCallback(() => setPreferenciasAbertas(true), []);
  const fecharPreferencias = useCallback(() => setPreferenciasAbertas(false), []);
  const limparAviso = useCallback(() => setAviso(null), []);

  const focarBuscaChats = useCallback(() => {
    if (colapsados.barraChats) alternarColapso("barraChats");
    requestAnimationFrame(() => {
      document.getElementById("busca-chats")?.focus();
    });
  }, [alternarColapso, colapsados.barraChats]);

  const verificarAmbiente = useCallback(() => {
    void doctor.rodar().then(() => focarDoctor());
  }, [doctor.rodar]);

  const executarComando = useCallback(
    (id: IdComando) => {
      switch (id) {
        case "conectar-pasta":
          void workspace.conectar();
          break;
        case "reindexar-pasta":
          void workspace.reindexar();
          break;
        case "verificar-ambiente":
          verificarAmbiente();
          break;
        case "preferencias":
          setPreferenciasAbertas(true);
          break;
        case "alternar-tema":
          void alternarTema();
          break;
        case "gerar-mapa-serie":
          setFocoGaleria((n) => n + 1);
          document.getElementById("painel-galeria")?.scrollIntoView({ block: "nearest" });
          break;
        case "nova-conversa":
          void conversas.criar();
          break;
        case "buscar-chats":
          focarBuscaChats();
          break;
        default:
          break;
      }
    },
    [conversas, focarBuscaChats, verificarAmbiente, workspace],
  );

  useAtalhosGlobais({
    abrirPaleta,
    fecharPaleta,
    paletaAberta,
    preferenciasAbertas,
    fecharPreferencias,
    conectarPasta: () => void workspace.conectar(),
    verificarAmbiente,
    abrirPreferencias,
    novaConversa: () => void conversas.criar(),
    focarBuscaChats,
    aoIndisponivel: setAviso,
  });

  // Informativos que o doctor sustenta com dado real; sem relatório, nada aparece.
  const semChaveIa = doctor.relatorio !== null && !doctor.relatorio.chaves.deepseek;
  const semArcMap = doctor.relatorio !== null && !doctor.relatorio.arcmap.encontrado;

  const divisor = (painel: PainelLateral, rotulo: string, invertido = false) => (
    <Divisor
      painel={painel}
      rotulo={rotulo}
      largura={larguras[painel]}
      invertido={invertido}
      aoRedimensionar={(largura) => definirLargura(painel, largura)}
      aoSoltar={gravar}
    />
  );

  return (
    <div className={estilos.shell}>
      <TopoApp
        nucleo={nucleo.estado}
        projeto={nomeDoProjeto(workspace.indice)}
        contaEmail={auth.conta?.email}
        aoSair={() => void sairConta(false)}
        aoAbrirPaleta={abrirPaleta}
        aoAbrirDoctor={verificarAmbiente}
      />
      {banner}
      <div className={estilos.corpo}>
        {colapsados.barraChats ? (
          <Trilho titulo="conversas" aoAbrir={() => alternarColapso("barraChats")} />
        ) : (
          <>
            <Painel
              id="barra-chats"
              titulo="conversas"
              largura={larguras.barraChats}
              aoColapsar={() => alternarColapso("barraChats")}
            >
              <BarraChats
                situacao={conversas.situacao}
                conversas={conversas.conversas}
                busca={conversas.busca}
                resultadosBusca={conversas.resultadosBusca}
                filtrarPastaAtual={conversas.filtrarPastaAtual}
                conversaAtiva={conversas.conversaAtiva}
                workspaceNome={nomeDoProjeto(workspace.indice) ?? null}
                erro={conversas.erro}
                aoCriar={() => void conversas.criar()}
                aoBuscar={(termo) => void conversas.buscar(termo)}
                aoSelecionar={conversas.selecionar}
                aoAlternarFiltro={conversas.alternarFiltroPasta}
                aoApagar={(id) => void conversas.apagar(id)}
              />
            </Painel>
            {divisor("barraChats", "conversas")}
          </>
        )}

        {colapsados.workspace ? (
          <Trilho titulo="pasta do projeto" aoAbrir={() => alternarColapso("workspace")} />
        ) : (
          <>
            <Painel
              id="painel-workspace"
              titulo="pasta do projeto"
              largura={larguras.workspace}
              aoColapsar={() => alternarColapso("workspace")}
            >
              <Workspace
                estado={workspace}
                aoConectar={() => void workspace.conectar()}
                aoAbrirRecente={(indice) => void workspace.abrirRecente(indice)}
                aoReindexar={() => void workspace.reindexar()}
                rodape={
                  <DoctorResumoPuro estado={doctor} aoRodar={() => void doctor.rodar()} />
                }
              />
            </Painel>
            {divisor("workspace", "pasta do projeto")}
          </>
        )}

        <section
          id="painel-chat"
          className={`${estilos.painel} ${estilos.painelChat}`}
          aria-label="conversa"
        >
          <PainelChat
            conversationId={conversas.conversaAtiva}
            semChaveIa={semChaveIa}
            bannerChave={semChaveIa ? <SemChaveDeepSeek /> : null}
            bannerArc={semArcMap ? <SemArcMap motor={doctor.relatorio?.motor_preferido ?? "nativo"} /> : null}
          />
          <div className={estilos.rodapeChat}>
            <BarraProgressoJob
              ativo={progressoJob !== null}
              onCancelar={
                progressoJob !== null
                  ? () => {
                      void api()?.chamar("mapa.cancelar", {
                        ...(progressoJob.jobId !== undefined
                          ? { job_id: progressoJob.jobId }
                          : {}),
                      });
                    }
                  : undefined
              }
            />
          </div>
        </section>

        {divisor("painelDireito", "preview e artefatos", true)}
        <Painel
          id="painel-direito"
          titulo="galeria e artefatos"
          largura={larguras.painelDireito}
          className={estilos.painelDireito}
        >
          {/* focoGaleria força relistar quando a paleta pede "gerar mapa da série" */}
          <span hidden data-foco-galeria={focoGaleria} />
          <div className={estilos.abas} role="tablist" aria-label="painel direito">
            {(["preview", "galeria"] as const).map((aba) => (
              <button
                key={aba}
                type="button"
                role="tab"
                id={`aba-${aba}`}
                className={estilos.aba}
                aria-selected={abaDireita === aba}
                onClick={() => setAbaDireita(aba)}
              >
                {aba}
              </button>
            ))}
          </div>
          {abaDireita === "preview" ? (
            <>
              <Preview mapspec={galeria.mapspecMontado} />
              <LinhaVersoes
                versoes={mapspecVersoes.estado.versoes}
                indiceExibido={mapspecVersoes.estado.indiceExibido}
                aoNavegar={mapspecVersoes.navegar}
                aoIrPara={mapspecVersoes.irPara}
              />
            </>
          ) : galeria.detalhe !== null ? (
            <GaleriaDetalhe
              detalhe={galeria.detalhe}
              mapspec={galeria.mapspecMontado}
              avisos={galeria.avisosMontagem}
              erro={galeria.erro}
              montando={montando}
              aoVoltar={galeria.limparDetalhe}
              aoMontar={() => {
                setMontando(true);
                void galeria.montar(galeria.detalhe!.id).finally(() => setMontando(false));
              }}
            />
          ) : (
            <Galeria
              modelos={galeria.modelos}
              situacao={galeria.situacao}
              erro={galeria.erro}
              aoAbrir={(id) => void galeria.detalhar(id)}
              selecionado={null}
            />
          )}
          {abaDireita === "galeria" &&
            galeria.detalhe === null &&
            galeria.situacao === "pronta" &&
            galeria.modelos.length === 0 && (
              <EstadoVazio
                titulo="Sem mapa gerado"
                descricao="Monte um modelo para o preview acompanhar a geração etapa a etapa."
                icone={<MapaIcone size={18} aria-hidden="true" />}
              />
            )}
        </Painel>
      </div>

      <PaletaComandos
        aberta={paletaAberta}
        temPasta={workspace.indice !== null}
        aoFechar={fecharPaleta}
        aoExecutar={executarComando}
      />
      <Preferencias aberta={preferenciasAbertas} aoFechar={fecharPreferencias} />
      <AvisoAtalho mensagem={aviso} aoFechar={limparAviso} />
    </div>
  );
}
