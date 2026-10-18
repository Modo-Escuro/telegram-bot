"""Apresentação do contrato da API; sem preço, identidade ou rótulo inferidos pelo modelo."""

import unicodedata

from .cart_client import CartError

MAX_CENTS = 2**53 - 1


def text(value):
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 180
        or any(unicodedata.category(c).startswith("C") for c in value)
    ):
        raise CartError("REVIEW_NOT_DISPLAYABLE")
    return value


def cents(value):
    if type(value) is not int or not 0 <= value <= MAX_CENTS:
        raise CartError("PROTOCOL")
    return value


def brl(value):
    value = cents(value)
    return f"R$ {value // 100},{value % 100:02d}"


def context_rows(display):
    if not isinstance(display, dict):
        raise CartError("REVIEW_NOT_DISPLAYABLE")
    return [
        "Conta iFood: " + text(display.get("accountLabel")),
        "Loja: " + text(display.get("merchantName")),
        "Endereço: " + text(display.get("addressLabel")),
    ]


def option_key(options):
    if not isinstance(options, list) or len(options) > 50:
        raise CartError("PROTOCOL")
    pairs = []
    for option in options:
        if (
            not isinstance(option, dict)
            or not isinstance(option.get("optionId"), str)
            or type(option.get("quantity")) is not int
            or not 1 <= option["quantity"] <= 99
        ):
            raise CartError("PROTOCOL")
        pairs.append((option["optionId"], option["quantity"]))
    if len({key for key, _ in pairs}) != len(pairs):
        raise CartError("PROTOCOL")
    return sorted(pairs)


def item_label(display, item_id, options, *, expected_name=None):
    if not isinstance(item_id, str) or not isinstance(display.get("items"), list):
        raise CartError("PROTOCOL")
    key = option_key(options)
    matches = [
        label
        for label in display["items"]
        if isinstance(label, dict)
        and label.get("itemId") == item_id
        and option_key(label.get("options")) == key
    ]
    if len(matches) != 1:
        raise CartError("REVIEW_NOT_DISPLAYABLE")
    label = matches[0]
    name = text(label.get("name"))
    if expected_name is not None and name != expected_name:
        raise CartError("REVIEW_NOT_DISPLAYABLE")
    if key:
        name += (
            " ("
            + ", ".join(f"{o['quantity']} × {text(o.get('name'))}" for o in label["options"])
            + ")"
        )
    return name


def cost_rows(costs, *, previous=False):
    if costs is None:
        return ["Custos completos indisponíveis; orçamento ainda não verificado."]
    if not isinstance(costs, dict):
        raise CartError("PROTOCOL")
    values = {
        k: cents(costs.get(k))
        for k in ("subtotal", "deliveryFee", "serviceFee", "discount", "total")
    }
    if (
        values["subtotal"] + values["deliveryFee"] + values["serviceFee"] - values["discount"]
        != values["total"]
    ):
        raise CartError("PROTOCOL")
    return [
        "Custos do carrinho atual, antes destas alterações:"
        if previous
        else "Custos observados nesta consulta:",
        "Itens: " + brl(values["subtotal"]),
        "Entrega: " + brl(values["deliveryFee"]),
        "Taxa de serviço: " + brl(values["serviceFee"]),
        "Desconto: " + brl(values["discount"]),
        ("Total atual: " if previous else "Total observado: ") + brl(values["total"]),
    ]


def current_text(value):
    if not isinstance(value, dict) or any(
        value.get(k) is not False
        for k in ("purchaseAuthorized", "checkoutEnabled", "paymentEnabled")
    ):
        raise CartError("PROTOCOL")
    display, cart, budget = value.get("display"), value.get("cart"), value.get("budget")
    rows = ["Consulta atual do carrinho", *context_rows(display)]
    if (
        not isinstance(cart, dict)
        or not isinstance(cart.get("items"), list)
        or len(cart["items"]) > 40
    ):
        raise CartError("PROTOCOL")
    subtotal, all_prices = 0, True
    for item in cart["items"]:
        if (
            not isinstance(item, dict)
            or type(item.get("quantity")) is not int
            or not 1 <= item["quantity"] <= 99
        ):
            raise CartError("PROTOCOL")
        row = f"{item['quantity']} × {item_label(display, item.get('itemId'), item.get('options'))}"
        if item.get("unitPrice") is None:
            all_prices = False
            row += " — preço unitário indisponível"
        else:
            subtotal += cents(item["unitPrice"]) * item["quantity"]
            row += " — " + brl(item["unitPrice"]) + " por unidade"
        rows.append(row)
    if not cart["items"]:
        rows.append("Carrinho sem itens.")
    costs = cart.get("totals")
    if all_prices and costs is not None and subtotal != costs.get("subtotal"):
        raise CartError("PROTOCOL")
    rows += ["", *cost_rows(costs)]
    status = budget.get("status") if isinstance(budget, dict) else None
    if status not in {"WITHIN_LIMITS", "LIMIT_EXCEEDED", "UNVERIFIED"}:
        raise CartError("PROTOCOL")
    rows.append(
        {
            "WITHIN_LIMITS": "Custos observados dentro dos limites informados.",
            "LIMIT_EXCEEDED": "ATENÇÃO: custos observados ultrapassam um limite informado.",
            "UNVERIFIED": "Orçamento não verificado; a composição ou os custos exigem revisão.",
        }[status]
    )
    rows += [
        "Restrições e disponibilidade não foram revalidadas nesta consulta.",
        "PEDIDO NÃO ENVIADO. Nenhum pagamento processado.",
    ]
    result = "\n".join(rows)
    if len(result.encode("utf-8")) > 3500:
        raise CartError("REVIEW_NOT_DISPLAYABLE")
    return result
