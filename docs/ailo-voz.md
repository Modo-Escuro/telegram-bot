# Ailo: apresentação, digitação e áudio

Apresentação corrente: “Olá! Eu sou o Ailo, seu assistente de compras”, seguida de convite para contar objetivo/ocasião, sem formulário inicial. O termo “compras agenciadas” foi simplificado. Não há declaração de atendimento humano. [Guia do assistente](assistente-conversacional.md).

Ao iniciar o serviço normal, o adaptador tenta definir o nome de exibição como Ailo (`setMyName`), sem alterar o username ou iniciar outro polling. Se a chamada falhar, a equipe pode ajustar o nome no BotFather. Os modos de diagnóstico não renomeiam o perfil. O Telegram ainda identifica a conta como bot em sua própria interface; o produto não controla esse rótulo.

O worker usa o indicador nativo `sendChatAction: typing` durante processamento, com intervalo mínimo de quatro segundos e falha não fatal. Não acrescenta atraso artificial à resposta. O sinal do Telegram expira sozinho; em uma chamada remota mais demorada pode haver intervalo sem indicador. Não se trata de uma pessoa digitando.

## Voz preparada, desabilitada por padrão

Opção sugerida para priorizar velocidade: Groq, `whisper-large-v3-turbo`, idioma `pt`. Referências oficiais consultadas em 18/10/2026: [transcrição Groq](https://console.groq.com/docs/speech-to-text), [Bot API](https://core.telegram.org/bots/api#sendchataction). A documentação aceita OGG e recomenda informar o idioma para reduzir latência. Não há benchmark ponta a ponta nesta entrega nem garantia de resposta instantânea.

Ativação no serviço Telegram requer:

- `TELEGRAM_CONVERSATION_ENABLED=true`.
- `TELEGRAM_VOICE_ENABLED=true` (padrão `false`).
- `GROQ_API_KEY`, configurada como segredo na Railway, nunca em Git/chat/logs.
- `TELEGRAM_VOICE_DAILY_SECONDS`, limite explícito global de 60 a 36000 segundos por dia UTC. Começar com um limite pequeno aprovado pela equipe; nenhum limite foi ativado por esta implementação.

O áudio é enviado à Groq somente após autenticação no Ailo. O arquivo fica apenas em memória no adaptador; a retenção no Telegram/Groq depende dos respectivos serviços. A fila guarda metadados do áudio até processamento/cancelamento/expiração, depois o texto segue a retenção já existente da conversa. Não registrar gravação, transcrição, token ou URL de download nos logs.

Recebimento não realiza rede nem transcrição no polling. A mensagem entra como texto pendente na mesma fila, preservando a ordem, o autor e o identificador original. O worker baixa o áudio do Telegram (destino fixo, caminho validado), transcreve uma vez e apresenta “Ouvi: …” para conferência. O texto passa ao processamento normal; não vira comando de menu, clique, login ou aprovação. A pessoa pode corrigir nomes, alergias e valores em seguida. A confiança do reconhecedor não é evidência de segurança alimentar.

Limites: mensagens de voz OGG, até um minuto e 5 MB. Arquivos de música/documentos não são tratados como voz. Resultados vazios ou com baixa confiança/silêncio são recusados. Não é transcrição ao vivo enquanto a pessoa grava: começa após o envio no Telegram. Os timeouts de transporte são curtos; não garantem latência total sob carga.

O orçamento local reserva `max(10, duração informada pelo Telegram)` antes da chamada e não reembolsa falha/timeout. O contador SQLite compartilhado em `TELEGRAM_STATE_DIR/voice-budget.sqlite3` sobrevive a reinícios. É um limite de uso, não garantia exata de cobrança do provedor. Limite financeiro adicional deve ser configurado na conta Groq.

Queda durante transcrição fica como resultado desconhecido: não repetir automaticamente a chamada cobrada. O usuário recebe orientação para reenviar ou escrever. Replay não muda o texto de uma intenção já transcrita. Interromper durante a transcrição impede seu envio ao agente, mesmo se a chamada remota já começou; sair da demo impede novas entregas/processamento. Login e aprovação de compra permanecem separados.

## Verificação

Testes usam Telegram, áudio e Groq sintéticos. Cobrem ordem, identidade, replay, cancelamento concorrente, saída da demo, reinício incerto, limites persistentes, baixa confiança, transporte de arquivo e digitação. Não houve envio de áudio real nem consumo pago. Depois da ativação, medir separadamente recebimento → transcrição → resposta, com áudio sintético em português e correção de orçamento. Não apresentar desempenho do fornecedor como latência medida do Ailo.
