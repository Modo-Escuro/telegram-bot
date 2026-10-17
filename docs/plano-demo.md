# Etapas da demo

Objetivo: organizar uma compra de grupo, alterar orçamento ou itens preservando restrições, revisar a sacola e enviar somente após aprovação humana válida no ambiente de teste autorizado.

1. Implementar e validar o [login iFood associado ao organizador](login-ifood.md), incluindo vínculo confirmado, expiração, renovação e desconexão. Token armazenado não comprova sessão válida. Depois validar listAddresses → searchOffers → getItem e preservar evidências sanitizadas.
2. Definir contrato HTTP para conversa, estado da sacola, alterações, aprovação e status. Rotas ainda não definidas; não presumir /chat ou /approve. Autenticar o bot e associar o organizador à conta de teste.
3. Implementar Python com long polling, conversa privada e organizador permitido. Não precisa de webhook público do Telegram; OAuth iFood é uma conexão separada.
4. Manter participantes, limites e restrições no backend. Definir rateio e quantidade de restaurantes explicitamente; permanecem decisões abertas.
5. Implementar operações de carrinho no backend após confirmar seus contratos. Preservar listAddresses, getItem antes de adicionar e listagens de entrega/pagamento/cupom antes de selecionar.
6. Apresentar versão, itens, distribuição de custos, total e validade. Validar aprovação fora do modelo. Bloquear confirmação antiga, usuário diferente e repetição de envio.
7. Ensaiar alteração de orçamento, item incompatível, clique repetido e timeout após envio. Não declarar sucesso externo sem confirmação do provedor.

## Dados necessários no contrato proposto

- Evento: identificador de deduplicação, origem Telegram validada, sessão, texto ou ação.
- Resposta: mensagem, opções elegíveis, estado, versão da sacola, custos em centavos, validade e ações permitidas.
- Aprovação: referência opaca à revisão, organizador autenticado e registro verificável do clique humano; nunca autorização gerada pelo agente.
- Resultado: não enviado, aguardando aprovação, enviando, confirmado, falhou ou resultado desconhecido; erros que permitam recuperação segura.

Estes são requisitos de contrato, não nomes de rotas nem schemas implementados.

## Preservação

O repositório original continua íntegro. Não apagar ou arquivar automaticamente. docs/baseline conserva a especificação e os contratos com hash SHA-256. Alterações futuras de requisitos devem identificar a versão de origem e preservar IDs e decisões abertas.
## Incremento entregue: canal Telegram

Long polling, /start, /status, /ajuda, identificação local por desafio, acesso privado ao organizador e cursor persistente estão implementados. Testes automatizados simulam Telegram; validação real depende do token local. Backend, login iFood e operações de compra continuam pendentes. Consulte [executar o bot](executar-bot.md).
