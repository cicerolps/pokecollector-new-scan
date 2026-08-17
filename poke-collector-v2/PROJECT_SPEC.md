# Poke Collector v2 — Especificação de Projeto

**Tipo:** Fork do projeto original "Poke Collector" (scanner de cartas Pokémon TCG)
**Objetivo:** Substituir a identificação de cartas baseada em API de IA generativa (Gemini 2.0 Flash) por um pipeline determinístico de visão computacional (hash perceptual + OCR de desambiguação), integrado a APIs públicas de catálogo.

---

## 1. Contexto e motivação

### 1.1 Situação atual
O container `poke-collector` existente identifica cartas enviando a foto para a API do Gemini 2.0 Flash, que retorna (em texto livre ou JSON) qual carta acredita estar vendo. Limitações observadas:

- **Confiabilidade baixa** em cartas holográficas/reflexivas, variantes de mesma espécie em sets diferentes, e cartas em idiomas não-inglês.
- **Dependência de cota/custo de API externa** — cada scan é uma chamada de LLM, sujeita a rate limit, latência de rede e possíveis mudanças de preço/disponibilidade do provedor.
- **Não determinístico** — a mesma foto pode gerar respostas diferentes em execuções distintas.
- **Sem fallback offline** — se a API de IA estiver fora do ar, o app não funciona.

### 1.2 Proposta
Substituir por um pipeline **local, determinístico e reproduzível**:

1. Detecção e normalização geométrica da carta na imagem (OpenCV).
2. Identificação primária por **hash perceptual** contra um banco de hashes pré-computado a partir de imagens oficiais de cartas.
3. **OCR de desambiguação**, aplicado apenas na região do símbolo do set + número de coleção, para resolver casos de hash ambíguo (reimpressões, variantes de mesma arte).
4. Enriquecimento dos dados finais (preço, raridade, texto, imagem em alta resolução) via API pública de catálogo.

Isso elimina a dependência de LLM externo para a tarefa de reconhecimento, reduz custo operacional a zero (fora a infraestrutura já existente), e roda inteiramente dentro da rede `netservices` do homelab.

---

## 2. Arquitetura geral

```
┌─────────────────────────────────────────────────────────────────┐
│  Cliente (app/web) — captura foto da carta                       │
└───────────────────────────────┬───────────────────────────────────┘
                                 │ POST /api/v1/scan (multipart/image)
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  poke-collector-api (FastAPI)                                    │
│                                                                     │
│  ┌────────────────┐   ┌──────────────────┐   ┌─────────────────┐ │
│  │ 1. Preprocess    │→ │ 2. Hash matching  │→ │ 3. OCR desambig. │ │
│  │  (OpenCV)        │  │  (imagehash +     │  │  (só se ambíguo) │ │
│  │  - crop/contorno │  │   banco local)    │  │  (EasyOCR)       │ │
│  │  - perspective   │  │                    │  │                  │ │
│  │  - normalização  │  │                    │  │                  │ │
│  └────────────────┘   └──────────────────┘   └─────────────────┘ │
│                                 │                                   │
│                                 ▼                                   │
│                    ┌────────────────────────┐                      │
│                    │ 4. Resolução final       │                     │
│                    │   set + número + variante│                     │
│                    └────────────┬────────────┘                      │
└─────────────────────────────────┼──────────────────────────────────┘
                                   │ lookup
                                   ▼
                    ┌──────────────────────────────┐
                    │  Cache local (SQLite)          │
                    │  - hashes pré-computados        │
                    │  - metadados de cartas           │
                    │  - preços (TTL configurável)     │
                    └───────────────┬──────────────────┘
                                     │ miss / refresh
                                     ▼
                    ┌──────────────────────────────┐
                    │  APIs públicas externas          │
                    │  - pokemontcg.io (catálogo/preço) │
                    │  - tcgdex.dev (catálogo multi-idioma, sem API key)│
                    └──────────────────────────────┘
```

### 2.1 Princípio de design
- **Local-first**: todo o reconhecimento roda sem chamada externa. APIs públicas só são usadas para (a) popular o banco de hashes inicialmente e (b) buscar metadados/preço de uma carta já identificada.
- **Determinístico**: mesma imagem → mesmo resultado, sempre. Facilita debugging e testes automatizados.
- **Sem chave de API obrigatória**: TCGdex não exige key; pokemontcg.io tem tier gratuito com key opcional (limites mais altos com key).

---

## 3. Pipeline de identificação — detalhamento técnico

### 3.1 Etapa 1 — Pré-processamento (OpenCV)
- Detecção de contorno do retângulo da carta na foto (`cv2.findContours` + aproximação poligonal).
- Correção de perspectiva (`cv2.getPerspectiveTransform` + `warpPerspective`) para "esticar" a carta e obter uma imagem frontal padronizada (ex: 600×825px, mesma proporção das imagens de referência da API).
- Normalização de iluminação/contraste (CLAHE) para atenuar brilho de cartas holo/reflexivas.
- Detecção de orientação (rotação 0°/90°/180°/270°) — testar hash nas 4 rotações caso a detecção de contorno não garanta a orientação correta.

### 3.2 Etapa 2 — Matching por hash perceptual
- Biblioteca: `imagehash` (Python), usando múltiplos algoritmos combinados para reduzir falso-positivo:
  - `phash` (perceptual hash — mais robusto a pequenas variações)
  - `dhash` (difference hash — rápido, bom para bordas)
  - `whash` (wavelet hash — robusto a compressão)
- Banco de hashes pré-computado: para cada carta de cada set (baixada uma vez da API pública), calcular os 3 hashes e armazenar junto ao `card_id`.
- Busca: calcular os 3 hashes da imagem normalizada e buscar por distância de Hamming mínima combinada no banco. Retornar os *N* candidatos mais próximos com suas distâncias.
- **Critério de confiança**: se o candidato #1 tiver distância significativamente menor que o #2 (threshold configurável), aceitar direto. Caso contrário, marcar como "ambíguo" e seguir para etapa 3.

### 3.3 Etapa 3 — OCR de desambiguação (só quando necessário)
- Aplicado **apenas na região inferior da carta** (símbolo do set + número de coleção, ex: `"025/198"`), não na carta inteira — reduz custo computacional e evita os problemas de fonte estilizada do nome.
- Biblioteca: **EasyOCR** (superior ao Tesseract em fontes pequenas/estilizadas, instalação mais simples que PaddleOCR em container). Rodar em CPU é aceitável para esse recorte pequeno.
- O texto extraído (número de coleção) é cruzado com os candidatos do hash matching para resolver a ambiguidade (ex: duas impressões da mesma arte em sets diferentes têm números diferentes).
- Fallback adicional: comparação de template do símbolo do set (pequeno ícone) contra uma biblioteca de símbolos de sets conhecidos, caso o OCR do número falhe.

### 3.4 Etapa 4 — Resolução final
- Retorna: `card_id`, `set`, `número`, `variante` (holo/reverse/normal), `nome`, `confiança do match`.
- Se confiança abaixo de um threshold mínimo mesmo após OCR: retornar os top-3 candidatos para o usuário escolher manualmente (UX de "confirmar carta"), em vez de forçar um resultado errado.

---

## 4. Integrações com APIs públicas

| API | Uso | Autenticação | Observações |
|---|---|---|---|
| **pokemontcg.io** | Catálogo completo, imagens de referência para gerar hashes, preços (TCGplayer/Cardmarket embutidos) | Key opcional (tier grátis sem key tem rate limit menor) | Fonte principal para popular o banco de hashes |
| **tcgdex.dev** | Catálogo multi-idioma (útil para cartas JP/PT), REST e GraphQL, sem key | Não requer key | Bom complemento para cartas fora do catálogo em inglês |

### 4.0 Estático vs. dinâmico — o que vai na imagem Docker e o que não vai

É importante não misturar dois tipos de asset diferentes:

- **Estático (baked na imagem no build)**: pesos do modelo EasyOCR. Não mudam com o tempo — é o modelo de reconhecimento de texto em si, não dado de catálogo. Baixar em build evita dependência de rede no startup do container.
- **Dinâmico (NUNCA na imagem — sempre em volume + job periódico)**: imagens de referência das cartas e o banco de hashes derivado delas. Isso cresce a cada set novo lançado pela Pokémon Company. Se fosse empacotado na imagem, cada set novo exigiria rebuild completo da imagem Docker — acoplamento que queremos evitar. Esses dados vivem num volume Docker persistente (ex: `./data/catalog:/app/data/catalog`) e são populados/atualizados pelo job de sincronização abaixo, independente do ciclo de vida da imagem.

### 4.1 Job de sincronização (build/refresh do banco de hashes)
- Rotina batch (script Python, rodável via `docker exec` ou cron/systemd timer, no padrão dos seus outros scripts de homelab) que:
  1. Lista sets via API pública.
  2. Baixa imagem de referência de cada carta (cache local em disco, evitando redownload).
  3. Calcula os hashes e grava/atualiza no banco.
  4. Roda incrementalmente — só processa sets novos ou cartas ainda não hasheadas.
- Frequência sugerida: acionado manualmente ou via systemd timer semanal (novos sets não saem com tanta frequência), similar ao padrão `OnBootSec`/`OnUnitActiveSec` que você já usa nos outros serviços.

### 4.2 Cache de preços
- Preços têm TTL próprio (ex: 24h), separado do cache de identificação (que é permanente, já que a arte da carta não muda). Evita bater na API pública a cada consulta de coleção.

---

## 5. Modelo de dados (proposta de schema)

```sql
-- Catálogo de cartas (populado a partir das APIs públicas)
cards (
  id              TEXT PRIMARY KEY,      -- id da API de origem (ex: "swsh1-1")
  source_api      TEXT,                  -- "pokemontcg" | "tcgdex"
  name            TEXT,
  set_id          TEXT,
  set_name        TEXT,
  number          TEXT,                  -- "025/198"
  rarity          TEXT,
  variant         TEXT,                  -- "normal" | "holo" | "reverse_holo"
  image_url       TEXT,
  last_synced_at  TIMESTAMP
)

-- Hashes pré-computados por carta
card_hashes (
  card_id     TEXT REFERENCES cards(id),
  phash       TEXT,
  dhash       TEXT,
  whash       TEXT,
  PRIMARY KEY (card_id)
)

-- Cache de preços (TTL separado)
card_prices (
  card_id       TEXT REFERENCES cards(id),
  market_price  NUMERIC,
  currency      TEXT,
  source        TEXT,
  fetched_at    TIMESTAMP
)

-- Coleção do usuário (dados já existentes no poke-collector original, preservar)
collection_items (
  id            SERIAL PRIMARY KEY,
  card_id       TEXT REFERENCES cards(id),
  condition     TEXT,
  language      TEXT,
  quantity      INTEGER,
  acquired_at   TIMESTAMP,
  notes         TEXT
)

-- Log de scans (útil para debugging/melhoria do pipeline)
scan_log (
  id                SERIAL PRIMARY KEY,
  image_hash        TEXT,          -- hash da própria foto enviada, p/ dedupe de testes
  matched_card_id   TEXT,
  confidence        NUMERIC,
  used_ocr_fallback BOOLEAN,
  candidates_json   JSONB,         -- top-N candidatos e distâncias, p/ auditoria
  created_at        TIMESTAMP
)
```

---

## 6. Endpoints da API (FastAPI)

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/api/v1/scan` | Recebe imagem, executa pipeline completo, retorna carta identificada (ou candidatos) |
| `POST` | `/api/v1/scan/confirm` | Confirma manualmente um candidato quando a confiança foi baixa |
| `GET` | `/api/v1/cards/{card_id}` | Detalhes de uma carta do catálogo |
| `GET` | `/api/v1/collection` | Lista a coleção do usuário |
| `POST` | `/api/v1/collection` | Adiciona item à coleção (a partir de um scan confirmado) |
| `POST` | `/api/v1/admin/sync` | Dispara job de sincronização do catálogo/hashes (uso interno/cron) |
| `GET` | `/api/v1/health` | Healthcheck do container |

---

## 7. Stack tecnológica proposta

- **Linguagem/Framework:** Python 3.12 + FastAPI (async, boa integração com OpenCV/numpy, e você já tem familiaridade com Python pelos scripts de beets/dedupe)
- **Visão computacional:** OpenCV (`opencv-python-headless` — sem dependências gráficas desnecessárias em container)
- **Hashing:** `imagehash` + `Pillow`
- **OCR:** `EasyOCR` — instalação mais simples em container (dependência principal é PyTorch CPU, sem toolchain C++ extra do PaddlePaddle), rodando adequadamente em CPU para o recorte pequeno (símbolo do set + número de coleção) usado aqui
- **Banco de dados:** SQLite — container standalone, sem dependência de serviço externo; volume de dados (hashes + catálogo + coleção) é pequeno o suficiente para não justificar Postgres. Arquivo `.db` montado em volume Docker persistente, seguindo o mesmo padrão de bind mounts dos seus outros serviços.
- **HTTP client para APIs externas:** `httpx` (async)
- **Containerização:** Dockerfile multi-stage (build das deps de visão computacional separado do runtime), integrado à rede `netservices` externa, seguindo suas convenções (`restart: unless-stopped`, `PUID/PGID=1000`, configs em `/etc/docker/config/`). Pesos do modelo EasyOCR baixados no build (asset estático); catálogo de cartas/hashes **fora da imagem**, em volume persistente populado pelo job de sync (ver seção 4.0)

---

## 8. Estrutura de diretórios sugerida

```
poke-collector-v2/
├── app/
│   ├── main.py                 # entrypoint FastAPI
│   ├── api/
│   │   ├── scan.py             # rotas de scan
│   │   ├── collection.py       # rotas de coleção
│   │   └── admin.py            # rotas de sync/admin
│   ├── pipeline/
│   │   ├── preprocess.py       # OpenCV: contorno, warp, normalização
│   │   ├── hash_matcher.py     # imagehash: cálculo e busca
│   │   ├── ocr_disambiguator.py# OCR do símbolo/número do set
│   │   └── resolver.py         # orquestra as 3 etapas e decide confiança
│   ├── integrations/
│   │   ├── pokemontcg_client.py
│   │   └── tcgdex_client.py
│   ├── db/
│   │   ├── models.py
│   │   └── migrations/
│   └── jobs/
│       └── sync_catalog.py     # job batch de população/atualização do banco de hashes
├── tests/
│   ├── fixtures/                # fotos de teste (variadas: holo, ângulo, idioma)
│   └── test_pipeline.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── PROJECT_SPEC.md              # este documento
```

---

## 9. Roadmap de implementação (fases)

**Fase 1 — Fundação**
- Fork do repositório original, remoção da dependência do Gemini.
- Setup do FastAPI + estrutura de diretórios.
- Cliente para pokemontcg.io e tcgdex.dev.

**Fase 2 — Banco de hashes**
- Job de sincronização: baixar catálogo + imagens, calcular hashes, popular banco.
- Rodar para 1-2 sets primeiro (validação), depois catálogo completo.

**Fase 3 — Pipeline de reconhecimento**
- Pré-processamento OpenCV (detecção + warp).
- Matching por hash + lógica de threshold de confiança.
- Testes com fotos reais (idealmente um pequeno dataset de cartas suas, variando ângulo/luz/holo).

**Fase 4 — OCR de desambiguação**
- Integração do OCR na região do número/símbolo do set.
- Lógica de resolução de empates.

**Fase 5 — Migração de dados e integração**
- Migrar coleção existente do container atual (se houver dados a preservar).
- Endpoints de coleção completos.
- Integração com o restante da sua stack (Nginx Proxy Manager, Authentik SSO se aplicável).

**Fase 6 — Refinamento**
- UX de confirmação manual para casos de baixa confiança.
- Cache de preços com TTL.
- Métricas/logs de acurácia do pipeline (via `scan_log`) para ajustar thresholds ao longo do tempo.

---

## 10. Critérios de aceite

- Identificação de carta sem chamada a nenhuma API de IA generativa externa.
- Taxa de acerto mensurável em um dataset de teste próprio (fotos reais de cartas da coleção do usuário), com meta inicial sugerida de ≥90% de acerto direto (sem precisar de confirmação manual) em condições normais de iluminação.
- Tempo de resposta do `/scan` compatível com uso interativo (meta: <2s em CPU, para o caminho feliz sem OCR fallback).
- Sistema funciona **offline** para identificação (só depende de rede externa no job de sync do catálogo).
- Coleção e histórico de scans preservados/migráveis do container atual.

---

## 11. Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Cartas muito danificadas/dobradas dificultam detecção de contorno | Fallback para captura manual do recorte (usuário ajusta os 4 cantos na UI) |
| Reimpressões com arte idêntica em sets diferentes | OCR do número de coleção resolve a maioria dos casos; símbolo do set como segunda camada |
| Catálogo desatualizado (carta muito nova, ainda não indexada pela API pública) | Job de sync deve rodar logo após lançamento de sets; fallback de "não encontrado, cadastrar manualmente" |
| Cartas em idiomas com pouca cobertura na API | TCGdex tem melhor cobertura multi-idioma que pokemontcg.io; usar como fonte complementar |
