// APENAS ENSAIO. Nenhuma credencial, Telegram, Gemini ou MCP externo. HTTP somente loopback.
import { serve } from '@hono/node-server';
import { createApp } from './src/server/app.js';
import { createConversationRuntime } from './src/server/conversation-runtime.js';
import { loadConfig } from './src/server/config.js';
import { IfoodAuth } from './src/server/auth.js';
import { setup, connectAndConfirm, ORG_A, ORG_B, BOT_TOKEN } from './test/helpers/fakes.js';
import { geminiReply } from './test/helpers/gemini.js';

if (process.env.CONTINUITY_TEST_ONLY !== '1' || !process.env.CONTINUITY_TEST_DB) throw new Error('Synthetic fixture only');
const model = loadConfig({ CONVERSATION_RUNTIME_ENABLED: 'true', CONVERSATION_DB_FILE: process.env.CONTINUITY_TEST_DB,
  BOT_TELEGRAM_ID: '900001', BOT_API_TOKEN: BOT_TOKEN, ALLOWED_ORGANIZER_IDS: `${ORG_A},${ORG_B}`,
  CONVERSATION_MODEL_ENABLED: 'true', CONVERSATION_MODEL_PROVIDER: 'google', CONVERSATION_MODEL: 'gemini-3.8-flash',
  GEMINI_API_KEY: 'synthetic-key', CONVERSATION_MODEL_MAX_REQUESTS: '20' }).conversationModel!;
const env = setup({ conversationRuntime: { dbFile: process.env.CONTINUITY_TEST_DB, botId: '900001' }, conversationModel: model });
await connectAndConfirm(env, ORG_A);
await connectAndConfirm(env, ORG_B);
let calls = 0;
const runtime = createConversationRuntime(env.cfg, env.links, async () => {
  calls++;
  // Demora controlada garante passagem pelo estado RUNNING e mensagem de processamento.
  await new Promise(r => setTimeout(r, 250));
  return geminiReply({ actions: [{ action: 'ADD_PARTICIPANT', name: 'Pessoa sintética' }] });
})!;
const app = createApp(new IfoodAuth(env.cfg, env.as.fetch, { tokenFile: null }), { config: env.cfg, links: env.links, conversations: runtime });
app.get('/synthetic/stats', c => c.json({ calls, operations: env.mcp.used.map(x => x.op) }));
app.post('/synthetic/addresses/:count', c => {
  const count = Number(c.req.param('count'));
  if (![0, 1, 2].includes(count)) return c.json({ ok: false }, 400);
  env.mcp.addresses = Array.from({ length: count }, (_, i) => ({ addressId: 'synthetic-address-' + i,
    alias: i === 0 ? 'Casa' : 'Trabalho', coordinates: { latitude: -1, longitude: -2 } }));
  return c.json({ ok: true });
});
runtime.start();
const server = serve({ fetch: app.fetch, port: 0, hostname: '127.0.0.1' }, info => console.log(JSON.stringify({ port: info.port })));
const stop = () => { runtime.stop(); server.close(); };
process.once('SIGTERM', stop);
process.once('SIGINT', stop);
