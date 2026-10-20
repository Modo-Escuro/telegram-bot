// Executável somente em teste: HTTP/SQLite/assistente/CART-01 reais; Telegram, modelo, OAuth e MCP sintéticos.
import { serve } from '@hono/node-server';
import { createApp } from './src/server/app.js';
import { loadConfig } from './src/server/config.js';
import { createAssistantProcessor } from './src/server/assistant/processor.js';
import { recipient } from './src/server/assistant/memory.js';
import { TurnRuntime } from './src/server/turns/runtime.js';
import { TurnStore } from './src/server/turns/store.js';
import { accountSession } from './src/server/turns/account-session.js';
import { DeliveryAddresses } from './src/server/services/delivery-addresses.js';
import { ConfirmedCartService } from './src/server/cart/write-service.js';
import { CartWriteStore } from './src/server/cart/write-store.js';
import type { IfoodLinkService } from './src/server/links/service.js';

if (process.env.ASSISTANT_TEST_ONLY !== '1' || !process.env.ASSISTANT_TEST_DB) throw new Error('Somente teste isolado.');
console.log = (...args) => { process.stderr.write(args.map(String).join(' ') + '\n'); };
const principal = { organizerId: '111111111', conversationId: '111111111', botId: '900001' };
const linkId = 'synthetic-authenticated-link';
const A = '11111111-1111-4111-8111-111111111111', M = '22222222-2222-4222-8222-222222222222', I = '33333333-3333-4333-8333-333333333333';
const address = { addressId: A, alias: 'Casa', coordinates: { latitude: -1, longitude: -2 },
  location: { street: 'Rua Sintética', number: '1', neighborhood: 'Centro', city: 'Cidade' } };
const listing = { itemId: I, itemName: 'Arroz', unitPrice: 20, merchant: { merchantId: M, merchantName: 'Loja sintética',
  isOpen: true, minimumOrderAmount: 0, deliveryMethod: { fee: 5, estimatedMinutes: { max: 30 } } } };
let models = 0, writes = 0;
const links = { status: async () => ({ state: 'CONNECTED', operational: true, linkId, attempt: null, scopeEvidence: 'TOKEN_SCOPES',
  allowedOperations: ['ADDRESSES_READ', 'OFFERS_EVALUATE', 'CART_READ', 'CART_WRITE'],
  account: { identity: { status: 'VERIFIED', displayName: 'Pessoa S.', emailMasked: 'p***@example.test', source: 'getUser' } } }),
  withOperational: async (_org: string, _op: string, fn: (ctx: unknown) => Promise<unknown>) => fn({ linkId,
    cart: { call: async () => { throw new Error('Nenhum carrinho remoto criado.'); },
      writeConfirmed: async () => { writes++; throw new Error('Teste nunca autoriza escrita.'); } },
    deps: { listAddresses: async () => ({ results: [address] }), searchOffers: async () => ({ results: [listing], hasMore: false }),
      getItem: async () => ({ itemId: I, merchantId: M, itemName: 'Arroz', merchantName: 'Loja sintética',
        itemDescription: 'Arroz e água', unitPrice: 20, merchantMinimumOrderAmount: 0, optionGroups: [] }) },
  }) } as unknown as IfoodLinkService;
const store = new TurnStore(process.env.ASSISTANT_TEST_DB);
const addresses = new DeliveryAddresses(store, links);
const runtime = new TurnRuntime(store, { sessionOf: async p => accountSession(p, linkId), processor: createAssistantProcessor({
  links, selectedAddress: (_org, id) => addresses.selected(principal, id),
  audienceModel: { id: 'synthetic-audience', propose: async ({ input }) => {
    const who = input.message.includes('namorada') ? { kind: 'RECIPIENT' as const, label: 'namorada', evidenceQuote: 'namorada' } : { kind: 'SELF' as const };
    return { targets: [who], mentioned: [who], purpose: 'FOOD', ambiguous: false };
  } },
  model: { id: 'synthetic-shopping', propose: async ({ input }) => {
    models++;
    if (input.message.includes('Não tenho restrições')) return { message: 'Dados registrados.', requests: [], itemRefs: [],
      memoryActions: [{ action: 'DECLARE_NO_RESTRICTIONS', subjectRef: 'SELF', evidenceQuote: input.message }],
      contextActions: [{ action: 'SET_LIMIT', amountCents: 10000, kind: 'MANDATORY' }] };
    if (input.message.includes('namorada')) return { message: 'Preferência registrada.', requests: [], itemRefs: [],
      memoryActions: [{ action: 'REMEMBER_PREFERENCE', subjectRef: recipient('namorada').ref, category: 'FOOD', value: 'chocolate', evidenceQuote: input.message }] };
    if (input.message.includes('alérgico')) return { message: 'Condição registrada.', requests: [], itemRefs: [],
      memoryActions: [{ action: 'REMEMBER_RESTRICTION', subjectRef: 'SELF', restriction: { kind: 'ALLERGY', code: 'PEANUT', requirement: 'MANDATORY' }, evidenceQuote: input.message }] };
    if (input.round === 1) return { message: 'Vou procurar opções.', requests: [{ name: 'searchOffers', arguments: { query: 'arroz', merchantType: 'RESTAURANT' } }], itemRefs: [] };
    if (input.round === 2) return { message: '', requests: [{ name: 'getItem', arguments: { itemRef: 'item_1' } }], itemRefs: [] };
    return { message: 'Veja esta opção.', requests: [], itemRefs: ['item_1'] };
  } },
}) });
// Gate sintético exclusivamente injetado neste servidor isolado; não é evidência externa.
const cartWrites = new ConfirmedCartService(new CartWriteStore(store), links, { verify: async () => {} });
const config = loadConfig({ BOT_API_TOKEN: 'synthetic-token-xxxxxxxxxxxxxxxxxxxxxxxxx', ALLOWED_ORGANIZER_IDS: principal.organizerId,
  CONVERSATION_RUNTIME_ENABLED: 'true', CONVERSATION_DB_FILE: process.env.ASSISTANT_TEST_DB, BOT_TELEGRAM_ID: principal.botId });
const app = createApp({ config, links, conversations: runtime, cartWrites });
app.get('/__synthetic-stats', c => c.json({ models, writes }));
runtime.start();
const server = serve({ fetch: app.fetch, hostname: '127.0.0.1', port: 0 }, info => process.stdout.write(JSON.stringify({ port: info.port }) + '\n'));
process.on('SIGTERM', () => { runtime.stop(); server.close(); });
