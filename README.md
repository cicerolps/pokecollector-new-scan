# ⚠️ Aviso
Tudo abaixo (e neste repositório) foi feito no estilo "vibecoded", sem pedir desculpas.
Espere vibe, não garantias. Prossiga com bom humor e controle de versão.

Contribuições são bem-vindas. Abra um pull request para correções, funcionalidades ou documentação. Não sabe por onde começar? Abra uma issue e conversamos. Pequenas melhorias são ótimas.

Encontrou um bug ou tem uma ideia? Abra uma issue. Inclua passos para reproduzir, comportamento esperado vs. real. Screenshots ou logs ajudam.

Faça um fork, crie uma branch e envie um PR focado. Adicione ou atualize testes e documentação conforme necessário. Explique o "porquê" e vincule issues relacionadas. Garanta que os checks passem.

Seja gentil. Seja claro. Presuma boa intenção. Mantenha o feedback construtivo.

# 🃏 PokéCollector

> Um gerenciador de coleção de Pokémon TCG full-stack e self-hosted para cartas, produtos lacrados, binders, análises, escaneamento e coleções multiusuário.

- 🌐 **Site do projeto original:** [pokecollector.romerg.de](https://pokecollector.romerg.de/)
- 👤 **Criador original:** [Gilles Romer](https://romerg.de/)
- ✉️ **Contato do projeto original:** [info@romerg.de](mailto:info@romerg.de)

![Version](https://img.shields.io/badge/version-v1.41.0-e3000b?style=flat-square) ![Dark Theme](https://img.shields.io/badge/theme-dark-1a1a2e?style=flat-square) ![TCGdex](https://img.shields.io/badge/card%20data-TCGdex-e3000b?style=flat-square) ![Docker](https://img.shields.io/badge/deploy-Docker-2496ed?style=flat-square) ![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688?style=flat-square) ![React](https://img.shields.io/badge/frontend-React%2018-61dafb?style=flat-square) [![Support animal rescue](https://img.shields.io/badge/support-animal%20rescue-e3000b?style=flat-square)](https://pokecollector.romerg.de/#support)

**Versão atual:** `v1.41.0` · Os lançamentos deste fork são acompanhados na [página de Releases do GitHub](https://github.com/cicerolps/pokecollector-new-scan/releases).

![Prévia do WebApp](preview-homescreen.png)

---

## 🔀 Sobre este fork

Este repositório é um fork do [PokéCollector](https://github.com/Git-Romer/pokecollector) original, criado por Gilles Romer. A filosofia e praticamente toda a aplicação foram mantidas exatamente como estão — coleção, binders, wishlist, preços, multiusuário, backups, etc. A única mudança estrutural é **como as cartas são reconhecidas ao escanear**:

| | Versão original (upstream) | Este fork |
|---|---|---|
| Motor de reconhecimento | Google Gemini (API externa, sujeita a limites e custo) | Pipeline 100% local: OpenCV + hash perceptual + EasyOCR |
| Precisa de chave de API? | Sim (`GEMINI_API_KEY`) | Não |
| Depende de serviço externo para reconhecer a carta? | Sim | Não |
| Escaneamento composto (várias cartas em uma foto) | Sim | Não por enquanto (removido — ainda não existe um equivalente local) |

Na prática: a foto é recortada e normalizada com OpenCV, comparada por hash perceptual (phash/dhash/whash) contra um banco de hashes gerado a partir do catálogo já sincronizado, e o número impresso na carta (lido via EasyOCR) desempata os casos ambíguos. Tudo roda no seu próprio servidor, sem chamada de rede para reconhecer a carta.

O restante deste documento descreve a aplicação como um todo — a grande maioria dela é idêntica ao projeto original.

---

## 📑 Índice

- [Funcionalidades](#-funcionalidades)
- [Início Rápido](#-início-rápido)
- [Autenticação via Proxy Reverso](#-autenticação-via-proxy-reverso)
- [Gerenciando Usuários](#-gerenciando-usuários)
- [Variáveis de Ambiente](#-variáveis-de-ambiente)
- [Comportamento de Sincronização](#-comportamento-de-sincronização)
- [Arquitetura](#-arquitetura)
- [Stack Tecnológica](#-stack-tecnológica)
- [Fontes Externas](#-fontes-externas)
- [Documentação](#-documentação)
- [Referência de Configuração](#-referência-de-configuração)
- [Atualizando](#-atualizando)
- [Projetos da Comunidade](#-projetos-da-comunidade)
- [Apoie o Projeto](#-apoie-o-projeto)
- [Licença](#-licença)

---

## ✨ Funcionalidades

### 📦 Gerenciamento de Coleção
- Adicione cartas com quantidade, condição, variante e preço de compra
- Variantes agora são limitadas a `Normal`, `Holo`, `Reverse Holo` e `First Edition`
- A raridade da carta vem da TCGdex (somente leitura) e é exibida separadamente da variante
- Acompanhe linhas de cartas localizadas da TCGdex separadamente por código de idioma, incluindo todos os idiomas suportados pela TCGdex
- Crie manualmente cartas personalizadas, restritas ao dono, que não existem na TCGdex
- Compartilhe cartas manuais como templates somente-cópia, para que outros treinadores recebam cartas e valores de portfólio independentes

### 🔍 Busca & Escaneamento
- Busque no banco de cartas cacheado localmente por nome, set, tipo, raridade, HP, artista e mais
- Busca por código curto, como `PFL 001`
- Seleção múltipla nos resultados de busca e adição em lote à coleção
- Scanner persistente com reconhecimento 100% local: OpenCV recorta e normaliza a foto, hash perceptual (phash/dhash/whash) identifica a carta comparando com o catálogo, e OCR (EasyOCR) confere o número impresso para desempatar casos ambíguos — sem API externa, sem chave, sem limite de uso
- Fila de escaneamento persistente e resistente a reinícios, com caixa de revisão, expiração em 14 dias e novas tentativas automáticas
- Correspondência determinística prioriza número local, total impresso, código do set, marca de regulamentação, artista e HP
- Captura nativa por câmera e galeria, com guia de posicionamento opcional; fotos na fila são sanitizadas e apagadas após confirmação ou descarte
- O scanner remove sufixos como `ex` / `GX` / `VSTAR` para ampliar a correspondência
- Diagnóstico opcional do scanner (com consentimento) para instalações que habilitam `SCAN_TRACE_DIR`; desativado por usuário por padrão, com ação de exclusão separada
- O modal da carta pré-seleciona automaticamente uma variante provável a partir das flags de variante da TCGdex

### 🗂️ Sets, Binders & Wishlist
- Visão geral dos sets com progresso de conclusão e checklist por set
- Pokédex Nacional #001–1025 com filtros por geração, conclusão por espécie, sprites/artes cacheados localmente e navegação até as impressões da carta
- Binders virtuais para visões de coleção e checklist
- Quantidades de cópia exata em binders de coleção, com limites de alocação entre binders e contagens totais/únicas
- Wishlist com alertas de preço via Telegram

### 📈 Preços, Portfólio & Análises
- Preços Cardmarket em EUR e TCGPlayer em USD via TCGdex
- Gráficos de histórico de preço e snapshots de portfólio
- Dashboard, duplicatas, maiores variações, estatísticas de raridade e rastreador de investimento
- Rastreamento de produtos lacrados com P&L realizado e não realizado

### 👤 Usuário Único & Multiusuário
- Modo usuário único: sem login, autenticação automática como admin
- Modo multiusuário: login via JWT, papéis admin/treinador, dados separados por usuário
- Configurações por usuário para idioma, moeda e chaves do Telegram
- Suporte a troca obrigatória de senha no primeiro login
- Edição de avatar e nome de perfil
- Exclusão em cascata dos dados de um usuário

### 🏆 Social & Comunidade
- Leaderboard, comparação entre treinadores e conquistas no modo multiusuário
- Veja coleções de outros treinadores pelo Leaderboard
- Perfis públicos opcionais com URLs por nome de treinador, diretório público, binders de coleção compartilhados individualmente e valores de mercado opt-in
- Interruptor de compartilhamento público controlado pelo admin, desativado por padrão em instalações novas e atualizadas
- Seção de Comunidade nas Configurações com contribuidores do GitHub e apoiadores do PokéCollector

### 🎨 UX & Localização
- Navegação compacta com 6 itens principais na home e navegação por abas agrupadas
- Traduções da UI para todos os idiomas suportados pela TCGdex, mais sueco
- 9 temas de cor por tipo de Pokémon: Padrão, Fogo, Água, Planta, Elétrico, Psíquico, Dragão, Sombrio, Fada

### ⚙️ Utilitários
- Exportação em CSV e PDF
- Importação estrita de coleção via CSV, com template para download; os valores obrigatórios por linha são `set_code` e `number`, enquanto `quantity`, `condition`, `variant`, `lang` e `purchase_price` podem ficar em branco
- Endpoints de sincronização e controles do agendador restritos ao admin
- Backup e restauração, incluindo grupos seletivos de backup para coleção, usuários, cartas, produtos, dados do sistema e imagens
- Proxy/cache de imagens no backend para cartas e sets

### Importação de Coleção via CSV

A página de Coleção inclui uma ação **Importar CSV** e um template para download. As importações de CSV são propositalmente estritas: o cabeçalho deve ser exatamente:

```csv
set_code,number,quantity,condition,variant,lang,purchase_price
```

Todas as colunas devem estar presentes, mas apenas `set_code` e `number` precisam de valor em cada linha. Use o código da carta mostrado nas listas do PokéCollector, por exemplo `ASC 152`: `ASC` vai em `set_code`, e `152` vai em `number`.

| Coluna | Valor obrigatório? | Notas |
| --- | --- | --- |
| `set_code` | Sim | Primeira parte do código da carta mostrado no app, ex.: `ASC` de `ASC 152`. |
| `number` | Sim | Segunda parte do código da carta mostrado no app, ex.: `152` de `ASC 152`. |
| `quantity` | Não | Padrão `1`; deve estar entre `1` e `999` quando informado. |
| `condition` | Não | Padrão `NM`; permitidos: `Mint`, `NM`, `LP`, `MP`, `HP`. |
| `variant` | Não | Deixe em branco ou use `Normal`, `Holo`, `Reverse Holo`, `First Edition`. |
| `lang` | Não | Padrão `en`; aceita qualquer código de idioma suportado pela TCGdex. |
| `purchase_price` | Não | Preço de compra opcional por carta. |

Exemplo:

```csv
set_code,number,quantity,condition,variant,lang,purchase_price
ASC,152,2,NM,,en,
PFL,001,1,LP,Reverse Holo,de,1.25
```

Se qualquer linha tiver um valor incorreto ou um código de carta desconhecido, a importação não adiciona nenhuma carta. A resposta mostra o número da linha afetada, para que o CSV possa ser corrigido e reenviado.

---

## 🚀 Início Rápido

### Pré-requisitos
- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/)

### 1. Clonar & Configurar

```bash
git clone https://github.com/cicerolps/pokecollector-new-scan.git
cd pokecollector-new-scan
```

Crie um arquivo `.env` na raiz do projeto:

```env
POSTGRES_PASSWORD=sua_senha_segura
JWT_SECRET_KEY=uma_string_aleatoria_longa

# Opcional
ADMIN_USERNAME=admin
ADMIN_PASSWORD=sua_senha_de_admin
TELEGRAM_BOT_TOKEN=seu_token_do_bot
TELEGRAM_CHAT_ID=seu_chat_id
TCGDEX_SYNC_LANGUAGES=en,de
PUBLIC_MODE=false
CORS_ORIGINS=https://seudominio.com
```

### 2. Iniciar

```bash
mkdir -p data/pokedex-images backups
docker compose up -d
```

### 3. Abrir

| Serviço | URL |
|---------|-----|
| App | http://localhost:3000 |
| Documentação da API | http://localhost:8000/docs |

### 4. Primeira Sincronização

No primeiro uso, dispare uma sincronização pelo app para popular sets e cartas a partir da TCGdex.

Depois de atualizar um catálogo já existente, o backend roda automaticamente em segundo plano o backfill único de metadados da Pokédex e registra a conclusão no banco. Se precisar repetir ou inspecionar manualmente, rode:

```bash
docker compose exec backend python -m scripts.backfill_pokedex_metadata --limit 5000
```

Repita o comando de metadados até `attempted` ser `0`. Opcionalmente, você pode pré-cachear todas as imagens de espécies:

```bash
docker compose exec backend python -m scripts.cache_pokedex_images
```

Veja a [documentação da Pokédex Nacional](docs/POKEDEX.md) para o modelo de dados, rotas, comportamento de cache e links do Cardmarket.

### 5. Login

- No modo usuário único, o login é pulado e o app se autentica automaticamente como admin
- No modo multiusuário, use a conta admin criada a partir de `ADMIN_USERNAME` / `ADMIN_PASSWORD`
- Se `ADMIN_PASSWORD` for omitido, uma senha aleatória pode ser registrada no log durante o bootstrap

> [!WARNING]
> O modo usuário único não tem autenticação: todo cliente que conseguir acessar o app é tratado como administrador. Use apenas em uma rede local confiável. Não exponha uma instalação em modo usuário único à internet; habilite o modo multiusuário e proteja implantações públicas com HTTPS e um proxy reverso configurado adequadamente.

---

## 🔐 Autenticação via Proxy Reverso

Se o PokéCollector estiver protegido por Authentik, Authelia, oauth2-proxy ou outra camada de forward-auth, o proxy verifica as requisições antes que elas cheguem ao PokéCollector. Habilitar perfis públicos dentro do app não é suficiente sozinho. O proxy também precisa liberar as páginas públicas, suas chamadas de API públicas e os assets usados por essas páginas.

Veja [Autenticação via proxy reverso](docs/REVERSE_PROXY_AUTH.md) para a lista completa de rotas, exemplos com Authentik e um checklist de verificação. Não desabilite a autenticação para todas as rotas `/api`.

---

## 👥 Gerenciando Usuários

O gerenciamento de usuários está disponível na UI do app quando o modo multiusuário está habilitado.

1. Faça login como usuário admin.
2. Vá em **Configurações**.
3. Habilite o **Modo Multiusuário**, se ainda não estiver habilitado.
4. Abra a aba **Usuários** em Configurações.

Na aba **Usuários**, admins podem:

- adicionar novos usuários
- editar usuários existentes
- alterar o papel do usuário entre `admin` e `treinador`
- ativar ou desativar usuários
- excluir outros usuários
- forçar novos usuários a trocarem a senha no primeiro login

A aba **Usuários** só é visível para usuários admin e apenas enquanto o modo multiusuário está habilitado. No modo usuário único, o PokéCollector pula o login e usa automaticamente a conta admin de bootstrap.

### Habilitando o modo multiusuário sem se trancar para fora

Ativar o modo multiusuário força a tela de login imediatamente e desconecta você, que então faz login novamente como o admin de bootstrap. No modo usuário único você nunca precisou digitar essa senha, então, se você não definiu `ADMIN_PASSWORD`, ela é a senha aleatória do log da primeira execução, e você pode não conhecê-la. Defina uma senha conhecida **antes** de habilitar o modo multiusuário. A partir do host:

```bash
# Docker
docker compose exec backend python -m scripts.set_admin_password
# Instalação nativa (rode no virtualenv do backend, a partir do diretório de trabalho do backend)
python -m scripts.set_admin_password
```

O script pede a nova senha (adicione `--username <nome>` para um admin não padrão, ou `--make-admin` se o único admin foi rebaixado).

### Recuperando-se de um bloqueio

Se você já está trancado para fora do modo multiusuário, defina `USER_MODE=single` no ambiente e reinicie. Isso fixa o modo usuário único e desabilita a tela de login independentemente da configuração salva, recuperando seu acesso local de admin; redefina a senha com o script acima, depois remova a variável e reinicie para voltar ao modo multiusuário. Enquanto `USER_MODE` estiver definido, o interruptor de Modo Multiusuário em Configurações fica desabilitado e mostra que o ambiente o controla. Como `USER_MODE=single` desabilita a tela de login, trate-o como uma ferramenta de recuperação local/LAN e não o deixe definido em uma instalação exposta à internet. (`USER_MODE=multi` fixa o modo multiusuário, que é seguro deixar definido.)

---

## 🔧 Variáveis de Ambiente

### Obrigatórias

| Variável | Descrição | Padrão |
|----------|-------------|---------|
| `POSTGRES_PASSWORD` | Senha do banco de dados PostgreSQL | `changeme` |

### Recomendadas

| Variável | Descrição | Padrão |
|----------|-------------|---------|
| `JWT_SECRET_KEY` | Segredo que assina os tokens de login. Quem o conhece pode forjar uma sessão de qualquer conta, incluindo admin, então trate como sensível. Deixe sem definir para que uma chave forte seja gerada e persistida automaticamente (em `data/auth/`); defina apenas se quiser controlar o valor ou compartilhá-lo entre réplicas. Um valor vazio é ignorado em vez de usado. | Gerada e persistida |

### Opcionais

| Variável | Descrição | Padrão |
|----------|-------------|---------|
| `ADMIN_USERNAME` | Usuário da conta admin de bootstrap | `admin` |
| `ADMIN_PASSWORD` | Senha da conta admin de bootstrap | Aleatória, pode ser registrada no log |
| `SCAN_TRACE_DIR` | Habilita diagnóstico do scanner com consentimento quando definido para um caminho gravável no container. Com o volume padrão do compose, use `/app/data/scan-traces`. Cada usuário ainda precisa habilitar individualmente. | *(vazio / desabilitado)* |
| `SCAN_TRACE_STORAGE_DIR` | Caminho estável de limpeza para diagnósticos do scanner já armazenados. O Docker Compose padrão define isso como `/app/data/scan-traces`; implantações customizadas devem manter isso apontado para o local de armazenamento mesmo quando `SCAN_TRACE_DIR` não estiver definido. | `/app/data/scan-traces` com Docker Compose |
| `TELEGRAM_BOT_TOKEN` | Token inicial do bot do Telegram para o usuário admin | *(vazio)* |
| `TELEGRAM_CHAT_ID` | Chat ID inicial do Telegram para o usuário admin | *(vazio)* |
| `TCGDEX_SYNC_LANGUAGES` | Padrão inicial do admin para os idiomas de sincronização de sets/cartas da TCGdex, apenas na primeira execução. Depois do bootstrap, a configuração no banco (em Configurações) é a que vale. Códigos de idioma da TCGdex separados por vírgula, ou `all` para habilitar todos os idiomas suportados. Valores vazios ou inválidos caem para `en,de`. Idiomas extras aumentam o tempo de sincronização, as chamadas de API e o tamanho do banco. | `en,de` |
| `ADMIN_BOOTSTRAP_LOG` | Se as credenciais de bootstrap podem ser registradas no log na primeira execução | `true` |
| `USER_MODE` | Fixa o modo a partir do ambiente, sobrepondo a configuração salva e desabilitando o interruptor no app. `single` força o modo usuário único (sem tela de login) e é a saída de emergência após um bloqueio no modo multiusuário; `multi` força o modo multiusuário. Como `single` desabilita a autenticação, use apenas em uma instalação local/LAN e remova a variável depois de recuperado. Não definido significa que a configuração no app controla o modo. | *(não definido)* |
| `PUBLIC_MODE` | Habilita meta tags de SEO, Open Graph e permite indexação por buscadores. O padrão bloqueia todos os crawlers. Requer rebuild. | `false` |
| `CORS_ORIGINS` | Lista separada por vírgula de origens permitidas para CORS. Se vazio, permite todas as origens. Defina para seu domínio em produção (ex.: `https://pokecollector.romerg.de`). | *(todas)* |
| `POKEDEX_METADATA_BACKFILL_ON_STARTUP` | Roda automaticamente o backfill único de metadados da Pokédex após a inicialização, quando linhas de cartas existentes não têm `dex_ids` ou metadados de produto do Cardmarket | `true` |
| `POKEDEX_METADATA_BACKFILL_BATCH_LIMIT` | Número de cartas selecionadas por lote automático de backfill de metadados da Pokédex | `5000` |
| `POKEDEX_METADATA_BACKFILL_BATCH_DELAY_SECONDS` | Pausa entre lotes automáticos de backfill de metadados da Pokédex, para evitar um loop apertado de requisições à TCGdex | `0.5` |
| `PRE_UPGRADE_BACKUP_ENABLED` | Cria um backup SQL automático antes das migrações de inicialização, quando uma instalação existente sobe em uma nova versão do app | `true` |
| `PRE_UPGRADE_BACKUP_REQUIRED` | Interrompe a inicialização se o backup automático de pré-atualização falhar. Defina como `false` apenas se você tiver outro processo de backup verificado. | `true` |
| `PRE_UPGRADE_BACKUP_KEEP` | Número de backups automáticos de pré-atualização a manter em `/app/backups`; mínimo `1` | `10` |
| `CARD_HASH_BACKFILL_BATCH_LIMIT` | Quantas cartas o backfill automático de hashes do scanner processa por execução agendada. O intervalo entre execuções é configurável em Configurações (padrão `15` minutos), não por variável de ambiente. | `300` |

Códigos suportados em `TCGDEX_SYNC_LANGUAGES`: `en`, `fr`, `es`, `es-mx`, `it`, `pt`, `pt-br`, `pt-pt`, `de`, `nl`, `pl`, `ru`, `ja`, `ko`, `zh-tw`, `id`, `th`, `zh-cn`. O valor `all` se expande para a lista completa de idiomas suportados durante o bootstrap inicial.

### Diagnóstico opcional do scanner

O diagnóstico do scanner exige consentimento do servidor e do usuário:

1. O administrador define `SCAN_TRACE_DIR=/app/data/scan-traces` e reinicia o backend.
2. Um usuário habilita **Configurações → IA / Scanner de Cartas → Compartilhar diagnóstico do scanner**. O interruptor vem desligado por padrão para todo usuário.

Somente as tentativas de escaneamento subsequentes desse usuário são armazenadas. Cada trace contém a foto sanitizada da carta, a decisão final do scanner (correspondência por hash, hash+OCR, ou sem correspondência) e o candidato selecionado, além de eventuais erros. O scanner não usa nenhuma chave de API, e credenciais de autenticação nunca são registradas.

Desligar o interruptor interrompe a coleta futura, mas mantém deliberadamente os diagnósticos já existentes. Não há expiração automática: os arquivos permanecem até o usuário clicar no botão **Excluir dados** ao lado, ou até a conta ser excluída. Ambas as ações removem apenas o JSON de trace e as fotos armazenadas daquele usuário. O caminho estável `SCAN_TRACE_STORAGE_DIR` mantém a exclusão disponível mesmo enquanto a nova coleta está desabilitada. Os arquivos são criados com permissões privadas `0700` (diretório) e `0600` (arquivo) e não fazem parte dos backups SQL.

Para analisar traces consentidos dentro do container do backend:

```bash
docker compose exec backend python scripts/analyse_scan_traces.py /app/data/scan-traces --field-nulls --failures
```

O inglês é usado como fonte alternativa preferida para dados sincronizados, imagens e preços ausentes, quando a mesma carta ou set da TCGdex existe em inglês. Cartas exclusivas de uma região que não existem em inglês são mantidas em seus dados no idioma nativo, em vez de serem adivinhadas pelo nome.

Apenas para metadados da Pokédex, os detalhes completos da carta podem inferir um `dexId` ausente da TCGdex a partir de um nome de espécie base exato em inglês ou alemão. Isso cobre cartas como Mega Charizard / Mega-Glurak quando a TCGdex omite o `dexId`, evitando cartas que não são de Pokémon e nomes ambíguos.

O seletor de idioma da UI do app inclui o conjunto de idiomas suportados pela TCGdex, mais sueco. O seletor de idioma de sincronização da TCGdex controla apenas a sincronização de dados de carta/set; mudar o idioma da UI do app não sincroniza automaticamente outros idiomas de carta.

---

## 🔄 Comportamento de Sincronização

O PokéCollector tem caminhos de sincronização separados, para que atualizações de preço frequentes permaneçam leves enquanto atualizações de catálogo ficam controladas.

| Sincronização | Onde roda | O que atualiza | Limites e agendamento |
|------|---------------|-----------------|---------------------|
| Sincronização leve de preços | Botão de sincronização na Home e job automático de preços | Preços das cartas rastreadas em coleções, wishlists e binders | Roda a cada `30` minutos por padrão. Atualiza `max(1000, 75% das cartas únicas rastreadas)`, com limite de `5000` cartas por execução. Cartas sem preço têm prioridade, mas cartas sem preço público têm um cooldown de nova tentativa. |
| Sincronização forçada de preços | Ação `Sync prices only` em Configurações | Preços de todas as cartas rastreadas em coleção, wishlist e binders | Roda sob demanda. Não tem o limite do lote automático leve e ignora o cooldown de novas tentativas para cartas sem preço. Não sincroniza sets, não descobre novas cartas nem atualiza imagens de carta. |
| Sincronização completa | Ação `Sync sets/cards` em Configurações e job automático de sincronização completa | Metadados de sets da TCGdex, listas de cartas, detalhes de cartas ausentes, preços de cartas rastreadas, preços de sets fixados, correspondências de cartas personalizadas, snapshots de portfólio e alertas de wishlist | Roda a cada `5` dias por padrão. A configuração de admin pode alterar isso para `1`, `2`, `3`, `5`, `7`, `14` ou `30` dias. |

A sincronização completa mantém o trabalho pesado de catálogo sob controle:

- sets incompletos e sets em idioma de fallback têm suas listas de cartas atualizadas a cada sincronização completa
- sets nativos já completos são atualizados em um lote rotativo de `25` sets por sincronização completa, ordenados pelo tempo de atualização mais antigo primeiro
- o enriquecimento de metadados de cartas ausentes tem limite separado de `2000` cartas por sincronização completa
- os limites normais de sincronização de preço não aumentam o limite de metadados de carta completa

Com os idiomas de sincronização padrão `en,de`, o lote rotativo de atualização de sets completos cobre o catálogo atual em aproximadamente `70` dias, no intervalo padrão de `5` dias entre sincronizações completas. Sincronizações completas manuais também avançam essa rotação.

---

## 🏗️ Arquitetura

```text
pokecollector/
├── backend/         # FastAPI + SQLAlchemy + PostgreSQL
│   ├── api/         # Roteadores de funcionalidades
│   ├── services/    # Auth, sincronização, agendador, Telegram, integração TCGdex
│   ├── models.py    # Modelos ORM
│   ├── schemas.py   # Schemas Pydantic
│   └── database.py  # Inicialização do banco e migrações idempotentes
├── frontend/        # React 18 + Vite + Tailwind CSS
│   └── src/
│       ├── pages/
│       ├── components/
│       ├── contexts/
│       ├── hooks/
│       ├── i18n/
│       └── api/
└── docker-compose.yml
```

O antigo layout aninhado `pokemon-tcg-collection/` não é mais usado.

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia |
|-------|-----------|
| Frontend | React 18, Vite, Tailwind CSS, TanStack Query |
| Backend | Python 3.11, FastAPI, SQLAlchemy, APScheduler, Pydantic |
| Banco de Dados | PostgreSQL 18 |
| Dados de Cartas | [TCGdex](https://tcgdex.dev/) |
| Scanner de Cartas | Pipeline local: OpenCV + hash perceptual (imagehash) + EasyOCR — sem API externa |
| Deploy | Docker + Docker Compose |

---

## 🌐 Fontes Externas

O PokéCollector é self-hosted, mas pode chamar estas fontes externas dependendo das funcionalidades habilitadas e das ações do usuário:

| Fonte | Host(s) | Usada para | Quando é chamada |
|--------|---------|----------|-------------------|
| TCGdex | `api.tcgdex.net`, `assets.tcgdex.net` | Dados de catálogo de sets/cartas, imagens, preços, metadados de carta localizados, `dexId` da Pokédex e metadados de produto do Cardmarket | Sincronização inicial, sincronização manual/admin, buscas alternativas, backfills de metadados e exibição de imagem de carta |
| Sprites do PokeAPI | `raw.githubusercontent.com/PokeAPI/sprites` | GIFs de perfil/avatar, emblemas de conquistas, ícones de binder, sprites da Pokédex Nacional e cache de artes oficiais | Exibição de imagem no navegador, cache ausente de imagem da Pokédex e `scripts.cache_pokedex_images` |
| Telegram Bot API | `api.telegram.org` | Notificações e alertas via Telegram | Apenas quando as configurações do Telegram estão definidas e um alerta/notificação é enviado |
| Frankfurter | `api.frankfurter.dev` | Taxas de câmbio | Conversão de moeda e formatação de preço no Telegram quando valores fora de EUR são necessários |
| Registro de apoiadores do PokéCollector | `pokecollector.romerg.de` | Nomes públicos de apoiadores estritamente limitados, links de perfil, coroas e detalhes agregados de apoio | O backend self-hosted busca o registro público quando a visão de Comunidade em Configurações é aberta; não há polling recorrente |
| GitHub | `api.github.com`, `raw.githubusercontent.com`, `avatars.githubusercontent.com`, `github.com` | Dados de contribuidores da comunidade, dados históricos de doações de resgate, avatares do GitHub, links de projeto e links de release/código-fonte | Seção de comunidade em Configurações e metadados de projetos vinculados |
| Betterplace | `www.betterplace.org` | Campanha de doação direta para resgate de animais | O navegador apenas abre o link externo da campanha; instâncias self-hosted não chamam a API da Betterplace |
| Cardmarket | `www.cardmarket.com` | Links de produto/busca para cartas | O navegador apenas abre links externos; o PokéCollector não chama nenhuma API do Cardmarket |

O build e a instalação de dependências também contatam registros de pacotes/distribuição, como o npm e o repositório apt do PostgreSQL, quando as imagens Docker são construídas.

---

## 📚 Documentação

| Doc | Descrição |
|-----|-------------|
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Fluxo de trabalho para contribuidores e orientações da interface de carta compartilhada |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Estrutura do sistema, fluxo de dados, contexts, modelo de configurações |
| [`docs/BACKEND.md`](docs/BACKEND.md) | Rotas da API, modelos, escopo de configurações, comportamento de backup |
| [`docs/FRONTEND.md`](docs/FRONTEND.md) | Rotas, páginas, componentes, contexts, temas, i18n |
| [`docs/CARD_SYSTEM.md`](docs/CARD_SYSTEM.md) | Componentes públicos de carta, variantes, galeria e fluxo de extensão |
| [`docs/REVERSE_PROXY_AUTH.md`](docs/REVERSE_PROXY_AUTH.md) | Exceções de forward-auth para perfis e binders públicos |

---

## 🔧 Referência de Configuração

Todas as configurações são persistidas no banco de dados e editadas na UI de Configurações.

| Configuração | Padrão | Notas |
|---------|---------|-------|
| Idioma | `en` | Idioma da UI do app. Opções incluem `en`, `fr`, `es`, `es-mx`, `it`, `pt`, `pt-br`, `pt-pt`, `de`, `nl`, `pl`, `ru`, `ja`, `ko`, `zh-tw`, `id`, `th`, `zh-cn` e `sv`. |
| Moeda | `EUR` | Por usuário |
| Preço Primário | `trend` | Por usuário. Opções: `trend`, `avg`, `avg1`, `avg7`, `avg30`, `low` |
| Modo Multiusuário | `false` | Interruptor restrito ao admin |
| Idiomas de Sincronização TCGdex | `en,de` | Restrito ao admin. Controla quais idiomas de set/carta da TCGdex a sincronização completa busca. Idiomas extras aumentam o tempo de sincronização, as chamadas de API e o tamanho do banco. |
| Fallback de Preço entre Idiomas | `true` | Restrito ao admin. Usa dados de preço em inglês pelo ID exato quando o idioma de carta selecionado não tem dados de preço público nativos. |
| Fallback de Imagem entre Idiomas | `true` | Restrito ao admin. Usa imagens em inglês pelo ID exato quando o idioma de carta selecionado não tem dados de imagem público nativos. |
| Modo Debug | `false` | Restrito ao admin. Habilita log de debug do backend para download. |
| Tema | `default` | Armazenado no local storage do navegador |
| Intervalo de Sincronização de Preço | `30` minutos | Restrito ao admin |
| Intervalo de Sincronização Completa | `5` dias | Restrito ao admin |
| Intervalo de Backfill de Hash das Cartas | `15` minutos | Restrito ao admin. Controla a frequência do backfill incremental automático do banco de hashes do scanner (`card_hashes`). |

### Campos de preço do Cardmarket

Os preços das cartas vêm dos dados de preço do Cardmarket na API da TCGdex e são armazenados em EUR. O preço primário selecionado controla totais de coleção, valores do dashboard, análises, binders, estatísticas sociais, exportações e alertas. A conversão de moeda é apenas para exibição quando USD está selecionado.

| Opção | Campo do Cardmarket | Significado |
|--------|------------------|---------|
| Trend | `trend` / `trend-holo` | Preço de tendência do Cardmarket; o campo disponível mais próximo de um valor de mercado atual, mas ainda um valor agregado da API, não um preço de anúncio ao vivo. |
| Average | `avg` / `avg-holo` | Preço médio de venda no Cardmarket. É estável e próximo do comportamento histórico do app. |
| Avg 1 Day | `avg1` / `avg1-holo` | Média do último dia; bem recente, mas pode ser ruidosa quando há poucas vendas. |
| Avg 7 Days | `avg7` / `avg7-holo` | Média dos últimos sete dias; valor recente mais suavizado. |
| Avg 30 Days | `avg30` / `avg30-holo` | Média dos últimos 30 dias; estável, reage mais devagar. |
| Low | `low` / `low-holo` | Menor preço no Cardmarket; útil como valor conservador, muitas vezes abaixo do valor real de coleção. |

Para itens de coleção holo e reverse-holo, o PokéCollector usa o campo `*-holo` correspondente quando disponível. Se a TCGdex reportar um preço holo como `0` ou ausente, o PokéCollector trata como indisponível e recorre ao campo Cardmarket não-holo selecionado, depois à média do Cardmarket, em vez de avaliar a carta em €0.

---

## 🔄 Atualizando

O PokéCollector tem uma camada de segurança de upgrade embutida para instalações existentes: antes de rodar as migrações de inicialização em uma nova versão do app, o backend cria um backup SQL automático em `./backups` por padrão. A inicialização é interrompida se esse backup automático falhar, a menos que você desabilite explicitamente essa exigência com `PRE_UPGRADE_BACKUP_REQUIRED=false`.

Esse backup automático ainda é apenas uma rede de segurança. Continue fazendo seu próprio backup manual antes de atualizações, especialmente antes de upgrades de versão major do banco.

### Upgrade para PostgreSQL 18

O PokéCollector agora usa PostgreSQL 18 nas instalações via Docker. Instalações Docker existentes que ainda têm um volume de dados do PostgreSQL 15 precisam rodar o script de upgrade único antes de recriar o container do banco com PostgreSQL 18. O PostgreSQL não consegue atualizar um diretório de dados de versão major apenas trocando a imagem Docker.

Você não precisa instalar todas as versões intermediárias do app antes. Atualize da sua instalação atual em PostgreSQL 15 diretamente para este release: o script cuida do upgrade de versão major do banco, e então o backend aplica as migrações cumulativas de inicialização do app. Instalações antigas anteriores ao registro de versão do app também são tratadas como instalações existentes e recebem backup antes dessas migrações.

Primeiro, crie ou verifique um backup manual enquanto sua stack atual em PostgreSQL 15 ainda está rodando:

```bash
docker compose exec postgres pg_dump -U pokemon pokemon_tcg > backup_$(date +%Y%m%d).sql
```

Depois, baixe os arquivos atualizados do projeto, mas ainda não rode o comando normal `docker compose up -d --build`. Também não rode `docker compose down -v` nem remova volumes do Docker antes do script de upgrade terminar; isso apaga o volume antigo do banco e deixa apenas seu backup manual como caminho de recuperação.

```bash
git pull
./scripts/upgrade-postgres-15-to-18.sh
```

O script para os serviços do app para evitar escritas durante o dump, cria um dump SQL a partir do PostgreSQL 15, mantém uma cópia de rollback do volume Docker antigo do PostgreSQL 15, inicializa um volume novo do PostgreSQL 18 usando o layout da imagem Docker do PostgreSQL 18, restaura o dump, e reconstrói/inicia a stack novamente. Ele pede confirmação antes de alterar volumes.

Depois que o script restaura o PostgreSQL 18 e inicia o app, o backup automático de pré-atualização existente ainda roda antes das migrações de inicialização do app quando a versão do app muda. Esse backup automático é uma rede de segurança extra; o dump do PostgreSQL 15 criado pelo script é o backup do upgrade de versão major do banco.

Se você rodar `docker compose up -d --build` acidentalmente antes do script, o container do PostgreSQL 18 se recusa a iniciar ao detectar dados antigos do PostgreSQL no volume existente. Não apague o volume. Rode `./scripts/upgrade-postgres-15-to-18.sh`; se o container original do PostgreSQL 15 já estiver parado, o script pode extrair o dump do volume existente por meio de um container temporário do PostgreSQL 15.

Instalações novas não precisam desse passo. Instalações existentes usam apenas o comando normal de atualização do app abaixo, depois que este upgrade único do PostgreSQL for concluído.

### Atualizações do app

O PokéCollector cria um backup SQL automático antes das migrações de inicialização, quando uma instalação existente sobe em uma nova versão do app. Esse backup de segurança existe para o caso de algo dar errado durante uma atualização, ou de uma migração quebrar depois de uma mudança de versão.

Os backups automáticos são armazenados na pasta de backups montada:

```text
./backups/pre_upgrade_<versao-antiga>_to_<versao-nova>_<timestamp>.sql
```

Por padrão, a inicialização é interrompida se esse backup de segurança falhar. Isso protege coleções de cartas existentes antes que as migrações de versão rodem.

> **Importante:** Sempre crie seu próprio backup manual antes de atualizar a aplicação. O backup automático de pré-atualização é uma rede de segurança extra, não um substituto para um backup verificado sob seu controle.

```bash
docker compose exec postgres pg_dump -U pokemon pokemon_tcg > backup_$(date +%Y%m%d).sql
```

Depois, atualize:

```bash
git pull
docker compose up -d --build
```

As migrações de banco rodam automaticamente na inicialização, depois que o backup de pré-atualização é bem-sucedido. Se precisar reverter, pare o app, volte para a versão anterior do app e restaure o backup SQL correspondente.

---

## 🌱 Projetos da Comunidade

O PokéCollector não é só sobre o app em si. É também sobre as formas como colecionadores organizam e usam suas coleções na vida real.

Um agradecimento especial a [f0rr3stfunk](https://github.com/f0rr3stfunk) pelos testes detalhados, relatos de bugs, feedback, e por compartilhar um projeto muito legal de divisórias de caixa de armazenamento para sets de cartas Pokémon.

As divisórias incluem logos de set e espaço para tags NFC, então aproximar o celular de uma divisória pode abrir a visão do set correspondente no PokéCollector.

Projeto no Makerworld:
https://makerworld.com/de/models/2816777-high-dividers-with-set-logo-nfc-tag#profileId-3136169

---

## ❤️ Apoie o Projeto

Se você quiser apoiar o PokéCollector, pode doar diretamente para resgate de animais através da campanha oficial:

https://pokecollector.romerg.de/#support

A Betterplace processa a doação e a repassa para o projeto de resgate de animais selecionado. O PokéCollector nunca recebe os fundos.

Para aparecer na lista pública de apoiadores, doe de forma não anônima e comece a mensagem pública da Betterplace com `POKECOLLECTOR: Seu nome desejado`. A seção de apoio do site também inclui um formulário de revisão manual sem login. Nomes publicados podem ser corrigidos ou removidos entrando em contato com [info@romerg.de](mailto:info@romerg.de).

As informações de apoiadores aprovadas ficam em um registro privado no servidor do site do PokéCollector. Ele publica apenas a projeção pública versionada em `https://pokecollector.romerg.de/api/v1/supporters`; entradas pendentes, identificadores de provedor, registros de supressão, dados privados de solicitação, bancos de dados e backups nunca são expostos. Cada backend self-hosted do PokéCollector valida essa projeção antes de devolvê-la ao próprio navegador. Ele não mantém cache persistente de apoiadores e mostra um estado temporário de indisponibilidade em vez de dados desatualizados ou hospedados no GitHub sempre que o registro não pode ser validado.

<!-- rescue-donation-total:start -->
**Doações históricas de resgate animal repassadas antes da Betterplace:** €0.00
<!-- rescue-donation-total:end -->

Transferências históricas feitas antes da campanha direta na Betterplace continuam registradas em `RESCUE_DONATIONS.csv`. Depois de atualizar esse CSV, rode `node scripts/update-rescue-donation-total.mjs` para atualizar esse total no README.

---

## 📝 Licença

[GNU AGPLv3](LICENSE)
