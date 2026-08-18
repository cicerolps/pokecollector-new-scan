# Autenticação via proxy reverso

O PokéCollector pode rodar atrás do Authentik, Authelia, oauth2-proxy, ou outra camada de autenticação no proxy reverso.

O proxy vê toda requisição antes do PokéCollector. Isso significa que as configurações de perfil público dentro do PokéCollector não conseguem tornar uma rota pública se o proxy ainda exigir login para essa rota.

## Contrato de rotas do perfil público

Permita acesso não autenticado a estes caminhos quando os perfis públicos precisarem ser alcançáveis fora do login do proxy:

| Caminho | Finalidade |
| --- | --- |
| `/u` e `/u/*` | Diretório público de treinadores, perfis e binders |
| `/api/public/*` | Dados anônimos de perfil público e binder |
| `/api/images/card/*` | Arte de carta usada por binders públicos |
| `/api/pokedex/images/sprites/*` | Avatares de treinador usados por páginas públicas |
| `/assets/*` | JavaScript, CSS compilados e pacotes de página carregados sob demanda |
| `/pokeball.svg` e `/cardback.jpg` | Arte de página pública e de carta ausente |
| `/favicon.ico`, `/favicon-48.png`, `/apple-touch-icon.png`, `/manifest.json`, `/icon-192.png`, `/icon-512.png`, e `/robots.txt` | Assets de navegador, PWA e crawler |

Mantenha toda outra rota da aplicação atrás do proxy. Em particular, não libere todo o `/api/*`. Os endpoints autenticados de coleção, configurações, sincronização, backup e administração ficam sob esse prefixo.

O PokéCollector ainda aplica seus próprios controles de compartilhamento depois que uma requisição chega ao app:

1. Um administrador precisa habilitar perfis públicos.
2. O treinador precisa publicar o próprio perfil.
3. Cada binder de coleção precisa ser compartilhado separadamente.
4. Os valores da coleção permanecem ocultos, a menos que o treinador os habilite.

## Authentik

Os provedores de proxy do Authentik suportam um campo **Unauthenticated Paths** ou **Unauthenticated URLs**. Cada linha é uma expressão regular Go.

Para o modo proxy, ou forward auth de uma única aplicação, o Authentik casa com o caminho da requisição. Adicione:

```text
^/u(/.*)?$
^/api/public(/.*)?$
^/api/images/card/.*$
^/api/pokedex/images/sprites/.*$
^/assets/.*$
^/(pokeball\.svg|cardback\.jpg|favicon\.ico|favicon-48\.png|apple-touch-icon\.png|manifest\.json|icon-192\.png|icon-512\.png|robots\.txt)$
```

Para forward auth em nível de domínio, o Authentik casa com a URL completa em vez disso. Substitua `cards.example.com` pelo host do PokéCollector:

```text
^https://cards\.example\.com/u(/.*)?(\?.*)?$
^https://cards\.example\.com/api/public(/.*)?(\?.*)?$
^https://cards\.example\.com/api/images/card/.*$
^https://cards\.example\.com/api/pokedex/images/sprites/.*$
^https://cards\.example\.com/assets/.*$
^https://cards\.example\.com/(pokeball\.svg|cardback\.jpg|favicon\.ico|favicon-48\.png|apple-touch-icon\.png|manifest\.json|icon-192\.png|icon-512\.png|robots\.txt)(\?.*)?$
```

Se a instalação usa HTTP ou uma porta não padrão internamente, case com a URL que o Authentik recebe. O Authentik documenta a diferença entre os modos de provedor na [documentação do proxy provider](https://docs.goauthentik.io/add-secure-apps/providers/proxy/#allowing-unauthenticated-requests).

Essas exceções expõem os arquivos e endpoints necessários para renderizar visões públicas anônimas. Os assets compilados do frontend e a arte de carta globalmente visível ficam disponíveis pelas rotas listadas, mas os dados protegidos de coleção e as APIs de administração permanecem atrás de autenticação. Elas não fazem o PokéCollector usar a identidade fornecida pelo Authentik. Suporte nativo a OIDC seria uma integração de autenticação separada.

## Verificação

Teste a partir de uma janela anônima do navegador, sem sessão no Authentik:

1. Abra `/u`.
2. Abra um perfil de treinador e um binder compartilhado.
3. Confirme que os sprites do treinador e as imagens de carta carregam.
4. Confirme que `/settings` ainda exige o login do proxy.
5. Confirme que uma rota de API protegida, como `/api/collection/`, ainda exige o login do proxy.

Se o HTML da página pública carregar mas continuar em branco, inspecione o painel de rede do navegador. Um redirecionamento ou resposta HTML de login para `/assets/*` geralmente significa que os pacotes do frontend ainda estão protegidos. Imagens de carta ausentes geralmente significam que `/api/images/card/*` ou `/cardback.jpg` ainda estão protegidos.
