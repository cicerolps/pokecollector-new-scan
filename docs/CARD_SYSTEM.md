# Sistema de Cartas

O PokéCollector expõe um módulo público de interface de carta em `frontend/src/components/card-system`. É o ponto de partida normal para funcionalidades de carta, porque já carrega a estrutura visual estabelecida, comportamento responsivo, bordas, indicadores de estado, fallbacks de imagem e estados de interação.

Este guia é uma referência compartilhada para contribuidores, mantenedores e revisões assistidas por IA. Ele ajuda um trabalho novo a se encaixar na aplicação sem exigir que ninguém memorize prints antigos. Não é uma proibição a ideias novas: uma interação ou apresentação genuinamente nova pode evoluir o sistema depois de revisão.

## API Pública

Importe a partir do ponto de entrada do diretório:

```jsx
import {
  CardDialog,
  CardDisplay,
  CardIdentity,
  CardLegend,
  CardRow,
  CardStack,
} from '../components/card-system'
```

| Componente | Uso |
| --- | --- |
| `CardDisplay` | Apresentações completas de carta e arte |
| `CardRow` | Linhas compactas de lista e tabela |
| `CardIdentity` | Arte compacta, nome, número e metadados dentro de uma linha maior |
| `CardDialog` | Moldura compartilhada de diálogo de detalhe da carta |
| `CardLegend` | Explicação recolhível ou sempre visível dos badges e bordas da carta |
| `CardStack` | Apresentação em camadas para impressões agrupadas, com comportamento de arte compartilhado |

`CardDisplay` suporta estas variantes:

| Variante | Contexto pretendido |
| --- | --- |
| `grid` | Grades padrão de coleção, set, Pokédex, binder e busca |
| `carousel` | Grupos horizontais compactos de cartas |
| `ranking` | Apresentações de ranking e cartas valiosas |
| `selectable` | Fluxos de seleção em lote e escolha |
| `artwork` | Arte completa dentro da borda compartilhada, sem legenda |
| `compact-artwork` | Miniatura compacta de lista/tabela |
| `comparison` | Arte responsiva usada em linhas de migração/comparação |

Os componentes aceitam os dados de carta e props de ação existentes. Eles fornecem automaticamente os estados visuais compartilhados quando recebem valores como `selected`, `dimWhenUnowned`, `unavailableReason`, `onClick` ou `onSelect`.

## Tokens de design

Dimensões, raios e cores de borda compartilhados vivem em `card-system/tokens.css`; consumidores em JavaScript usam `CARD_SYSTEM_TOKENS` de `tokens.js`. Ajuste esses tokens ou um componente compartilhado quando uma decisão de design deve mudar em todo lugar.

As páginas continuam responsáveis pelo layout ao redor, grades, painéis, filtros e ações específicas da funcionalidade. Reutilizar os componentes de carta estabelecidos costuma ser a opção mais limpa; quando uma funcionalidade precisa de algo diferente, explique o motivo para que os revisores possam decidir se é uma interação local ou uma adição compartilhada útil.

## Linguagem visual estabelecida

Use estes pontos ao implementar ou revisar qualquer tela que apresente cartas:

- Cartas completas usam uma moldura. A moldura padrão é cinza; fallbacks de dado, preço e imagem usam os tratamentos de moldura compartilhados roxo, âmbar e azul. Arte manual usada porque a arte oficial está ausente pertence ao tratamento de fallback de imagem.
- Hover e foco por teclado clareiam a moldura com um brilho contido. Ações de toque precisam continuar disponíveis sem hover.
- Indicadores de propriedade, variação de impressão, quantidade, wishlist, origem de produto, seleção e progresso de binder usam os badges compartilhados. Qualquer tela que exiba esses indicadores também fornece a legenda compartilhada por perto.
- Cartas ausentes em contextos de comparação, como as visões de Set e Pokédex, mantêm a sobreposição cinza de não-propriedade. Cartas desabilitadas mostram um motivo em vez de ignorar a interação silenciosamente.
- Nomes de carta ficam em uma linha com reticências em grades e linhas compactas alinhadas. A abreviação do set/número da carta e o preço permanecem alinhados quando nomes vizinhos têm tamanhos diferentes.
- Arte ausente usa o verso da carta Pokémon. O carregamento usa o esqueleto compartilhado; arte fornecida que falha oferece nova tentativa; listas compactas priorizam imagens visíveis e adiam linhas distantes.
- Linhas compactas mostram a arte completa dentro da moldura compacta padrão. Coleção, Análises, Wishlist, trocas, comparações, rankings, binders e linhas do otimizador devem parecer da mesma família.
- Diálogos usam a moldura flutuante compartilhada, do tamanho do conteúdo, em desktop e mobile. A ação de fechar fica no canto superior direito, e abas/ações permanecem centralizadas e usáveis por teclado e toque.
- Fluxos especializados podem otimizar velocidade e comportamento de seleção, mas as telas de scanner, binder, otimizador, troca, seleção em lote e migração mantêm a identidade de carta e a linguagem de estado compartilhadas.

## Galeria de componentes

Em desenvolvimento, rode:

```bash
cd frontend
npm run dev
```

Abra `/__card-system` para ver as variantes suportadas, estados de propriedade, fallbacks, cartas indisponíveis, legendas, linhas e diálogos juntos. A rota é excluída dos builds de produção.

## Adicionando uma ideia nova

Não force uma interação genuinamente diferente na variante errada. Um contribuidor pode propor um padrão compartilhado novo, ou uma apresentação específica de funcionalidade claramente justificada:

1. Descreva a necessidade do usuário e por que o padrão existente mais próximo não se encaixa.
2. Decida durante a revisão se a ideia é específica da funcionalidade ou pertence aos componentes compartilhados.
3. Preserve o comportamento de teclado, toque, carregamento, nova tentativa, indisponibilidade e responsividade.
4. Mostre o resultado em desktop e mobile.
5. Se virar compartilhado, adicione a `CardSystemGallery.jsx`, aos testes e a este guia.

A revisão deve focar em saber se a ideia pertence ao sistema compartilhado e se os consumidores existentes permanecem estáveis, não em desencorajar a proposta.

## Checklist do contribuidor

- Identifique os padrões existentes mais próximos de carta completa, linha compacta, ranking, seleção, comparação, pilha, diálogo e legenda antes de começar.
- Use componentes compartilhados onde eles se encaixam; explique diferenças intencionais no pull request.
- Verifique combinações reais de dados: possuído/não possuído, wishlist, múltiplas variantes, quantidades, idiomas mistos, todas as combinações de fonte de fallback, arte manual, arte ausente e estados indisponíveis.
- Verifique nomes, números, preços, raridade e metadados longos ou ausentes sem quebrar o alinhamento.
- Verifique carregamento, nova tentativa, remontagens em cache, listas grandes, teclado, toque e comportamento responsivo.
- Inclua screenshots de desktop e mobile para as telas afetadas, e atualize os snapshots visuais compartilhados quando apropriado.
- Adicione chaves de tradução em inglês para novos rótulos. Outros idiomas podem cair para o inglês até serem traduzidos.

## Checklist do revisor

Mantenedores e revisões assistidas por IA devem usar este checklist para todo pull request ou issue que adicione ou altere UI de carta:

1. Compare a proposta com os padrões estabelecidos mais próximos e a linguagem visual acima.
2. Inspecione todo consumidor afetado, não só o screenshot ou a página citada na issue.
3. Confirme que os dados da carta vêm do objeto correto, especialmente variante, quantidade, condição, idioma, wishlist e estado de produto do item de coleção.
4. Verifique se os indicadores têm legenda e se as molduras de fallback ainda comunicam os estados de fallback de dado, preço, imagem e arte manual.
5. Exercite estados de borda e fluxos especializados, em vez de revisar apenas a carta padrão.
6. Teste páginas reais representativas em desktop e mobile. Use Chromium e WebKit/Safari para mudanças de carregamento ou layout voltadas ao navegador.
7. Se o design for genuinamente novo, ajude o contribuidor a integrá-lo de forma limpa, ou promova-o a um padrão compartilhado, em vez de rejeitar a ideia.
8. Ajuste detalhes inconsistentes antes do merge, e atualize este guia quando a linguagem visual aceita mudar.

Os testes automatizados de unidade, tradução, build e regressão visual continuam sendo redes de segurança úteis. A suíte visual cobre a galeria de componentes mais páginas reais representativas de Coleção e Análises em desktop e mobile, com uma verificação dedicada de lista grande no WebKit. A consistência visual é, em última instância, uma responsabilidade de revisão, não uma restrição de importação aplicada por código.
