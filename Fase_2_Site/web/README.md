# Mapas Fácil — site da Fase 2

Landing pública de apresentação e distribuição do aplicativo Mapas Fácil para Windows.

## O que existe

- Home cinematográfica com uma cena procedural da geração de mapa
- Mapa demonstrativo com propriedade, geometria e dados inteiramente fictícios
- Páginas de requisitos, download e contato
- Identificação pública do desenvolvedor Álvaro Emanuel
- Contatos diretos por e-mail, WhatsApp e LinkedIn
- Estado de “instalador em breve” quando não há URL configurada
- Movimento adaptado para `prefers-reduced-motion`
- Metadados sociais próprios em `public/og.png`

O site não tem login, chat, geração de mapas ou envio de credenciais. Conta, projetos e chaves
existem apenas no aplicativo desktop.

## Desenvolvimento

Requer Node.js 22.13 ou superior.

```powershell
npm install
npm run dev
```

Build de produção:

```powershell
npm run build
```

## Variáveis públicas

Copie `.env.example` para `.env.local` quando precisar configurar os canais públicos.

| Variável | Uso |
|---|---|
| `NEXT_PUBLIC_DOWNLOAD_URL` | URL do instalador Windows; vazia mantém “Instalador em breve” |
| `NEXT_PUBLIC_DEVELOPER_NAME` | Nome público do desenvolvedor |
| `NEXT_PUBLIC_CONTACT_EMAIL` | E-mail mostrado em `/contato` e no rodapé |
| `NEXT_PUBLIC_WHATSAPP_NUMBER` | WhatsApp no formato internacional, somente números |
| `NEXT_PUBLIC_REPO_URL` | Link opcional do repositório público |
| `NEXT_PUBLIC_LINKEDIN_URL` | Perfil do LinkedIn exibido no menu e no rodapé |

Não coloque chaves DeepSeek, credenciais ou segredos no site.

## Mídia

`public/mapa-demo-ficticio.webp` foi criado especificamente para a demonstração visual. A folha
marca “DADOS FICTÍCIOS” e “SEM VALIDADE TÉCNICA”; não representa imóvel, pessoa ou local real.
Quando houver uma gravação aprovada do aplicativo, ela poderá complementar a cena em
`public/demo-mapa.webm`, preservando o fallback atual.

## Documentação completa

O histórico da implementação, a arquitetura, os contatos públicos e o roteiro de validação
estão em [`../DOCUMENTACAO_FASE_2.md`](../DOCUMENTACAO_FASE_2.md).
