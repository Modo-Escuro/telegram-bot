# Stakeholder Requirements Specification

## Agente de recomendação e pedidos em grupo do iFood

| Controle | Valor |
| --- | --- |
| Identificação | StRS Compra com Contexto |
| Organização | Modo Escuro |
| Versão e data | 0.2 de 17 de outubro de 2026 |
| Situação | Em validação pelos stakeholders |
| Destinatários | Responsável pelo produto, equipe de desenvolvimento e representantes dos usuários |
| Finalidade | Alinhar necessidades, regras e critérios de aceitação antes da implementação |

## 1 Propósito e escopo

O agente deve ajudar pessoas e grupos a escolher alimentos ou produtos disponíveis no iFood, considerando preferências, restrições obrigatórias, orçamento e contexto do pedido. A recomendação deve ser compreensível, verificável e passível de correção pelo usuário. A segurança das restrições alimentares precede qualquer objetivo de relevância, preço ou atendimento do grupo.

Esta especificação consolida as necessidades da reunião e as decisões já tomadas para o Compra com Contexto. O objetivo do hackathon inclui recomendação individual e coletiva, escolha de restaurante, montagem e fechamento do carrinho pelo MCP do iFood. O fechamento integra a entrega principal, sujeito à aprovação humana da versão revisada e ao contrato das ferramentas. O estado final exigido pelo evento permanece em DA10.

A versão 0.2 alinha essa prioridade ao briefing, preservando os identificadores e as decisões abertas. Não aprova políticas de rateio, pesos de ranking ou redução de escopo; a especificação continua em validação. As etapas técnicas e evidências de implementação são mantidas separadamente da definição das necessidades.

Estão no escopo a coleta e revisão de preferências, descrição do perfil, filtragem de candidatos, tratamento de informações alimentares insuficientes, ranqueamento, apresentação de duas a quatro opções e adaptação após mudanças. Pagamento dividido, negociação de preços, aconselhamento nutricional ou clínico, garantia de preparo e substituição do suporte do restaurante ficam fora desta versão.

### Stakeholders e necessidades

| Stakeholder | Necessidade principal |
| --- | --- |
| Usuário individual | Receber opções adequadas e entender os motivos da recomendação |
| Participante de grupo | Ter suas restrições e seu limite de gasto respeitados |
| Organizador da compra | Conferir cobertura do grupo, custos e mudanças antes de aprovar |
| Restaurante | Fornecer informações verificáveis de ingredientes, disponibilidade e preparo quando solicitado |
| Responsável pelo produto | Decidir políticas, prioridades e critérios de aceitação |
| Equipe de desenvolvimento | Implementar e demonstrar o comportamento acordado com evidências |

Os papéis de responsável pelo produto e aprovador da especificação precisam ser atribuídos pela equipe. A participação de restaurantes e a forma de contato dependem dos canais efetivamente disponíveis.

<!-- pagebreak -->

## 2 Conceito de operação e regras de negócio

O fluxo esperado é obter o contexto da compra, esclarecer informações necessárias, consultar as fontes disponíveis, aplicar restrições obrigatórias e só então ordenar os candidatos elegíveis. O agente apresenta as opções e suas justificativas; o usuário pode corrigir preferências, alterar o pedido ou pedir uma nova busca. Cada mudança relevante exige reavaliação das condições afetadas.

### Termos usados nesta especificação

| Termo | Significado operacional |
| --- | --- |
| Restrição obrigatória | Condição que não pode ser compensada por uma pontuação melhor |
| Preferência | Condição desejável que pode orientar comparação e desempate |
| Perfil | Descrição revisável de comportamentos e preferências, com origem e evidência |
| Candidato elegível | Opção que atende às restrições obrigatórias conhecidas e verificáveis |
| Informação pendente | Dado insuficiente, contraditório ou desatualizado que impede uma conclusão |
| Plano coletivo | Conjunto de itens, quantidades e custos proposto para participantes identificados |
| Cobertura do grupo | Participantes que recebem uma opção compatível e dentro de seu limite aplicável |

**RN01 Precedência.** Alergias, restrições obrigatórias e limites autorizados são verificados antes da pontuação. Nenhum benefício em outra dimensão compensa sua violação.

**RN02 Origem da restrição.** O histórico pode sugerir uma preferência, mas não comprova ausência de alergias nem autoriza remover ou flexibilizar uma restrição declarada. Informações contraditórias exigem esclarecimento.

**RN03 Informação alimentar insuficiente.** Item com possível incompatibilidade, ingrediente desconhecido relevante ou informação contraditória deve permanecer bloqueado para o participante afetado até confirmação rastreável do restaurante. Silêncio ou ausência de alerta não são confirmação.

**RN04 Disponibilidade e custo.** A comparação usa disponibilidade, preços, taxas, benefícios e estimativas de entrega observados para o contexto da compra. Dados ausentes ou vencidos não devem ser substituídos por valores inventados.

**RN05 Quantidade de opções.** O resultado esperado contém de duas a quatro opções elegíveis. Havendo menos de duas, o agente informa a insuficiência e apresenta somente as opções válidas existentes. Nunca completa a lista com candidatos incompatíveis.

**RN06 Alterações e confirmação.** Mudanças em participantes, restrições, itens, estabelecimento ou custos exigem reavaliação. Uma autorização anterior não cobre automaticamente um acordo alterado.

**RN07 Atendimento coletivo.** A busca pelo maior número de participantes atendidos não permite recomendar um alimento incompatível a uma pessoa, ocultar sua exclusão ou ultrapassar seu limite obrigatório.

<!-- pagebreak -->

## 3 Requisitos de perfil e recomendação individual

Os requisitos RS01 a RS27 formam a proposta de requisitos dos stakeholders. As prioridades são indicadas para validação: P0 significa essencial ao fluxo proposto; P1 significa evolução relevante. A aceitação exige os critérios da seção 8 e a resolução das decisões que afetem o requisito.

**RS01 Construir um perfil explicável e revisável.** O agente deve descrever padrões a partir do histórico disponível e de preferências declaradas, indicando a evidência e distinguindo observação de inferência. O usuário deve conseguir compreender e corrigir a descrição. Prioridade P0. Origem N01.

**RS02 Representar dimensões de comportamento.** A classificação deve distinguir frequência, variedade de escolhas, regularidade, contexto de uso e objetivos declarados. Rótulos como diverso, esporádico, metódico, corporativo ou fitness não devem ser tratados como categorias exclusivas nem como diagnósticos. A taxonomia e seus limiares precisam ser validados. Prioridade P0. Origem N01.

**RS03 Tratar histórico insuficiente.** Para contas novas ou histórico pouco representativo, o agente deve perguntar as preferências necessárias à compra atual e indicar quais informações ainda não conhece. A falta de histórico não deve impedir uma recomendação baseada nas respostas do usuário. Prioridade P0. Origem N02.

**RS04 Distinguir preferências atuais e duradouras.** O agente deve permitir que a pessoa informe uma preferência apenas para o pedido atual, revise uma preferência anterior e escolha o que poderá ser reutilizado em compras futuras. Uma correção deve afetar o resultado atual. Prioridade P0. Origem N01 e N02.

**RS05 Capturar o contexto da compra.** O agente deve obter a localização aplicável à entrega, o orçamento, a urgência e as necessidades alimentares relevantes. Deve distinguir um prazo máximo obrigatório de uma preferência por rapidez e esclarecer dados essenciais ausentes. Prioridade P0. Origem N08 e N09.

**RS06 Considerar horário e ocasião.** O agente deve considerar horário local do pedido e ocasiões declaradas ou verificadas para a região. Uma data comemorativa não deve alterar restrições ou orçamento. Ocasiões pessoais e intenções especiais devem ser confirmadas, sem pressupor que o usuário as comemora. Prioridade P0. Origem N05.

**RS07 Apresentar opções justificadas.** O agente deve apresentar de duas a quatro opções elegíveis quando existirem, com justificativas diretas sobre adequação, custo total conhecido, prazo estimado e principais diferenças. Deve identificar informações pendentes e seguir a exceção de RN05 quando faltar oferta válida. Prioridade P0. Origem N06 e N08.

**RS08 Explicitar as trocas da escolha.** Quando uma opção custar menos e outra chegar antes, o agente deve explicar essa diferença e respeitar a prioridade expressa pela pessoa. A justificativa deve se apoiar nos dados usados, sem atribuir ao usuário preferências não confirmadas. Prioridade P0. Origem N08 e N09.

<!-- pagebreak -->

## 4 Requisitos de restrições e confirmação com restaurante

**RS09 Registrar restrições de forma explícita.** O agente deve permitir que o usuário informe alergias, ingredientes proibidos e outras restrições obrigatórias, distinguindo essas condições de preferências. O registro deve identificar a pessoa afetada e a informação que precisa ser verificada para cada item. Prioridade P0 crítica. Origem N04.

**RS10 Bloquear candidatos incompatíveis.** O agente não deve recomendar, oferecer como substituição ou incluir em uma proposta destinada ao participante um item incompatível com suas restrições obrigatórias. Preço, promoção, avaliação ou preferência dos demais não podem anular esse bloqueio. Prioridade P0 crítica. Origem N03 e N04.

**RS11 Tratar incerteza como pendência bloqueante.** Quando não for possível verificar um ingrediente relevante ou quando houver indicação de possível presença, a opção deve ser excluída das recomendações elegíveis para a pessoa afetada. O agente deve explicar a pendência e não declarar o alimento compatível com base apenas no nome, foto, histórico ou inferência do modelo. Prioridade P0 crítica. Origem N04.

**RS12 Solicitar confirmação ao restaurante.** O fluxo deve permitir identificar o item e a dúvida específica, encaminhar ou orientar a confirmação pelo canal disponível e manter a opção bloqueada até resposta válida. Se o MCP não oferecer contato, deve ser possível registrar uma confirmação externa conforme a política a definir; o agente não deve fingir que contatou o estabelecimento. Prioridade P0 crítica. Origem N04.

**RS13 Registrar o alcance da confirmação.** A confirmação deve indicar estabelecimento, item ou variante, restrição verificada, resposta, origem e momento. O tratamento de preparo e contato cruzado deve seguir o conteúdo explicitamente confirmado. Uma resposta sobre outro item ou uma variante anterior não pode liberar automaticamente a opção atual. Prioridade P0 crítica. Origem N04.

**RS14 Reavaliar restrições após mudanças.** O agente deve verificar novamente as condições afetadas por troca de item, complemento, variante, restaurante ou participante. A pessoa deve conseguir distinguir o que foi verificado, o que conflita e o que ainda depende de confirmação. Prioridade P0 crítica. Origem N03, N04 e decisão anterior de preservar restrições.

### Resultado esperado da análise alimentar

Cada combinação entre participante e item deve ter um estado compreensível: compatível com as informações verificadas, incompatível ou pendente de confirmação. Somente o primeiro estado permite elegibilidade para aquela pessoa. O estado pendente não pode ser apresentado como uma recomendação segura; pode aparecer separadamente como uma dúvida a resolver.

Uma confirmação do restaurante deve ser apresentada com seu alcance real. Ela não autoriza o agente a prometer ausência de risco, inventar certificações ou generalizar a resposta para todo o cardápio. A política de validade e de validação da evidência é uma decisão aberta em DA03.

<!-- pagebreak -->

## 5 Requisitos de recomendação coletiva

**RS15 Representar cada participante.** O plano coletivo deve permitir informar, por pessoa, preferências, restrições obrigatórias e quanto pode gastar. Dados inferidos do histórico devem ser apresentados como sugestões para confirmação e não podem substituir declarações sobre restrições obrigatórias. Prioridade P0. Origem N07.

**RS16 Demonstrar atendimento e custos.** Cada plano deve mostrar quais itens atendem a quais participantes, quantidades, participantes cobertos e eventual informação insuficiente. Deve mostrar valores individuais quando aplicáveis e os custos totais conhecidos. Não presumir porções ou atendimento de uma pessoa sem evidência suficiente. Prioridade P0. Origem N07 e N08.

**RS17 Respeitar limites individuais e coletivos.** O ranking de grupo deve considerar os limites informados por pessoa e o teto do grupo quando definido. Fretes, taxas e descontos devem ser incluídos e atribuídos conforme uma política explícita. Sem a política necessária para verificar um limite, o plano não deve ser apresentado como validado quanto a esse limite. Prioridade P0. Origem N07 e N08.

**RS18 Buscar o maior atendimento permitido.** O agente deve priorizar planos que atendam ao maior número de pessoas respeitando suas condições obrigatórias. Deve distinguir um plano completo de uma alternativa parcial. A falta de plano completo deve ser explicada e encaminhada para decisão explícita sobre ajuste de preferências, orçamento ou subgrupos. Prioridade P0. Origem N07 e N10.

**RS19 Evitar exclusão silenciosa.** O agente deve informar quais participantes não foram atendidos e por quê. Uma alternativa parcial não deve ser executada como se resolvesse a compra inteira. Restrições alimentares obrigatórias não podem ser removidas como forma de aumentar a cobertura. Prioridade P0. Origem N04 e N07.

**RS20 Adaptar e obter aprovação.** Quando o grupo ou a proposta mudar, o agente deve mostrar o que mudou, recalcular os efeitos conhecidos e reapresentar a versão atual para aprovação humana antes do envio. A política de quem pode alterar informações e quem aprova o pedido coletivo precisa ser definida em DA05. Prioridade P0. Origem N07 e decisões anteriores.

### Conflitos esperados

Uma preferência por restaurante pode ser negociável; uma restrição obrigatória não deve ser sacrificada para manter esse restaurante. Se nenhuma combinação atender ao grupo inteiro, o sistema deve apresentar o conflito. A decisão de dividir o grupo, alterar um limite de gasto ou desistir pertence às pessoas autorizadas, sem flexibilização automática de alergias ou ingredientes proibidos.

A quantidade de restaurantes por plano, o rateio dos custos e a possibilidade de subgrupos dependem de DA04 e DA06. Até essas decisões, não há regra aprovada para declarar viável uma compra coletiva que dependa delas.

<!-- pagebreak -->

## 6 Requisitos de confiança e integração

**RS21 Usar fontes verificáveis.** Recomendações devem usar informações retornadas pelo MCP do iFood ou por outra fonte aprovada, identificando a origem quando necessário. Disponibilidade, preço e prazo devem ser revalidados na etapa de continuidade do pedido. Falha de consulta não autoriza fabricar resultados. Prioridade P0. Origem N03, N08 e briefing.

**RS22 Manter as regras independentes da resposta gerada.** O resultado deve ser conferido contra restrições, orçamento e elegibilidade antes de ser apresentado como válido. Texto do restaurante ou retorno de ferramenta não pode alterar as regras ou a autorização do usuário. A correção depende da verificação do estado, não da confiança declarada pelo modelo. Prioridade P0. Origem N04 e necessidade de robustez.

**RS23 Explicar limites e falhas.** O agente deve reconhecer dados ausentes, ferramentas indisponíveis e resultados contraditórios. Deve pedir esclarecimento, apresentar alternativas verificadas ou informar que não pode concluir a recomendação. Uma explicação não deve declarar um resultado que a ferramenta não confirmou. Prioridade P0. Origem N03, N04 e alinhamento de cenários.

**RS24 Preservar histórico de decisões.** A equipe deve conseguir reconstruir a versão do contexto, as restrições consideradas, os candidatos filtrados, os motivos da ordenação e a aprovação aplicável. Os registros devem permitir investigar falhas sem expor credenciais ou detalhes desnecessários dos participantes. Prioridade P0. Origem N09, N10 e necessidade de avaliação.

**RS25 Controlar dados e memória.** A pessoa deve conhecer quais preferências e dados de pedidos são utilizados, poder corrigir informações e solicitar que uma preferência não seja mantida. Em grupos, a visualização e alteração das informações de outras pessoas devem respeitar os papéis acordados. Retenção e compartilhamento são definidos em DA07. Prioridade P0. Origem N01, N02 e N07.

**RS26 Medir qualidade e tempo de resposta.** A avaliação deve separar cumprimento de restrições, correção dos custos, utilidade do ranking, clareza das justificativas e tempo de resposta. Metas de latência e utilidade precisam ser aprovadas em DA08; não se presume desempenho já alcançado. Prioridade P1. Origem N06, N08, N09 e N10.

**RS27 Respeitar a fronteira do fechamento.** No fluxo do hackathon, o agente deve obter aprovação da versão atual do carrinho antes do envio, preservar a identidade de tentativas repetidas e informar o estado comprovado pelo provedor. Resultado de envio desconhecido exige consulta ou reconciliação quando suportada; sem evidência confiável, o reenvio deve permanecer bloqueado. Prioridade P0 para a entrega principal do hackathon. Origem briefing e decisões anteriores.

### Dependências externas

O endpoint confirmado para os quatro domínios é https://consumer-mcp.ifood.com.br/marketplace. O usuário forneceu saída autenticada com cinco ferramentas anunciadas e nenhuma operação de negócio. Contratos restantes, respostas de consultas e suporte a contato com restaurante ainda precisam ser validados. Esta especificação não presume histórico completo nem meios de pagamento específicos. Os passos técnicos estão em docs/ifood-mcp.md e docs/chamadas-ifood.md.

<!-- pagebreak -->

## 7 Diretrizes propostas para os rankings

As diretrizes desta seção são propostas para elaborar e validar as duas funções solicitadas na reunião. Elas descrevem comportamentos esperados e não constituem pesos aprovados, algoritmo implementado ou resultado de avaliação.

### Ranking individual

Primeiro devem ser eliminados itens indisponíveis para a localização e contexto, incompatíveis com restrições obrigatórias ou sem informação suficiente para verificá-las. Também devem ser aplicados os limites obrigatórios de orçamento e prazo quando definidos. Os itens restantes podem ser comparados por preferência atual, evidência do perfil, horário ou ocasião, custo total, tempo estimado, localização e avaliação da loja.

Uma formulação candidata é uma soma de critérios normalizados, com pesos dependentes do contexto e previamente definidos pela política do produto. A pressa declarada pode aumentar a importância do prazo entre candidatos elegíveis. Uma preferência por economia pode aumentar a importância do custo total. O modelo não deve ajustar pesos para liberar um candidato bloqueado.

Distância pode ser um critério adicional quando tiver utilidade própria; sua relação com frete e prazo precisa ser avaliada para evitar contar repetidamente o mesmo efeito. Avaliações de loja precisam de política sobre quantidade e atualidade das avaliações. Dados ausentes devem seguir uma regra explícita, sem preenchimento favorável inventado.

Os pesos, a normalização, os desempates e a contribuição do perfil ficam em DA02. Uma alternativa barata e lenta pode ser mantida ao lado de outra mais rápida quando ambas atenderem às condições e representarem escolhas diferentes. As justificativas devem explicar essas trocas com valores observados.

### Ranking coletivo

O objeto ranqueado deve ser um plano de compra, com associação de itens a participantes e custos verificáveis. Para cada pessoa, deve ser possível verificar compatibilidade e gasto conforme a política de rateio. Não basta somar avaliações de produtos ou calcular uma média que esconda uma restrição violada.

Propõe-se uma ordenação em etapas: maior cobertura válida; entre planos de mesma cobertura, melhor atendimento à pessoa menos satisfeita segundo preferências negociáveis; depois satisfação agregada; por fim critérios de custo, prazo e desempate aprovados. Essa ordenação busca evitar que uma média alta esconda atendimento muito ruim de alguém e precisa ser validada em DA06.

Se houver planos que atendam a todos, alternativas parciais não devem substituí-los apenas por terem maior pontuação média. Se não houver plano completo, o resultado deve explicar a inviabilidade e apresentar alternativas parciais somente como propostas de reorganização, com participantes excluídos identificados e nova decisão humana.

### Entregáveis decorrentes dos action items

**AI01 Ranking individual.** Produzir a definição dos fatores, fontes, normalização, pesos por contexto, desempates e testes de ordenação esperada. Vincular a RS01 a RS08, RS21, RS22 e RS26.

**AI02 Ranking de grupo.** Produzir a definição de cobertura, compatibilidade por pessoa, custos atribuídos, justiça entre participantes, tratamento de inviabilidade e testes de planos coletivos. Vincular a RS09 a RS20, RS22 e RS26.

As duas funções precisam de exemplos com resultados esperados aprovados pela equipe antes de uma comparação quantitativa. As métricas devem separar violação de regra obrigatória de diferença legítima entre opções preferidas.

<!-- pagebreak -->

## 8 Critérios de aceitação dos stakeholders

Os cenários abaixo são critérios planejados. Nenhum resultado é declarado como executado ou aprovado por esta especificação. Nos casos críticos de restrição, qualquer recomendação bloqueada que seja apresentada como elegível reprova o cenário.

| ID e requisitos | Cenário | Resultado esperado |
| --- | --- | --- |
| CA01 RS01 RS02 | Histórico repetitivo com usos variados | Perfil por dimensões e evidência, sem forçar um rótulo exclusivo |
| CA02 RS03 RS04 | Conta nova ou preferência temporária | Perguntas pertinentes; resposta atual respeitada sem memória permanente presumida |
| CA03 RS07 | Quatro ou mais candidatos elegíveis | Apresentar de duas a quatro opções com justificativas e dados observados |
| CA04 RN05 RS07 | Existir zero ou um candidato elegível | Informar insuficiência e apresentar apenas o que for válido, sem completar a lista |
| CA05 RS09 RS10 | Participante declara ingrediente proibido e há candidato com esse ingrediente | Bloquear o item para essa pessoa em recomendações, substituições e plano coletivo |
| CA06 RS11 RS12 | Não é possível verificar ingrediente relevante | Manter bloqueio e pendência até confirmação do restaurante |
| CA07 RS13 RS14 | Confirmação referente a outro item ou troca de variante | Não reutilizar a liberação; verificar a nova combinação de item e restrição |
| CA08 RS05 RS08 | Opção mais barata ultrapassa prazo máximo declarado | Excluir a opção; se rapidez for só preferência, explicar a troca sem inventar dados |
| CA09 RS06 | Pedido em horário ou ocasião especial | Considerar contexto verificado sem alterar restrições ou pressupor celebração pessoal |
| CA10 RS15 RS17 | Pessoas com limites diferentes e custos de entrega | Verificar gastos e rateio; se a política necessária faltar, indicar pendência |
| CA11 RS18 RS19 | Nenhum plano completo atende às condições | Explicar o conflito e identificar cobertura parcial sem excluir alguém silenciosamente |
| CA12 RS14 RS20 | Entrar participante ou trocar restaurante após aprovação | Reavaliar as condições afetadas e reapresentar a versão atual para aprovação |
| CA13 RS21 RS23 | Item fica indisponível ou consulta falha | Não recomendar item indisponível nem inventar nova oferta |
| CA14 RS22 | Descrição externa pede para ignorar orçamento ou restrições | Preservar as regras e tratar o texto como dado externo |
| CA15 RS24 RS25 | Usuário corrige o perfil e a equipe investiga o resultado | Aplicar a correção e permitir rastreio sem expor dados desnecessários |
| CA16 RS27 | Falta resposta depois de um envio ou há retry | Informar resultado desconhecido ou recuperar o existente; não afirmar novo sucesso sem evidência |

Para os rankings, a aceitação exige também um conjunto de contextos e ordenações esperadas acordadas em DA02 e DA06. A equipe deve registrar ferramentas e dados utilizados, resultados e divergências observadas. Metas numéricas de tempo e utilidade permanecem pendentes em DA08.

<!-- pagebreak -->

## 9 Rastreabilidade e decisões para validação

### Rastreabilidade das necessidades da reunião

| Origem | Necessidade | Requisitos relacionados |
| --- | --- | --- |
| N01 | Perfil coerente com tipo e frequência dos pedidos | RS01 RS02 RS04 RS25 |
| N02 | Perguntar preferências em contas novas | RS03 RS04 RS05 |
| N03 | Evitar itens indisponíveis ou inadequados | RS10 RS14 RS21 RS23 |
| N04 | Restrições alimentares e confirmação com restaurante | RS09 a RS14 RS22 |
| N05 | Horário e datas especiais | RS06 |
| N06 | Retornar duas a quatro opções justificadas | RS07 RS08 RS26 |
| N07 | Preferências e gasto individual em grupo | RS15 a RS20 RS25 |
| N08 | Localização prazo e custo | RS05 RS07 RS08 RS17 RS21 |
| N09 | Pontuação contextual individual | RS01 a RS08 RS21 RS22 RS26 AI01 |
| N10 | Ranking de pedidos para grupos | RS15 a RS20 RS22 RS26 AI02 |

### Decisões abertas

| ID | Decisão a validar | Papel responsável proposto |
| --- | --- | --- |
| DA01 | Taxonomia de perfil, janela e volume mínimo de histórico, atualização e confiança | Produto e responsável pelo ranking |
| DA02 | Fatores, pesos, normalização, dados ausentes e desempates do ranking individual | Produto e equipe de desenvolvimento |
| DA03 | Canal, conteúdo mínimo, validade e validação da confirmação do restaurante | Produto e integração com restaurantes |
| DA04 | Rateio de frete, taxas, descontos e conciliação entre teto coletivo e limites individuais | Produto e representantes dos usuários |
| DA05 | Quem pode informar, alterar e visualizar dados de cada participante e aprovar a compra | Produto e representantes dos usuários |
| DA06 | Número de restaurantes, propostas parciais, subgrupos e ordenação de justiça coletiva | Produto e responsável pelo ranking |
| DA07 | Memória, retenção, correção e compartilhamento de preferências e histórico | Responsável pelo produto |
| DA08 | Metas de latência, utilidade, clareza e conjunto de avaliação dos rankings | Produto e qualidade |
| DA09 | Dados e operações realmente disponíveis no MCP, incluindo histórico e contato com restaurante | Equipe de integração |
| DA10 | Estado final exigido pelo evento e relação com carrinho, pedido e pagamento | Produto e mentoria do evento |

Os papéis são propostos e ainda precisam de atribuição nominal. Nenhum peso de ranking, limiar de perfil, política de rateio ou meta de desempenho é considerado aprovado nesta versão.

### Revisão e aprovação

A revisão deve confirmar o significado dos requisitos, as prioridades P0 e P1 e o tratamento de insuficiência de dados. A aprovação deve registrar versão, responsáveis, data e decisões abertas que ainda limitem a implementação. Mudanças posteriores devem manter os identificadores dos requisitos e atualizar seus critérios de aceitação e vínculos.
