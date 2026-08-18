# Referência do Frontend

SPA em React 18 construída com Vite. O código-fonte fica em `frontend/src/`.

## Tabela de Rotas

As rotas são definidas em `frontend/src/App.jsx`.

| Rota | Arquivo do Componente | Notas |
|------|----------------|-------|
| `/login` | `pages/Login.jsx` | Tela de login multiusuário |
| `/` | `pages/HomeScreen.jsx` | Tela inicial estilo portal |
| `/dashboard` | `pages/Dashboard.jsx` | Resumo de portfólio |
| `/search` | `pages/CardSearch.jsx` | Busca de cartas, entrada do scanner e adição em lote com seleção múltipla |
| `/scans` | `pages/ScanQueue.jsx` | Caixa de entrada persistente de escaneamento |
| `/scans/:jobId` | `pages/ScanQueue.jsx` | Revisa um job de escaneamento na fila |
| `/collection` | `pages/Collection.jsx` | Coleção do usuário |
| `/collection/user/:userId` | `pages/UserCollection.jsx` | Visão somente leitura da coleção de outro usuário |
| `/sets` | `pages/Sets.jsx` | Navegador de sets |
| `/sets/:setId` | `pages/SetDetail.jsx` | Checklist do set |
| `/wishlist` | `pages/Wishlist.jsx` | Wishlist e alertas |
| `/binders` | `pages/Binders.jsx` | Lista de binders |
| `/binders/:binderId` | `pages/BinderDetail.jsx` | Detalhe do binder |
| `/analytics` | `pages/Analytics.jsx` | Abas de análises |
| `/products` | `pages/Products.jsx` | Produtos lacrados |
| `/leaderboard` | `pages/Leaderboard.jsx` | Leaderboard multiusuário |
| `/leaderboard/compare/:userId` | `pages/Compare.jsx` | Comparação entre treinadores |
| `/achievements` | `pages/Achievements.jsx` | Conquistas do usuário atual |
| `/achievements/:userId` | `pages/Achievements.jsx` | Conquistas de outro usuário |
| `/settings` | `pages/Settings.jsx` | Configurações do app e ferramentas de admin |
| `/migration` | `pages/CardMigration.jsx` | Fila de migração de cartas personalizadas |

## Fluxo de Autenticação

### `AuthContext`

Definido em `frontend/src/contexts/AuthContext.jsx`.

Responsabilidades:

- Busca `/api/auth/mode` na inicialização
- No modo usuário único, tenta `/api/auth/me` sem token
- No modo multiusuário, restaura o usuário a partir do token armazenado, se presente
- Expõe:
  - `user`
  - `loading`
  - `multiUser`
  - `loginUser(token, userData)`
  - `updateCurrentUser(updates)`
  - `logout()`

Comportamento relacionado à segurança:

- `logout()` remove o token e o usuário do local storage
- O logout força um reload completo da página para limpar os dados em cache do React Query e evitar vazamento entre usuários
- O Axios também limpa o estado de autenticação em respostas `401`

### Login e Troca de Senha

- `pages/Login.jsx` só é usado quando `multiUser === true`
- `App.jsx` define uma `ForcePasswordChangeScreen` embutida
- Se `user.must_change_password` for verdadeiro, as rotas normais do app ficam bloqueadas até `/api/auth/me/force-password` ter sucesso

## Configurações & Localização

### `SettingsContext`

Definido em `frontend/src/contexts/SettingsContext.jsx`.

Fornece:

- `settings`
- `updateSettings(updates)`
- `t(path)`
- `language`
- `priceDisplay`
- `pricePrimary`
- `pricePrimaryField`
- `currency`
- `currencySymbol`
- `exchangeRate`
- `formatPrice(eurAmount)`
- `formatUsdPrice(usdAmount)`

Notas:

- Os pacotes de tradução são carregados de `frontend/src/i18n/` e conectados no `SettingsContext`
- Os idiomas de UI incluem todos os códigos de idioma suportados pela TCGdex, mais sueco. Variantes regionais como `es-mx`, `pt-br`, `pt-pt`, `zh-tw` e `zh-cn` são selecionáveis em um dropdown compacto em Configurações.
- Configurações antigas armazenadas como `zh` são normalizadas no frontend para `zh-cn` na exibição
- A exibição em USD usa taxas de câmbio do endpoint Frankfurter no backend

### `useTheme`

Definido em `frontend/src/hooks/useTheme.js`.

- Armazena o tema selecionado no `localStorage`
- Aplica o tema via `data-theme` em `document.documentElement`
- Temas disponíveis:
  - `default`
  - `fire`
  - `water`
  - `grass`
  - `electric`
  - `psychic`
  - `dragon`
  - `dark`
  - `fairy`

## Navegação

### Navegação Home / Portal

- `pages/HomeScreen.jsx` é a visão principal do portal
- O app agora usa um padrão de navegação compacto, com 6 itens principais do portal na tela inicial
- Seções secundárias são organizadas com abas agrupadas nas páginas individuais

### `TabNav`

Definido em `frontend/src/components/TabNav.jsx`.

- Barra de abas horizontal reutilizável
- Marca uma aba como ativa se o pathname atual for igual ou começar com o caminho da aba
- Usado por páginas como `Dashboard`, `Collection`, `Wishlist`, `Binders`, `Analytics`, `Products`, `Leaderboard` e `Achievements`

### `Layout` e `AppNav`

- `components/Layout.jsx` envolve as rotas protegidas
- `components/AppNav.jsx` mostra o título da página atual e o controle de logout multiusuário

## Telas Principais

### `pages/Login.jsx`

- Tela de login multiusuário
- Suporta retorno rápido ao último usuário logado via `lastUser` e `lastUserAvatar` no local storage

### `pages/Leaderboard.jsx`

- Visão de ranking social para o modo multiusuário
- Usa `TabNav`

### `pages/Compare.jsx`

- Comparação lado a lado entre treinadores
- Parâmetro de rota: `userId`

### `pages/Achievements.jsx`

- Mostra as conquistas do usuário atual, ou de outro usuário quando `:userId` está presente

### `pages/Settings.jsx`

- Mistura preferências por usuário e controles restritos ao admin
- Usuários admin podem habilitar o modo multiusuário em Configurações
- Quando o modo multiusuário está habilitado, usuários admin veem uma aba **Usuários**
- A aba **Usuários** suporta criar usuários, editar nome de usuário/papel/senha, ativar/desativar usuários, excluir outros usuários e forçar a troca de senha no primeiro login
- Inclui:
  - edição de nome de perfil
  - seletor de avatar
  - seletor de tema
  - dropdown de idioma do app e controles de moeda
  - seleção de idiomas de sincronização da TCGdex para admins
  - chave do Telegram
  - consentimento por usuário para diagnóstico do scanner e exclusão explícita dos dados armazenados
  - controles de sincronização
  - interruptor de modo de autenticação
  - backup e restauração
  - seções de Comunidade para contribuidores e apoiadores

A seção de apoiadores chama o endpoint próprio da instalação `/api/community/supporters` uma vez, sempre que a visão de Comunidade é aberta. Ela mantém apenas o último resultado válido no cache em memória de query do navegador, esconde esse cache enquanto a busca de entrada está pendente ou depois que ela falha, e não faz atualizações programadas, em segundo plano ou por foco. Acima dos cartões de apoiadores, mostra a contagem de apoiadores, a contagem combinada de doações e os totais exatos conhecidos por moeda, agrupados por moeda; registros de moeda mista são identificados em vez de combinados em um valor enganoso. O navegador nunca chama o registro do site público diretamente, e nenhuma projeção de apoiadores é persistida pela instalação.

## UI de Cartas

### Sistema de cartas compartilhado

As páginas de funcionalidades importam a API pública de `frontend/src/components/card-system`. Seus componentes de alto nível são `CardDisplay`, `CardRow`, `CardIdentity`, `CardDialog`, `CardLegend` e `CardStack`.

O sistema centraliza a estrutura da carta, bordas, tratamento de imagem, badges, estados de propriedade/indisponibilidade, comportamento responsivo e interações de teclado/toque. As páginas fornecem dados, layout e ações, em vez de montar suas próprias visuais de carta.

As variantes aprovadas de `CardDisplay` incluem `grid`, `carousel`, `ranking`, `selectable`, `artwork` e `compact-artwork`. Uma galeria de componentes, disponível apenas em desenvolvimento, fica em `/__card-system`.

Veja [`CARD_SYSTEM.md`](CARD_SYSTEM.md) para uso, tokens de design, orientação de revisão e o processo, amigável a contribuidores, para propor uma nova variante compartilhada.

`CardItem.jsx`, `UnifiedCard.jsx` e os componentes de estado de baixo nível continuam sendo detalhes de implementação desse sistema público, e não devem ser importados por páginas de funcionalidades.

### `pages/CardSearch.jsx`

- UI principal de busca para cartas da TCGdex cacheadas localmente e cartas personalizadas correspondentes
- Suporta modo de seleção nos resultados de busca
- Pode selecionar a página atual ou todos os resultados de busca correspondentes
- A adição em lote envia as cartas selecionadas para `/api/collection/bulk-add` com quantidade padrão `1`, condição `NM`, sem variante, sem preço de compra, e o idioma da carta
- O toast de sucesso da adição em lote reporta as contagens de adicionados, atualizados e falhos

### Scanner e caixa de revisão

`components/UnifiedCardScanner.jsx` é o ponto de entrada apenas de captura. Ele suporta a câmera nativa do dispositivo e uploads de galeria, prepara uma ou mais fotos, permite substituições de reconhecimento individual por foto, e inclui um guia de posicionamento opcional ao lado de **Tirar foto**. Toda submissão enfileira um job persistente e roteia para a mesma caixa de revisão, incluindo um escaneamento de uma única foto.

`pages/ScanQueue.jsx` e `components/ScanReview.jsx` mostram o progresso do job, contagens regressivas/motivos de nova tentativa, fotos de origem sanitizadas, candidatos classificados, itens com falha, nova tentativa individual, descarte e revisão de adição à coleção. O selo de navegação conta os itens pendentes. O id do candidato confirmado é enviado ao resolver um item, para que diagnósticos com consentimento possam ser rotulados com a verdade de referência revisada por humano.

As contagens regressivas de nova tentativa mostram por que uma nova tentativa foi agendada e quando ela vai rodar — o pipeline de reconhecimento é totalmente local, então não há mais distinção de cota diária de um provedor externo, apenas o backoff genérico de falhas transitórias. Fotos ficam disponíveis apenas enquanto seu item precisa de revisão e são apagadas na confirmação/descarte; jobs expiram após 14 dias.

A seção IA/Scanner de Cartas em `pages/Settings.jsx` mostra **Compartilhar diagnóstico do scanner** como um controle disponível apenas quando o servidor configurou um armazenamento gravável em `SCAN_TRACE_DIR`. O interruptor vem desligado por padrão. Desligá-lo interrompe o rastreamento futuro sem apagar os dados existentes; o botão de exclusão confirmado ao lado remove todos os diagnósticos armazenados do usuário atual e continua disponível pelo caminho estável de limpeza mesmo quando a nova coleta está desabilitada.

## Camada de API

`frontend/src/api/client.js` é o cliente Axios central.

Vínculos notáveis de API no frontend incluem:

- endpoints de modo de autenticação e troca de senha forçada
- endpoints de comunidade do GitHub
- endpoints sociais para leaderboard / comparação / conquistas
- download seletivo de backup via `downloadBackup(include)`

## Removido / Não Mais Documentado

- Sem integração com eBay no frontend atual
- Sem UI de grading no frontend atual
