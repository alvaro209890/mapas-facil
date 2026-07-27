# Documentação da Fase 2 — site Mapas Fácil

Atualizado em 27 de julho de 2026.

## 1. Objetivo

A Fase 2 entrega o front público de apresentação e distribuição do Mapas Fácil.
O site explica o produto, apresenta seus requisitos, prepara o acesso ao
instalador Windows e oferece canais diretos de contato com o desenvolvedor.

O site não executa a análise cartográfica. Login, conta, projetos, credenciais e
geração efetiva dos mapas pertencem ao aplicativo desktop da Fase 1.

## 2. Resultado implementado

O front está em [`web/`](web/) e possui quatro rotas:

| Rota | Finalidade |
|---|---|
| `/` | Landing page cinematográfica do produto |
| `/requisitos` | Requisitos para uso no Windows |
| `/download` | Distribuição do instalador ou aviso de disponibilidade futura |
| `/contato` | Dados públicos e canais do desenvolvedor |

O preview local é servido normalmente em `http://localhost:3000/`.

## 3. Direção visual

A interface foi construída com uma linguagem de cartografia técnica:

- fundo verde-escuro com grade e linhas topográficas;
- tipografia de grande escala e alto contraste;
- verde ácido para ações, progresso e detalhes;
- cartões claros representando os arquivos técnicos;
- composição responsiva para desktop, tablet e celular;
- animações reduzidas quando o sistema informa `prefers-reduced-motion`.

O hero comunica a ideia central: “Do pedido ao mapa pronto”.

## 4. Animação do mapa

O componente principal está em
[`web/components/CenaMapa.tsx`](web/components/CenaMapa.tsx).

A cena representa visualmente o fluxo de produção:

1. leitura do pedido “faça a Dinâmica desta pasta”;
2. carregamento da base de satélite;
3. entrada do limite ATP;
4. entrada das camadas de vegetação, uso do solo e município;
5. varredura da folha cartográfica;
6. traçado animado do perímetro;
7. identificação ATP, AVN e AC;
8. apresentação de escala, datum e padrão de layout;
9. exibição de legenda, minimapa e progresso;
10. conclusão com os artefatos MXD editável e PDF de conferência.

A sequência é cíclica e dura aproximadamente 18 segundos.

## 5. Dados e mapa demonstrativo

Nenhuma propriedade real é usada na demonstração.

O mapa foi produzido especificamente para o front com:

- perímetro aleatório;
- classes e valores demonstrativos;
- localização não associada a imóvel real;
- textos “DADOS FICTÍCIOS” e “SEM VALIDADE TÉCNICA”.

O arquivo usado pela interface é
[`web/public/mapa-demo-ficticio.webp`](web/public/mapa-demo-ficticio.webp).
Ele foi otimizado de uma fonte PNG de aproximadamente 2,57 MB para um WebP de
208.740 bytes, preservando a leitura visual e deixando o preview local mais
estável.

## 6. Desenvolvedor e contatos públicos

Os dados informados para identificação pública são:

| Campo | Valor |
|---|---|
| Desenvolvedor | Álvaro Emanuel |
| E-mail | `alvaroemanuel642@gmail.com` |
| WhatsApp | `+55 (66) 98439-6232` |
| LinkedIn | `https://www.linkedin.com/in/alvaro-emanuel-4673a63a7/` |

Essas informações aparecem:

- na página `/contato`;
- no rodapé compartilhado por todas as páginas;
- no menu, por meio do link do LinkedIn.

O WhatsApp usa o endereço
`https://wa.me/5566984396232`, sem espaços ou pontuação.

Os valores padrão ficam centralizados em
[`web/lib/site.ts`](web/lib/site.ts) e podem ser substituídos por variáveis de
ambiente.

## 7. Arquitetura do front

| Camada | Implementação |
|---|---|
| Framework | Next.js com App Router |
| Build e execução | vinext/Vite |
| Linguagem | TypeScript e React |
| Estilos | CSS global responsivo |
| Imagens | ativos locais, sem propriedade real |
| Persistência | nenhuma |
| Backend público | nenhum na versão atual |

Arquivos importantes:

| Arquivo | Responsabilidade |
|---|---|
| `web/app/page.tsx` | página inicial |
| `web/app/globals.css` | design system, layout e animações |
| `web/app/layout.tsx` | metadados e estrutura global |
| `web/app/contato/page.tsx` | contato do desenvolvedor |
| `web/app/download/page.tsx` | distribuição do aplicativo |
| `web/components/CenaMapa.tsx` | animação cartográfica |
| `web/components/SiteHeader.tsx` | cabeçalho e navegação |
| `web/components/SiteFooter.tsx` | rodapé e créditos |
| `web/lib/site.ts` | contatos públicos centralizados |
| `web/tests/rendered-html.test.mjs` | verificações automatizadas |

## 8. Variáveis públicas

O modelo está em [`web/.env.example`](web/.env.example).

| Variável | Uso |
|---|---|
| `NEXT_PUBLIC_DOWNLOAD_URL` | URL do instalador Windows (`.exe` no GitHub Releases) |
| `NEXT_PUBLIC_DOWNLOAD_MANIFEST_URL` | Manifesto JSON da release (`download-manifest.json`) |
| `NEXT_PUBLIC_DEVELOPER_NAME` | nome do desenvolvedor |
| `NEXT_PUBLIC_CONTACT_EMAIL` | e-mail público |
| `NEXT_PUBLIC_WHATSAPP_NUMBER` | WhatsApp internacional somente com números |
| `NEXT_PUBLIC_LINKEDIN_URL` | perfil público do LinkedIn |
| `NEXT_PUBLIC_REPO_URL` | repositório público opcional |

São dados enviados ao navegador. Não devem ser usados para chaves privadas,
senhas, tokens ou credenciais do aplicativo desktop.

## 9. Execução local

No PowerShell:

```powershell
cd C:\GIS\mapas-facil\Fase_2_Site\web
npm install
npm run dev
```

Depois, abrir:

```text
http://localhost:3000/
```

Para criar o build:

```powershell
npm run build
```

## 10. Validação realizada

Na entrega de 27 de julho de 2026 foram executados:

```powershell
npm run build
node --test tests/rendered-html.test.mjs
npx tsc --noEmit
git diff --check
```

Resultados:

- build concluído para as quatro rotas;
- tipagem TypeScript sem erros;
- oito testes automatizados aprovados;
- verificação de diferenças sem erros de whitespace;
- mapa fictício carregado diretamente no preview;
- LinkedIn presente no cabeçalho e no rodapé;
- animação conferida no estado inicial, durante o processamento e na saída
  MXD/PDF.

## 11. Acessibilidade e comportamento responsivo

- navegação por links sem dependência de JavaScript;
- textos alternativos para a folha demonstrativa;
- elementos puramente decorativos marcados para não poluir leitores de tela;
- contraste forte entre fundo, textos e ações;
- layout dos contatos convertido para uma coluna em telas menores;
- estado estático final para usuários que preferem movimento reduzido.

## 12. Privacidade e segurança

- o site não possui formulário que armazena mensagens;
- e-mail, WhatsApp e LinkedIn abrem canais externos;
- não existe login ou cadastro;
- não existem chaves de API no front;
- o mapa demonstrativo não representa pessoa, propriedade ou localização real;
- os contatos publicados foram fornecidos pelo próprio desenvolvedor para essa
  finalidade.

## 13. Situação atual e próximos passos

Concluído:

- front completo e responsivo;
- mapa fictício;
- animação cartográfica ampliada;
- páginas internas;
- contatos e crédito do desenvolvedor;
- execução local e validações.

Pendente de decisão ou material externo:

- definir a URL final do instalador em `NEXT_PUBLIC_DOWNLOAD_URL`;
- informar um repositório público, caso desejado;
- publicar em produção quando as credenciais do serviço de hospedagem estiverem
  disponíveis.

O site está concluído localmente. Uma tentativa anterior de publicação não foi
finalizada porque a credencial do repositório usada pelo serviço de hospedagem
foi recusada; isso não afeta o funcionamento local.
