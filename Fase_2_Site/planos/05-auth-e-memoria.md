# F2-05 — Auth e memória de projeto

O diferencial do site em relação ao desktop: **projetos e histórico que sobrevivem entre
máquinas**.

## Auth (rascunho)

| Decisão | Valor provisório | Notas |
|---|---|---|
| Provedor | a definir (Auth.js / Clerk / próprio) | não bloqueia o desenho da API |
| Sessão | cookie HTTP-only + refresh | sem JWT longo no `localStorage` |
| Escopo mínimo | email + projetos do usuário | sem SSO corporativo na v1 |

Credenciais e tokens **nunca** entram em log. Ver
[`../../planos/05-seguranca-e-segredos.md`](../../planos/05-seguranca-e-segredos.md).

## Memória de projeto

O que o backend guarda por usuário/projeto:

| Dado | Persistência | Sensível? |
|---|---|---|
| Metadados do imóvel (nome, CAR, município, área) | Postgres | baixo |
| Histórico de conversas e tool calls | Postgres | médio (pode citar áreas) |
| Versões de `MapSpec` | Postgres, append-only | baixo |
| Artefatos PDF/PNG gerados | disco neste PC / object storage local | médio |
| Shapefiles do cliente | **só com consentimento**; preferência = ficar no desktop | alto |

Regra: se o usuário só usa o site para "mapa por CAR" a partir de dados públicos/SEMA, não
é necessário upload de shape. Upload é opt-in e apagável.

## Histórico entre máquinas

1. Usuário autentica no notebook e no desktop.
2. Lista de projetos e versões de `MapSpec` é a mesma.
3. Arquivos `.mxd` gerados no Windows **não** sobem automaticamente — só metadados e, se
   consentido, PDF/PNG.

## Relação com a Fase 1

O desktop guarda conversas em `%APPDATA%\MapasFacil\projetos\<hash>\` (SQLite local). A Fase 2
**não substitui** esse armazenamento local; oferece um espelho opcional na nuvem deste PC quando
o usuário faz login.

Detalhe da ponte em [`03-integracao-fase1.md`](03-integracao-fase1.md).

## Estado

Rascunho. Auth provider e schema Postgres entram na reescrita de
[`02-backend-api.md`](02-backend-api.md).
