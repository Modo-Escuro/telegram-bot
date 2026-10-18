# Contrato de conversa — especificação proposta v0

Estado: proposta de interface, **não implementada**. [API-01](https://github.com/Modo-Escuro/api-backend/issues/12) fecha nomes de rotas, schemas e compatibilidade antes da implementação. [Plano](plano-conversacional.md).

## Operações lógicas

| Operação | Entrada | Saída |
| --- | --- | --- |
| Aceitar evento | eventId estável, conversa, tipo, texto ou referência de ação, versão esperada quando aplicável | operationId, estado aceito/em andamento/concluído, versão do contrato |
| Consultar processamento | operationId pertencente ao organizador | estado, resultado recuperável ou erro seguro, orientação de nova consulta |
| Consultar compra | referência da conversa/compra | versão, contexto resumido, propostas/sacola e ações disponíveis |
| Aplicar ação humana | referência opaca e evidência do callback validado pelo adaptador | resultado da ação ou conflito/expiração |
| Solicitar cancelamento local | operationId | aceitação/rejeição e alcance; não alega reversão de efeito remoto |

Essas linhas não declaram endpoints disponíveis. O contrato de login existente permanece. F7 contém rotas em branch e não é habilitada por este documento.

## Identidade e autorização

Bearer de serviço e identidade do Telegram validada no adaptador. A API verifica allowlist, pertencimento e vínculo atual. Não confiar em organizerId/userId fornecido pelo texto/modelo. userId não é parâmetro do MCP iFood.

Aprovação de conexão e de compra são ações diferentes. A referência de compra é opaca, expira, tem uso único e fica fora do contexto do modelo. A API rejeita dados de conta ou preço fornecidos pelo botão como fonte de verdade.

## Evento e deduplicação

A chave é gerada/derivada pelo adaptador antes do primeiro envio e preservada em retry/restart. O escopo inclui a origem autorizada; não deduplicar apenas pelo texto ou valor. Persistir hash canônico do conteúdo: mesma chave/outro conteúdo => conflito.

API só confirma aceitação após persistência. Bot só avança o tratamento durável depois de registrar o vínculo evento/operação ou uma resposta final. Definir atomicidade, recuperação de falha entre passos e retenção de chaves; nunca expirar identidade de uma intenção remota ainda desconhecida.

## Proveniência de cada alteração

Cada alteração declarada pelo usuário deve conservar o `eventId` aceito pela API e uma referência interna à mensagem ou ação específica que a originou. A referência é escopada ao canal, bot e conversa; no Telegram, o adaptador a deriva do update validado (mensagem ou callback). IDs isolados não são globalmente únicos nem autorização.

O adaptador autenticado fornece os metadados de origem; o modelo não os inventa. A API associa patch, versão resultante e origem. Correções posteriores preservam a cadeia de origem das versões anteriores; replay conserva a associação sem criar nova alteração. Recalculos derivados apontam para o evento causador, sem fabricar uma mensagem humana.

O registro de proveniência não exige armazenar o texto integral. Retenção, acesso e expurgo dos metadados seguem DA07 e precisam preservar o mínimo necessário às intenções ainda em andamento. Dados privados do canal não entram em logs ou fixtures.

Critérios de contrato: rastrear mudança de orçamento até a mensagem correta após reinício; conservar a origem de restrição anterior; rejeitar referência de outro escopo; não duplicar proveniência em replay. Implementação em [DATA-01](https://github.com/Modo-Escuro/api-backend/issues/13), com schemas em [API-01](https://github.com/Modo-Escuro/api-backend/issues/12).

## Versionamento e resultado

Schema estrito, versão de contrato e versão de compra independentes. Patches usam versão esperada; resultado de busca vincula-se à versão consultada e não substitui estado novo. Resultado informa fase, versão, pendências, cobertura por pessoa, custos/validade e ações realmente permitidas.

Dinheiro em *Cents, BRL, inteiros; null/desconhecido distinto de zero. Categorias ELIGIBLE/BLOCKED/NEEDS_VERIFICATION não equivalem a autorização de compra. A API devolve fatos estruturados; mensagens podem explicar, mas não substituir os dados.

Separar erro de validação, identidade, estado obsoleto, limite excedido, indisponibilidade e resultado remoto desconhecido. Não devolver token, payload privado ou erro bruto do provedor.

## Tempo, fila e recuperação

Aceitação rápida e consulta com espera progressiva limitada; prazos/cadência serão definidos em API-01 e DEC-01. Ajuda e callbacks não aguardam a geração inteira. Atualizações de estado da conversa são serializadas, com recuperação após crash e limites de fila.

Sucesso da ferramenta seguido de falha na resposta não repete mutação. Cancelar espera não comprova cancelamento externo. Repetir envio só é permitido após determinar pelo contrato o estado remoto; UNKNOWN permanece bloqueado.

## Apresentação

Blocos de texto, resumo, propostas e revisão devem ser renderizáveis no Telegram sem confiar em marcação arbitrária do modelo. Definir tamanho, escaping, paginação e tratamento de resposta parcial.

Custo total, validade, elegibilidade e estado de pedido são renderizados dos campos validados. Ações usam referências do servidor; nenhum botão é criado somente por sugestão textual do LLM.

## Testes de contrato obrigatórios

- Aceitação/replay/resultados equivalentes em Python e TypeScript.
- Conflito de chave, versão antiga e outra identidade.
- Reinício antes/depois da aceitação e entrega de resposta.
- Resposta tardia após alteração e erro sem dado privado.
- Callback repetido/expirado e troca de conta.
- Falha do modelo com continuidade de ajuda/status.
- Compatibilidade de consumers com needsVerification e futura versão.
