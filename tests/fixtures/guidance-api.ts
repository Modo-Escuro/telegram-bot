// Somente HTTP local com OAuth/MCP/modelo sintéticos; nenhuma credencial externa.
import { serve } from '@hono/node-server';
import { createApp } from './src/server/app.js';
import { createAgentProcessor } from './src/server/agent/processor.js';
import { DeterministicModel } from './src/server/agent/mock-model.js';
import { linkedProposalProvider } from './src/server/services/group.js';
import { TurnStore } from './src/server/turns/store.js';
import { TurnRuntime } from './src/server/turns/runtime.js';
import { setup, connectAndConfirm, ORG_A } from './test/helpers/fakes.js';

if (process.env.GUIDANCE_TEST_ONLY !== '1' || !process.env.GUIDANCE_TEST_DB) throw new Error('Synthetic fixture only');
const env = setup({ botApiToken: 'test-bot-token-0123456789abcdefghijklmnop', conversationRuntime: { botId: '900001', dbFile: process.env.GUIDANCE_TEST_DB } });
await connectAndConfirm(env, ORG_A);
const runtime = new TurnRuntime(new TurnStore(process.env.GUIDANCE_TEST_DB), { processor: createAgentProcessor({
  model: new DeterministicModel(), linkOf: async org => (await env.links.status(org)).linkId,
  proposals: linkedProposalProvider(env.links),
}) });
const app = createApp(undefined, { config: env.cfg, links: env.links, conversations: runtime });
runtime.start();
const server = serve({ fetch: app.fetch, hostname: '127.0.0.1', port: 0 }, info => console.log(JSON.stringify({ port: info.port })));
const stop = () => { runtime.stop(); server.close(); };
process.once('SIGTERM', stop); process.once('SIGINT', stop);
