/**
 * Upload do pacote `.zip` por partes (W4-03 do lado do navegador).
 *
 * O contrato é o do servidor (`importacao/upload.py`), e replicá-lo aqui é o que permite
 * **retomar** um envio interrompido: o `GET /uploads/{id}` diz quais partes já chegaram e a
 * gente manda só as que faltam.
 *
 * Duas provas de integridade, de propósito:
 *
 * 1. cada parte vai com `X-Parte-SHA256` — o servidor recusa texto trocado no caminho;
 * 2. no fim, `hash_partes` = sha256 da concatenação dos hex das partes, na ordem, que é
 *    exatamente o que o servidor calcula para montar o arquivo.
 *
 * Arquivo grande (até 2 GB) não é carregado na memória: as partes são lidas como `Blob`.
 */

import { api } from './cliente';

export interface InfoUpload {
  upload_id: string;
  nome: string;
  tamanho: number;
  parte_bytes: number;
  total_partes: number;
  partes_ok: number[];
  faltam: number[];
}

export interface ResultadoUpload {
  upload_id: string;
  sha256: string;
  tamanho: number;
}

/** sha256 em hex minúsculo, do jeito que o servidor compara. */
export async function sha256Hex(dados: ArrayBuffer | Uint8Array): Promise<string> {
  const bytes = dados instanceof Uint8Array ? dados : new Uint8Array(dados);
  const buffer = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

/**
 * `hash_partes` = sha256(concatenação dos hex das partes, na ordem).
 * É o mesmo cálculo de `upload.hash_partes()` no servidor — se um dos dois mudar sem o
 * outro, o `concluir` responde `SV-102` e o teste pega.
 */
export async function hashPartes(hashes: string[]): Promise<string> {
  const texto = hashes.join('');
  return sha256Hex(new TextEncoder().encode(texto));
}

export interface OpcoesEnvio {
  /** Chamado a cada parte concluída — é o único percentual honesto do envio. */
  aoProgresso?: (enviadas: number, total: number) => void;
  sinal?: AbortSignal;
}

/** Cria o upload e devolve o estado inicial (partes, tamanho da parte, o que falta). */
export async function criarUpload(arquivo: File): Promise<InfoUpload> {
  return api.post<InfoUpload>('/uploads', { nome: arquivo.name, tamanho: arquivo.size });
}

/**
 * Envia (ou retoma) o arquivo e conclui.
 *
 * `uploadId` serve para retomar depois de uma queda: sem ele, cria um upload novo.
 */
export async function enviarZip(
  arquivo: File,
  opcoes: OpcoesEnvio = {},
  uploadId?: string,
): Promise<ResultadoUpload> {
  const info = uploadId
    ? await api.get<InfoUpload>(`/uploads/${uploadId}`)
    : await criarUpload(arquivo);

  const partes = info.total_partes;
  const tamanhoParte = info.parte_bytes;
  const jaTem = new Set(info.partes_ok);

  if (info.tamanho !== arquivo.size) {
    throw new Error(
      `o servidor espera ${info.tamanho} bytes e o arquivo tem ${arquivo.size}; recomece o envio`,
    );
  }

  // O hash de **todas** as partes sai do arquivo local — é a única fonte confiável depois de
  // uma retomada (o servidor não devolve hash avulso de parte já recebida).
  const hashes: string[] = [];
  for (let numero = 0; numero < partes; numero += 1) {
    const inicio = numero * tamanhoParte;
    const fatia = arquivo.slice(inicio, Math.min(inicio + tamanhoParte, arquivo.size));
    hashes.push(await sha256Hex(new Uint8Array(await fatia.arrayBuffer())));
  }

  let enviadas = jaTem.size;
  opcoes.aoProgresso?.(enviadas, partes);

  for (let numero = 0; numero < partes; numero += 1) {
    if (sinalAbortado(opcoes.sinal)) throw new Error('envio cancelado');
    if (jaTem.has(numero)) continue;

    const inicio = numero * tamanhoParte;
    const fatia = arquivo.slice(inicio, Math.min(inicio + tamanhoParte, arquivo.size));
    const bytes = new Uint8Array(await fatia.arrayBuffer());
    const hash = hashes[numero];
    if (!hash) throw new Error(`hash da parte ${numero} ausente`);

    await api.putCru(`/uploads/${info.upload_id}/partes/${numero}`, new Blob([bytes]), {
      cabecalhos: { 'X-Parte-SHA256': hash, 'Content-Type': 'application/octet-stream' },
      ...(opcoes.sinal ? { sinal: opcoes.sinal } : {}),
    });
    enviadas += 1;
    opcoes.aoProgresso?.(enviadas, partes);
  }

  if (sinalAbortado(opcoes.sinal)) throw new Error('envio cancelado');

  const resultado = await api.post<{ sha256: string; tamanho: number; upload_id: string }>(
    `/uploads/${info.upload_id}/concluir`,
    { hash_partes: await hashPartes(hashes) },
  );
  return {
    upload_id: resultado.upload_id ?? info.upload_id,
    sha256: resultado.sha256,
    tamanho: resultado.tamanho,
  };
}

function sinalAbortado(sinal?: AbortSignal): boolean {
  return Boolean(sinal?.aborted);
}
