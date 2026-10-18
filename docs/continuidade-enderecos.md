# Continuidade automática e endereço iFood — 18/10/2026

Base `main@d239edd43d072198367fd2fda3846fa29774ba65`, branch `codex/conversation-continuity-addresses`. O #17 de cart permanece separado. Este repositório não possui CLAUDE.md; foram lidos AGENTS.md, plano-conversacional.md, fila BOT-01, retomada BOT-02, contratos e código vigente dos dois repositórios. Nenhuma produção, flag, volume, polling real ou compra foi alterada.

## Causa e correção

O worker existente já consultava operações automaticamente. A navegação do #15 passou a anexar teclado comum à mensagem “Estou processando”; a edição final então podia receber 400, entrando em DELIVERY_UNKNOWN. Isso explica o efeito de Retomar conversa na imagem: o comando elimina o ID anterior e permite novo envio. A combinação foi reproduzida com Telegram real como cliente e servidor sintético que aplica a [restrição de edição da Bot API](https://core.telegram.org/bots/api#updating-messages). Não foram lidos logs/dados privados da instância; a causa operacional específica permanece a confirmar no ensaio.

Mensagens do worker agora usam teclado inline vazio e podem ser editadas, mantendo o menu já presente no chat. Uma edição repetida reconhecida como “message is not modified” confirma o mesmo ID/conteúdo, sem novo envio. Erros 400 genéricos continuam ambíguos. O reconhecimento após edição é persistido; replay de update e reinício não criam outro turno. O texto de processamento informa que a resposta chegará automaticamente; Acompanhar distingue fila, processamento/entrega, pausa e incerteza, além do último resultado concluído/falho/interrompido.

Após CONNECTED, o acompanhamento de OAuth agenda contexto e revisão de endereços automaticamente. Operação conhecida pausada por UNAVAILABLE pode voltar ao GET uma vez por origem de login. Não retoma POST desconhecido, transcrição, cancelamento, compra nem entrega Telegram incerta. Retomar conversa permanece recuperação manual opcional e explícita. Polling segue limitado por pollAfterMs/deadline, três falhas por ciclo e esperas existentes; não há nova implementação RUN-01.

Não existe garantia de execução única do sendMessage quando a resposta se perde antes do message_id. Nesse caso o bot mantém DELIVERY_UNKNOWN, sem reenviar automaticamente. Isso preserva ausência de duplicatas automáticas; o usuário pode escolher recuperação manual com aviso. Esse limite não é convertido em autorização para outro evento Gemini.

## Endereços

O novo cliente consome `GET .../addresses` e `POST .../addresses/select` da API da mesma branch; API deve ser implantada antes do bot. Sem endereço retornado validamente, orienta cadastro no aplicativo iFood. Com um, apresenta resumo e pede clique. Com vários, usa opções numeradas. Erro/timeout/schema inválido nunca afirma que a conta não tem endereço.

O callback `ifa:` exige organizador, conversa privada, bot emissor, mensagem original, referência e prazo registrados. A referência não é enviada ao modelo. Antes do clique só ficam hashes técnicos para vincular o botão; após clique, a outbox persiste a referência opaca autorizada para recuperação idempotente. Não persiste endereço, lista, rótulos, nome ou coordenadas. A API revalida lista, vínculo e seleção, sem escrita MCP. Endereço removido, trocado ou vencido exige nova confirmação.

Endereços iFood é uma navegação fora do modelo; coleta do grupo segue sem endereço. A API bloqueia apenas sugestões dependentes de localização até a escolha. Seleção de endereço não é PREPARE_CART, aprovação, entrega contratada ou pedido.

## Arquivos e validação

`conversation_runner.py` mantém acompanhamento/entrega e integra `address_flow.py`; `outbox.py` guarda deduplicação e vínculos técnicos dos botões; `conversation.py` valida o contrato adicional; `runner.py` e `menu.py` roteiam a navegação humana; `telegram.py` classifica somente o erro fixo de edição já aplicada, sem expor texto remoto.

Regressores em `test_continuity_addresses.py` cobrem a imagem, resposta sem Retomar, edição com ack perdido, reinício, OAuth, zero/um/múltiplos, callback/replay, origens inválidas, expiração e erro MCP com tentativas limitadas. `test_continuity_integration.py` usa HTTP real e API fixada com transporte Gemini, OAuth/MCP e Telegram sintéticos; valida consulta sem chamada extra ao modelo e isolamento entre organizadores. Os pins/testes históricos RUN-01 foram preservados.

Validação local final: **211 testes aprovados, nenhum ignorado**, com API atual fixada em `a72f7958bafda3036a5c6f77045d13925b25233b` ([API #47](https://github.com/Modo-Escuro/api-backend/pull/47)) e API histórica RUN-01 no pin preservado. Inclui os três novos ensaios HTTP e os sete históricos. Ruff, compileall, CLI --help e wheel aprovados. Não existe typechecker estático configurado neste projeto Python; compileall verifica sintaxe, não substitui análise estática de tipos. Build Docker fica na CI existente; a integração nova tem job próprio Windows/Linux.

## GO/NO-GO e deploy

GO técnico para revisão após checks; NO-GO operacional até revisão, autorização e ensaio humano. Preservar SQLite/WAL/SHM, vínculos/cursor, outbox e uma instância. Implantar API primeiro, conferir rotas/escopos/rollout sem cart, depois bot. Ensaiar texto → resultado automático, OAuth → contexto/endereço, seleção e sugestões, reinício e isolamento em dois celulares. Cart, pedido e pagamento continuam desligados.

Rollback do bot primeiro. Não apagar filas ou referências para contornar resultado incerto. Se reverter API para versão que usa endereço único automaticamente, pausar sugestões/conversa até restabelecer a confirmação obrigatória.
