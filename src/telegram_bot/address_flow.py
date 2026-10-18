"""Fluxo só de leitura MCP e seleção local humana; executado pelo worker existente."""

from .conversation import ConversationError
from .conversation_contract import decode


class AddressFlow:
    def __init__(self, worker):
        self.worker = worker

    def tick(self, row):
        w = self.worker
        if row["kind"] == "ADDRESS_SELECT":
            reference = decode(bytes(row["body"]))["choiceRef"]
            w.client.select_address(reference)
            w.box.save(row["seq"], state="NOTICE", notice="ADDRESS_SELECTED", body=None, attempts=0)
            return
        try:
            value = w.client.get_addresses()
        except ConversationError as error:
            if error.code != "ACTION_UNAVAILABLE":
                raise
            if row["link_hash"]:
                w.box.finish(
                    row["seq"]
                )  # Compatibilidade: API antiga não altera a retomada informativa.
            else:
                w.box.save(row["seq"], state="NOTICE", notice="ADDRESS_UNAVAILABLE", attempts=0)
            return
        if row["link_hash"] and row["link_hash"] != value["linkHash"]:
            raise ConversationError("LINK_CHANGED")
        options = value["options"]
        if not options:
            w._deliver(
                row,
                [
                    "Sua conta iFood está conectada, mas não retornou endereços cadastrados. Cadastre um endereço no aplicativo iFood e depois toque em Endereços iFood. Podemos continuar organizando participantes, restrições e orçamento por aqui."
                ],
            )
            return
        if len(options) == 1:
            text = (
                "Encontrei um endereço cadastrado: "
                + options[0]["label"]
                + ".\nConfirma usar este endereço para as sugestões?"
            )
        else:
            text = "Qual endereço cadastrado devemos usar para as sugestões?\n" + "\n".join(
                f"{i}. {option['label']}" for i, option in enumerate(options, 1)
            )
        if len(text.encode("utf-8")) > 3500:
            raise ConversationError("PROTOCOL")
        markup = {
            "inline_keyboard": [
                [{"text": "Usar endereço " + str(i), "callback_data": "ifa:" + option["choiceRef"]}]
                for i, option in enumerate(options, 1)
            ]
        }
        known = w.box.delivered(row["seq"], 0)
        if known:
            w.box.bind_addresses(known, w.client.bot_id, options)
        w._deliver(
            row,
            [text],
            markup=markup,
            on_delivery=lambda mid: w.box.bind_addresses(mid, w.client.bot_id, options),
        )
