"""Projeção textual mínima. Não oferece ações de compra nem imprime documentos/referências."""

import re


def money(price):
    def brl(value):
        return f"R$ {value // 100},{value % 100:02d}"

    if price["kind"] == "UNKNOWN":
        return "Custo desconhecido; revisão/aprovação indisponível."
    if price["kind"] == "RANGE":
        return f"Faixa: {brl(price['minCents'])} a {brl(price['maxCents'])}."
    label = "Estimativa" if price["kind"] == "ESTIMATE" else "Cotação informada pela API"
    return f"{label}: {brl(price['totalCents'])}."


def render(snapshot):
    document = snapshot.to_dict()
    lines = []
    for block in document["blocks"]:
        kind = block["kind"]
        if kind == "TEXT":
            # Texto do modelo é identificado e nunca vira evidência de pedido/aprovação.
            prefix = "Assistente: " if block["source"] == "MODEL" else ""
            lines.append(prefix + block["text"])
        elif kind == "GROUP":
            lines.append("Grupo informado:")
            for person in block["participants"]:
                conditions = "; ".join(person["conditions"]) or "condições ainda não informadas"
                lines.append(f"• {person['displayName']}: {conditions}")
            if block["budgetCents"] is not None:
                lines.append(
                    money({"kind": "ESTIMATE", "totalCents": block["budgetCents"]}).replace(
                        "Estimativa", "Orçamento"
                    )
                )
        elif kind in {"PROPOSAL", "REVIEW"}:
            lines.append("Proposta informativa." if kind == "PROPOSAL" else "Revisão informativa.")
            lines.append(money(block["price"]))
            for blocker in block.get("blockers", []):
                lines.append("Pendência: " + blocker)
            for coverage in block["coverage"]:
                if coverage["status"] != "COVERED":
                    lines.append("Há participante sem atendimento verificado.")
        elif kind == "OUTCOME":
            lines.append(
                "Resultado de compra fora do fluxo disponível neste bot; não houve envio por esta interface."
            )
    lines.extend("Falta esclarecer: " + question for question in document["pending"])
    lines.append("Conversa em preparação. Nenhum pedido é enviado por este bot.")
    text = "\n\n".join(lines)
    # Defesa adicional: nunca exibir referências humanas nem identificadores técnicos do documento.
    references = [document.get("conversationId", "")]
    for action in document["allowedActions"]:
        references.append(action["actionRef"])
    if document["humanApproval"]:
        references.extend(document["humanApproval"][k] for k in ("reviewRef", "approvalRef"))
    for block in document["blocks"]:
        references.extend(block.get(k, "") for k in ("proposalRef", "reviewRef", "evidenceRef"))
        references.extend(p.get("participantRef", "") for p in block.get("participants", []))
        references.extend(p.get("participantRef", "") for p in block.get("coverage", []))
    for ref in sorted(set(references), key=len, reverse=True):
        if ref:
            text = text.replace(ref, "[referência omitida]")
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)


def chunks(text, limit=3500):
    """Telegram limita por unidades UTF-16; dividir sem cortar um ponto Unicode."""
    result, current, size = [], [], 0
    for char in text:
        units = len(char.encode("utf-16-le")) // 2
        if size + units > limit:
            result.append("".join(current))
            current, size = [], 0
        current.append(char)
        size += units
    if current:
        result.append("".join(current))
    return result
