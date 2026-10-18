# Documentação do bot Compra com Contexto

[Incremento BOT-02](validacao-bot02.md): acompanhamento do login, cancelamento, desconexão e validação offline. Deploy e ensaio online são evidências separadas.

## Por onde começar

1. [Estado atual](estado-atual.md): implementação, ensaio real, evidência sanitizada e limites.
2. [Arquitetura](arquitetura.md): responsabilidades dos módulos, transporte e persistência.
3. [Login iFood](login-ifood.md): comandos, botão humano, estados e recuperação.
4. [Operação na Railway](deploy-railway.md): serviços, variáveis, deploy e transferência do estado.
5. [Execução local](executar-bot.md): configuração, diagnóstico e prevenção de polling simultâneo.
6. [Plano da demo](plano-demo.md): próximos incrementos e critérios de conclusão.
7. [Regras preservadas](regras-preservadas.md): requisitos, restrições e decisões ainda abertas.

## Como interpretar o status

- **Implementado:** comportamento localizado no código deste repositório ou no backend identificado.
- **Verificado online:** observação real com origem e versão de referência registradas em [estado atual](estado-atual.md).
- **Informado pelo usuário:** etapa humana relatada, como aprovação do cadastro OAuth e uso do Telegram.
- **Planejado:** requisito ou proposta ainda sem entrega demonstrada.

Operações anunciadas ou permitidas não provam sua execução. Uma sessão operacional não autoriza compra. Não registrar tokens, URLs OAuth, códigos, identidade ou dados da conta como evidência.

## Baseline e contratos

A [StRS v0.2](baseline/stakeholder-requirements-specification.md) continua em validação. Os IDs e as decisões abertas são preservados. [Proveniência e hashes](baseline/proveniencia.json) identificam as cópias históricas, incluindo o snapshot OpenCode que não estava versionado no repositório original. Não editar essas cópias para atualizar status operacional.

O [contrato bot→API](https://github.com/Modo-Escuro/api-backend/blob/686300d1a10c12bb6c3bd899e40fbd3a68c648f5/docs/bot-api.md) é a referência da revisão atual. Não presumir que rotas propostas ou ferramentas externas descritas estejam disponíveis ou implementadas no bot.
