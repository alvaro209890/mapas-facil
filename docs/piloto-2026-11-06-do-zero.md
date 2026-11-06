# Teste do zero — 06/11/2026

O app está no ar em **https://mapasfacil-app.cursar.space** com o banco **virgem**
(0 contas, 0 projetos, schema 3). Este roteiro é o teste ponta a ponta, sem dado antigo.

## Estado no momento em que este doc foi escrito

| Peça | Estado |
|---|---|
| Serviço `mapasfacil-app.service` | `active` em `127.0.0.1:3130` |
| Túnel `mapasfacil-app-tunnel.service` | `active` (HTTPS público 200) |
| SQLite `dados/mapasfacil.sqlite` | recriado pelas migrações, **schema 3**, 0 usuários e 0 projetos |
| `dados/projetos/` e `dados/uploads/` | vazios |
| Backup da base antiga | `/home/server/mapasfacil/backups/zeragem-20261106-143250.tar.gz` (155 MB) |
| SPA | build novo (com `chat.turno` e o título dentro do quadro) |

O schema é recriado no boot (`create_app` chama `banco.migrar()`), então apagar o `.sqlite` é seguro.

## Passo a passo

1. Abra **https://mapasfacil-app.cursar.space**.
   A tela de entrada tem as abas **Entrar** e **Criar conta**. O cadastro é aberto (sem
   confirmação de e-mail): nome, e-mail e senha.
2. Em **Projetos**, clique em **Novo mapa** (ou em "Criar meu primeiro mapa").
3. **Folha**: dê um nome ao projeto (ex.: `Teste zero`), escolha `A4` e `Retrato`.
4. **Dados**: clique em **Escolher o pacote .zip** e selecione um pacote do SIMCAR
   (`CAR/*.shp` + recibo `.pdf`) ou o pacote sintético abaixo. Clique em **Enviar o pacote**
   e depois em **Criar projeto e importar**.
5. O projeto abre com a barra de importação. Quando ela termina (~3 s), o palco mostra o
   shape e o chat mostra **na hora**:
   ```
   Leitura do pacote concluída:
   • Imóvel: ...
   • Área: ... ha
   • Município/UF: ...
   • Datum: ...
   • Camadas identificadas: ...
   • Sugestão de folha: A4 retrato
   ```
   Em seguida a IA pensa (30–60 s) e oferece a escolha:
   **"Qual modelo de mapa você deseja gerar?"** com os modelos da galeria (os `pronto`
   primeiro). Clique em um deles (ex.: **Dinâmica 2008 (SPOT)**).
6. A IA monta o `MapSpec` e chama a geração. A faixa de versões mostra a **v001**; o palco
   anima; os botões de download entregam `.zip` com `MXD/ SHP/ Mapas/` (PDF, PNG, XLSX).

## O que conferir

- Depois da importação, **não** aparece a caixa "O que você precisa neste mapa?" — o chat
  já abre com a leitura do pacote (correção de 06/11).
- O título do mapa (ex.: "Dinâmica 2008") fica **dentro** do quadro, abaixo dos rótulos de
  longitude — não mais por cima da moldura (correção `28c31e3`).
- O PDF abre no leitor; o `.mxd` abre no ArcMap 10.8 sem *broken data sources*.
- O histórico sobrevive a recarregar a página (a pergunta com as opções volta pelos
  `tool_traces`; o painel de resumo da importação continua na tela).

## Pacote sintético (sem dado de cliente)

No Windows, com o venv do núcleo:

```powershell
C:\GIS\mapas-facil\Fase_1_Desktop\nucleo\.venv\Scripts\python.exe `
  C:\GIS\mapas-facil\Fase_3_Web\fixtures\gerar_zip_sintetico.py `
  --destino C:\Users\Usuario\Downloads\imovel_ficticio.zip
```

Gera ~1 km em UTM 22S, recibo fictício (`MT-0000000-FICTICIO0001`) e o shape `ATP`.

## Onde os dados ficam (no server)

```
/home/server/mapasfacil/dados/
  mapasfacil.sqlite        contas, projetos, importações, versões
  projetos/<id>/           workspace do projeto (entrada, SHP, MXD, Mapas/vNNN, .estado)
  uploads/                 partes de upload em andamento
  logs/                    log de operação (não é dado de usuário)
/home/server/mapasfacil/backups/   backups (zeragem + diário 02:30)
```

## Zerar de novo

Existe um script versionado que faz backup, apaga e sobe:

```bash
ssh sd
bash /home/server/mapasfacil/codigo/Fase_3_Web/deploy/scripts/zerar-dados.sh
```

Saída esperada: backup em `backups/zeragem-<data>.tar.gz`, `/saude` ok e
`usuarios=0/projetos=0/schema=3`.

Restaurar um backup (volta tudo, inclusive contas e projetos):

```bash
systemctl --user stop mapasfacil-app
tar xzf /home/server/mapasfacil/backups/zeragem-<data>.tar.gz -C /home/server/mapasfacil
systemctl --user start mapasfacil-app
```

## Admin (opcional)

O cadastro cria contas `usuario`. Para ter uma conta `admin`:

- defina `MF_ADMIN_EMAIL=<e-mail>` em `segredos/servidor.env` e reinicie — quem se cadastrar
  com esse e-mail vira admin; **ou**
- pela CLI, no server:
  ```bash
  /home/server/mapasfacil/venv/bin/python -m mapasfacil_servidor conta criar \
    --email <e-mail> --nome "<nome>" --admin --sem-trocar
  ```

O admin vê todos os projetos (somente leitura nos alheios), bloqueia contas e acessa `/admin`.

## Limites conhecidos

- O turno da abertura depende do 9Router; o texto factual é determinístico, mas a pergunta
  pode levar ~1 min (raciocínio `high`). Se o 9Router cair, a pergunta determinística com a
  galeria entra como Plano B.
- O mosaico SPOT/SEMA é WMS: uma falha transitória deixa o mapa sem imagem naquela geração
  (os fallbacks SEMA/Esri entram depois). Regerar resolve.
- O texto da abertura é ao vivo (não é gravado na conversa do núcleo); ao recarregar, os
  mesmos dados aparecem no painel de resumo da importação.
- O site de distribuição `mapasfacil.cursar.space` (landing/download do instalador desktop)
  continua fora do ar — não afeta este teste, que é do app web.
