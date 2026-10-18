// SOMENTE TESTE. Copiado temporariamente para a raiz da API fixada; nunca registrado em produção.
import { Hono } from 'hono';
import { serve } from '@hono/node-server';
import { botAuth } from './src/server/botAuth.js';
import { registerConversationRoutes } from './src/server/routes/conversation.js';
import { TurnStore } from './src/server/turns/store.js';
import { TurnRuntime, type TurnProcessor } from './src/server/turns/runtime.js';

if (process.env.BOT01_TEST_ONLY !== '1' || !process.env.BOT01_TEST_DB) throw new Error('Synthetic fixture only');
const app = new Hono();
let age = 0, executions = 0;
const store = new TurnStore(process.env.BOT01_TEST_DB, {}, () => Date.now() + age);
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
const runtime = new TurnRuntime(store, { processor, intervalMs: 10 });
app.get('/synthetic/stats', c => c.json({ executions }));
app.post('/synthetic/expire', c => { age += 86400001; return c.json(store.purge()); });
app.use('/api/bot/*', botAuth({ token: 'synthetic-token-xxxxxxxxxxxxxxxxxxxxxxxxx', allowedOrganizerIds: ['111111111'] }));
registerConversationRoutes(app, runtime, '900001');
runtime.start();
const server = serve({ fetch: app.fetch, port: 0, hostname: '127.0.0.1' }, info => {
  console.log(JSON.stringify({ port: info.port }));
});
const stop = () => { runtime.stop(); server.close(); };
process.once('SIGTERM', stop);
process.once('SIGINT', stop);
