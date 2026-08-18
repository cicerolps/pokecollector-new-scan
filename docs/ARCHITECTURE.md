# Visão Geral da Arquitetura

Este documento reflete a estrutura de código atual na raiz do repositório.

## Stack

| Camada | Tecnologia | Porta |
|-------|-----------|------|
| Frontend | React 18 + Vite + Tailwind CSS | 3000 |
| Backend | FastAPI | 8000 |
| Banco de Dados | PostgreSQL 18 | 5432 |
| APIs Externas | TCGdex, Frankfurter, GitHub | externo |
| Containerização | Docker + docker compose | - |

O reconhecimento de cartas (scanner) **não** usa API externa — roda inteiramente no backend local. Veja [Fluxo do Scanner](#fluxo-do-scanner) abaixo.

## Estrutura de Diretórios

```text
pokecollector/
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── api/
│   │   ├── auth.py
│   │   ├── backup.py
│   │   ├── binders.py
│   │   ├── cards.py
│   │   ├── collection.py
│   │   ├── dashboard.py
│   │   ├── export.py
│   │   ├── github.py
│   │   ├── images.py
│   │   ├── products.py
│   │   ├── recognize.py
│   │   ├── scan_jobs.py
│   │   ├── settings.py
│   │   ├── sets.py
│   │   ├── social.py
│   │   ├── sync.py
│   │   └── wishlist.py
│   └── services/
│       ├── auth.py
│       ├── card_fallbacks.py
│       ├── card_scan_preprocess.py   # OpenCV: recorte, warp, normalização
│       ├── card_scan_hash.py         # Hash perceptual + busca de candidatos
│       ├── card_scan_ocr.py          # EasyOCR: leitura do número da carta
│       ├── card_scan_resolver.py     # Orquestra o pipeline de reconhecimento local
│       ├── pokemon_api.py
│       ├── pre_upgrade_backup.py
│       ├── scan_queue.py
│       ├── scan_storage.py
│       ├── scan_trace.py
│       ├── scheduler.py
│       ├── sync_service.py
│       ├── tcgdex_languages.py
│       └── telegram.py
├── frontend/
│   ├── src/
│   │   ├── api/client.js
│   │   ├── components/
│   │   │   ├── AppNav.jsx
│   │   │   ├── CardItem.jsx
│   │   │   ├── CardScanner.jsx
│   │   │   ├── Layout.jsx
│   │   │   └── TabNav.jsx
│   │   ├── contexts/
│   │   │   ├── AuthContext.jsx
│   │   │   └── SettingsContext.jsx
│   │   ├── hooks/
│   │   │   └── useTheme.js
│   │   ├── i18n/        # Pacotes de tradução do app
│   │   ├── utils/       # Helpers compartilhados do frontend, incluindo registros de idioma
│   │   └── pages/
│   └── index.html
├── docs/
├── docker-compose.yml
└── README.md
```

Removido da arquitetura atual:

- sem `backend/api/ebay.py`
- sem `services/notifications.py`
- sem o antigo diretório aninhado `pokemon-tcg-collection/`
- sem `services/gemini_rate_limit.py` e `services/card_composite.py` (removidos junto com o Gemini)

## Arquitetura do Backend

### Registro de Rotas

`backend/main.py` registra os roteadores de funcionalidades sob `/api/*`.

Módulos importantes adicionados desde a documentação antiga:

- `api/auth.py`
- `api/github.py`
- `api/images.py`
- `api/products.py`

### Modelo de Dados

Principais modelos ORM em `backend/models.py`:

- `Set`
- `Card`
- `CardHash` — hashes perceptuais (phash/dhash/whash) por carta, usados pelo scanner local
- `User`
- `CollectionItem`
- `WishlistItem`
- `Binder`
- `BinderCard`
- `ProductPurchase`
- `SyncLog`
- `PortfolioSnapshot`
- `Setting`
- `UserSetting`
- `CustomCardMatch`
- `ImageCache`
- `ScanJob`
- `ScanJobItem`
- `ScanQueueUserState`

Regras atuais notáveis do modelo:

- `Set.id` e `Card.id` são ids compostos com sufixos de idioma da TCGdex, incluindo códigos de várias partes como `zh-tw` e `pt-br`
- `Card.rarity` vem da TCGdex e é tratado como metadado somente leitura
- Os idiomas de origem do fallback de dados, imagem e preço de carta são marcados quando dados de fallback pelo ID exato em inglês são usados
- Variantes de coleção são limitadas às variantes físicas de impressão
- Itens de wishlist armazenam quantidade solicitada de `1` a `99`
- `User.must_change_password` conduz o fluxo de troca de senha obrigatória
- `UserSetting` armazena preferências e segredos por usuário
- `CardHash` é populado por `backend/scripts/backfill_card_hashes.py` e consultado pelo scanner a cada tentativa de reconhecimento

## Arquitetura de Configurações

As configurações são divididas entre dois armazenamentos:

- Tabela global `settings`
- Tabela `user_settings`, por usuário

A divisão é definida em `backend/api/settings.py`:

- `PER_USER_KEYS`
  - idioma
  - moeda
  - preferências de exibição de preço
  - chaves do Telegram e preferências de alerta
  - consentimento de diagnóstico do scanner
  - nome de treinador
- `ADMIN_ONLY_KEYS`
  - intervalo de sincronização completa
  - intervalo de sincronização de preço
  - modo multiusuário
  - idiomas de sincronização da TCGdex

Na prática:

- usuários normais só podem alterar suas próprias configurações por usuário
- admins também podem alterar configurações operacionais globais
- o isolamento de configurações por usuário é aplicado na camada de API
- `tcgdex_sync_languages` controla quais idiomas de set/carta da TCGdex a sincronização completa busca. O padrão é `en,de`; idiomas extras são opcionais porque aumentam o tempo de sincronização, as chamadas de API e o tamanho do banco.
- Valores inválidos ou vazios de `TCGDEX_SYNC_LANGUAGES` caem com segurança para `en,de` durante o primeiro bootstrap; o valor `all` se expande para todos os idiomas suportados pela TCGdex
- A seleção de idioma da UI do app é separada da seleção de idioma de sincronização da TCGdex. O seletor da UI inclui todos os códigos de idioma suportados pela TCGdex, mais sueco.

## Arquitetura de Autenticação

A autenticação vive em:

- `backend/api/auth.py`
- `backend/services/auth.py`
- `frontend/src/contexts/AuthContext.jsx`

Modelo de autenticação atual:

- O modo usuário único retorna o usuário admin em `get_current_user()` quando nenhum token está presente
- O modo multiusuário exige autenticação JWT
- `/api/auth/mode` expõe se o app está em modo usuário único ou multiusuário
- `must_change_password` é retornado por `/api/auth/login` e `/api/auth/me`
- O frontend bloqueia rotas protegidas até que a troca de senha obrigatória seja concluída

## Fluxo do Scanner

O reconhecimento é implementado em `backend/api/recognize.py` (que delega para `backend/services/card_scan_resolver.py`) e exposto através de `frontend/src/components/UnifiedCardScanner.jsx`, `frontend/src/pages/ScanQueue.jsx`, e os componentes compartilhados de adição/revisão.

Fluxo atual — **100% local, sem chamada a API externa**:

1. O usuário captura ou envia até 50 fotos. Os uploads têm tamanho limitado, são recodificados, normalizados de orientação, têm metadados removidos e são armazenados como arquivos JPEG privados.
2. Cada foto é processada individualmente (não há mais agrupamento composto de várias cartas por foto — veja a nota abaixo).
3. `card_scan_preprocess.py` localiza os quatro cantos da carta na foto (rejeitando contornos que não têm formato de carta), aplica correção de perspectiva (warp) e normaliza a iluminação (CLAHE). Se nenhum contorno confiável for encontrado, a imagem inteira é usada como fallback.
4. `card_scan_hash.py` calcula três hashes perceptuais (phash/dhash/whash, via `imagehash`) da imagem normalizada — testando também as quatro rotações possíveis — e busca os candidatos mais próximos na tabela `card_hashes` por distância de Hamming combinada.
5. A confiança é avaliada pela distância do melhor candidato e pela diferença (gap) para o segundo colocado, configuráveis via `SCAN_HASH_TOP_N`, `SCAN_HASH_CONFIDENCE_GAP` e `SCAN_HASH_NO_MATCH_DISTANCE`: `confident` (correspondência única e clara), `ambiguous` (dois ou mais candidatos próximos) ou `no_match`.
6. Quando o resultado é `ambiguous`, `card_scan_ocr.py` recorta a região inferior direita da carta e usa EasyOCR para ler o número local e o total impresso do set, desempatando entre os candidatos por número de coleção.
7. Os resultados são persistidos na caixa de revisão `/scans`. Confirmar ou descartar um item apaga sua foto na fila; jobs não resolvidos expiram após 14 dias.

> **Nota:** o escaneamento composto (várias cartas detectadas e recortadas automaticamente de uma única foto) existia na versão baseada em Gemini e foi removido nesta troca de mecanismo — ainda não há um equivalente local para essa detecção de grade. Toda foto é escaneada individualmente por enquanto.

`backend/services/scan_queue.py` fornece um despacho justo em segundo plano, resistente a reinícios, com leases. As tentativas de reconhecimento têm um limite (atualmente três), e falhas transitórias usam backoff genérico com nova tentativa — não há mais lógica de cota compartilhada por chave de API, porque não existe mais nenhuma API externa envolvida no reconhecimento.

Diagnósticos opcionais vivem em `backend/services/scan_trace.py`. O servidor precisa definir `SCAN_TRACE_DIR`, e cada usuário precisa habilitar separadamente **Compartilhar diagnóstico do scanner** (desligado por padrão). Apenas tentativas com consentimento armazenam uma foto sanitizada mais a decisão final do scanner (correspondência por hash, hash+OCR, ou sem correspondência) e o candidato selecionado. Desligar o interruptor interrompe futuros traces sem apagar os antigos; a ação de exclusão ao lado remove a subárvore de traces daquele usuário. `SCAN_TRACE_STORAGE_DIR` permanece estável quando a coleta está desabilitada, para que a exclusão explícita e a exclusão de conta ainda encontrem dados antigos. A exclusão de conta grava um marcador de revogação antes da limpeza, para que uma tentativa em andamento não recrie os arquivos do usuário excluído. Nenhuma credencial de autenticação é registrada — e, diferente da versão anterior, não existe mais nenhuma chave de API envolvida no scanner.

## Estado do Frontend

Camadas de estado atuais do frontend:

- Estado do servidor: TanStack Query
- Estado de autenticação: `AuthContext`
- Estado de configurações e i18n: `SettingsContext`
- Estado local de UI: `useState` no nível do componente
- Estado de tema: `useTheme` com `data-theme` e local storage

`AuthContext` agora é parte central da arquitetura do app, não um recurso opcional.

## Arquitetura de Navegação

- `HomeScreen.jsx` é o ponto de entrada compacto do portal
- `Layout.jsx` envolve as rotas protegidas
- `AppNav.jsx` fornece a faixa de título da página e o controle de logout
- `TabNav.jsx` é o componente de abas compartilhado usado nas telas principais

## Integrações

### TCGdex

- Fonte de verdade para sets e cartas
- Flags de disponibilidade de variante vêm da TCGdex
- A raridade é lida da TCGdex e exibida como somente leitura
- Os idiomas de sincronização suportados são centralizados em `backend/services/tcgdex_languages.py`
- O inglês é o fallback preferido para dados, imagens e preços ausentes apenas quando a mesma carta ou set da TCGdex existe em inglês com o mesmo ID exato
- Cartas exclusivas de uma região não são adivinhadas pelo nome traduzido

### Reconhecimento local de cartas

- Implementado em `backend/services/card_scan_preprocess.py`, `card_scan_hash.py`, `card_scan_ocr.py` e `card_scan_resolver.py`
- Não depende de nenhuma API externa, chave, ou conexão de rede — todo o processamento acontece no próprio backend
- O banco de hashes (`card_hashes`) precisa ser populado com `backend/scripts/backfill_card_hashes.py` depois de cada sincronização de catálogo que adicione cartas novas
- EasyOCR baixa os pesos do modelo apenas durante o build da imagem Docker (`EASYOCR_MODEL_DIR`), não em tempo de execução

### Telegram

- Implementado em `backend/services/telegram.py`
- O serviço aceita `user_id` para que os alertas usem as credenciais do Telegram daquele usuário

### GitHub / Comunidade

- `backend/api/github.py` busca contribuidores pela API do GitHub
- `backend/api/community.py` é o único cliente do registro público versionado de apoiadores em `pokecollector.romerg.de`
- As respostas de apoiadores têm tamanho limitado e são estritamente validadas antes do uso; campos desconhecidos, valores inseguros, respostas malformadas, redirecionamentos e falhas do upstream são rejeitados
- Os dados de apoiadores não são persistidos nem servidos por um fallback. A visão de Comunidade busca a cada entrada, mantém apenas um cache em memória no navegador entre entradas, e esconde o cache enquanto essa busca está pendente ou depois que ela falha; não há polling recorrente
- `frontend/src/pages/Settings.jsx` renderiza os contribuidores e a projeção validada de apoiadores na seção de Comunidade

## Notas de Segurança

- Endpoints de sincronização são restritos ao admin
- Backup e restauração são restritos ao admin
- As chaves de configuração são separadas em escopos restritos ao admin e por usuário
- O logout do frontend limpa o local storage e força um reload completo para evitar vazamento de dados de usuário em cache entre sessões
- A exclusão de usuário remove explicitamente as linhas de propriedade dele em coleção, wishlist, binders, produtos, snapshots de portfólio e configurações de usuário antes de excluir o usuário

## Notas de Migração

Mudanças de schema são tratadas por SQL idempotente em `backend/database.py`, não por Alembic.

Alguns comentários de migração ainda mencionam funcionalidades históricas, mas a arquitetura de runtime atual não inclui integração com eBay nem expõe grading na UI ou no modelo ORM ativos. A tabela `gemini_quota_state`, criada por versões anteriores do app, também não é mais criada por novas migrações — instalações que já a tinham a mantêm como uma tabela órfã inofensiva.
