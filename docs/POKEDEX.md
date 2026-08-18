# Visão da Pokédex Nacional

O PokéCollector agora inclui uma Pokédex Nacional em nível de espécie, além do seu catálogo já existente, organizado primeiro por set.

## Modelo de conclusão

Uma espécie está **Possuída** quando o usuário atual tem pelo menos um item de coleção cuja carta tem aquele número da Pokédex Nacional em `cards.dex_ids`. A conclusão é derivada da coleção existente; não há um registro separado de "marcar como completo".

Uma carta com múltiplos Pokémon pode conter vários `dex_ids` e contar para cada espécie. Remover o último item de coleção correspondente muda a espécie de volta para **Faltando**.

## Fontes de dados

- O arquivo `backend/data/pokedex.json`, incluído no projeto, contém a Pokédex Nacional #001–1025, nomes em inglês e alemão, geração, região e tipos.
- O enriquecimento completo de carta da TCGdex armazena o `dexId` em `cards.dex_ids`.
- Se a TCGdex omitir o `dexId` para uma carta completa de Pokémon, o PokéCollector infere de forma conservadora o número da Pokédex Nacional a partir de um nome de espécie base exato em inglês ou alemão, como `Mega-Glurak Y-ex` -> `Glurak` -> `006`.
- Os IDs de produto do catálogo Cardmarket por variante da TCGdex são armazenados em `cards.cardmarket_products`, sem colapsar variantes foil.

Linhas existentes de lista de set contêm apenas dados breves de carta. Depois de um upgrade, o backend inicia um backfill único em segundo plano e registra a conclusão na configuração `pokedex_metadata_backfill_completed`. Revisões do parser, como melhorias na inferência de `dexId` ausente, podem avançar a revisão interna de backfill, para que mapeamentos vazios já tentados sejam tentados novamente uma vez. Para repetir ou inspecionar o backfill manualmente:

```bash
docker compose exec backend \
  python -m scripts.backfill_pokedex_metadata --limit 5000
```

Repita o comando manual até `attempted` chegar a `0`, ou use `--refresh` para buscar novamente linhas selecionadas do catálogo.

## Cache de imagens

Os blocos da Pokédex usam primeiro um sprite em pixel art. Os cabeçalhos de espécie usam primeiro a arte oficial. Ambos são servidos a partir do cache local persistente:

```text
/app/data/pokedex-images/sprites/{dex_id}.png
/app/data/pokedex-images/artwork/{dex_id}.png
```

O bind mount do Compose é:

```yaml
- ./data/pokedex-images:/app/data/pokedex-images
```

As imagens são cacheadas de forma preguiçosa (lazy) na primeira requisição. Para popular o cache completo com antecedência:

```bash
docker compose exec backend \
  python -m scripts.cache_pokedex_images
```

Opções úteis:

```bash
python -m scripts.cache_pokedex_images --min 152 --max 386
python -m scripts.cache_pokedex_images --refresh
python -m scripts.cache_pokedex_images --delay 0.1
```

O buscador grava arquivos temporários e os renomeia atomicamente, continua após falhas individuais, e reporta entradas ausentes/com falha ao final.

## Rotas

Frontend:

```text
/pokedex
/pokedex/{dex_id}
```

API:

```text
GET /api/pokedex
GET /api/pokedex/{dex_id}
GET /api/pokedex/images/sprites/{dex_id}.png
GET /api/pokedex/images/artwork/{dex_id}.png
GET /api/cards/search?dex_id={dex_id}
```

A visão geral suporta os parâmetros de query `generation`, `region`, `status`, `search` e `lang`.

## Links do Cardmarket

Visões de carta específicas preferem um redirecionamento exato de produto público do Cardmarket, armazenado em `cardmarket_products`:

```text
https://www.cardmarket.com/en/Pokemon/Products?idProduct={product_id}
```

Quando nenhum ID exato de produto está disponível, o PokéCollector abre uma busca do Cardmarket na categoria Pokémon, construída a partir do nome da carta, abreviação do set e número de coleção.

## Continuação da exportação da wishlist

O schema atual expõe deliberadamente os metadados necessários para um futuro assistente de transferência "Exportar wishlist para o Cardmarket". Login automático de conta no Cardmarket, sincronização de lista de desejos, criação de carrinho e execução do Shopping Wizard não fazem parte desta mudança.
