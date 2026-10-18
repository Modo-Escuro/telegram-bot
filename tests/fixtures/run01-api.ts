// SOMENTE TESTE. Copiado temporariamente para a raiz da API fixada; nunca registrado em produção.
import { Hono } from 'hono';
import { serve } from '@hono/node-server';
import { botAuth } from './src/server/botAuth.js';
import { registerConversationRoutes } from './src/server/routes/conversation.js';
import { TurnStore } from './src/server/turns/store.js';
import { TurnRuntime, type TurnProcessor } from './src/server/turns/runtime.js';
import { loadConfig } from './src/server/config.js';
import { createConversationRuntime } from './src/server/conversation-runtime.js';
import type { IfoodLinkService } from './src/server/links/service.js';

if (process.env.BOT01_TEST_ONLY !== '1' || !process.env.BOT01_TEST_DB) throw new Error('Synthetic fixture only');
const app = new Hono();
let age = 0, executions = 0;
const processor: TurnProcessor = async (ctx) => {
  executions++;
  const ending = ctx.event.input.kind === 'TEXT' && ctx.event.input.text === 'encerrar';
  const domain = { ops: ending ? [{ op: 'END' as const, reason: 'CLOSED' as const }]
    : [{ op: 'ADD_PARTICIPANT' as const, displayName: 'Pessoa sintética' }] };
  const next = ctx.previewDomain(domain);
  return { completeness: 'COMPLETE', paths: ['PARTICIPANTS'], cause: 'USER', domain,
    snapshot: { ...ctx.snapshot, version: ctx.snapshot.version + 1, phase: 'COLLECTING',
      humanApproval: null, allowedActions: [], pending: [], blocks: next ? [{ kind: 'GROUP',
        participants: next.participants.map(p => ({ participantRef: p.participantId,
          displayName: p.displayName, conditions: ['Ainda não informado'] })), budgetCents: null }] : [] } };
};
// Exercita a montagem de produção com transporte Gemini falso. Não é fallback nem inferência real.
const assembled = process.env.BOT02_TEST_ASSEMBLED === '1';
const outputs = [
  [{ action: 'ADD_PARTICIPANT', name: 'Ana' }, { action: 'ADD_PARTICIPANT', name: 'Bia' },
    { action: 'ADD_RESTRICTION', participant: { name: 'Ana' }, restriction: { kind: 'ALLERGY', code: 'PEANUT', requirement: 'MANDATORY' } },
    { action: 'SET_NO_RESTRICTIONS', participant: { name: 'Bia' } },
    { action: 'SET_LIMIT', target: 'GROUP', amountCents: 18000, kind: 'MANDATORY' }],
  [{ action: 'SET_LIMIT', target: 'GROUP', amountCents: 15000, kind: 'MANDATORY' }],
];
const links = {
  status: async () => ({ state: 'CONNECTED', linkId: 'synthetic-link-xxxxxxxxxxxxxxxx' }),
  withOperational: async () => { throw new Error('MCP fora deste ensaio de coleta'); },
} as unknown as Pick<IfoodLinkService, 'status' | 'withOperational'>;
const runtime = assembled ? createConversationRuntime(loadConfig({
  CONVERSATION_RUNTIME_ENABLED: 'true', CONVERSATION_DB_FILE: process.env.BOT01_TEST_DB,
  BOT_TELEGRAM_ID: '900001', BOT_API_TOKEN: 'synthetic-token-xxxxxxxxxxxxxxxxxxxxxxxxx',
  ALLOWED_ORGANIZER_IDS: '111111111', CONVERSATION_MODEL_ENABLED: 'true',
  CONVERSATION_MODEL_PROVIDER: 'google', CONVERSATION_MODEL: 'gemini-3.8-flash',
  GEMINI_API_KEY: 'synthetic-key', CONVERSATION_MODEL_MAX_REQUESTS: '2',
}), links, async () => {
  executions++;
  if (!outputs.length) throw new Error('Nenhuma resposta sintética prevista');
  return Response.json({ candidates: [{ content: { role: 'model', parts: [
    { text: JSON.stringify({ actions: outputs.shift() }) },
  ] }, finishReason: 'STOP' }], modelVersion: 'gemini-3.8-flash',
  usageMetadata: { promptTokenCount: 800, candidatesTokenCount: 40, totalTokenCount: 840 } });
})! : new TurnRuntime(new TurnStore(process.env.BOT01_TEST_DB, {}, () => Date.now() + age), { processor, intervalMs: 10 });
const store = runtime.store;
app.get('/synthetic/stats', c => c.json({ executions }));
app.post('/synthetic/expire', c => { age += 86400001; return c.json(store.purge()); });
app.use('/api/bot/*', botAuth({ token: 'synthetic-token-xxxxxxxxxxxxxxxxxxxxxxxxx', allowedOrganizerIds: ['111111111'], passwordAccess: assembled }));
registerConversationRoutes(app, runtime, '900001');
runtime.start();
const server = serve({ fetch: app.fetch, port: 0, hostname: '127.0.0.1' }, info => {
  console.log(JSON.stringify({ port: info.port }));
});
const stop = () => { runtime.stop(); server.close(); };
process.once('SIGTERM', stop);
process.once('SIGINT', stop);
