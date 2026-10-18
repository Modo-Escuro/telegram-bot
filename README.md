# Compra com Contexto — bot Telegram

Interface Python 3.12 do projeto SEMCOMP. Organiza compra em grupo com condições por pessoa, preservando orçamento/restrições quando o pedido muda.

O código remoto conferido integra login e confirmação humana, cancelamento/desconexão, cliente de conversa v1, outbox/polling opt-in, retomada do grupo e acesso por senha com isolamento por usuário. A API remota já monta Gemini/AI-02/GRP-01 mediante configuração explícita. Isso não comprova ativação nem ensaio completo online.

Carrinho real está aprovado no escopo somente após confirmação humana específica. O código novo CART-01 permanece local na API; apresentação/callbacks BOT-03, outputs reais INT-02 e validação QA-01 continuam pendentes. Envio de pedido e pagamento permanecem proibidos neste incremento. Login/senha não confirmam carrinho nem aprovam compra.

- [Remoto publicado × alterações locais](docs/estado-remoto-local.md)
- [Plano integrado](docs/plano-conversacional.md) e [backlog](docs/backlog-conversacional.md)
- [Decisões vigentes](docs/decisoes-conversacionais.md)
- [Evidências online históricas](docs/estado-atual.md)
- [Documentação e operação](docs/README.md)

Tokens iFood ficam exclusivamente no backend; o bot usa o canal autenticado. O acesso por senha conserva um polling e dados separados por usuário. Não iniciar outra instância com token real durante testes. Baseline e fixtures fixadas não são atualizadas por esta revisão documental.

## Desenvolvimento

```bash
./.venv/Scripts/python.exe -m pip install -r requirements.lock
./.venv/Scripts/python.exe -m pip install --no-deps -e .
./.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Use `.venv/bin/python` no Linux/macOS. Testes não comprovam resposta do iFood; mudanças só documentais exigem conferir coerência, links e diff.
