// C7 + A12 — `painel-workspace`: a árvore da pasta conectada com metadados inline.
//
// O que o técnico precisa ver sem abrir nada: quantas feições, qual CRS e quantos
// hectares. Tudo vem de `workspace.abrir` / `workspace.reindexar` / `workspace.mudou`
// — o renderer não toca em disco (fronteira 1 / fsguard).
//
// A12: arquivo novo chega por `workspace.mudou` e ganha realce de 2 s (F1-16 A6).
// O botão de reindexar permanece como fallback.

import type { ReactNode } from "react";
import { FileText, FolderOpen, Layers, RefreshCw, TriangleAlert } from "lucide-react";

import { ErroDoNucleo, PastaSemShapefile, SemPastaConectada } from "../componentes/EstadoVazio.js";
import type { ProjetoRecente } from "../estado/ponte.js";
import type { EstadoWorkspace, Shapefile } from "../estado/workspace.js";
import { nomeDoProjeto, problemasDoShapefile } from "../estado/workspace.js";
import { contarFeicoes, formatarData, formatarHectares } from "../formato/numeros.js";
import estilos from "./Workspace.module.css";

export interface PropsWorkspace {
  estado: EstadoWorkspace;
  aoConectar: () => void;
  aoAbrirRecente: (indice: number) => void;
  aoReindexar: () => void;
  /** `doctor-resumo` do rodapé; vem pronto do `AppShell`, que roda o doctor uma vez só. */
  rodape?: ReactNode;
}

function nomeArquivo(caminho: string): string {
  const partes = caminho.split("/");
  return partes[partes.length - 1] ?? caminho;
}

function crsDoShapefile(shapefile: Shapefile): string {
  const { epsg, adivinhado } = shapefile.crs;
  if (epsg === null) return "CRS desconhecido";
  return adivinhado ? `EPSG:${epsg} (estimado)` : `EPSG:${epsg}`;
}

function Grupo({ titulo, icone, children }: { titulo: string; icone: ReactNode; children: ReactNode }) {
  return (
    <section className={estilos.grupo}>
      <h3 className={estilos.tituloGrupo}>
        {icone}
        {titulo}
      </h3>
      {children}
    </section>
  );
}

function ItemShapefile({
  shapefile,
  destaque,
}: {
  shapefile: Shapefile;
  destaque: boolean;
}) {
  const problemas = problemasDoShapefile(shapefile);
  const temProblema = problemas.length > 0 || !shapefile.valido;

  return (
    <li
      className={estilos.item}
      data-alerta={temProblema}
      data-arquivo={shapefile.caminho}
      data-destaque={destaque ? "true" : undefined}
    >
      <span className={estilos.linhaArquivo}>
        <span className={estilos.arquivo}>{nomeArquivo(shapefile.caminho)}</span>
        {shapefile.papel !== null && <span className={estilos.papel}>{shapefile.papel}</span>}
        {temProblema && (
          <span className={estilos.alerta} title={problemas.join(" · ")} role="img" aria-label="atenção">
            <TriangleAlert size={13} aria-hidden="true" />
          </span>
        )}
      </span>
      <span className={`${estilos.meta} mf-num`}>
        <span>{contarFeicoes(shapefile.feicoes)}</span>
        <span>{crsDoShapefile(shapefile)}</span>
        <span className={estilos.area}>{formatarHectares(shapefile.area_ha)} ha</span>
      </span>
    </li>
  );
}

function Recentes({
  recentes,
  aoAbrirRecente,
}: {
  recentes: ProjetoRecente[];
  aoAbrirRecente: (indice: number) => void;
}) {
  if (recentes.length === 0) return null;
  return (
    <Grupo titulo="projetos recentes" icone={<FolderOpen size={12} aria-hidden="true" />}>
      <ul className={estilos.recentes}>
        {recentes.map((projeto) => (
          <li key={`${projeto.indice}-${projeto.nome}`}>
            <button
              type="button"
              className={estilos.recente}
              onClick={() => aoAbrirRecente(projeto.indice)}
            >
              <span>{projeto.nome}</span>
              <span className={`${estilos.dataRecente} mf-num`}>
                {formatarData(projeto.abertoEm)}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </Grupo>
  );
}

export function Workspace({
  estado,
  aoConectar,
  aoAbrirRecente,
  aoReindexar,
  rodape,
}: PropsWorkspace) {
  const { situacao, indice, recibo, erro, recentes, destaques } = estado;
  const rodapeDoctor =
    rodape === undefined ? null : <div className={estilos.rodape}>{rodape}</div>;
  const setDestaques = new Set(destaques ?? []);

  if (situacao === "erro" && erro !== null) {
    return (
      <div className={estilos.painel}>
        <ErroDoNucleo codigo={erro.codigo} mensagem={erro.mensagem} aoTentarDeNovo={aoConectar} />
        <Recentes recentes={recentes} aoAbrirRecente={aoAbrirRecente} />
        {rodapeDoctor}
      </div>
    );
  }

  if (indice === null) {
    return (
      <div className={estilos.painel}>
        {situacao === "abrindo" ? (
          // Indexação é assíncrona e sem evento de progresso: texto, nunca barra (AP-07).
          <p className={estilos.abrindo}>indexando a pasta…</p>
        ) : (
          <SemPastaConectada aoConectar={aoConectar} />
        )}
        <Recentes recentes={recentes} aoAbrirRecente={aoAbrirRecente} />
        {rodapeDoctor}
      </div>
    );
  }

  const semShapefile = indice.shapefiles.length === 0;

  return (
    <div className={estilos.painel}>
      <div className={estilos.projeto}>
        <FolderOpen size={14} aria-hidden="true" />
        <span className={estilos.nome} title={nomeDoProjeto(indice)}>
          {nomeDoProjeto(indice)}
        </span>
        <span className={estilos.acoesProjeto}>
          <button
            type="button"
            className={estilos.botaoIcone}
            onClick={aoReindexar}
            aria-label="reindexar a pasta"
            title="reindexar a pasta"
          >
            <RefreshCw size={14} aria-hidden="true" />
          </button>
          <button
            type="button"
            className={estilos.botaoIcone}
            onClick={aoConectar}
            aria-label="conectar outra pasta"
            title="conectar outra pasta"
          >
            <FolderOpen size={14} aria-hidden="true" />
          </button>
        </span>
      </div>

      {situacao === "abrindo" && <p className={estilos.abrindo}>reindexando…</p>}

      {recibo !== null && (
        <div className={estilos.imovel}>
          <span className={estilos.imovelTitulo}>{recibo.nome_imovel ?? "Imóvel sem nome"}</span>
          <span>
            {[recibo.municipio, recibo.uf].filter(Boolean).join("/") || "município não informado"}
            {recibo.car_estadual !== null && ` · CAR ${recibo.car_estadual}`}
          </span>
          <span className={`${estilos.area} mf-num`}>
            {formatarHectares(recibo.area_total_ha)} ha
          </span>
        </div>
      )}

      {semShapefile ? (
        <PastaSemShapefile aoConectarOutra={aoConectar} />
      ) : (
        <Grupo titulo="camadas" icone={<Layers size={12} aria-hidden="true" />}>
          <ul>
            {indice.shapefiles.map((shapefile) => (
              <ItemShapefile
                key={shapefile.caminho}
                shapefile={shapefile}
                destaque={setDestaques.has(shapefile.caminho)}
              />
            ))}
          </ul>
        </Grupo>
      )}

      {indice.pdfs.length > 0 && (
        <Grupo titulo="documentos" icone={<FileText size={12} aria-hidden="true" />}>
          <ul>
            {indice.pdfs.map((pdf) => (
              <li
                key={pdf.caminho}
                className={estilos.item}
                data-arquivo={pdf.caminho}
                data-destaque={setDestaques.has(pdf.caminho) ? "true" : undefined}
              >
                <span className={estilos.linhaArquivo}>
                  <span className={estilos.arquivo}>{nomeArquivo(pdf.caminho)}</span>
                  {pdf.recibo_car && <span className={estilos.papel}>recibo do CAR</span>}
                </span>
              </li>
            ))}
          </ul>
        </Grupo>
      )}

      {(indice.zips.length > 0 || indice.outros.length > 0) && (
        <Grupo titulo="outros arquivos" icone={<FileText size={12} aria-hidden="true" />}>
          <ul>
            {[...indice.zips, ...indice.outros].map((arquivo) => (
              <li
                key={arquivo.caminho}
                className={estilos.item}
                data-arquivo={arquivo.caminho}
                data-destaque={setDestaques.has(arquivo.caminho) ? "true" : undefined}
              >
                <span className={estilos.arquivo}>{nomeArquivo(arquivo.caminho)}</span>
              </li>
            ))}
          </ul>
        </Grupo>
      )}

      <Recentes recentes={recentes} aoAbrirRecente={aoAbrirRecente} />

      {rodapeDoctor}
    </div>
  );
}
