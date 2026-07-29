# Entrega das análises aos clientes (Acer / Cloudflare)

No ar desde **2026-07-29**. Os mapas gerados pela Análise de área ficam
disponíveis por link, servidos deste PC e publicados pelo tunnel do Cloudflare.

| O quê | Onde |
|---|---|
| Índice das análises | https://analises.cursar.space |
| Uma análise | `https://analises.cursar.space/<slug>/` |
| Site de download do app (já existia) | https://mapasfacil.cursar.space |

---

## ⚠️ Sem senha — decisão de 2026-07-29

O dono do sistema optou por **link público, sem login**. Isso significa, em
termos práticos:

- **qualquer pessoa com a URL abre os mapas** — não há e-mail, senha ou código;
- um mapa de análise mostra **número do CAR, nome da propriedade e a geometria
  do imóvel** do cliente;
- o índice em `/` **lista todas** as análises publicadas, então basta abrir a
  raiz para ver o que existe.

O que foi feito para reduzir o dano dentro dessa escolha:

| Medida | Efeito |
|---|---|
| Publicação é **explícita** | só aparece o que passou por `publicar_analise.py`; nenhuma pasta de trabalho é servida |
| Só PDF é copiado | shapefile do cliente, relatório interno e cache **não** saem do PC |
| `X-Robots-Tag: noindex` + `robots.txt` | não entra em buscador |
| Servidor só de leitura, preso à pasta | sem upload, sem execução, sem `..`, sem seguir link para fora |
| `--remover` | tira do ar em um comando |

**Como fechar com login depois** (não muda uma linha de código): no painel do
Cloudflare → Zero Trust → Access → Applications → Add, domínio
`analises.cursar.space`, política *Allow* por e-mail. A partir daí o cliente
recebe um código por e-mail antes de ver qualquer coisa.

## Publicar uma análise

```bash
# 1. gerar a série (ver docs/analise-de-area-serie.md)
# 2. publicar
python3 ferramentas/publicar_analise.py ~/Documentos/MapasFacil_Aruana --slug aruana-i
#    → https://analises.cursar.space/aruana-i/

python3 ferramentas/publicar_analise.py --listar
python3 ferramentas/publicar_analise.py --remover aruana-i
```

Republicar o mesmo slug **apaga os PDFs antigos** antes de copiar os novos —
mapa velho não fica para trás junto do novo.

O manifesto `analise.json` de cada pasta guarda nome do imóvel, município, CAR,
quantos mapas saíram e quando foi publicado. É o que a página usa para o título
e o subtítulo.

## Como isso sobe neste PC

```
servidor_analises.py  ──127.0.0.1:3081──  cloudflared (tunnel mapasfacil)  ──  analises.cursar.space
        ▲                                          ▲
 mapas-facil-analises.service              mapas-facil-tunnel.service
```

| Peça | Onde |
|---|---|
| Servidor | `Fase_2_Site/deploy/servidor_analises.py` (stdlib, sem dependência) |
| Unidade systemd (usuário) | `Fase_2_Site/deploy/mapas-facil-analises.service` |
| Pasta publicada | `~/MapasFacil_Publicado/<slug>/` |
| Ingress do tunnel | `~/.cloudflared/mapasfacil-config.yml` — hostname `analises.cursar.space` |
| DNS | CNAME criado com `cloudflared tunnel route dns 1d0a92d1-… analises.cursar.space` |

O servidor escuta **só em `127.0.0.1`**. Quem fala com a internet é o
`cloudflared` — não há porta aberta na máquina.

### Operação

```bash
systemctl --user status mapas-facil-analises.service
systemctl --user restart mapas-facil-analises.service
journalctl --user -u mapas-facil-analises.service -f     # cada acesso vira log

curl -I https://analises.cursar.space/
```

### Instalar em outro PC

```bash
cp Fase_2_Site/deploy/mapas-facil-analises.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now mapas-facil-analises.service
# acrescente o ingress de analises.cursar.space no config do tunnel e rode:
cloudflared tunnel route dns <TUNNEL_ID> analises.cursar.space
```

## Por que `analises.cursar.space` e não `analise.mapasfacil.cursar.space`

O Universal SSL do Cloudflare cobre `*.cursar.space`, **um nível só**. Um
terceiro nível (`algo.mapasfacil.cursar.space`) daria erro de certificado sem o
Advanced Certificate Manager, que é pago.

## Pegadinha: o PDF compilado é grande

`Analise_de_area.pdf` da Aruanã tem **~168 MB** — são 20 páginas com imagem de
satélite a 300 dpi embutida. Abre no navegador (o servidor aceita *range
request*, o Cloudflare responde `206`), mas em conexão ruim demora. Se virar
problema, o caminho é baixar a resolução do basemap em `motores/basemap.py`
(`LARGURA_PADRAO`) ou gerar uma versão comprimida só para entrega.

## O que **não** está exposto

- não há API: o cliente não manda shapefile nem dispara geração pela web
  (contraria a **D21** e o **AP-14**; a geração continua sendo do app desktop);
- nada de `Testes/`, `secrets.local.json`, cache de camadas ou workspace;
- o site de download (`mapasfacil.cursar.space`) segue independente, no 3080.
