# Assistente conversacional e resposta progressiva

Reconciliação de 20/10 em worktrees separados: bot base 43105ba, API base f6ef20e. Publicação autorizada pelo usuário: commit funcional do bot `be55381` e API [#58](https://github.com/Modo-Escuro/api-backend/pull/58), com integração fixada em `148b595082823288fbb713d1a6e341e32dfbffc7`. GitHub consultado; sem merge/deploy, consulta de volume ou serviço online. API v6 unifica variantes v5 e mantém UNKNOWN obrigatório bloqueante.

## Direção de produto

A entrada principal passa a ser uma conversa natural: “quero um bolo para presentear minha namorada”, por exemplo. A API entrega a intenção à IA, que solicita consultas ao iFood. O bot apresenta acolhimento e, assim que disponíveis, opções com fatos montados pela API. O `/start` convida a pessoa a contar o objetivo/ocasião, sem abrir automaticamente o formulário individual/grupo. Callbacks antigos continuam reconhecidos com as validações existentes.

## Extensão implementada no cliente

Durante uma operação RUN-01 pendente, o bot pode consultar:

`GET /api/bot/v1/conversations/:conversationId/operations/:operationId/progress`.

O cliente valida contrato, operação/evento e texto limitado a 600 caracteres, usando a mesma identidade e sessão. A prévia é enviada uma vez; a resposta final edita a mesma mensagem pelo mecanismo de entrega existente. Não cria outro evento, não repete a consulta do modelo e não persiste o texto da prévia em SQLite.

404 indica API anterior e desliga somente a extensão opcional. Falha de prévia não pausa a consulta da operação principal. Prévia perdida após reinício não impede recuperar o resultado durável.

Na API, o assistente é o único processador; os opt-ins de runtime/modelo continuam separados. Remova `CONVERSATION_AGENT_MODE` da configuração; o valor antigo `assistant` só é aceito por compatibilidade e `structured` é recusado. F7, painel e sessão global foram retirados. O bot não recebe chave Gemini ou credenciais iFood. Nenhuma configuração do serviço real foi alterada por esta revisão.

## Sessão capturada e compatibilidade

Antes de enfileirar texto, captura sessionRef em `/account-context` quando enabled e conserva-o em outbox/cabeçalho durante envio/consulta/replay. Não troca a referência de evento antigo pela conta nova. A API v6 revalida e recusa sessão antiga com LINK_CHANGED, sem identidade estável inferida por nome/e-mail.

API antiga com 404/disabled mantém compatibilidade sem associação por evento. O schema **v6 é da API**, não do banco do bot. Registros antigos da outbox são preservados, sem inventar vínculo retrospectivo.

## Menu e administração de memória

O teclado persistente tem apenas **Menu**. Após acesso, o menu inline mostra Conta iFood, Endereços iFood, Remover pessoa, Limpar tudo, Meus dados, Ajuda e Sair da demo; Revisar carrinho depende do opt-in CART-01. O `/start` não abre formulário individual/grupo automaticamente. Callbacks/aliases antigos existem para compatibilidade, sem garantir que a API atual execute ações do intérprete retirado.

| Controle | Alias | Texto fixo após clique validado | Efeito na API atual |
| --- | --- | --- | --- |
| Limpar tudo | `/limpar` | `Confirmo: apagar todos os dados deste pedido.` | Limpa memória do vínculo atual e encerra compra local ativa; não altera OAuth/carrinho remoto |
| Meus dados | `/limpadados` | `Confirmo: apagar meus dados da memória.` | Apaga apenas fatos SELF; titular continua existindo e destinatários são preservados |
| Remover pessoa | `/remover` | `Confirmo: remover <rótulo> do pedido.` | Remove destinatário/fatos da memória; não remove automaticamente participante DATA-01 ou itens já compostos |

Os comandos abrem pergunta; só o clique válido enfileira o texto fixo. O teclado é de uso único, preso a mensagem, tipo, sessão, versão e prazo de cinco minutos. Confirmação antiga não é atualizada silenciosamente para a conta/revisão nova. Esses textos não vêm da IA; a API os trata antes dos modelos.

`GET .../memory` retorna `{contractVersion:"1.0",revision,recipients,enabled}`. O diretório atual contém destinatários salvos, sem fatos/SELF. O cliente aceita a tipagem de personas e filtra RECIPIENT para até dez botões. Se a extensão falta/desabilita, usa nomes GROUP do snapshot por compatibilidade; lista vazia com extensão ativa é respeitada. O controle SELF permanece separado. Erro de protocolo/rede não vira exclusão confirmada.

## Cartões, escolha e preparação real

Na API atual, candidatos detalhados e elegíveis podem gerar `SET_PROPOSALS` persistido com cartões TEXT numerados. O texto digitado **`Confirmo: escolher a opção N.`** aplica SELECT_PROPOSAL sem IA e seleciona a sacola local. Referências transitórias itemRef não são IDs MCP nem sobrevivem como ferramentas entre turnos. Pessoa com restrições desconhecidas não ganha consumo elegível por confirmação genérica; falta de evidência obrigatória também bloqueia o item para ela.

O bot apresenta os textos da API; não há novo botão de escolha/CART-01 emitido automaticamente por esses cartões TEXT. Callbacks antigos guiados não são o contrato atual de escolha. O canal [CART-01](cart-01-telegram.md) existe com flag separada, mas o fio completo dessa nova sacola até revisão/confirmação ainda requer integração/verificação própria, sem ativação externa por suposição.

O ensaio `test_assistant_integration.py`, com ASSISTANT_API_ROOT para checkout exclusivo da API, percorre endereço→memória→proposta→escolha sem IA→revisão PREPARE_CART sem escrita, remoção de destinatário e invalidação após alergia. Modelo/OAuth/MCP/Telegram/gate são sintéticos. O novo job `integration-assistant` em Windows/Ubuntu está fixado no SHA completo acima; os dois pins históricos são preservados. Isso não comprova callback real de confirmação ou ativação online; resultados da CI devem ser conferidos no draft.

Suíte local na reconciliação: **290 testes executados, 17 ignorados e 273 aprovados**; Ruff check aprovado. Integrações históricas sem seus checkouts fixados continuam skips declarados; o novo caso acima foi executado contra a API atual. Não é CI remota/Docker ou polling real.

## Fechamento solicitado

O objetivo definido pelo usuário inclui **concluir o pedido pelo Telegram**, depois de revisar a composição, endereço, entrega, pagamento e total e clicar **“Confirmar e fazer pedido — R$ X”**.

Esse botão terá finalidade `SUBMIT_ORDER`, distinta do `PREPARE_CART` atual. Ele deve estar preso ao organizador/conta, carrinho, revisão/hash, total, pagamento, entrega, prazo e mensagem original. Mudanças invalidam a confirmação. O envio depende de intenção durável e resposta externa verificada; resultado desconhecido bloqueia repetição até reconciliação.

O código local cobre entrada natural, progresso, sessão capturada e administração de memória. A API já seleciona sacola por confirmação digitada; isso não é botão de envio. Entrega/pagamento/envio e o fio integrado da nova sacola às revisões continuam dependências próprias. Não há botão entregue que prometa fechar pedido sem backend correspondente.

Contrato completo e alcance: `api-backend/docs/assistente-conversacional.md` no checkout coordenado. Testes locais são sintéticos, sem polling real, cobrança ou escrita no iFood.

## Verificação documental e técnica

Fontes conferidas: `menu.py`, `runner.py`, `conversation.py`, `conversation_runner.py` e `outbox.py`; na API, `routes/conversation.ts`, `turns/store.ts`, `turns/runtime.ts` e `assistant/`. Testes relevantes: `test_assistant_progress.py`, `test_clear_profile.py`, `test_conversation_worker.py` e demais testes de sessão/outbox. Resultados datados de outros guias não são nova execução sobre esta árvore; testes que exigem checkout fixado permanecem históricos.
