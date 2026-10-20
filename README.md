# Compra com Contexto — bot Telegram

Interface Python 3.12 do Ailo, projeto SEMCOMP. Entrada principal por intenção natural; a API resolve memória, destinatários, consultas e composição. O bot valida identidade, mantém outbox/recuperação e apresenta resultados.

A árvore reconciliada inclui login no navegador, outbox/worker, senha e [assistente/progresso/memória](docs/assistente-conversacional.md). Menu: Remover pessoa/Limpar tudo/Meus dados. Sessão conservada por evento; API coordenada sobre main `f6ef20e`, com assistente único e SQLite v6. Isso não comprova ativação online.

Carrinho real só após confirmação específica. O [canal PREPARE_CART](docs/cart-01-telegram.md) mantém opt-in OFF; API #46 já mergeado e capturas INT-02 preservadas. Novo ensaio HTTP sintético percorre proposta→escolha→revisão e bloqueio após alergia, sem escrita. Confirmação/callback ponta a ponta, outputs com opções e QA online ainda exigem evidência própria; envio/pagamento proibidos.

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
