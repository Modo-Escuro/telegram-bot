# Conversa curta e menu reduzido

Pedido de 18/10/2026: respostas pequenas, sem repetir o grupo e com menos botões. O menu passa a ter somente Conectar iFood, Endereços iFood, Esvaziar sacola, Ajuda e Sair da demo. Minha conexão, Verificar conexão, Interromper e Acompanhar saem do menu; os aliases antigos continuam funcionando. Ajuda mantém /retomar e /desconectar. Acompanhar consultava mensagens do bot, nunca acompanhamento de pedido.

O worker usa apresentação concisa: confirmações das alterações e uma pergunta rotineira por vez, sem repetir GROUP, orçamento inalterado, “Nada foi alterado” ou “Pergunta registrada”. Bloqueios, custo desconhecido, recusas e alertas continuam aparecendo. O renderizador completo permanece disponível para a retomada do grupo após OAuth. Não há novos snapshots ou dados pessoais persistidos no bot.

Esvaziar sacola envia uma intenção humana explícita de limpar a composição simulada pelo fluxo existente, com isolamento, eventId e outbox. A API valida CLEAR_BAG; o botão não chama carrinho real, cancelamento ou pagamento. Ele permanece disponível no menu e a API informa quando a sacola já está vazia. O despacho direto sem modelo e a interpretação contextual de “Não” dependem da continuação correspondente da API (#49).

A API pode fornecer link da foto original de um item da primeira proposta completa. A prévia depende do Telegram; não há envio separado de foto nem imagem inventada. Candidato sem evidência alimentar não é promovido a recomendação por ter foto.

Regressões sintéticas: menu reduzido, botão sem reenvio por replay, resposta sem grupo repetido, confirmação curta e preservação dos avisos de alergia e custo. Sem polling real, merge na main ou deploy. O comportamento online ainda depende de implantação autorizada e ensaio humano.
