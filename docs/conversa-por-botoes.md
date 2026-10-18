# Conversa e navegação por botões

Pedido do usuário em 18/10/2026: respostas mais amigáveis, navegação sem digitar comandos e conclusão do login no navegador sem confirmação duplicada no Telegram.

O teclado persistente oferece Conectar iFood, Minha conexão, Verificar conexão, Acompanhar, Retomar conversa, Interromper, Ajuda e Sair da demo. Minha conexão apresenta os botões de cancelamento da tentativa e desconexão, vinculados à referência atual. Rótulos são traduzidos em controles antes da fila/modelo; aliases antigos continuam aceitos por compatibilidade, sem serem anunciados. O botão Iniciar nativo do Telegram permanece a entrada inicial.

Entrar na demo solicita a senha em mensagem privada. A senha não entra na fila, no modelo, no SQLite nem na resposta; sua mensagem é apagada por melhor esforço. Só metadados de espera por cinco minutos são persistidos. Permanecem os limites de tentativas e sessões. Cancelar entrada encerra a espera; Sair da demo encerra o acesso sem desconectar silenciosamente a conta iFood.

O grupo é apresentado sem repetir confirmações de inclusão e orçamento já refletidas nos fatos do snapshot. Alergias, preferências, dados desconhecidos, alertas, recusas e bloqueios permanecem. Apenas perguntas rotineiras de coleta são apresentadas uma de cada vez; outras pendências não são ocultadas. Nenhuma nova chamada de modelo foi adicionada.

Refinamento de texto em `codex/bot-accessible-messages`, em continuação ao PR #18 já mergeado: apresentação em parágrafos curtos e explicação dos botões em lista, tanto no Iniciar quanto na entrada com senha. O aviso geral sobre login, sacola simulada e ausência de envio fica na apresentação inicial; consultas de conexão, endereço, acompanhamento e rodapé da conversa não o acrescentam novamente. Ajuda também usa lista, e Status não recebe novamente todo o guia de botões. Avisos específicos de custo desconhecido, restrição alimentar, aprovação indisponível, cancelamento e resultado externo desconhecido permanecem.

Retomar conversa explica que uma resposta já recebida pode aparecer novamente durante a recuperação. Essa informação aparece ao retomar, sem o termo técnico “entrega incerta” na apresentação. Acompanhar apresenta os estados em lista, sem repetir a explicação dos botões. Não houve alteração de fila, aprovação, chamadas ao modelo, bancos ou polling.

Validação deste refinamento: suíte com **201 testes aprovados e 10 integrações ignoradas** por falta das variáveis de checkout fixado; Ruff check/format, compileall e diff conferidos. As integrações ignoradas não foram contadas como aprovadas. Sem merge/deploy deste refinamento.

Atualização da base do PR #20 para `main@46afe08beedd617a4d547ed18cd3f47fd4b11f72`: preserva a recuperação de respostas antigas do #19, sem alterar suas condições de reenvio ou recuperação por GET. A suíte atualizada passou com **205 testes aprovados e 10 integrações ignoradas**. Foram normalizados apenas imports e formatação trazidos pela nova base para manter Ruff check/format aprovados; compileall e diff também aprovados. A atualização ocorreu somente na branch do PR, sem merge na main ou deploy.

O retorno automático depende da atualização correspondente do api-backend (`docs/login-retorno-natural.md`). O bot acompanha o estado existente, consulta o grupo e não repete ações. Um botão antigo de confirmação mostra o estado atual, sem confirmar uma nova tentativa. A confirmação manual permanece como recuperação de uma tentativa antiga ou falha ao salvar o vínculo. Cancelar/desconectar antigos continuam incapazes de afetar outra referência.

## Ensaio humano

O usuário relatou que a retomada anterior funcionou, mas também informou o erro no botão antigo e o texto repetitivo. Esse relato não é inspeção independente nem comprova isolamento em uma segunda conta.

Após implantar ambos os incrementos: entrar na demo pelos botões, informar Ana/Bia, alergia a amendoim e teto de R$ 180; corrigir para R$ 150; tocar Conectar iFood, autorizar a conta teste e voltar ao Telegram. Esperado: conexão acompanhada sem segundo clique, grupo preservado com R$ 150,00 e sem proposta/aprovação antiga. Conferir Minha conexão, Acompanhar e um botão antigo. Não iniciar outra instância de polling; preservar os volumes e bancos.

Validação local: testes sintéticos da navegação, captura privada de senha, expiração/reinício, botão antigo, transporte do teclado e resposta apresentada pelo usuário, além da suíte completa e integração HTTP. A nova experiência online ainda precisa do ensaio humano.
