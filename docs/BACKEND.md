# Referência do Backend

Ponto de entrada do app FastAPI: `backend/main.py`.

## Rotas da API

### Autenticação

| Método | Rota | Notas |
|--------|------|-------|
| POST | `/api/auth/login` | Login por usuário/senha |
| GET | `/api/auth/me` | Usuário atualmente autenticado |
| GET | `/api/auth/mode` | Retorna `{ multi_user: boolean }` |
| PUT | `/api/auth/mode` | Interruptor restrito ao admin entre modo usuário único e multiusuário |
| GET | `/api/auth/users` | Lista de usuários, restrita ao admin |
| POST | `/api/auth/users` | Criação de usuário, restrita ao admin |
| PUT | `/api/auth/users/{user_id}` | Atualização de usuário, restrita ao admin |
| DELETE | `/api/auth/users/{user_id}` | Exclusão de usuário, restrita ao admin; propaga a limpeza dos dados de propriedade dele |
| PUT | `/api/auth/me/password` | Trocar senha com a senha atual |
| PUT | `/api/auth/me/force-password` | Completa a troca de senha obrigatória no primeiro login |
| PUT | `/api/auth/me/avatar` | Atualiza o avatar do usuário atual |
| PUT | `/api/auth/me/username` | Atualiza o nome de perfil do usuário atual |

### Cartas

| Método | Rota | Notas |
|--------|------|-------|
| GET | `/api/cards/search` | Busca local de cartas |
| GET | `/api/cards/custom` | Lista as cartas personalizadas e templates compartilhados do usuário atual |
| POST | `/api/cards/custom` | Cria uma carta personalizada restrita ao dono |
| POST | `/api/cards/custom/{card_id}/clone` | Copia um template compartilhado em uma carta privada independente |
| PUT | `/api/cards/custom/{card_id}` | Atualização de carta personalizada, restrita ao dono |
| DELETE | `/api/cards/custom/{card_id}` | Exclusão de carta personalizada, restrita ao dono |
| GET | `/api/cards/custom/matches` | Correspondências pendentes de migração de carta personalizada |
| POST | `/api/cards/custom/migrate/{match_id}` | Migra carta personalizada para carta da API |
| POST | `/api/cards/custom/dismiss/{match_id}` | Descarta a correspondência |
| GET | `/api/cards/{card_id}/lang/{lang}` | Resolve a carta equivalente em outro idioma |
| GET | `/api/cards/{card_id}/price-history` | Histórico de preço |
| PUT | `/api/cards/{card_id}/custom-image` | Define uma URL de imagem personalizada temporária |
| GET | `/api/cards/{card_id}` | Detalhe da carta |
| POST | `/api/cards/recognize` | Reconhecimento local de carta (hash perceptual + OCR), sem API externa |
| POST | `/api/cards/recognize/jobs` | Sanitiza e enfileira até 50 fotos de escaneamento persistente |
| GET | `/api/cards/recognize/jobs` | Jobs de escaneamento ativos/acionáveis do usuário atual |
| GET | `/api/cards/recognize/jobs/{job_id}` | Job de escaneamento e itens de revisão, restritos ao usuário |
| GET | `/api/cards/recognize/jobs/{job_id}/items/{item_id}/image` | Foto de revisão sanitizada e privada |
| POST | `/api/cards/recognize/jobs/{job_id}/items/{item_id}/resolve` | Confirma/descarta um item e apaga sua foto na fila |
| POST | `/api/cards/recognize/jobs/{job_id}/items/{item_id}/retry` | Tenta novamente um item revisável individualmente |
| DELETE | `/api/cards/recognize/jobs/{job_id}` | Exclui um job e suas fotos na fila |

Cartas personalizadas pertencem a exatamente um usuário. Donos podem publicar uma carta como template compartilhado, mas outros usuários precisam cloná-la antes de usá-la em coleções, wishlists, binders, produtos ou trocas. Clones têm IDs, metadados, imagens e preços independentes. URLs de imagem manual precisam usar destinos HTTPS públicos e são buscadas através do proxy de imagem com limite de tamanho. Durante o upgrade, cartas personalizadas existentes viram templates compartilhados de propriedade da primeira conta admin criada, enquanto cada outro usuário que as referenciava recebe um clone privado e mantém suas referências existentes.

### Coleção, Sets, Wishlist, Binders

| Método | Rota | Notas |
|--------|------|-------|
| GET | `/api/collection/` | Coleção do usuário |
| GET | `/api/collection/user/{user_id}` | Vê a coleção de outro usuário (somente leitura, requer autenticação) |
| POST | `/api/collection/` | Adiciona à coleção |
| POST | `/api/collection/bulk-add` | Adiciona cartas selecionadas em lote; cada item é commitado independentemente e reporta as contagens de adicionados/atualizados/falhos |
| POST | `/api/collection/import-csv` | Importação estrita de coleção via CSV, com validação tudo-ou-nada |
| PUT | `/api/collection/{item_id}` | Atualiza item da coleção |
| DELETE | `/api/collection/{item_id}` | Exclui item da coleção |
| GET | `/api/collection/stats/summary` | Resumo da coleção |
| GET | `/api/sets/` | Lista sets |
| GET | `/api/sets/new` | Sets recém-detectados |
| POST | `/api/sets/mark-seen` | Marca os selos de sets novos como vistos |
| GET | `/api/sets/{set_id}` | Detalhe do set |
| GET | `/api/sets/{set_id}/checklist` | Checklist do set |
| GET | `/api/wishlist/` | Wishlist |
| POST | `/api/wishlist/` | Adiciona item à wishlist |
| PUT | `/api/wishlist/{item_id}` | Atualiza quantidade e alertas de preço da wishlist |
| DELETE | `/api/wishlist/{item_id}` | Remove item da wishlist |
| GET | `/api/binders/` | Binders |
| POST | `/api/binders/` | Cria binder |
| PUT | `/api/binders/{binder_id}` | Atualiza binder |
| DELETE | `/api/binders/{binder_id}` | Exclui binder |
| GET | `/api/binders/{binder_id}/cards` | Cartas do binder |
| GET | `/api/binders/{binder_id}/optimize-prints` | Prévia da otimização de impressões equivalentes |
| POST | `/api/binders/{binder_id}/optimize-prints` | Aplica a otimização de impressões equivalentes |
| POST | `/api/binders/{binder_id}/cards` | Adiciona carta ao binder |
| POST | `/api/binders/{binder_id}/collection-items` | Adiciona item de coleção já possuído ao binder |
| PUT | `/api/binders/{binder_id}/entries/{binder_card_id}` | Atualiza a quantidade de uma entrada do binder |
| GET | `/api/binders/{binder_id}/entries/{binder_card_id}/equivalent-prints` | Lista impressões equivalentes para uma entrada |
| PUT | `/api/binders/{binder_id}/entries/{binder_card_id}/card` | Troca uma entrada para uma impressão equivalente |
| POST | `/api/binders/{binder_id}/entries/{binder_card_id}/wishlist` | Move a entrada do binder para a wishlist |
| POST | `/api/binders/{binder_id}/wishlist` | Adiciona carta da wishlist ao binder |
| GET | `/api/binders/{binder_id}/export-csv` | Exportação CSV do binder |
| POST | `/api/binders/{binder_id}/import-csv` | Importação CSV do binder |
| DELETE | `/api/binders/{binder_id}/entries/{binder_card_id}` | Remove entrada do binder |
| DELETE | `/api/binders/{binder_id}/cards/{card_id}` | Remove carta do binder |

### Dashboard, Análises, Social, Comunidade

| Método | Rota | Notas |
|--------|------|-------|
| GET | `/api/dashboard/` | Resumo do dashboard |
| GET | `/api/analytics/duplicates` | Cartas duplicadas |
| GET | `/api/analytics/top-movers` | Maiores variações de preço |
| GET | `/api/analytics/rarity-stats` | Distribuição de raridade |
| GET | `/api/analytics/investment-tracker` | Histórico de portfólio |
| GET | `/api/analytics/new-sets` | Sets novos nas análises |
| GET | `/api/social/leaderboard` | Leaderboard multiusuário |
| GET | `/api/social/compare/{user_id}` | Comparação multiusuário |
| GET | `/api/social/achievements/{user_id}` | Progresso de conquistas |
| GET | `/api/github/contributors` | Feed público de contribuidores do GitHub |
| GET | `/api/community/supporters` | Projeção atualizada e estritamente validada do registro público de apoiadores; retorna `503` com `Cache-Control: no-store` em qualquer falha de upstream ou de validação |
| GET | `/api/github/rescue-donations` | Total de doações de resgate a partir de `RESCUE_DONATIONS.csv` |

### Produtos, Exportação, Backup, Sincronização, Configurações

| Método | Rota | Notas |
|--------|------|-------|
| GET | `/api/products/types` | Sugestões de tipo de produto |
| GET | `/api/products/` | Lista de produtos |
| POST | `/api/products/` | Cria produto |
| PUT | `/api/products/{product_id}` | Atualiza produto |
| DELETE | `/api/products/{product_id}` | Exclui produto |
| GET | `/api/products/summary` | Resumo de produtos |
| GET | `/api/products/{product_id}` | Detalhe do produto |
| POST | `/api/products/{product_id}/cards` | Vincula cartas da coleção ao produto |
| DELETE | `/api/products/{product_id}/cards/{product_card_id}` | Desvincula carta do produto |
| POST | `/api/products/{product_id}/cards/{product_card_id}/sell` | Registra venda de carta do produto |
| POST | `/api/products/{product_id}/ledger` | Adiciona lançamento ao livro-razão do produto |
| GET | `/api/export/csv` | Exportação CSV |
| GET | `/api/export/pdf` | Exportação PDF |
| GET | `/api/backup/download` | Backup SQL, restrito ao admin |
| POST | `/api/backup/restore` | Restauração SQL, restrita ao admin |
| POST | `/api/backup/clear-image-cache` | Limpeza do cache de imagens, restrita ao admin |
| POST | `/api/sync/` | Sincronização completa, restrita ao admin |
| POST | `/api/sync/prices` | Sincronização leve de preços, restrita ao admin |
| POST | `/api/sync/prices/all` | Sincronização forçada de preços para todas as cartas rastreadas, restrita ao admin |
| POST | `/api/sync/reschedule-full` | Reagenda a sincronização completa |
| POST | `/api/sync/reschedule-prices` | Reagenda a sincronização de preços |
| GET | `/api/sync/status` | Status e histórico de sincronização |
| GET | `/api/card-hashes/status` | Cobertura do banco de hashes do scanner (total/hasheadas/faltando) e se um backfill está rodando, restrito ao admin |
| POST | `/api/card-hashes/backfill` | Dispara um backfill de hashes em segundo plano; `{"force": false}` para incremental, `{"force": true}` para recalcular tudo, restrito ao admin |
| POST | `/api/card-hashes/reschedule` | Reagenda o backfill automático de hashes, restrito ao admin |
| GET | `/api/images/card/{card_id}/{size}` | Proxy/cache de imagem de carta |
| GET | `/api/images/set/{set_id}/{image_type}` | Proxy/cache de logo/símbolo de set |
| GET | `/api/settings/` | Configurações efetivas do usuário atual |
| GET | `/api/settings/tcgdex-languages` | Metadados de idiomas suportados pela TCGdex |
| PUT | `/api/settings/` | Atualiza configurações |
| GET | `/api/settings/debug-log` | Download do log de debug, restrito ao admin |
| DELETE | `/api/settings/scan-diagnostics` | Exclui todo o diagnóstico de scanner persistido do usuário atual |
| GET | `/api/settings/telegram_status` | Se o Telegram está configurado para o usuário atual |
| GET | `/api/settings/exchange-rate` | Consulta de taxa de câmbio para a moeda de exibição |
| GET | `/api/settings/{key}` | Obtém uma configuração |
| POST | `/api/settings/{key}` | Define uma configuração |

## Modelos

### `Card`

- Chave primária composta: `{tcg_card_id}_{lang}`, por exemplo `sv1-1_de`
- `tcg_card_id` armazena o id original da carta na TCGdex
- `set_id` armazena o id original do set na TCGdex, não o id composto da linha do set
- `rarity` é dado da API, somente leitura
- A disponibilidade de variante é representada por flags booleanas:
  - `variants_normal`
  - `variants_reverse`
  - `variants_holo`
  - `variants_first_edition`

### `CardHash`

- Chave estrangeira para `Card.id`
- Armazena os três hashes perceptuais (`phash`, `dhash`, `whash`) calculados a partir da imagem oficial da carta
- Populado automaticamente por `services/card_hash_backfill.py`, agendado em `services/scheduler.py` (incremental, em lotes, a cada `card_hash_backfill_interval_minutes`); `backend/scripts/backfill_card_hashes.py` continua disponível para uso manual (`--force` para recalcular tudo, `--limit` para um teste rápido)
- Consultado por `backend/services/card_scan_hash.py` a cada tentativa de escaneamento

### `CollectionItem`

- Armazena cópias de cartas de propriedade do usuário
- Campos ativos: `card_id`, `user_id`, `quantity`, `condition`, `variant`, `purchase_price`, `lang`
- Os valores de variante agora são apenas as variantes físicas de impressão: `Normal`, `Holo`, `Reverse Holo`, `First Edition`
- A antiga UI de grading não existe mais; o histórico de migração do banco ainda contém uma coluna legada `grade`, mas ela não faz parte do modelo ORM ou do schema de API atuais
- Linhas existentes são agrupadas por usuário, carta, variante, idioma, condição e preço de compra quando cartas são adicionadas pela API

### `User`

- Campos incluem `role`, `avatar_id` e `must_change_password`
- `must_change_password` é retornado pelas respostas de autenticação e aplicado pelo frontend após o login

### `Setting`

- Tabela global de chave/valor
- Usada para configurações restritas ao admin, como cadência de sincronização e modo de autenticação

### `UserSetting`

- Tabela de chave/valor por usuário
- Usada para preferências e segredos isolados do usuário
- Restrição de unicidade: `user_id + key`

### Outros Modelos Principais

- `Set`
- `WishlistItem`
- `Binder` / `BinderCard`
- `ProductPurchase`
- `PriceHistory`
- `PortfolioSnapshot`
- `SyncLog`
- `ImageCache`
- `CustomCardMatch`

## Escopo das Configurações

As configurações atuais são divididas em `backend/api/settings.py`:

- `PER_USER_KEYS`
  - `language`
  - `currency`
  - `price_primary`
  - `price_display`
  - `telegram_bot_token`
  - `telegram_chat_id`
  - `telegram_enabled`
  - `price_alerts_enabled`
  - `price_alert_threshold`
  - `scan_diagnostics_enabled`
  - `trainer_name`
  - `collection_language_primary`
  - `collection_language_shortlist`
- `ADMIN_ONLY_KEYS`
  - `full_sync_interval_days`
  - `price_sync_interval_minutes`
  - `card_hash_backfill_interval_minutes`
  - `multi_user_mode`
  - `tcgdex_sync_languages`
  - `debug_mode`
  - `cross_language_price_fallback`
  - `cross_language_image_fallback`

Comportamento importante:

- Cada usuário só lê e escreve suas próprias linhas de `UserSetting`
- Configurações restritas ao admin são armazenadas globalmente em `settings`
- Sincronizações automáticas recorrentes incluem uma cadência de sincronização completa e uma cadência separada de sincronização leve de preços
- `tcgdex_sync_languages` é semeado a partir de `TCGDEX_SYNC_LANGUAGES` apenas quando a linha ainda não existe; depois disso, o valor no banco é o que vale. Valores de ambiente vazios ou inválidos caem com segurança para `en,de`. O valor `all` se expande para todos os idiomas suportados pela TCGdex durante o primeiro bootstrap.
- Os códigos de idioma de sincronização suportados pela TCGdex são centralizados em `services/tcgdex_languages.py`. Idiomas extras opcionais são `fr`, `es`, `es-mx`, `it`, `pt`, `pt-br`, `pt-pt`, `nl`, `pl`, `ru`, `ja`, `ko`, `zh-tw`, `id`, `th` e `zh-cn`, além do padrão `en,de`.
- O inglês é a fonte de fallback preferida entre idiomas para dados, imagens e preços ausentes pelo ID exato da TCGdex. O backend não adivinha substitutos em inglês pelo nome da carta para cartas exclusivas de uma região.
- Usuários admin podem receber valores iniciais de fallback a partir de variáveis de ambiente para o Telegram
- `scan_diagnostics_enabled` vem desligado por padrão e só tem efeito quando o servidor configura `SCAN_TRACE_DIR`

## Comportamento de Sincronização & Backup

### Sincronização

- `/api/sync/`, `/api/sync/prices` e `/api/sync/prices/all` exigem acesso de admin
- `/api/sync/` roda a sincronização completa de sets/cartas da TCGdex usando os `tcgdex_sync_languages` configurados
- `/api/sync/prices` roda a sincronização leve de preços das cartas rastreadas
- `/api/sync/prices/all` força a atualização de preços de todas as cartas rastreadas
- O status de sincronização retorna as flags atuais mais as últimas 10 linhas do log de sincronização
- A sincronização completa e a de preços podem ser reagendadas por endpoints dedicados

### Backup Seletivo

`GET /api/backup/download` aceita `include` como parâmetro de query separado por vírgulas.

Grupos suportados:

- `full`
- `collection`
- `users`
- `cards`
- `products`
- `system`
- `images`

Mapeamento atual de tabelas:

- `collection`: `collection`, `wishlist`, `binders`, `binder_cards`
- `users`: `users`, `user_settings`, `settings`
- `cards`: `cards`, `sets`, `price_history`, `custom_card_matches`
- `products`: `product_purchases`, `portfolio_snapshots`
- `system`: `sync_log`
- `images`: `image_cache`

Se `include=full`, o cache de imagens é excluído, a menos que `images` também seja explicitamente incluído.

### Backup Automático de Pré-Atualização

A imagem do backend instala as ferramentas cliente do PostgreSQL 18, para que `pg_dump` possa fazer backup do serviço padrão PostgreSQL 18 e de servidores PostgreSQL 18 externos mais novos. O PostgreSQL exige que `pg_dump` seja pelo menos tão novo quanto a versão major do servidor.

`backend/services/pre_upgrade_backup.py` roda antes das migrações de inicialização de `init_db()`.

Comportamento:

- Lê a versão atual do app a partir de `VERSION` através de `backend/main.py`.
- Lê `settings.last_successful_app_version` do banco existente.
- Pula instalações novas, onde a tabela `settings` ainda não existe.
- Cria um dump SQL completo em `/app/backups` quando uma instalação existente sobe em uma nova versão.
- Usa nomes de arquivo como `pre_upgrade_1.17.0_to_1.18.0_20260526_010500.sql`.
- Só registra `last_successful_app_version` depois que a inicialização é concluída com sucesso.
- Mantém os `PRE_UPGRADE_BACKUP_KEEP` backups automáticos mais recentes, padrão `10`, mínimo `1`.
- Grava os dumps primeiro em um nome de arquivo temporário, depois renomeia atomicamente após um `pg_dump` bem-sucedido e não-vazio, para que arquivos parciais não sejam tratados como backups válidos.

Controles de ambiente:

- `PRE_UPGRADE_BACKUP_ENABLED`, padrão `true`
- `PRE_UPGRADE_BACKUP_REQUIRED`, padrão `true`; quando verdadeiro, a inicialização falha antes das migrações se `pg_dump` falhar
- `PRE_UPGRADE_BACKUP_KEEP`, padrão `10`, mínimo `1`

## Notas do Scanner

`backend/api/recognize.py`, `backend/api/scan_jobs.py` e `backend/services/scan_queue.py` implementam a fila persistente em segundo plano usada pelo scanner unificado. O endpoint de reconhecimento direto de uma única carta continua disponível por compatibilidade de API.

O reconhecimento roda inteiramente no backend, sem chamada a nenhuma API externa:

1. Os uploads são JPEGs limitados em tamanho, sanitizados, normalizados de orientação, com metadados removidos.
2. `backend/services/card_scan_preprocess.py` localiza os quatro cantos da carta (rejeitando contornos sem formato de carta), aplica correção de perspectiva e normaliza a iluminação com CLAHE. Sem contorno confiável, a imagem inteira é usada como fallback.
3. `backend/services/card_scan_hash.py` calcula phash/dhash/whash (via `imagehash`) para a imagem normalizada — testando as quatro rotações — e busca os candidatos mais próximos em `card_hashes` por distância de Hamming combinada.
4. A confiança da correspondência é avaliada como `confident`, `ambiguous` ou `no_match`, com base na distância do melhor candidato e no gap para o segundo colocado (`SCAN_HASH_TOP_N`, `SCAN_HASH_CONFIDENCE_GAP`, `SCAN_HASH_NO_MATCH_DISTANCE`).
5. Quando ambíguo, `backend/services/card_scan_ocr.py` recorta a região do número da carta e usa EasyOCR para ler o número local e o total impresso do set, desempatando entre os candidatos.
6. Cada foto é processada individualmente — não há mais agrupamento composto de várias cartas por foto (removido junto com o Gemini; sem equivalente local ainda).
7. Os resultados da fila continuam revisáveis após reinícios. Confirmar/descartar um item apaga sua foto na fila; jobs não revisados expiram após 14 dias.

Tratamento de erro:

- Falhas transitórias de processamento (imagem corrompida, decodificação falha) são reportadas com uma mensagem clara para o usuário
- Retentativas usam backoff genérico — não há mais lógica de cota, chave de API, ou limite de taxa de provedor externo, porque não existe mais provedor externo
- Os nomes de sufixo de carta como `EX`, `GX`, `V`, `VMAX`, `VSTAR`, `TAG TEAM`, `BREAK` e `LV.X` são removidos antes da busca por número
- A busca pode recorrer do idioma detectado da carta para o inglês
- O payload de resultado inclui os metadados reconhecidos e as cartas candidatas

### Diagnóstico do scanner

`backend/services/scan_trace.py` fica desabilitado a menos que `SCAN_TRACE_DIR` aponte para um armazenamento que o backend possa criar e escrever. A disponibilidade sozinha não coleta dados: cada usuário precisa habilitar com `scan_diagnostics_enabled=true`, que vem desligado por padrão. `SCAN_TRACE_STORAGE_DIR` é o local estável de limpeza; o Docker Compose padrão o mantém em `/app/data/scan-traces` mesmo quando a nova coleta está desabilitada.

Para tentativas com consentimento, um trace JSON por usuário e um JPEG sanitizado são armazenados. Os traces contêm a foto sanitizada, a decisão final do scanner (correspondência por hash, hash+OCR, ou sem correspondência) e o candidato selecionado, além de eventuais erros. Nenhuma chave de API é usada pelo scanner, e credenciais de autenticação nunca são registradas.

Quando um candidato enfileirado é confirmado, o id da carta na TCGdex rotula todas as tentativas armazenadas daquele item de job como verdade de referência (ground truth). `backend/scripts/analyse_scan_traces.py` reporta a acurácia top-1 e detalhes opcionais de campos nulos/falhas.

Desligar o consentimento interrompe a captura futura e deixa os traces existentes inalterados. Não há limite automático de retenção. `DELETE /api/settings/scan-diagnostics` é a ação explícita de exclusão por usuário; excluir uma conta revoga escritas em andamento e também remove sua subárvore de traces. Diretórios de trace usam o modo `0700` e arquivos JSON/JPEG usam `0600`. Os diagnósticos não fazem parte dos backups SQL, porque são dados de análise do sistema de arquivos.

## Adição em Lote à Coleção

`POST /api/collection/bulk-add` aceita `BulkCollectionAddRequest` com múltiplos itens `CollectionItemCreate` e retorna `BulkCollectionAddResponse`:

- `added`: novas linhas de coleção criadas
- `updated`: linhas existentes correspondentes cuja quantidade foi incrementada
- `failed`: itens que não puderam ser adicionados
- `errors`: detalhes de erro por carta

Cada item é commitado independentemente, então uma carta inválida ou indisponível não reverte o restante do lote. Linhas existentes são pareadas por carta, variante, idioma e usuário atual.

## Notificações

`backend/services/telegram.py` agora aceita `user_id` e lê as credenciais do Telegram primeiro das linhas de `UserSetting` daquele usuário.

## Migrações

- Migrações são instruções SQL puras em `backend/database.py`
- São idempotentes e rodam na inicialização
- Backups automáticos de pré-atualização rodam antes das migrações de `init_db()` em instalações existentes quando a versão do app muda
- Comentários de migração legados ainda mencionam colunas antigas como `grade` ou integrações removidas, mas o modelo e os roteadores de runtime atuais não incluem funcionalidade de eBay
