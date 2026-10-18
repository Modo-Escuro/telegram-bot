// SOMENTE ENSAIO SINTÉTICO. HTTP loopback; nenhuma credencial ou operação externa.
import { serve } from '@hono/node-server';
import { randomUUID } from 'node:crypto';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { createApp } from './src/server/app.js';
import { loadConfig } from './src/server/config.js';
import { applyPatch } from './src/server/domain/purchase.js';
import { composeProposals } from './src/server/domain/group.js';
import { renderSnapshot } from './src/server/agent/render.js';
import { ConfirmedCartService } from './src/server/cart/write-service.js';
import { CartWriteStore } from './src/server/cart/write-store.js';
import { TurnRuntime } from './src/server/turns/runtime.js';
import { scopeKey, TurnStore } from './src/server/turns/store.js';
import { candidate } from './test/group/catalog.js';

if (process.env.CART_TEST_ONLY !== '1' || !process.env.CART_TEST_DB || !process.env.CART_TEST_REMOTE)
  throw new Error('Synthetic fixture only');
const p = { botId: '900001', organizerId: '111111111', conversationId: '111111111' };
const token = 'test-bot-token-0123456789abcdefghijklmnop', linkId = 'synthetic-cart-link-0001';
const merchantId = '11111111-1111-4111-8111-111111111111', itemId = '22222222-2222-4222-8222-222222222222';
const address = { addressId: '33333333-3333-4333-8333-333333333333', alias: 'Casa',
  location: { street: 'Rua Sintética', number: '10', neighborhood: 'Centro', city: 'Cidade sintética' }, coordinates: { latitude: -1, longitude: -2 } };
const store = new TurnStore(process.env.CART_TEST_DB), runtime = new TurnRuntime(store);
if (!store.db.prepare('SELECT domain FROM conversations WHERE scope=?').get(scopeKey(p))) {
  let state = applyPatch(null, [{ op: 'ADD_PARTICIPANT', displayName: 'Pessoa sintética' }], { seed: 'http-cart', eventId: 'one' }).state;
  state = applyPatch(state, [{ op: 'SET_RESTRICTIONS', participantId: state.participants[0]!.participantId, value: 'NONE' },
    { op: 'SET_LIMIT', target: state.participants[0]!.participantId, value: 'NONE' }, { op: 'SET_LIMIT', target: 'GROUP', value: 'NONE' },
    { op: 'SET_PRIORITY', value: 'ECONOMY' }, { op: 'SET_ADDRESS', addressId: address.addressId }, { op: 'SET_MERCHANT', merchantId }], { seed: 'http-cart', eventId: 'two' }).state;
  const proposals = composeProposals(state, [candidate({ itemId, merchantId, name: 'Arroz', price: 20, fee: 5 })], { seed: 'http-cart', addressId: address.addressId }).proposals;
  state = applyPatch(state, [{ op: 'SET_PROPOSALS', proposals: proposals.map(x => x.proposal) },
    { op: 'SELECT_PROPOSAL', proposalId: proposals[0]!.proposal.proposalId }], { seed: 'http-cart', eventId: 'three' }).state;
  state.linkId = linkId;
  const snapshot = renderSnapshot({ contractVersion: '1.0', conversationId: p.conversationId, version: state.version - 1,
    phase: 'COLLECTING', blocks: [], pending: [], allowedActions: [], humanApproval: null }, state, [], []);
  store.db.prepare('INSERT INTO conversations(scope,snapshot,domain,last_activity_at) VALUES(?,?,?,?)')
    .run(scopeKey(p), JSON.stringify(snapshot), JSON.stringify(state), Date.now());
}
const remoteFile = process.env.CART_TEST_REMOTE;
let remote = existsSync(remoteFile) ? JSON.parse(readFileSync(remoteFile, 'utf8')) : { writes: 0, cart: null };
let mode = 'normal';
// CART_TEST_SHAPE=observed: forma das respostas reais da INT-02 (carrinho inteiro, sem addressId, promoção). Valores sintéticos.
const observedShape = process.env.CART_TEST_SHAPE === 'observed';
const observed = (cart: { cartId: string; items: { itemId: string; cartItemId: string; quantity: number }[] }, promo: boolean) => {
  const sub = cart.items.reduce((n, i) => n + i.quantity * 20, 0);
  return { cartId: cart.cartId, merchant: { merchantId, merchantName: 'Loja sintética' },
    items: cart.items.map(i => ({ itemId: i.itemId, cartItemId: i.cartItemId, quantity: i.quantity, unitPrice: 20, name: 'Arroz' })),
    deliveryAddress: { streetName: 'Rua Sintética', streetNumber: '10', neighborhood: 'Centro' },
    deliveryMethod: { deliveryMethodId: 'DEFAULT', deliveryMethodMode: 'DELIVERY', fee: 0 },
    fees: [{ name: 'Taxa de serviço', amount: 0.99 }],
    summary: { totalAmount: Math.round((promo ? sub + 0.99 - 5 : sub + 0.99) * 100) / 100, subtotalAmount: sub, deliveryFeeAmount: 0,
      feeTotalAmount: 0.99, benefitsTotalAmount: promo ? 10 : 5, voucherTotalAmount: 0 } };
};
const gateway = {
  async call(tool: string) {
    if (tool !== 'getCart' || !remote.cart || mode === 'read-failed') throw new Error('synthetic read failure');
    return observedShape ? observed(remote.cart, true) : structuredClone(remote.cart);
  },
  async writeConfirmed(tool: string, args: Record<string, unknown>) {
    if (tool !== 'createCart') throw new Error('Synthetic fixture implements create only');
    remote.writes++;
    remote.cart = { cartId: randomUUID(), merchantId, addressId: address.addressId,
      items: (args.items as object[]).map(item => ({ ...item, cartItemId: randomUUID(), unitPrice: 20 })),
      totals: { subtotal: 20, deliveryFee: 5, serviceFee: 1, discount: 0, total: 26 } };
    writeFileSync(remoteFile, JSON.stringify(remote));
    if (mode === 'unknown') return { queued: true };
    return observedShape ? observed(remote.cart, false) : { cartId: remote.cart.cartId };
  },
};
const identity = { status: 'VERIFIED', displayName: 'Pessoa S.', emailMasked: 'p***@example.test', source: 'getUser' };
const deps = {
  async listAddresses() { return { results: [address] }; },
  async searchOffers() { return { results: [{ itemId, itemName: 'Arroz', unitPrice: 20,
    merchant: { merchantId, merchantName: 'Loja sintética', isOpen: true, minimumOrderAmount: 0,
      deliveryMethod: { fee: 5, deliveryMethodId: 'DELIVERY', deliveryMethodMode: 'DELIVERY' } } }] }; },
  async getItem() { return { itemId, merchantId, itemName: 'Arroz', merchantName: 'Loja sintética', unitPrice: 20,
    merchantMinimumOrderAmount: 0, optionGroups: [] }; },
};
const links = {
  async status() { return { state: 'CONNECTED', operational: true, linkId, attempt: null,
    scopeEvidence: 'TOKEN_SCOPES', account: { identity }, allowedOperations: ['CART_READ', 'CART_WRITE', 'OFFERS_EVALUATE', 'ADDRESSES_READ'] }; },
  async withOperational(_organizer: string, _operation: string, fn: (ctx: unknown) => unknown) { return fn({ linkId, deps, cart: gateway }); },
};
// Injeção SOMENTE deste teste. Não escreve manifesto nem apresenta fakes como evidência observada.
const service = new ConfirmedCartService(new CartWriteStore(store), links as never, { async verify() {} });
const config = loadConfig({ BOT_API_TOKEN: token, BOT_TELEGRAM_ID: p.botId, ALLOWED_ORGANIZER_IDS: '111111111,222222222',
  CONVERSATION_RUNTIME_ENABLED: 'true', CONVERSATION_DB_FILE: process.env.CART_TEST_DB });
const app = createApp(undefined, { config, links: links as never, conversations: runtime, cartWrites: service });
app.get('/synthetic/stats', c => c.json({ writes: remote.writes }));
app.post('/synthetic/mode/:mode', c => { mode = c.req.param('mode'); return c.json({ ok: true }); });
const server = serve({ fetch: app.fetch, port: 0, hostname: '127.0.0.1' }, info => console.log(JSON.stringify({ port: info.port })));
const stop = () => { server.close(); store.close(); };
process.once('SIGTERM', stop); process.once('SIGINT', stop);
