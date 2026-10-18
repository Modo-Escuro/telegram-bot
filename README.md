# Compra Agenciada — bot Telegram

Interface Telegram do projeto SEMCOMP. O objetivo do produto é organizar uma compra em grupo com restrições individuais e orçamento, preservar essas condições quando o pedido muda e exigir aprovação humana antes do envio.

**Entregue e ensaiado:** bot privado na Railway, login iFood pelo navegador, confirmação humana por botão no Telegram e sessão operacional reconhecida pelo backend. A consulta autenticada registrou `CONNECTED`, `operational: true` e verificação `OK`. A evidência e seus limites estão em [estado atual](docs/estado-atual.md).

**Pendente:** conversa de compras, participantes, busca apresentada pelo bot, sacola, aprovação de pedido e checkout. O login não aprova uma compra. Não apresentar esses requisitos como funcionalidades entregues.

## Arquitetura

Fluxo implementado: Telegram → adaptador Python → [api-backend](https://github.com/Modo-Escuro/api-backend) → OAuth e verificação da sessão pelo MCP iFood. O agente de compra e as regras de grupo ainda precisam ser integrados a esse fluxo.

Python 3.12, transporte pela biblioteca padrão, validação de contrato com `jsonschema`, long polling e acesso restrito a um organizador em conversa privada. Cursor e ações iniciadas ficam em SQLite; tokens iFood ficam exclusivamente no backend.

O [cliente de conversa v1.0](docs/cliente-conversa.md) está implementado e validado offline como parte da BOT-01. Ainda falta conectá-lo ao polling e às rotas duráveis da RUN-01 para habilitar a conversa com IA.

## Documentação

Comece pelo [índice](docs/README.md). As referências principais são:

| Necessidade | Documento |
| --- | --- |
| Saber o que funciona e qual evidência existe | [Estado atual](docs/estado-atual.md) |
| Entender os módulos e suas fronteiras | [Arquitetura implementada](docs/arquitetura.md) |
| Usar login, confirmação e verificação | [Login iFood](docs/login-ifood.md) |
| Operar o serviço e manter o estado | [Railway](docs/deploy-railway.md) |
| Executar localmente sem disputar polling | [Execução local](docs/executar-bot.md) |
| Escolher o próximo incremento | [Plano da demo](docs/plano-demo.md) |
| Preservar regras e decisões abertas | [Regras](docs/regras-preservadas.md) |

As cópias em [docs/baseline](docs/baseline/proveniencia.json) preservam a StRS v0.2, ainda em validação, e os contratos recebidos. O [protótipo original](https://github.com/Modo-Escuro/compra-com-contexto) mantém seu histórico e sua simulação Python; essas evidências não equivalem à implementação deste bot.

## Desenvolvimento

```bash
./.venv/Scripts/python.exe -m pip install -r requirements.lock
./.venv/Scripts/python.exe -m pip install --no-deps -e .
./.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Os testes simulam Telegram e backend, sem polling real nem credenciais. A CI executa em Windows e Linux. Use `.venv/bin/python` no Linux/macOS. Consulte [execução local](docs/executar-bot.md) para preparar o ambiente e configurar variáveis; `.env` não é carregado automaticamente.
