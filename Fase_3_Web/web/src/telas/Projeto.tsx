/**
 * Tela do projeto (W6-07) — chat de um lado, mapa do outro.
 *
 * O que já é real aqui:
 *
 * - **chat** com a timeline herdada do desktop (bolha que junta deltas, grupo de tools,
 *   raciocínio, pergunta com chips) alimentada pelo SSE do projeto;
 * - **faixa de versões** clicável (a versão aberta vem da URL `/versoes/:n`);
 * - **downloads** por `GET /projetos/{id}/arquivos/{caminho}` (o PDF abre, o resto baixa);
 * - **sugestões** de primeiro turno vindas do servidor.
 *
 * O que **ainda não** é real: o palco. Até o W8 ele é um desenho estático da folha com o
 * número da versão — sem animação, sem mapa falso.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { api, ErroHttp } from '../api/cliente';
import { ligarProjeto, type Ligacao } from '../api/ponteWeb';
import type { Mensagem, Sugestao, Versao } from '../api/tipos';
import { BolhaMarkdown } from '../herdados/BolhaMarkdown';
import { BlocoRaciocinio } from '../herdados/BlocoRaciocinio';
import { CartaoPergunta } from '../herdados/CartaoPergunta';
import { CartaoTool } from '../herdados/CartaoTool';
import { GrupoTools } from '../herdados/GrupoTools';
import { IndicadorPensando } from '../herdados/IndicadorPensando';
import { Palco } from '../palco/Palco';
import { useChat } from '../estado/chat';
import { useConexao } from '../estado/conexao';
import { useProjetoAtivo, type ProgressoImportacao } from '../estado/projetoAtivo';
import { seloFolha, tempoRelativo } from '../utilitarios/tempo';
import estilos from './Projeto.module.css';

const ROTULO_ESTADO: Record<string, string> = {
  aguardando_zip: 'aguardando dados',
  importando: 'importando',
  indexando: 'indexando',
  pronto: 'pronto',
  gerando: 'gerando',
  erro: 'erro',
  lixeira: 'na lixeira',
};

/** Nome de arquivo para a faixa de downloads, com o rótulo em português. */
const ROTULO_ARTEFATO: Record<string, string> = {
  pdf: 'PDF',
  mxd: 'MXD',
  zip: 'Pacote .zip',
  png: 'Miniatura',
  geojson: 'GeoJSON',
  xlsx: 'Planilha',
};

export function Projeto() {
  const { id = '', numero } = useParams();
  const navegar = useNavigate();
  const { projeto, importacao, resumo, versoes, versaoAberta, carregando, erro, carregar, abrirVersao } =
    useProjetoAtivo();
  const { mensagens, blocos, turnoEmCurso, pensando, sugestoes, erro: erroChat, carregar: carregarChat, enviarLocal, definirErro, limpar: limparChat } =
    useChat();
  const limparProjeto = useProjetoAtivo((s) => s.limpar);
  const estadoConexao = useConexao((s) => s.estado);
  const [texto, setTexto] = useState('');
  const [enviando, setEnviando] = useState(false);
  const ligacao = useRef<Ligacao | null>(null);
  const fimDaLista = useRef<HTMLDivElement | null>(null);

  const versaoDaUrl = numero ? Number(numero) : null;
  const versao = useMemo(() => {
    const qual = versaoDaUrl ?? versaoAberta;
    return versoes.find((v) => v.numero === qual) ?? versoes.at(-1) ?? null;
  }, [versoes, versaoAberta, versaoDaUrl]);

  // Carga inicial: projeto, versões, mensagens e sugestões.
  useEffect(() => {
    if (!id) return;
    // As stores são globais: sem zerar aqui, o projeto novo mostrava o chat, o resumo e até a
    // versão aberta do projeto anterior até a carga terminar (e a versão nem era trocada).
    limparChat();
    limparProjeto();
    let vivo = true;
    void carregar(id);
    void (async () => {
      try {
        const [lista, sug] = await Promise.all([
          api.get<{ itens: Mensagem[] }>(`/projetos/${id}/mensagens`),
          api.get<{ itens: Sugestao[] }>(`/projetos/${id}/sugestoes`).catch(() => ({ itens: [] })),
        ]);
        if (vivo) carregarChat(lista.itens, sug.itens);
      } catch {
        if (vivo) carregarChat([], []);
      }
    })();
    return () => {
      vivo = false; // resposta atrasada do projeto anterior não pode pintar o atual
    };
  }, [id, carregar, carregarChat, limparChat, limparProjeto]);

  // SSE do projeto: um só, fechado ao sair da tela.
  useEffect(() => {
    if (!id) return;
    const l = ligarProjeto(id, 0);
    ligacao.current = l;
    return () => {
      l.fechar();
      ligacao.current = null;
    };
  }, [id]);

  useEffect(() => {
    if (versaoDaUrl && versaoDaUrl !== versaoAberta) abrirVersao(versaoDaUrl);
  }, [versaoDaUrl, versaoAberta, abrirVersao]);

  useEffect(() => {
    // `scrollIntoView` não existe no jsdom (e em navegador antigo pode faltar).
    fimDaLista.current?.scrollIntoView?.({ block: 'end' });
  }, [blocos.length, pensando]);

  const enviar = useCallback(
    async (mensagem: string) => {
      const limpo = mensagem.trim();
      if (!limpo || !id || enviando) return;
      setEnviando(true);
      definirErro(null);
      const reqId = `web-${Date.now()}`;
      enviarLocal(limpo, reqId);
      setTexto('');
      try {
        await api.post(`/projetos/${id}/mensagens`, { texto: limpo });
      } catch (e) {
        definirErro(e instanceof ErroHttp ? `${e.codigo}: ${e.texto}` : 'Não foi possível enviar.');
      } finally {
        setEnviando(false);
      }
    },
    [id, enviando, enviarLocal, definirErro],
  );

  async function cancelar() {
    if (!id || !turnoEmCurso) return;
    try {
      await api.post(`/projetos/${id}/cancelar`, { req_id: turnoEmCurso });
    } catch {
      // Cancelar é best-effort: se o turno já terminou, o SSE já fechou por conta própria.
    }
  }

  if (carregando && !projeto) {
    return (
      <main className={estilos.tela}>
        <p className={estilos.carregando}>Carregando o projeto…</p>
      </main>
    );
  }

  if (erro && !projeto) {
    return (
      <main className={estilos.tela}>
        <div className={estilos.erro} role="alert">
          {erro}
        </div>
        <Link to="/projetos" className={estilos.voltar}>
          Voltar para os projetos
        </Link>
      </main>
    );
  }

  const ocupado = projeto?.estado === 'importando' || projeto?.estado === 'indexando';

  return (
    <main className={estilos.tela}>
      <header className={estilos.cabecalho}>
        <div className={estilos.cabecalhoTexto}>
          <Link to="/projetos" className={estilos.voltar}>
            ← Projetos
          </Link>
          <h1 className={estilos.titulo}>{projeto?.nome ?? 'Projeto'}</h1>
          <p className={estilos.subtitulo}>
            {projeto?.imovel?.nome ?? 'sem dados ainda'}
            {projeto?.imovel?.municipio ? ` · ${projeto.imovel.municipio}/${projeto.imovel.uf}` : ''}
          </p>
        </div>
        <div className={estilos.selos}>
          <span className={estilos.selo}>{seloFolha(projeto?.folha)}</span>
          <span className={estilos.selo} data-estado={projeto?.estado}>
            {ROTULO_ESTADO[projeto?.estado ?? ''] ?? projeto?.estado}
            {projeto?.erro_codigo ? ` · ${projeto.erro_codigo}` : ''}
          </span>
          {estadoConexao === 'offline' && (
            <span className={`${estilos.selo} ${estilos.seloRuim}`}>sem conexão</span>
          )}
        </div>
      </header>

      <div className={estilos.divisor}>
        {/* ---------------------------------------------------------- chat */}
        <section className={estilos.chat} aria-label="Conversa do projeto">
          <div className={estilos.lista}>
            {ocupado && <BarraImportacao estado={projeto?.estado} progresso={importacao} />}

            {mensagens.length === 0 && blocos.length === 0 && (
              <div className={estilos.boasVindas}>
                <h2>O que você precisa neste mapa?</h2>
                <p>
                  Escreva com as suas palavras. A IA monta a versão, gera o MXD, o PDF e os
                  shapefiles — e explica cada escolha.
                </p>
                {sugestoes.length > 0 && (
                  <div className={estilos.sugestoes}>
                    {sugestoes.map((s) => (
                      <button
                        key={s.id}
                        type="button"
                        className={estilos.sugestao}
                        title={s.porque}
                        onClick={() => void enviar(s.texto)}
                      >
                        <strong>{s.texto}</strong>
                        <span>{s.porque}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {resumo && <ResumoDados resumo={resumo} />}

            {blocos.map((bloco) => {
              if (bloco.tipo === 'usuario') {
                return (
                  <article key={bloco.id} className={estilos.bolhaUsuario} data-papel="usuario">
                    <span className={estilos.papelUsuario}>você</span>
                    <p>{bloco.texto}</p>
                  </article>
                );
              }
              if (bloco.tipo === 'texto') {
                return (
                  <BolhaMarkdown
                    key={bloco.id}
                    markdown={bloco.markdown}
                    streaming={bloco.streaming ?? false}
                  />
                );
              }
              if (bloco.tipo === 'raciocinio') {
                return (
                  <BlocoRaciocinio
                    key={bloco.id}
                    id={bloco.id}
                    texto={bloco.texto}
                    streaming={bloco.streaming ?? false}
                  />
                );
              }
              if (bloco.tipo === 'tools') {
                // Uma tool só fica melhor como cartão; várias viram grupo recolhido.
                const unica = bloco.tools[0];
                if (bloco.tools.length === 1 && unica) {
                  return <CartaoTool key={bloco.id} estado={unica} />;
                }
                return <GrupoTools key={bloco.id} id={bloco.id} tools={bloco.tools} />;
              }
              return (
                <CartaoPergunta
                  key={bloco.id}
                  dados={bloco.dados}
                  aoResponder={(resposta) => void enviar(resposta)}
                />
              );
            })}

            {pensando && <IndicadorPensando />}
            {erroChat && (
              <div className={estilos.erro} role="alert">
                {erroChat}
              </div>
            )}
            <div ref={fimDaLista} />
          </div>

          <form
            className={estilos.formulario}
            onSubmit={(evento) => {
              evento.preventDefault();
              void enviar(texto);
            }}
          >
            <textarea
              className={estilos.entrada}
              aria-label="Mensagem para a IA"
              placeholder={
                ocupado
                  ? 'A importação está rodando — a conversa abre quando terminar.'
                  : 'Ex.: faz a dinâmica de 2023 e destaca o uso do solo'
              }
              rows={2}
              value={texto}
              disabled={ocupado}
              onChange={(e) => setTexto(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  void enviar(texto);
                }
              }}
            />
            {turnoEmCurso ? (
              <button type="button" className={estilos.parar} onClick={() => void cancelar()}>
                Parar
              </button>
            ) : (
              <button
                type="submit"
                className={estilos.enviar}
                disabled={!texto.trim() || enviando || ocupado}
              >
                Enviar
              </button>
            )}
          </form>
        </section>

        {/* --------------------------------------------------------- palco */}
        <section className={estilos.palco} aria-label="Mapa">
          <Palco versao={versao} />

          <div className={estilos.faixaVersoes} role="list" aria-label="Versões">
            {versoes.length === 0 && <span className={estilos.dica}>sem versões</span>}
            {versoes.map((v) => (
              <BotaoVersao
                key={v.numero}
                versao={v}
                aberta={versao?.numero === v.numero}
                aoAbrir={() => {
                  abrirVersao(v.numero);
                  navegar(`/projetos/${id}/versoes/${v.numero}`);
                }}
              />
            ))}
          </div>

          {versao && (
            <div className={estilos.downloads}>
              <h3>Baixar a versão {versao.numero}</h3>
              <div className={estilos.botoesDownload}>
                {Object.entries(versao.artefatos ?? {}).map(([tipo, caminho]) => (
                  <a
                    key={tipo}
                    className={estilos.download}
                    href={`/api/v1/projetos/${id}/arquivos/${caminho}?anexo=true`}
                    download
                  >
                    {ROTULO_ARTEFATO[tipo] ?? tipo}
                  </a>
                ))}
                {Object.keys(versao.artefatos ?? {}).length === 0 && (
                  <span className={estilos.dica}>Esta versão ainda não tem arquivo publicado.</span>
                )}
              </div>
              <p className={estilos.dica}>Gerada {tempoRelativo(versao.criada_em)}</p>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

/**
 * Barra da importação do `.zip`: extração com porcentagem real (arquivo N de M, do evento
 * `importacao.progresso`) e, depois, a leitura dos shapefiles pelo núcleo — que não tem
 * contagem, então a barra fica cheia até 90% e pulsa. Nada aqui avança por timer (AP-07).
 */
function BarraImportacao({
  estado,
  progresso,
}: {
  estado: string | undefined;
  progresso: ProgressoImportacao | null;
}) {
  const indexando = progresso?.fase === 'indexando' || estado === 'indexando';
  const total = progresso?.total ?? 0;
  const feitos = Math.min(progresso?.indice ?? 0, total);
  // Extração vale 0–85% da barra; a indexação fecha o resto.
  const pct = indexando ? 90 : total > 0 ? Math.round((feitos / total) * 85) : 0;
  const texto = indexando
    ? 'Lendo os shapefiles e montando o índice do projeto…'
    : total > 0
      ? `Extraindo ${feitos} de ${total} arquivos`
      : 'Preparando o pacote…';

  return (
    <section className={estilos.importacao} aria-label="Importação dos dados">
      <div className={estilos.importacaoTopo}>
        <strong>Importando os dados</strong>
        <span className={estilos.importacaoPct}>{indexando ? 'quase lá' : `${pct}%`}</span>
      </div>
      <div
        className={estilos.importacaoTrilho}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-valuetext={texto}
      >
        <div
          className={estilos.importacaoBarra}
          data-indeterminado={indexando ? 'sim' : undefined}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className={estilos.importacaoTexto}>
        {texto}
        {!indexando && progresso?.arquivo && (
          <span className={estilos.importacaoArquivo}> · {progresso.arquivo}</span>
        )}
      </p>
    </section>
  );
}

interface ShapefileResumo {
  papel?: string;
  id_local?: string;
  area_ha?: number | null;
  feicoes?: number;
}

/**
 * Cartão curto do que veio no `.zip`: contagem de arquivos, área do imóvel e os papéis
 * reconhecidos. O resumo bruto do índice (caminhos, WKT do CRS, bbox) é para a IA, não
 * para o usuário — despejá-lo aqui estourava a coluna do chat.
 */
function ResumoDados({ resumo }: { resumo: Record<string, unknown> }) {
  const lista = (chave: string): unknown[] => {
    const valor = resumo[chave];
    return Array.isArray(valor) ? valor : [];
  };
  const shapefiles = lista('shapefiles') as ShapefileResumo[];
  const pdfs = lista('pdfs').length;
  const zips = lista('zips').length;
  const atp = shapefiles.find((s) => s.papel === 'ATP');
  const papeis = Array.from(
    new Set(
      shapefiles
        .map((s) => s.papel)
        .filter((p): p is string => typeof p === 'string' && p !== '' && p !== 'outro'),
    ),
  ).sort();
  const area = typeof atp?.area_ha === 'number' ? atp.area_ha : null;

  if (shapefiles.length === 0 && pdfs === 0 && zips === 0) return null;

  return (
    <section className={estilos.resumoDados} aria-label="Dados do projeto">
      <div className={estilos.resumoNumeros}>
        <div>
          <dt>shapefiles</dt>
          <dd>{shapefiles.length}</dd>
        </div>
        {area !== null && (
          <div>
            <dt>área do imóvel</dt>
            <dd>{area.toLocaleString('pt-BR', { maximumFractionDigits: 2 })} ha</dd>
          </div>
        )}
        {pdfs > 0 && (
          <div>
            <dt>PDFs</dt>
            <dd>{pdfs}</dd>
          </div>
        )}
        {zips > 0 && (
          <div>
            <dt>zips</dt>
            <dd>{zips}</dd>
          </div>
        )}
      </div>
      {papeis.length > 0 && (
        <div className={estilos.resumoPapeis} aria-label="Camadas reconhecidas">
          {papeis.map((papel) => (
            <span key={papel} className={estilos.papelChip}>
              {papel}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}

function BotaoVersao({
  versao,
  aberta,
  aoAbrir,
}: {
  versao: Versao;
  aberta: boolean;
  aoAbrir: () => void;
}) {
  return (
    <button
      type="button"
      role="listitem"
      className={aberta ? `${estilos.versao} ${estilos.versaoAberta}` : estilos.versao}
      aria-current={aberta ? 'true' : undefined}
      onClick={aoAbrir}
    >
      <span className={estilos.numeroVersao}>v{String(versao.numero).padStart(3, '0')}</span>
      <span className={estilos.estadoVersao} data-conforme={versao.conforme}>
        {versao.conforme ? 'conforme' : 'não conforme'}
      </span>
    </button>
  );
}
