"""Canal humano PREPARE_CART; referências ficam só na RAM, fora da conversa/modelo."""

import hashlib
import secrets
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from .backend import BackendError
from .cart_client import CartError
from .cart_view import brl, context_rows, cost_rows, current_text, item_label
from .conversation import ConversationError
from .conversation_contract import ProtocolError
from .conversation_runner import link_fingerprint
from .telegram import TelegramError

COMMANDS = {"/revisarcarrinho", "/conferircarrinho"}
NOTICE = "Estou conferindo a composição. Nenhum pedido será enviado."
UNKNOWN = (
    "Resultado da preparação ainda desconhecido. Use Conferir carrinho; não vou repetir a escrita."
)
REVIEW_PROBLEMS = {
    "CART_BAG_UNVERIFIED": "Escolha uma opção das sugestões para colocar no carrinho antes de revisar. Se ainda não buscou, diga o que quer comer.",
    "CART_LINK_CHANGED": "Confira a conta iFood conectada em Conta iFood antes de revisar o carrinho.",
    "CART_ADDRESS_CONFIRMATION_REQUIRED": "Escolha o endereço de entrega em Endereços iFood antes de revisar o carrinho.",
    "CART_GROUP_BLOCKED": "Ainda há pendências nas restrições, no orçamento ou nos itens escolhidos. Retome a conversa para concluir essas informações antes de revisar.",
    "CART_FEATURE_DISABLED": "A revisão de carrinho está indisponível nesta versão. Você pode continuar escolhendo opções na conversa.",
    "CART_PERMISSIONS_UNVERIFIED": "A conta conectada ainda não tem permissão confirmada para preparar o carrinho. Confira com a equipe.",
    "CART_CONTRACT_UNVERIFIED": "A integração iFood ainda não retornou os dados necessários para uma revisão confiável. Confira com a equipe.",
    "CART_REVIEW_NOT_DISPLAYABLE": "Faltam dados para identificar a conta, o endereço ou os itens na revisão. Confira com a equipe.",
}


def review_text(review, snapshot):
    """Revisão completa ou bloqueio; não cortar destinatários, quantidades ou incertezas."""
    if snapshot.version != review["version"]:
        raise CartError("CART_REVIEW_CHANGED")
    group = next((b for b in snapshot.to_dict()["blocks"] if b["kind"] == "GROUP"), None)
    if not group:
        raise CartError("PROTOCOL")
    people = {p["participantRef"]: p for p in group["participants"]}
    rows = [
        "REVISÃO PARA PREPARAR O CARRINHO",
        *context_rows(review.get("display")),
        f"Versão: {review['version']} · revisão: {review['fingerprint']}",
        "Válida até: " + review["expiresAt"],
        "",
    ]
    group_budget = group.get("budgetCents")
    if group_budget is not None:
        if type(group_budget) is not int or not 0 <= group_budget <= 2**53 - 1:
            raise CartError("PROTOCOL")
        qualifiers = [
            b["text"]
            for b in snapshot.to_dict()["blocks"]
            if b["kind"] == "TEXT"
            and b.get("source") == "SERVER"
            and b["text"]
            in {
                f"Orçamento do grupo: R$ {group_budget // 100}.{group_budget % 100:02d} (máximo).",
                f"Orçamento do grupo: R$ {group_budget // 100}.{group_budget % 100:02d} (referência).",
            }
        ]
        rows.append(
            qualifiers[0].replace(
                f"{group_budget // 100}.{group_budget % 100:02d}",
                f"{group_budget // 100},{group_budget % 100:02d}",
            )
            if qualifiers
            else "Orçamento informado do grupo: " + brl(group_budget)
        )
    subtotal = 0
    for line in review["lines"]:
        try:
            name, quantity, consumers = line["name"], line["quantity"], line["consumerIds"]
            unit = line["unitMinCents"]
            if (
                not isinstance(name, str)
                or not name
                or len(name) > 300
                or type(quantity) is not int
                or not 1 <= quantity <= 20
                or type(unit) is not int
                or unit < 0
                or line["unitMaxCents"] != unit
                or not isinstance(consumers, list)
                or not consumers
                or any(p not in people for p in consumers)
            ):
                raise CartError("PROTOCOL")
            label = item_label(
                review["display"],
                line["itemId"],
                [{"optionId": o, "quantity": 1} for o in line["optionIds"]],
                expected_name=name,
            )
            subtotal += unit * quantity
            rows.append(f"{quantity} × {label} — {brl(unit)} por unidade")
            rows.append("Para: " + ", ".join(people[p]["displayName"] for p in consumers))
        except (KeyError, TypeError):
            raise CartError("PROTOCOL") from None
    if subtotal != review["observedSubtotalCents"]:
        raise CartError("PROTOCOL")
    for person in people.values():
        rows.append(person["displayName"] + ": " + "; ".join(person["conditions"]))
    remote = review.get("remoteItems", [])
    if not isinstance(remote, list):
        raise CartError("PROTOCOL")
    if remote:
        rows += ["", "Composição atual do carrinho:"]
        for item in remote:
            if not isinstance(item, dict) or not isinstance(item.get("itemId"), str):
                raise CartError("PROTOCOL")
            if type(item.get("quantity")) is not int or not 1 <= item["quantity"] <= 99:
                raise CartError("PROTOCOL")
            rows.append(
                f"{item['quantity']} × {item_label(review['display'], item['itemId'], item.get('options'))}"
            )
    costs = review.get("remoteCosts")
    if costs is not None:
        rows += ["", *cost_rows(costs, previous=True)]
    labels = {
        "createCart": "criar o carrinho",
        "addItemToCart": "adicionar item",
        "updateCartItem": "alterar quantidade",
        "removeItemFromCart": "remover item",
    }
    rows += [
        "",
        "Alterações: " + ", ".join(labels[s["tool"]] for s in review["changes"]),
        "Subtotal observado dos itens: " + brl(subtotal),
        "Total completo desconhecido; frete, taxas e descontos precisam de conferência.",
        "O botão autoriza somente estas alterações no carrinho da conta conectada.",
        "NÃO ENVIA PEDIDO NEM PROCESSA PAGAMENTO.",
    ]
    text = "\n".join(rows)
    if len(text.encode("utf-8")) > 3500:
        raise CartError("REVIEW_NOT_DISPLAYABLE")
    return text


class Carts:
    def __init__(
        self, state, client, conversation, backend, bot_id, owner, *, scope, clock=time.time
    ):
        self.state, self.client, self.conversation, self.backend = (
            state,
            client,
            conversation,
            backend,
        )
        self.bot_id, self.owner, self.scope, self.clock = bot_id, owner, scope, clock
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cart-human")
        self.future = None
        self.review = None
        self.generation = 0
        self.state.db.execute(
            "CREATE TABLE IF NOT EXISTS cart_callbacks (scope TEXT NOT NULL, request_id TEXT PRIMARY KEY, callback_hash TEXT UNIQUE NOT NULL, phase TEXT NOT NULL, created REAL NOT NULL)"
        )
        self.state.db.commit()

    def close(self):
        self.review = None
        self.executor.shutdown(wait=False, cancel_futures=True)

    def invalidate(self):
        self.review = None
        self.generation += 1

    def _row(self):
        return self.state.db.execute(
            "SELECT request_id,phase FROM cart_callbacks WHERE scope=? ORDER BY created DESC,rowid DESC LIMIT 1",
            (self.scope,),
        ).fetchone()

    def _start(self, kind, work, request_id=None):
        if self.future is not None:
            return "Já estou conferindo o carrinho. Aguarde o resultado."
        self.future = (kind, request_id, self.executor.submit(work))
        return NOTICE

    def receive(self, command, *, expected_version=None):
        row = self._row()
        if command == "/conferircarrinho":
            if not row:
                return "Não há preparação registrada aqui. Use Revisar carrinho."
            return self._start(
                "result", lambda: self._with_current(self.client.request(row[0])), row[0]
            )
        if row and row[1] in {"PENDING", "RESULT_UNKNOWN"}:
            return UNKNOWN
        self.invalidate()
        generation = self.generation

        def prepare():
            if (
                expected_version is not None
                and self.conversation.get_snapshot().version != expected_version
            ):
                raise CartError("CART_REVIEW_STALE")
            link = link_fingerprint(self.backend.status(timeout=5))
            if not link:
                raise CartError("CART_LINK_CHANGED")
            value = self.client.review()
            snapshot = self.conversation.get_snapshot()
            if link_fingerprint(self.backend.status(timeout=5)) != link:
                raise CartError("CART_LINK_CHANGED")
            expires = datetime.fromisoformat(value["expiresAt"])
            if (
                expires.tzinfo is None
                or not self.clock() < expires.timestamp() <= self.clock() + 301
            ):
                raise CartError("CART_CONFIRMATION_EXPIRED")
            return value, link, expires.timestamp(), review_text(value, snapshot), generation

        return self._start("review", prepare)

    def _with_current(self, result):
        # A consulta não altera o estado da intenção reconhecida e nunca repete POST.
        result = dict(result)
        if result.get("state") in {"SUCCEEDED", "FAILED"}:
            try:
                result["_currentText"] = current_text(self.client.current())
            except (CartError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
                result["_currentText"] = None
        return result

    def click(self, callback):
        sender, message = callback.get("from", {}), callback.get("message", {})
        saved = self.review
        if not saved:
            return "Este botão expirou ou já foi usado. Use Conferir carrinho para consultar uma preparação registrada."
        if (
            not isinstance(sender, dict)
            or not isinstance(message, dict)
            or not isinstance(message.get("chat"), dict)
            or not isinstance(message.get("from"), dict)
        ):
            return "Botão inválido. Peça uma nova revisão."
        valid = (
            sender.get("is_bot") is False
            and type(sender.get("id")) is int
            and sender["id"] == self.owner
            and message.get("chat", {}).get("type") == "private"
            and type(message["chat"].get("id")) is int
            and message["chat"].get("id") == self.owner
            and message.get("from", {}).get("is_bot") is True
            and type(message["from"].get("id")) is int
            and message["from"].get("id") == self.bot_id
            and message.get("message_id") == saved["message_id"]
            and type(message.get("message_id")) is int
            and not message.get("forward_origin")
            and callback.get("data") == "cart:" + saved["button"]
            and isinstance(callback.get("id"), str)
            and 0 < len(callback["id"]) <= 128
        )
        if not valid or self.clock() >= saved["expires"] or self.future is not None:
            return "Botão inválido ou expirado. Peça uma nova revisão."
        self.review = None
        request_id = str(uuid.uuid4())
        callback_id = callback["id"]
        digest = hashlib.sha256(callback_id.encode()).hexdigest()
        # Marker antes de agendar a rede. Nunca persistir referência, composição ou texto.
        with self.state.db:
            if self.state.db.execute(
                "SELECT 1 FROM cart_callbacks WHERE callback_hash=?", (digest,)
            ).fetchone():
                return UNKNOWN
            self.state.db.execute(
                "INSERT INTO cart_callbacks VALUES(?,?,?,'PENDING',?)",
                (self.scope, request_id, digest, self.clock()),
            )

        def confirm():
            try:
                if (
                    link_fingerprint(self.backend.status(timeout=5)) != saved["link"]
                    or self.conversation.get_snapshot().version != saved["version"]
                ):
                    raise CartError("CART_REVIEW_CHANGED")
            except (BackendError, ConversationError, ProtocolError):
                raise CartError("CART_REVIEW_CHANGED") from None
            try:
                result = self.client.confirm(saved["reference"], request_id, callback_id)
            except CartError as error:
                if error.uncertain:
                    # Só consulta; a referência nunca é reenviada, mesmo após timeout.
                    try:
                        result = self.client.request(request_id)
                    except CartError:
                        raise CartError(uncertain=True) from None
                else:
                    raise
            return self._with_current(result)

        return self._start("confirm", confirm, request_id)

    def tick(self, telegram):
        if not self.future or not self.future[2].done():
            return
        kind, request_id, future = self.future
        self.future = None
        try:
            value = future.result()
            if kind == "review":
                review, link, expires, text, generation = value
                if generation != self.generation or self.clock() >= expires:
                    return
                button = secrets.token_urlsafe(18)
                sent = telegram.send(
                    self.owner,
                    text,
                    {
                        "inline_keyboard": [
                            [{"text": "Preparar este carrinho", "callback_data": "cart:" + button}]
                        ]
                    },
                )
                if not isinstance(sent, dict) or type(sent.get("message_id")) is not int:
                    raise CartError("PROTOCOL")
                self.review = {
                    "reference": review["confirmationRef"],
                    "version": review["version"],
                    "link": link,
                    "expires": expires,
                    "button": button,
                    "message_id": sent["message_id"],
                }
                return
            phase = value["state"]
            with self.state.db:
                self.state.db.execute(
                    "UPDATE cart_callbacks SET phase=? WHERE scope=? AND request_id=?",
                    (phase, self.scope, request_id),
                )
            text = {
                "PENDING": UNKNOWN,
                "RESULT_UNKNOWN": UNKNOWN,
                "SUCCEEDED": "PREPARAÇÃO CONCLUÍDA — PEDIDO NÃO ENVIADO.",
                "FAILED": "A preparação foi interrompida. Pode haver alterações já reconhecidas. Consulte a equipe antes de uma nova revisão.",
            }[phase]
            if phase in {"SUCCEEDED", "FAILED"}:
                text += "\n\n" + (
                    value.get("_currentText")
                    or "Não consegui conferir a composição e os custos atuais. Use Conferir carrinho para consultar novamente; nenhuma escrita será repetida."
                )
        except (
            CartError,
            BackendError,
            ConversationError,
            ProtocolError,
            ValueError,
            TypeError,
            KeyError,
            OverflowError,
            AttributeError,
        ) as error:
            if request_id:
                phase = (
                    "FAILED"
                    if kind == "confirm" and isinstance(error, CartError) and not error.uncertain
                    else "RESULT_UNKNOWN"
                )
                with self.state.db:
                    self.state.db.execute(
                        "UPDATE cart_callbacks SET phase=? WHERE scope=? AND request_id=?",
                        (phase, self.scope, request_id),
                    )
                text = (
                    UNKNOWN
                    if phase == "RESULT_UNKNOWN"
                    else "A revisão perdeu a validade antes da preparação. Nenhuma repetição será enviada; peça uma nova revisão."
                )
            else:
                text = REVIEW_PROBLEMS.get(
                    getattr(error, "code", None),
                    "Não consegui consultar os dados para revisar o carrinho agora. Se continuar, confira com a equipe.",
                )
                text += " Nenhuma alteração foi enviada ao iFood."
        except TelegramError:
            self.review = None
            return  # Entrega incerta não mantém um botão de autorização utilizável na RAM.
        try:
            telegram.send(self.owner, text)
        except TelegramError:
            pass  # Conferir carrinho recupera por GET; nunca refaz a confirmação.
