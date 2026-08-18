# Briefing de implementação: Pokédex Nacional para o PokéCollector

## Objetivo

Adicionar uma visão aditiva, organizada primeiro por espécie, cobrindo a Pokédex Nacional #001–1025, mantendo todos os fluxos existentes de set, carta, coleção, binder e wishlist.

## Jornada de usuário necessária

```text
Pokédex → filtro/busca → abre uma espécie faltando → navega pelas impressões de carta correspondentes
→ abre um produto exato do Cardmarket ou busca alternativa → adquire/adiciona a carta
→ a espécie vira Possuída automaticamente
```

## Requisitos funcionais

- Navegação de primeira classe `/pokedex` e rotas de espécie `/pokedex/{dex_id}`.
- Grade visual compacta de blocos, inspirada no comportamento de uma Pokédex tradicional: sprite em pixel art, número, nomes, status de conclusão, quantidade possuída e contagem de impressões disponíveis.
- Visão nacional agrupada de Kanto a Paldea, com pílulas de Nacional e Ger. 1–9.
- Busca por nome em inglês/alemão e número da Pokédex Nacional, com ou sem zeros à esquerda.
- Filtros Todos/Possuídos/Faltando e progresso no nível do escopo.
- Página de espécie com arte oficial, sprite como fallback, navegação anterior/próximo, e a grade de cartas existente filtrada por `dex_id`.
- Propriedade derivada apenas dos itens de coleção existentes.
- Armazenar o `dexId` da TCGdex como um array, e os produtos do Cardmarket como uma lista sensível a variante.
- Enriquecimento completo de carta e um backfill idempotente; sem join ao vivo com a TCGdex durante a renderização da página.
- Cache local persistente de imagens, com população antecipada via CLI e preenchimento preguiçoso (lazy).
- Links exatos de produto do Cardmarket por impressão/variante, com uma busca alternativa segura.
- O comportamento existente orientado por set precisa permanecer inalterado.

## Limites de escopo

Não incluído nesta funcionalidade:

- cartas representativas/de slot de binder selecionadas manualmente;
- registros de conclusão separados para uma Pokédex com curadoria;
- autenticação ou sincronização via API do Cardmarket;
- operações automáticas de lista de desejos/carrinho/Shopping Wizard;
- substituição da lógica existente de conclusão por set.

## Continuação

Adicionar um assistente de transferência de wishlist para o Cardmarket depois desta funcionalidade. A primeira versão deve fornecer links/checklist de produto exato e uma exportação opcional de texto de decklist para o Cardmarket, com limitações de correspondência claras.
