# Regras preservadas

Atualização: [remoto/local](estado-remoto-local.md) e [decisões vigentes](decisoes-conversacionais.md) distinguem preparação real confirmada de aprovação de pedido futura. Envio/pagamento continuam proibidos. O levantamento de 17/10 ao final é histórico, não estado do domínio já integrado.

A StRS v0.2 em baseline é uma cópia integral, com IDs e decisões abertas preservados. Continua em validação. O protótipo original demonstra regras em simulação; sua persistência SQLite não garante execução única no iFood.

**Reconciliação local de 20/10:** memória não mistura pessoas/finalidades e fila conserva sessão. Limpeza de dados não cancela carrinho remoto. API usa v6 e assistente único; identidade estável entre relogins não comprovada. Usuário confirmou UNKNOWN obrigatório bloqueante por consumidor, substituindo liberação com aviso do #52. [Alcance](assistente-conversacional.md).

## Requisitos que permanecem

A tabela descreve requisitos a implementar e verificar, não funcionalidades de compra já entregues. Consulte [estado atual](estado-atual.md) para o alcance real do incremento.

| Regra | Comportamento exigido na nova arquitetura |
| --- | --- |
| RN01: restrições e limites antes do ranking | Backend bloqueia candidatos incompatíveis; o bot explica o motivo. |
| RN02: histórico não autoriza flexibilizar restrições | Agente esclarece contradições; bot apresenta perguntas. |
| RN03: informação alimentar insuficiente bloqueia | Backend mantém bloqueio por pessoa até confirmação rastreável do restaurante. |
| RN04: disponibilidade e custos observados | Backend calcula em centavos e inclui frete/taxas; bot identifica estimativas e dados ausentes. |
| RN05: duas a quatro opções elegíveis | Não completar a lista com candidatos incompatíveis. |
| RN06: mudança exige reavaliação | Nova versão de carrinho e invalidação da aprovação anterior. |
| RN07: atendimento coletivo não supera restrição individual | Mostrar participantes não atendidos; não ultrapassar limites obrigatórios. |

## Cenários já construídos a transportar

Origem: tests/test_shopping.py do protótipo. São critérios para novos testes, não testes executáveis neste repositório.

- Total inclui entrega; nenhum envio acima do orçamento autorizado.
- Nenhuma execução sem aprovação humana válida, com total divergente ou cotação expirada/alterada.
- Repetir a mesma intenção com o mesmo conteúdo preserva identidade; reutilizar a chave com conteúdo diferente gera conflito.
- Intenções distintas com valores iguais são legítimas.
- Concorrência e cliques repetidos não produzem novos envios para a mesma intenção.
- Restrição não suportada ou informação essencial ausente deve bloquear ou pedir esclarecimento.
- Canal de aprovação desabilitado ou não autorizado não aprova.

## Critérios adicionais do Telegram e integração remota

- Deduplicar updates e callbacks, persistindo o processamento sem perder eventos após reinício.
- Validar o ID do organizador e a sessão; nomes de usuário não são credenciais de aprovação.
- Botão antigo não aprova carrinho novo; o preço não deve ser aceito apenas por vir no payload do botão.
- Segregar token Telegram, autenticação bot→API e credenciais iFood; apenas o backend recebe as últimas.
- Timeout após envio significa resultado desconhecido; consultar e reconciliar antes de qualquer nova tentativa.
- Confirmar sucesso por resposta confiável do provedor, não pelo texto produzido pelo modelo.

## Pendências do backend

A inspeção inicial de 17/10/2026 levantou a necessidade de alinhar UNKNOWN/ignorar restrição a RN01/RN03. O contrato revisado do backend `686300d` já descreve alergia como bloqueada e sem PASS automático; isso não comprova restrições por participante, ingredientes ou segurança das opções reais. A integração de grupo precisa ser verificada por pessoa contra RN01/RN03. O backend documenta recomendação sem checkout. Não remover a barreira de escrita sem implementar aprovação e tratamento de resultado desconhecido.

O novo bot não resolve automaticamente essas pendências. A migração das regras precisa de implementação e testes no backend, além dos testes de identidade, transporte e apresentação no bot.
