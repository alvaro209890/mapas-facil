import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
const layout = await readFile(
  new URL("../app/layout.tsx", import.meta.url),
  "utf8",
);
const download = await readFile(
  new URL("../app/download/page.tsx", import.meta.url),
  "utf8",
);
const contact = await readFile(
  new URL("../app/contato/page.tsx", import.meta.url),
  "utf8",
);
const mapScene = await readFile(
  new URL("../components/CenaMapa.tsx", import.meta.url),
  "utf8",
);
const header = await readFile(
  new URL("../components/SiteHeader.tsx", import.meta.url),
  "utf8",
);
const footer = await readFile(
  new URL("../components/SiteFooter.tsx", import.meta.url),
  "utf8",
);
const site = await readFile(
  new URL("../lib/site.ts", import.meta.url),
  "utf8",
);

test("home comunica o produto e a entrega", () => {
  assert.match(page, /Do pedido ao/);
  assert.match(page, /MXD \+ PDF/);
  assert.match(page, /CenaMapa/);
});

test("site não cria rotas de autenticação ou chat", () => {
  assert.doesNotMatch(page, /href=["']\/(?:login|signup|chat)/);
});

test("download resolve o instalador via manifesto/env com fallback", () => {
  assert.match(download, /resolveDownloadInfo/);
  assert.match(download, /Instalador em breve/);
  assert.match(download, /Pronto para instalar/);
  assert.match(download, /Baixar para Windows/);
});

test("a demonstração usa somente o mapa fictício", () => {
  assert.match(mapScene, /mapa-demo-ficticio\.webp/);
  assert.match(mapScene, /propriedade fictícia/);
  assert.doesNotMatch(mapScene, /dinamica_2026_(?:retrato|quantitativos)/);
});

test("metadados sociais representam o site", () => {
  assert.match(layout, /Mapas Fácil/);
  assert.match(layout, /\/og\.png/);
  assert.doesNotMatch(layout, /codex-preview/);
});

test("animação do mapa representa o fluxo completo de produção", () => {
  assert.match(mapScene, /map-scene__layers/);
  assert.match(mapScene, /map-paper__parcel-trace/);
  assert.match(mapScene, /map-scene__metadata/);
  assert.match(mapScene, /map-scene__done/);
});

test("LinkedIn fica disponível no menu e no rodapé", () => {
  assert.match(header, /LinkedIn/);
  assert.match(footer, /LinkedIn/);
  assert.match(site, /NEXT_PUBLIC_LINKEDIN_URL/);
  assert.match(site, /alvaro-emanuel-4673a63a7/);
});

test("contato identifica o desenvolvedor e seus canais públicos", () => {
  assert.match(site, /Álvaro Emanuel/);
  assert.match(site, /alvaroemanuel642@gmail\.com/);
  assert.match(site, /5566984396232/);
  assert.match(contact, /contact__channels/);
  assert.match(footer, /whatsappUrl/);
});
