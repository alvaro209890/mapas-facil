/**
 * Assistente de novo mapa (W6-06) — três passos, um estado só.
 *
 * 1. **Folha**: nome do projeto + formato (A4…A0) e orientação, vendo a proporção real.
 * 2. **Dados**: escolher o `.zip` e subir por partes (progresso = partes enviadas, o único
 *    número honesto disponível aqui).
 * 3. **Resumo**: confere tudo e cria o projeto; a importação começa no servidor e a tela
 *    vai para o projeto, onde o SSE mostra o que está acontecendo.
 *
 * O projeto **só é criado no fim**: se o envio falhar, não sobra projeto vazio na lista.
 */

import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { api, ErroHttp } from '../../api/cliente';
import { enviarZip, type ResultadoUpload } from '../../api/upload';
import { CartaoFolha } from '../../componentes/CartaoFolha';
import {
  equivalenciaA4,
  FORMATOS,
  ORDEM_FORMATOS,
  ORIENTACOES,
  problemasZip,
  textoFolha,
  type FormatoFolha,
  type Orientacao,
} from '../../componentes/formatos';
import estilos from './NovoMapa.module.css';

type Passo = 1 | 2 | 3;

export interface Rascunho {
  nome: string;
  formato: FormatoFolha;
  orientacao: Orientacao;
  arquivo: File | null;
}

export function NovoMapa() {
  const navegar = useNavigate();
  const [passo, setPasso] = useState<Passo>(1);
  const [rascunho, setRascunho] = useState<Rascunho>({
    nome: '',
    formato: 'A3',
    orientacao: 'paisagem',
    arquivo: null,
  });
  const [erro, setErro] = useState<{ codigo: string; texto: string } | null>(null);
  // O resultado do upload vive aqui: o passo 2 envia, o passo 3 usa o `upload_id`.
  const [upload, setUpload] = useState<ResultadoUpload | null>(null);

  function atualizar(parcial: Partial<Rascunho>) {
    setRascunho((atual) => ({ ...atual, ...parcial }));
  }

  const podeAvancar =
    passo === 1
      ? rascunho.nome.trim().length > 0
      : passo === 2
        ? rascunho.arquivo !== null
        : true;

  return (
    <main className={estilos.tela}>
      <header className={estilos.cabecalho}>
        <div>
          <h1 className={estilos.titulo}>Novo mapa</h1>
          <p className={estilos.subtitulo}>
            Passo {passo} de 3 — {passo === 1 ? 'a folha' : passo === 2 ? 'os dados' : 'o resumo'}
          </p>
        </div>
        <ol className={estilos.passos} aria-label="Passos">
          {[1, 2, 3].map((n) => (
            <li
              key={n}
              className={
                n === passo
                  ? `${estilos.passo} ${estilos.passoAtual}`
                  : n < passo
                    ? `${estilos.passo} ${estilos.passoFeito}`
                    : estilos.passo
              }
              aria-current={n === passo ? 'step' : undefined}
            >
              {n < passo ? '✓' : n}
            </li>
          ))}
        </ol>
      </header>

      {erro && (
        <div className={estilos.erro} role="alert">
          <strong>{erro.codigo}</strong>
          <span>{erro.texto}</span>
        </div>
      )}

      {passo === 1 && (
        <PassoFolha rascunho={rascunho} aoMudar={atualizar} />
      )}
      {passo === 2 && (
        <PassoZip
          arquivo={rascunho.arquivo}
          upload={upload}
          aoEscolher={(arquivo) => {
            atualizar({ arquivo });
            setUpload(null);
          }}
          aoEnviado={setUpload}
          aoErro={setErro}
        />
      )}
      {passo === 3 && (
        <PassoResumo
          rascunho={rascunho}
          upload={upload}
          aoErro={setErro}
          aoCriar={async (upload) => {
            const criado = await api.post<{ projeto: { id: string } }>('/projetos', {
              nome: rascunho.nome.trim(),
              folha: { formato: rascunho.formato, orientacao: rascunho.orientacao },
            });
            const projetoId = criado.projeto.id;
            if (upload) {
              await api.post(`/projetos/${projetoId}/importacao`, { upload_id: upload.upload_id });
            }
            navegar(`/projetos/${projetoId}`);
          }}
        />
      )}

      <footer className={estilos.rodape}>
        <button
          type="button"
          className={estilos.secundario}
          onClick={() => (passo === 1 ? navegar('/projetos') : setPasso((passo - 1) as Passo))}
        >
          {passo === 1 ? 'Cancelar' : 'Voltar'}
        </button>
        {passo < 3 && (
          <button
            type="button"
            className={estilos.principal}
            disabled={!podeAvancar}
            onClick={() => {
              setErro(null);
              setPasso((passo + 1) as Passo);
            }}
          >
            Continuar
          </button>
        )}
      </footer>
    </main>
  );
}

// ---------------------------------------------------------------- passo 1

export function PassoFolha({
  rascunho,
  aoMudar,
}: {
  rascunho: Rascunho;
  aoMudar: (parcial: Partial<Rascunho>) => void;
}) {
  return (
    <section className={estilos.bloco}>
      <div className={estilos.campo}>
        <label htmlFor="mf-nome-projeto">Nome do projeto</label>
        <input
          id="mf-nome-projeto"
          type="text"
          maxLength={120}
          placeholder="Ex.: Boa Vista — dinâmica 2023"
          value={rascunho.nome}
          onChange={(e) => aoMudar({ nome: e.target.value })}
        />
        <small className={estilos.dica}>
          Pode ser o nome do imóvel ou do serviço. Dá para renomear depois.
        </small>
      </div>

      <div className={estilos.grupo}>
        <span className={estilos.rotuloGrupo}>Formato da folha</span>
        <div className={estilos.formatos}>
          {ORDEM_FORMATOS.map((formato) => (
            <CartaoFolha
              key={formato}
              formato={formato}
              orientacao={rascunho.orientacao}
              selecionado={rascunho.formato === formato}
              aoEscolher={(f) => aoMudar({ formato: f })}
            />
          ))}
        </div>
        <p className={estilos.dica}>
          {`${rascunho.formato} equivale a ${equivalenciaA4(rascunho.formato)} folhas A4 (` +
            `${FORMATOS[rascunho.formato].largura_mm}×${FORMATOS[rascunho.formato].altura_mm} mm em retrato). ` +
            "Folha maior = mais área no mesmo detalhe."}
        </p>
      </div>

      <div className={estilos.grupo}>
        <span className={estilos.rotuloGrupo}>Orientação</span>
        <div className={estilos.abas} role="group" aria-label="Orientação">
          {ORIENTACOES.map((orientacao) => (
            <button
              key={orientacao}
              type="button"
              aria-pressed={rascunho.orientacao === orientacao}
              className={
                rascunho.orientacao === orientacao
                  ? `${estilos.aba} ${estilos.abaAtiva}`
                  : estilos.aba
              }
              onClick={() => aoMudar({ orientacao })}
            >
              {orientacao}
            </button>
          ))}
        </div>
        <p className={estilos.dica}>{textoFolha(rascunho.formato, rascunho.orientacao)}</p>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------- passo 2

export function PassoZip({
  arquivo,
  upload,
  aoEscolher,
  aoEnviado,
  aoErro,
}: {
  arquivo: File | null;
  upload: ResultadoUpload | null;
  aoEscolher: (arquivo: File | null) => void;
  aoEnviado: (resultado: ResultadoUpload | null) => void;
  aoErro: (erro: { codigo: string; texto: string } | null) => void;
}) {
  const [enviando, setEnviando] = useState(false);
  const [enviadas, setEnviadas] = useState(0);
  const [total, setTotal] = useState(0);
  const [problema, setProblema] = useState<string | null>(null);
  const entrada = useRef<HTMLInputElement | null>(null);
  const resultado = upload;

  useEffect(() => {
    if (!arquivo) {
      setEnviadas(0);
      setTotal(0);
    }
  }, [arquivo]);

  async function subir() {
    if (!arquivo) return;
    const p = problemasZip(arquivo);
    if (p) {
      setProblema(p);
      return;
    }
    setProblema(null);
    setEnviando(true);
    aoErro(null);
    try {
      const r = await enviarZip(arquivo, {
        aoProgresso: (e, t) => {
          setEnviadas(e);
          setTotal(t);
        },
      });
      aoEnviado(r);
    } catch (e) {
      setProblema(e instanceof ErroHttp ? `${e.codigo}: ${e.texto}` : String((e as Error).message));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section className={estilos.bloco}>
      <div
        className={estilos.areaArquivo}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          const solto = e.dataTransfer.files?.[0];
          if (solto) {
            aoEscolher(solto);
            setProblema(problemasZip(solto));
          }
        }}
      >
        <input
          ref={entrada}
          id="mf-zip"
          type="file"
          accept=".zip,application/zip"
          className={estilos.escondido}
          onChange={(e) => {
            const escolhido = e.target.files?.[0] ?? null;
            aoEscolher(escolhido);
            setProblema(escolhido ? problemasZip(escolhido) : null);
          }}
        />
        <label htmlFor="mf-zip" className={estilos.botaoArquivo}>
          Escolher o pacote .zip
        </label>
        <p className={estilos.dica}>
          O pacote do imóvel com os shapefiles e o recibo do CAR. Arraste aqui ou use o botão.
        </p>
        {arquivo && (
          <p className={estilos.arquivoEscolhido}>
            {arquivo.name} · {(arquivo.size / 1024 / 1024).toFixed(1)} MB
          </p>
        )}
      </div>

      {problema && (
        <div className={estilos.erro} role="alert">
          <span>{problema}</span>
        </div>
      )}

      {arquivo && !resultado && (
        <button type="button" className={estilos.principal} disabled={enviando} onClick={() => void subir()}>
          {enviando ? `Enviando ${enviadas}/${total} partes…` : 'Enviar o pacote'}
        </button>
      )}

      {enviando && total > 0 && (
        <div
          className={estilos.barra}
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={enviadas}
          aria-label="Partes enviadas"
        >
          <span style={{ width: `${Math.round((enviadas / total) * 100)}%` }} />
        </div>
      )}

      {resultado && (
        <p className={estilos.ok}>
          Pacote enviado e conferido ({resultado.tamanho} bytes).{' '}
          <span className={estilos.hash}>sha256 {resultado.sha256.slice(0, 12)}…</span>
        </p>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- passo 3

export function PassoResumo({
  rascunho,
  upload,
  aoCriar,
  aoErro,
}: {
  rascunho: Rascunho;
  upload: ResultadoUpload | null;
  aoCriar: (upload: ResultadoUpload | null) => Promise<void>;
  aoErro: (erro: { codigo: string; texto: string } | null) => void;
}) {
  const [criando, setCriando] = useState(false);

  return (
    <section className={estilos.bloco}>
      <dl className={estilos.resumo}>
        <div>
          <dt>Projeto</dt>
          <dd>{rascunho.nome}</dd>
        </div>
        <div>
          <dt>Folha</dt>
          <dd>{textoFolha(rascunho.formato, rascunho.orientacao)}</dd>
        </div>
        <div>
          <dt>Pacote</dt>
          <dd>
            {rascunho.arquivo
              ? `${rascunho.arquivo.name} · ${(rascunho.arquivo.size / 1024 / 1024).toFixed(1)} MB`
              : 'nenhum arquivo escolhido'}
            {upload ? ' · enviado e conferido' : ' · ainda não enviado'}
          </dd>
        </div>
      </dl>

      <p className={estilos.dica}>
        Ao criar, o servidor importa os dados e a conversa abre no projeto. Se algo falhar na
        importação, o projeto mostra o código do erro — nada é apagado.
      </p>

      <button
        type="button"
        className={estilos.principal}
        disabled={criando}
        onClick={() => {
          setCriando(true);
          aoErro(null);
          void aoCriar(upload).catch((e: unknown) => {
            setCriando(false);
            aoErro(
              e instanceof ErroHttp
                ? { codigo: e.codigo, texto: e.texto }
                : { codigo: 'REDE', texto: 'Não foi possível criar o projeto.' },
            );
          });
        }}
      >
        {criando ? 'Criando…' : 'Criar projeto e importar'}
      </button>
    </section>
  );
}
