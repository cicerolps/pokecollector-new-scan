# Contribuindo com o PokéCollector

Contribuições de qualquer tamanho são bem-vindas: correções de bugs, novas funcionalidades, ideias visuais, documentação e testes.

## Fluxo de desenvolvimento

1. Faça um fork do repositório e crie uma branch focada.
2. Explique o problema de usuário que sua mudança resolve.
3. Adicione ou atualize testes e documentação quando apropriado.
4. Rode as verificações relevantes antes de abrir um pull request.

Para trabalho no frontend:

```bash
cd frontend
npm ci
npm test
npm run build
```

O comando de teste do frontend também valida chaves de tradução literais. Adicione novas chaves voltadas ao usuário em `src/i18n/en.js`; outros pacotes de idioma podem cair para o inglês até que uma tradução seja contribuída. Chaves ausentes falham com o arquivo e a linha de origem, em vez de aparecer como rótulos crus no app.

## Interfaces de carta

O sistema público de cartas em `src/components/card-system` é o ponto de partida normal para interfaces de carta. Ele fornece molduras, linhas, badges, diálogos e estados de carregamento/erro já estabelecidos, para que os contribuidores possam focar na própria funcionalidade.

```jsx
import { CardDisplay, CardLegend, CardRow, CardStack } from '../components/card-system'

<CardDisplay variant="grid" card={card} image={image} />
<CardRow card={card} name={card.name} image={image} />
<CardLegend />
<CardStack card={card} image={image} layers={2} />
```

Isso mantém as novas funcionalidades visualmente consistentes, sem pedir que os contribuidores memorizem cada detalhe de design. Os componentes e variantes disponíveis estão documentados em [`docs/CARD_SYSTEM.md`](docs/CARD_SYSTEM.md).

Novas ideias visuais são incentivadas. Se uma variante existente não se encaixa na funcionalidade, explique a diferença e considere se a ideia deveria virar uma variante compartilhada reutilizável:

1. Descreva por que as variantes existentes não se encaixam.
2. Decida com o revisor se a ideia é específica da funcionalidade ou amplamente reutilizável.
3. Para uma ideia reutilizável, adicione-a ao módulo público card-system e à galeria de componentes.
4. Atualize os testes e a documentação relevantes para qualquer uma das abordagens.

Esse processo dá aos contribuidores espaço para evoluir o design, ao mesmo tempo em que ajuda melhorias aceitas a permanecerem consistentes entre funcionalidades. O guia é revisado por mantenedores; não há uma regra automática rejeitando uma implementação alternativa só porque ela é nova.

## Pull requests

Mantenha os pull requests focados e explique o motivo da mudança. Inclua screenshots de desktop e mobile para trabalho visual quando for prático. Revisores usam [`docs/CARD_SYSTEM.md`](docs/CARD_SYSTEM.md) como checklist de consistência, e podem sugerir adaptar uma contribuição à linguagem visual compartilhada antes do merge.

Seja gentil, claro, e presuma boa intenção durante a revisão.
