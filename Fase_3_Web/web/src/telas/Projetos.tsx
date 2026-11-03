/**
 * Lista de projetos (W6-05).
 *
 * Regras do W-06 que estão implementadas aqui:
 * - busca com debounce de 250 ms (`GET /projetos?busca=`), filtro Ativos / Lixeira;
 * - grade de cartões (3–4 colunas no desktop, 1 no celular);
 * - cartão com miniatura da última versão **ou** a silhueta da folha na proporção certa;
 * - selo de folha (`A3 · paisagem`) e selo de estado, com o código do erro quando falhou;
 * - menu do cartão: renomear, mandar para a lixeira, restaurar;
 * - atalho `N` abre o assistente de novo mapa.
 *
 * O que **não** existe: barra de progresso no cartão. `importando` aparece como selo, sem
 * percentual — o número real só existe no SSE do projeto aberto, e inventar porcentagem aqui
 * seria animação sem evento.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { api, ErroHttp } from '../api/cliente';
import type { Projeto } from '../api/tipos';
import { useProjetos, type Filtro } from '../estado/projetos';
import { seloFolha, tempoRelativo } from '../utilitarios/tempo';
import estilos from './Projetos.module.css';

const DEBOUNCE_MS = 250;

const ROTULO_ESTADO: Record<string, string> = {
  aguardando_zip: 'aguardando dados',
  importando: 'importando',
  indexando: 'indexando',
  pronto: 'pronto',
  gerando: 'gerando',
  erro: 'erro',
  lixeira: 'na lixeira',
};

/** Proporção (largura/altura) da folha em retrato, para a silhueta não mentir. */
const PROPORCAO: Record<string, number> = {
  A4: 210 / 297,
  A3: 297 / 420,
  A2: 420 / 594,
  A1: 594 / 841,
  A0: 841 / 1189,
};

export function Projetos() {
  const navegar = useNavigate();
  const { itens, filtro, busca, carregando, erro, carregar, mais, proximo, renomearLocal, removerLocal } =
    useProjetos();
  const [termo, setTermo] = useState(busca);
  const [aviso, setAviso] = useState<string | null>(null);
  const primeiroRender = useRef(true);

  useEffect(() => {
    if (primeiroRender.current) {
      primeiroRender.current = false;
      void carregar();
      return;
    }
  }, [carregar]);

  // Debounce da busca: só bate no servidor 250 ms depois da última tecla.
  useEffect(() => {
    const t = setTimeout(() => {
      void carregar({ busca: termo });
    }, DEBOUNCE_MS);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [termo, filtro]);

  // Atalho `N` = novo mapa (ignorado quando o foco está num campo).
  useEffect(() => {
    function aoTeclar(evento: KeyboardEvent) {
      const alvo = evento.target as HTMLElement | null;
      const digitando = alvo && ['INPUT', 'TEXTAREA', 'SELECT'].includes(alvo.tagName);
      if (digitando || evento.metaKey || evento.ctrlKey || evento.altKey) return;
      if (evento.key === 'n' || evento.key === 'N') {
        evento.preventDefault();
        navegar('/projetos/novo');
      }
    }
    window.addEventListener('keydown', aoTeclar);
    return () => window.removeEventListener('keydown', aoTeclar);
  }, [navegar]);

  async function renomear(projeto: Projeto) {
    const novo = window.prompt('Novo nome do projeto', projeto.nome)?.trim();
    if (!novo || novo === projeto.nome) return;
    try {
      await api.patch(`/projetos/${projeto.id}`, { nome: novo });
      renomearLocal(projeto.id, novo);
    } catch (e) {
      setAviso(e instanceof ErroHttp ? `${e.codigo}: ${e.texto}` : 'Não foi possível renomear.');
    }
  }

  async function mandarParaLixeira(projeto: Projeto) {
    if (!window.confirm(`Mandar "${projeto.nome}" para a lixeira?`)) return;
    try {
      await api.del(`/projetos/${projeto.id}`);
      if (filtro === 'ativos') removerLocal(projeto.id);
      else void carregar();
    } catch (e) {
      setAviso(e instanceof ErroHttp ? `${e.codigo}: ${e.texto}` : 'Não foi possível apagar.');
    }
  }

  async function restaurar(projeto: Projeto) {
    try {
      await api.post(`/projetos/${projeto.id}/restaurar`, {});
      removerLocal(projeto.id);
      setAviso(`"${projeto.nome}" voltou para os projetos ativos.`);
    } catch (e) {
      setAviso(e instanceof ErroHttp ? `${e.codigo}: ${e.texto}` : 'Não foi possível restaurar.');
    }
  }

  const vazio = !carregando && itens.length === 0;

  return (
    <main className={estilos.tela}>
      <header className={estilos.cabecalho}>
        <div>
          <h1 className={estilos.titulo}>Projetos</h1>
          <p className={estilos.subtitulo}>
            Cada projeto é um mapa: uma folha, um pacote de dados e uma conversa.
          </p>
        </div>
        <button type="button" className={estilos.novo} onClick={() => navegar('/projetos/novo')}>
          Novo mapa <kbd className={estilos.tecla}>N</kbd>
        </button>
      </header>

      <div className={estilos.filtros}>
        <input
          type="search"
          className={estilos.busca}
          placeholder="Buscar por nome, imóvel ou CAR"
          aria-label="Buscar projetos"
          value={termo}
          onChange={(e) => setTermo(e.target.value)}
        />
        <div className={estilos.abas} role="tablist">
          {(['ativos', 'lixeira'] as Filtro[]).map((f) => (
            <button
              key={f}
              type="button"
              role="tab"
              aria-selected={filtro === f}
              className={filtro === f ? `${estilos.aba} ${estilos.abaAtiva}` : estilos.aba}
              onClick={() => {
                void carregar({ filtro: f, busca: termo });
              }}
            >
              {f === 'ativos' ? 'Ativos' : 'Lixeira'}
            </button>
          ))}
        </div>
      </div>

      {aviso && (
        <div className={estilos.aviso} role="alert">
          {aviso}
          <button type="button" className={estilos.fecharAviso} onClick={() => setAviso(null)}>
            fechar
          </button>
        </div>
      )}

      {erro && (
        <div className={estilos.aviso} role="alert">
          {erro}
        </div>
      )}

      {vazio ? (
        <section className={estilos.vazio}>
          <div className={estilos.silhuetaVazia} aria-hidden="true" />
          <h2>{filtro === 'lixeira' ? 'A lixeira está vazia' : 'Crie seu primeiro mapa'}</h2>
          <p>
            {filtro === 'lixeira'
              ? 'Projetos apagados ficam aqui por 30 dias antes de sumir de vez.'
              : 'Envie o pacote de dados do imóvel (.zip) e diga o que você precisa — a IA monta o mapa.'}
          </p>
          {filtro === 'ativos' && (
            <button type="button" className={estilos.novo} onClick={() => navegar('/projetos/novo')}>
              Novo mapa
            </button>
          )}
        </section>
      ) : (
        <>
          <ul className={estilos.grade}>
            {itens.map((projeto) => (
              <li key={projeto.id}>
                <CartaoProjeto
                  projeto={projeto}
                  naLixeira={filtro === 'lixeira'}
                  aoAbrir={() => navegar(`/projetos/${projeto.id}`)}
                  aoRenomear={() => void renomear(projeto)}
                  aoApagar={() => void mandarParaLixeira(projeto)}
                  aoRestaurar={() => void restaurar(projeto)}
                />
              </li>
            ))}
          </ul>
          {proximo && (
            <button type="button" className={estilos.mais} onClick={() => void mais()}>
              Carregar mais
            </button>
          )}
        </>
      )}

      {carregando && itens.length === 0 && <p className={estilos.carregando}>Carregando…</p>}
    </main>
  );
}

interface CartaoProps {
  projeto: Projeto;
  naLixeira: boolean;
  aoAbrir: () => void;
  aoRenomear: () => void;
  aoApagar: () => void;
  aoRestaurar: () => void;
}

export function CartaoProjeto({
  projeto,
  naLixeira,
  aoAbrir,
  aoRenomear,
  aoApagar,
  aoRestaurar,
}: CartaoProps) {
  const [menu, setMenu] = useState(false);
  const folha = projeto.folha ?? {};
  const proporcao = useMemo(() => PROPORCAO[folha.formato ?? 'A4'] ?? 210 / 297, [folha.formato]);
  const paisagem = folha.orientacao === 'paisagem';
  const imovel = projeto.imovel ?? {};
  const local = [imovel.municipio, imovel.uf].filter(Boolean).join('/');
  const rotulo = ROTULO_ESTADO[projeto.estado] ?? projeto.estado;

  const largura = paisagem ? 88 : Math.round(88 * proporcao);
  const altura = paisagem ? Math.round(88 * proporcao) : 88;

  return (
    <article className={estilos.cartao} data-estado={projeto.estado}>
      <button type="button" className={estilos.areaAbrir} onClick={aoAbrir}>
        <div className={estilos.miniatura}>
          {projeto.miniatura ? (
            <img src={projeto.miniatura} alt="" loading="lazy" className={estilos.imagem} />
          ) : (
            <div
              className={estilos.silhueta}
              style={{ width: `${largura}px`, height: `${altura}px` }}
              aria-hidden="true"
            />
          )}
        </div>
        <div className={estilos.info}>
          <h2 className={estilos.nome}>{projeto.nome}</h2>
          <p className={estilos.linhaSecundaria}>
            {imovel.nome ?? 'sem dados ainda'}
            {local ? ` · ${local}` : ''}
          </p>
          <div className={estilos.selos}>
            <span className={estilos.selo}>{seloFolha(folha)}</span>
            <span className={`${estilos.selo} ${estilos[`estado_${projeto.estado}`] ?? ''}`}>
              {rotulo}
              {projeto.estado === 'erro' && projeto.erro_codigo ? ` ${projeto.erro_codigo}` : ''}
            </span>
            <span className={estilos.tempo}>{tempoRelativo(projeto.atualizado_em)}</span>
          </div>
        </div>
      </button>

      <div className={estilos.menuZona}>
        <button
          type="button"
          className={estilos.menuBotao}
          aria-haspopup="menu"
          aria-expanded={menu}
          aria-label={`Ações de ${projeto.nome}`}
          onClick={() => setMenu((aberto) => !aberto)}
        >
          ⋯
        </button>
        {menu && (
          <div className={estilos.menu} role="menu">
            {naLixeira ? (
              <button role="menuitem" type="button" onClick={aoRestaurar}>
                Restaurar
              </button>
            ) : (
              <>
                <button role="menuitem" type="button" onClick={aoRenomear}>
                  Renomear
                </button>
                <button role="menuitem" type="button" onClick={aoApagar}>
                  Mandar para a lixeira
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </article>
  );
}
