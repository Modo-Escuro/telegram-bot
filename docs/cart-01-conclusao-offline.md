# CART-01 — Continuação integrada offline em 18/10/2026

Esta continuação acompanha o [draft bot #17](https://github.com/Modo-Escuro/telegram-bot/pull/17), dependente do [draft API #46](https://github.com/Modo-Escuro/api-backend/pull/46). Endereços API #47 e bot #18 já estão nas mains `a027ed4` e `6adb78d`. O texto abaixo registra a preparação/auditoria local anterior à publicação; publicar não significa merge, deploy ou ativação.

Integração local de `codex/conversation-continuity-addresses@52b9381` (#18) com `codex/cart-01-telegram@0d6caec` (#17), em `codex/cart-01-integration`. O checkout antigo do usuário e as branches remotas foram preservados. A API local combina main `39edd95` (INT-02 #48), endereço #47 e CART-01 #46. Código local não comprova merge remoto, deploy ou resposta real do iFood.

Foram seguidos AGENTS.md, regras preservadas, plano da demo e conversacional, DEC-01, fila BOT-01, retomada BOT-02, contratos de endereço/CART-01 e documentação da API. Baseline, schemas v1.0, fixtures e pins históricos RUN-01/endereços não foram alterados.

## O que mudou nesta continuação

- Um mesmo roteador atende `ifa:` (endereço) e `cart:` (preparação), mantendo a validação de remetente, bot, chat privado, mensagem, referência e prazo. Nenhum callback vira mensagem ao modelo.
- Revisão mostra conta mascarada, loja, resumo seguro do endereço, itens, opções com nomes, quantidades, destinatários/restrições, orçamento e custos anteriores. A API vincula descrições/identidade por hash; mudanças invalidam a revisão mesmo com total igual.
- Item remoto a remover tem identificação legível, sem depender de estar na composição desejada. Opção sem nome, identidade incompleta ou revisão longa continuam bloqueando o botão.
- Após confirmar, o bot consulta `GET cart-writes/requests/:requestId` quando necessário e `GET cart-writes/current` para exibir composição/custos observados. A consulta atual informa que restrições/disponibilidade não foram revalidadas; não libera pedido/pagamento.
- Falha da consulta final preserva o resultado técnico SUCCEEDED e permite nova consulta por GET, sem repetir POST. Uma resposta perdida da confirmação pode ser recuperada no mesmo ciclo; reinício mantém RESULT_UNKNOWN bloqueado.
- `cart_view.py` valida centavos inteiros, componentes/somas, preços unitários, quantidades, rótulos e tamanho antes de mostrar custos como observados. Dado ausente não vira zero nem total confirmado.

Referências humanas permanecem apenas na RAM e fora do modelo. SQLite do bot guarda marcador técnico e deduplicação; não guarda nomes, identidade, endereço, composição, custos, texto ou referência de autorização. `PREPARE_CART` não é `SUBMIT_ORDER`.

## Ensaio reproduzível

Com a API local de integração e a venv do bot preparados:

```powershell
$env:CART_API_ROOT = 'caminho absoluto do checkout da API integrada'
python -m unittest discover -s tests -p test_cart_integration.py -v
```

O teste sobe API/Hono/SQLite reais em loopback com gateway MCP falso e dados sintéticos. Nenhum token real, polling Telegram, login ou ferramenta iFood é usado. O fixture só inicia com `CART_TEST_ONLY=1`, não herda env de credenciais e persiste o efeito do provedor falso separadamente do banco da API.

Os três cenários exercitam endereço obrigatório → revisão → clique → preparação → custos finais; replay/isolation; resposta perdida e falha de consulta; reinício de API/bot com resultado desconhecido e sem segunda escrita. Unitários também cobrem rótulos ausentes, opções e remoções, erro de protocolo, privacidade no SQLite e recuperação do mesmo requestId.

A workflow `Ensaio HTTP CART-01` roda em push/PR com a API fixada em `11a05ce87ed61c1d9ab013fd98aa65ec89ea7d54` (draft #46), em Windows/Linux. Também aceita execução manual com outro SHA completo revisado. Não altera os pins históricos RUN-01/endereços. A execução remota será conferida após a publicação.

Checks finais após a correção da auditoria: **237/237 testes passaram**, sem ignorados, com CART_API_ROOT na API integrada e CONTINUITY_API_ROOT/BOT01_API_ROOT nos commits históricos preservados. Ruff check/format dos sete arquivos alterados, compileall, pip check, CLI --help e diff check aprovados. A API passou em 1.050 testes (dois ignorados por plataforma), typecheck/lint/build. HTTP e SQLite são reais; as respostas MCP continuam sintéticas.

## Estado de entrega e próximas tarefas

`TELEGRAM_CART_ENABLED=false` permanece padrão. A auditoria independente autorizada encontrou e revalidou a correção de uma chave de opção que duplicava rótulos na revisão de carrinho existente. O probe passou a devolver um único rótulo; 23 testes bot e quatro regressões API passaram na reauditoria, além dos 87 API e três HTTP da primeira rodada. Parecer: GO técnico com flags desligadas, nenhum achado acionável remanescente no delta. Se a API demorar e a intenção retornar PENDING, o acompanhamento final exige Conferir carrinho (GET); é uma limitação UX documentada, sem retry de POST.

A suíte e a auditoria não dão GO operacional: faltam evidência autenticada/manifesto INT-02 e ensaio humano em ambiente autorizado. O #48 da API entregou preparação offline, sem outputs observados de carrinho. A autorização atual não permite contornar essas guardas.

BOT-03 foi adiantada na revisão e apresentação final; escolha/correção integral de propostas por botões permanece pendente. A API também adianta OPS-02 com métricas sanitizadas de tentativas e contagens persistidas de intenções. BUY-01 pode avançar offline em contrato/regressões para uma autorização própria de envio; BUY-02 depende de contrato específico de envio/status/recuperação. Não houve envio ou pagamento.

Na implantação futura autorizada: API antes do bot, bancos/vínculos/outbox/cursor preservados e um único polling. Não rebaixar banco v3 nem apagar PENDING/RESULT_UNKNOWN para liberar tentativa. O delta atual ainda não foi publicado nem implantado.
