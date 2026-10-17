# Login iFood no fluxo Telegram

Requisito confirmado em 17/10/2026: o bot precisa verificar a conexão iFood do organizador antes de liberar operações vinculadas à conta. Implementação pendente no bot e no backend. Login não significa autorização para enviar pedido.

## Fluxo esperado

1. /start em conversa privada: validar o ID numérico do organizador permitido.
2. Consultar no backend o vínculo entre essa identidade Telegram e a autorização iFood. Sem vínculo confirmado, bloquear consultas de dados da conta, sacola e pedidos. A coleta de preferências pode continuar sem acessar o iFood.
3. Apresentar Conectar iFood. O backend cria uma tentativa de autorização com state aleatório, PKCE, validade e associação à sessão do organizador; o usuário abre a autorização no navegador. O botão não contém tokens nem credenciais.
4. O callback é recebido pelo backend, que valida state, validade, uso único e associação à tentativa antes de trocar o código. Tokens permanecem somente no backend.
5. O bot apresenta Verificar conexão e consulta o estado no backend. Uma mensagem como "já entrei" ou um clique não comprova autenticação. A transação deve continuar associada ao iniciador e a conta vinculada deve ser confirmada por ele antes de uso. Não inventar identidade da conta nem adicionar getUser à allowlist sem validar seu contrato e escopo.
6. O backend verifica a sessão com uma chamada autenticada de leitura permitida, limitada à finalidade necessária e sem expor dados em logs; consulta a validade e tenta renovar quando aplicável. A ausência de endereços é distinta de falha de autenticação. Metadados de ferramentas não provam escopo para compras.
7. Somente após vínculo confirmado e sessão operacional, liberar o fluxo de endereço, ofertas e sacola. Cada operação continua sujeita aos escopos e às regras de negócio.
8. Quando a renovação falhar por credencial inválida/revogada, suspender operações e pedir nova conexão. Falha de rede é indisponibilidade, não prova de logout. Não repetir envio de pedido com resultado desconhecido.
9. Desconectar remove o vínculo e encerra a sessão local correspondente. Não alegar revogação no provedor sem suporte confirmado. Troca de conta invalida a sacola/aprovação anterior; após reconexão, revalidar a revisão antes de qualquer envio.

## O que existe no api-backend

Inspeção do código em 17/10/2026; não foi executado login real nesta revisão.

- GET /api/auth/status: configured, authenticated, expiresAt, expired, hasRefreshToken e scopes.
- GET /api/auth/login: inicia OAuth e responde com redirecionamento.
- POST /api/auth/logout: remove os tokens locais e reinicia o cliente MCP.
- GET /callback e GET /: tratam o retorno OAuth.
- authenticated é Boolean(tokens): token presente, mesmo expirado, não comprova sessão operacional.
- A instância de autenticação e o armazenamento de tokens são globais. Não existe vínculo por telegram_user_id nas rotas examinadas.
- O state é mantido com verifier e createdAt; o callback examinado não verifica explicitamente a idade da tentativa. A limpeza por idade acontece ao iniciar outro login. Exigir a validação de prazo também no callback.

Fontes: [auth.ts](https://github.com/Modo-Escuro/api-backend/blob/main/src/server/auth.ts) e [app.ts](https://github.com/Modo-Escuro/api-backend/blob/main/src/server/app.ts).

Essas rotas são a base existente, não um contrato pronto para múltiplos usuários Telegram. Nunca liberar acesso a uma sessão global somente porque quem enviou /start está logado no Telegram.

## Contrato a implementar

Estados conceituais, ainda sem novos endpoints definidos: desconectado, aguardando autorização, aguardando confirmação do vínculo, conectado, reconexão necessária e indisponível.

- Chamadas bot→backend autenticadas e associadas ao organizador validado pelo adaptador; IDs recebidos em texto do usuário ou do modelo não definem identidade.
- Tentativa expira, é consumida uma única vez e não pode ser reutilizada por outro organizador. Confirmar o vínculo pelo mesmo canal Telegram antes de liberar a conta reduz o risco de associação indevida de links encaminhados.
- Resposta segura para o bot: estado, referência opaca de tentativa/vínculo, validade, limitações de escopo e URL de autorização quando necessária; nunca access_token, refresh_token, secret ou código de callback.
- Para o primeiro MVP, um organizador permitido e uma conta dedicada de teste. Mesmo nesse recorte, o vínculo deve ser explícito; ampliar usuários exige isolamento de sessões/tokens no backend.
- Aprovação do pedido continua sendo uma etapa separada, associada à conta/vínculo, responsável, versão, total e validade da sacola.

## Navegador e callback local

Long polling dispensa webhook público do Telegram. Não dispensa um callback OAuth alcançável pelo navegador do usuário.

Se o backend usa callback localhost/127.0.0.1, o navegador precisa rodar na mesma máquina do backend. Abrir o link no Telegram do celular aponta o callback para o celular, não para o computador. Para a demo local, usar Telegram Desktop e navegador no computador do backend. Para acesso pelo celular, configurar endereço de callback alcançável e cadastrado exatamente no iFood; não alterar o redirect apenas no link de autorização.

Não pedir ao usuário que cole senha, código de autenticação, token ou URL de retorno no chat. Não navegar automaticamente.

## Critérios de aceite

- Sem vínculo, nenhum dado da conta é retornado e nenhuma operação de compra é executada.
- authenticated=true com sessão vencida/rejeitada não libera o fluxo.
- Callback sem state correto, expirado, repetido ou de outra tentativa é rejeitado.
- Outra pessoa não consegue consultar ou confirmar a sessão do organizador.
- Sessão renovada com sucesso retoma consultas; renovação recusada pede login, sem repetir pedidos pendentes.
- Login concluído não aprova sacola. Troca de conta invalida aprovação anterior.
- Tokens e dados privados não aparecem em mensagens, logs, fixtures ou commits.