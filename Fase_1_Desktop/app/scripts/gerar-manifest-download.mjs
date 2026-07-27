#!/usr/bin/env node
/**
 * Gera sha256.txt + download-manifest.json para a release (site + suporte).
 *
 * Uso:
 *   node scripts/gerar-manifest-download.mjs \
 *     --dir release \
 *     --versao 0.5.0 \
 *     --tag desktop-v0.5.0 \
 *     --repo alvaro209890/mapas-facil
 */
import { createHash } from "node:crypto";
import { createReadStream, readdirSync, statSync, writeFileSync } from "node:fs";
import { basename, join, resolve } from "node:path";

function arg(nome, padrao = undefined) {
  const i = process.argv.indexOf(`--${nome}`);
  if (i >= 0 && process.argv[i + 1]) return process.argv[i + 1];
  return padrao;
}

async function sha256Arquivo(caminho) {
  const hash = createHash("sha256");
  const stream = createReadStream(caminho);
  for await (const pedaco of stream) hash.update(pedaco);
  return hash.digest("hex");
}

const dir = resolve(arg("dir", "release"));
const versao = arg("versao");
const tag = arg("tag", versao ? `desktop-v${versao}` : undefined);
const repo = arg("repo", "alvaro209890/mapas-facil");
const canal = arg("canal", "stable");

if (!versao || !tag) {
  console.error("Obrigatório: --versao e --tag (ou --versao sozinho → desktop-vX)");
  process.exit(1);
}

const arquivos = readdirSync(dir)
  .filter((nome) => /\.(exe|zip|yml|blockmap)$/i.test(nome))
  .map((nome) => join(dir, nome));

const linhasSha = [];
const hashes = {};
for (const caminho of arquivos) {
  const digest = await sha256Arquivo(caminho);
  const nome = basename(caminho);
  hashes[nome] = digest;
  linhasSha.push(`${digest}  ${nome}`);
  console.log(`${digest}  ${nome}`);
}

const shaPath = join(dir, "sha256.txt");
writeFileSync(shaPath, `${linhasSha.join("\n")}\n`, "utf8");

const instalador =
  arquivos.find((c) => /MapasFacil-Setup-.*\.exe$/i.test(basename(c))) ??
  arquivos.find((c) => /\.exe$/i.test(basename(c)));

const baseUrl = `https://github.com/${repo}/releases/download/${tag}`;

const manifest = {
  schema: "mapasfacil.download_manifest/1",
  canal,
  versao,
  tag,
  publicado_em: new Date().toISOString(),
  repositorio: `https://github.com/${repo}`,
  requisitos: [
    "Windows 10 ou 11 (x64)",
    "ArcMap 10.6–10.8 opcional (motor T1 / .mxd completo)",
    "Sem ArcMap: PDF nativo e .mxd estrutural (T2) quando o template estiver pronto",
  ],
  instalador: instalador
    ? {
        nome: basename(instalador),
        url: `${baseUrl}/${basename(instalador)}`,
        sha256: hashes[basename(instalador)],
        tamanho_bytes: statSync(instalador).size,
      }
    : null,
  latest_yml: hashes["latest.yml"]
    ? { url: `${baseUrl}/latest.yml`, sha256: hashes["latest.yml"] }
    : { url: `${baseUrl}/latest.yml` },
  sha256_txt: { url: `${baseUrl}/sha256.txt` },
  hashes,
  notas:
    "Beta do instalador desktop (M10). Assinatura Authenticode ainda não aplicada — " +
    "no SmartScreen use Mais informações → Executar mesmo assim e confira o SHA-256.",
};

const manifestPath = join(dir, "download-manifest.json");
writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
console.log(`OK: ${shaPath}`);
console.log(`OK: ${manifestPath}`);
