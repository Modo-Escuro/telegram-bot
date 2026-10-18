"""Projeção textual mínima. Não oferece ações de compra nem imprime documentos/referências."""

import re

BUDGET_LABELS = ("Orçamento do grupo", "Orçamento")
SEPARATOR = "━━━━━━━━━━━━"


def collection_text(text, group):
    """Remover apenas confirmações redundantes reconstruíveis dos fatos atuais.

    Não descarta texto desconhecido, recusas, alertas nem texto do modelo.
    """
    redundant = []
    for person in group["participants"]:
        name = person["displayName"]
        redundant.append(f"{name} entrou na compra.")
        if "Sem restrições alimentares" in person["conditions"]:
            redundant.append(f"{name} não tem restrições.")
        for condition in person["conditions"]:
            match = re.fullmatch(r"Alergia: (.+) \(obrigatória\)", condition)
            if match:
                redundant.append(f"Registrei alergia a {match[1]} para {name}.")
    for sentence in sorted(redundant, key=len, reverse=True):
        # Só frases completas na sequência de confirmações do servidor.
        if text.startswith(sentence):
            text = text[len(sentence) :].lstrip()
    # A ordem das ações pode divergir da ordem do grupo.
    if any(text.startswith(sentence) for sentence in redundant):
        return collection_text(text, group)
    return text


def money(price):
    def brl(value):
        return f"R$ {value // 100},{value % 100:02d}"

    if price["kind"] == "UNKNOWN":
        return "Total final ainda desconhecido; não confirma o orçamento."
    if price["kind"] == "RANGE":
        return f"Faixa: {brl(price['minCents'])} a {brl(price['maxCents'])}."
    label = "Estimativa" if price["kind"] == "ESTIMATE" else "Cotação informada pela API"
    return f"{label}: {brl(price['totalCents'])}."


def render(snapshot, *, collection_only=False, concise=False):
    document = snapshot.to_dict()
    # API histórica pode devolver somente GROUP. Nesse caso ele é a própria resposta.
    if not document["pending"] and all(b["kind"] == "GROUP" for b in document["blocks"]):
        concise = False
    lines = []
    group = next((b for b in document["blocks"] if b["kind"] == "GROUP"), None)
    # Uso individual: com uma pessoa só, os textos do bot não falam em "grupo".
    single = bool(group) and len(group["participants"]) == 1
    budget_text = None
    if group and group["budgetCents"] is not None:
        cents = group["budgetCents"]
        amount = f"R$ {cents // 100}.{cents % 100:02d}"
        for b in document["blocks"]:
            if b["kind"] == "TEXT" and b["source"] == "SERVER":
                for qualifier in ("máximo", "referência"):
                    # API usa "Orçamento:" quando há uma pessoa só (uso individual).
                    if b["text"] in {
                        f"{label}: {amount} ({qualifier})." for label in BUDGET_LABELS
                    }:
                        budget_text = b["text"].replace(amount, amount.replace(".", ","))
    for block in document["blocks"]:
        kind = block["kind"]
        if collection_only and kind != "GROUP":
            continue
        if kind == "TEXT":
            # Texto do modelo é identificado e nunca vira evidência de pedido/aprovação.
            prefix = "Assistente: " if block["source"] == "MODEL" else ""
            text = block["text"]
            if concise and block["source"] == "SERVER":
                if text in {"Nada foi alterado.", "Pergunta registrada."}:
                    continue
                if budget_text and text.startswith(tuple(f"{label}: " for label in BUDGET_LABELS)):
                    continue
                text = re.sub(r"(R\$ \d+)\.(\d{2})(?!\d)", r"\1,\2", text)
            elif group and block["source"] == "SERVER":
                text = collection_text(text, group)
                if budget_text and group["budgetCents"] is not None:
                    cents = group["budgetCents"]
                    amount = f"R$ {cents // 100}.{cents % 100:02d}"
                    if text in {
                        f"{label}: {amount} ({q})."
                        for label in BUDGET_LABELS
                        for q in ("máximo", "referência")
                    }:
                        text = ""
                    for who in ("o grupo", "você"):  # "você" no uso individual
                        if "(máximo)" in budget_text:
                            text = text.removeprefix(
                                f"Teto máximo de {amount} para {who}."
                            ).lstrip()
                        if "(referência)" in budget_text:
                            text = text.removeprefix(
                                f"Valor de referência de {amount} para {who}."
                            ).lstrip()
            if text:
                lines.append(prefix + text)
        elif kind == "GROUP":
            if concise and not collection_only:
                continue
            noun = "pedido" if single else "grupo"
            lines.append(
                f"Certo! Seu {noun} ficou assim:"
                if not collection_only
                else f"Seu {noun} continua aqui:"
            )
            people = []
            for person in block["participants"]:
                conditions = "; ".join(person["conditions"]) or "condições ainda não informadas"
                people.append(f"• {person['displayName']}: {conditions}")
            lines.append("\n".join(people))
            if block["budgetCents"] is not None:
                lines.append(
                    budget_text
                    or money({"kind": "ESTIMATE", "totalCents": block["budgetCents"]}).replace(
                        "Estimativa", "Orçamento"
                    )
                )
        elif kind in {"PROPOSAL", "REVIEW"}:
            # Separador visual entre propostas; os detalhes vêm no texto do servidor logo abaixo.
            lines.append(SEPARATOR)
            if kind == "REVIEW":
                lines.append("Revisão informativa.")
                lines.append(money(block["price"]))
            for blocker in block.get("blockers", []):
                lines.append("Pendência: " + blocker)
            uncovered = {c["participantRef"] for c in block["coverage"] if c["status"] != "COVERED"}
            if uncovered:
                names = [
                    p["displayName"]
                    for p in (group or {}).get("participants", [])
                    if p["participantRef"] in uncovered
                ]
                lines.append(
                    "Sem atendimento verificado: "
                    + (", ".join(names) or "há participante com restrições pendentes")
                    + "."
                )
        elif kind == "OUTCOME":
            lines.append(
                "Resultado de compra fora do fluxo disponível no Ailo; não houve envio por esta interface."
            )
    if collection_only:
        if not lines:
            lines.append("Não há grupo salvo para apresentar. Envie uma mensagem para começar.")
        lines.insert(
            0,
            "Vamos continuar de onde paramos? Retomada informativa do "
            + ("pedido" if single else "grupo")
            + " salvo.",
        )
        lines.append(
            "Envie sua próxima mensagem para continuar. Itens, preços, endereço e ações precisam de nova validação na conta atual."
        )
        lines.append("Se faltar uma resposta, consulte Ajuda.")
    else:
        asked = False
        for question in document["pending"]:
            routine = question in {
                "Quem vai participar da compra?",
                "Qual é o orçamento do grupo?",
                "Qual é o seu orçamento?",
                "Vocês preferem economia ou rapidez?",
                "Você prefere economia ou rapidez?",
            } or (
                group
                and any(
                    question
                    in {
                        f"{p['displayName']} tem alguma alergia ou restrição alimentar?",
                        f"{p['displayName']} tem alguma alergia ou restrição alimentar? Pode confirmar?",
                    }
                    for p in group["participants"]
                )
            )
            if not routine or not asked:
                lines.append(question)
            asked = asked or bool(routine)
    if not collection_only and document["allowedActions"]:
        kinds = {a["kind"] for a in document["allowedActions"]}
        if "REQUEST_REVIEW" in kinds:
            lines.append(
                "Confira os itens do carrinho. Você pode mudar a busca ou revisar o carrinho quando essa função estiver disponível."
            )
        elif "SELECT_PROPOSAL" in kinds:
            lines.append(
                "Qual opção você prefere? Toque em uma opção ou diga, por exemplo, ‘a segunda’. Também pode pedir outra busca."
            )
        elif any(
            a["actionRef"].startswith(("search_", "more_")) for a in document["allowedActions"]
        ):
            lines.append(
                "Você pode mudar o tipo de comida ou pedir uma nova busca, mantendo as restrições."
            )
    text = "\n\n".join(lines) or (
        "O pedido continua igual. O que deseja mudar?"
        if single
        else "O grupo continua igual. O que deseja mudar?"
    )
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
