"""Projeção textual mínima. Não oferece ações de compra nem imprime documentos/referências."""

import re


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
        return "Custo desconhecido; revisão/aprovação indisponível."
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
    budget_text = None
    if group and group["budgetCents"] is not None:
        cents = group["budgetCents"]
        amount = f"R$ {cents // 100}.{cents % 100:02d}"
        for b in document["blocks"]:
            if b["kind"] == "TEXT" and b["source"] == "SERVER":
                for qualifier in ("máximo", "referência"):
                    if b["text"] == f"Orçamento do grupo: {amount} ({qualifier}).":
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
                if budget_text and text.startswith("Orçamento do grupo: "):
                    continue
                text = re.sub(r"(R\$ \d+)\.(\d{2})(?!\d)", r"\1,\2", text)
            elif group and block["source"] == "SERVER":
                text = collection_text(text, group)
                if budget_text and group["budgetCents"] is not None:
                    cents = group["budgetCents"]
                    amount = f"R$ {cents // 100}.{cents % 100:02d}"
                    if text in {
                        f"Orçamento do grupo: {amount} (máximo).",
                        f"Orçamento do grupo: {amount} (referência).",
                    }:
                        text = ""
                    if "(máximo)" in budget_text:
                        text = text.removeprefix(f"Teto máximo de {amount} para o grupo.").lstrip()
                    if "(referência)" in budget_text:
                        text = text.removeprefix(
                            f"Valor de referência de {amount} para o grupo."
                        ).lstrip()
            if text:
                lines.append(prefix + text)
        elif kind == "GROUP":
            if concise and not collection_only:
                continue
            lines.append(
                "Certo! Seu grupo ficou assim:"
                if not collection_only
                else "Seu grupo continua aqui:"
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
            lines.append("Proposta informativa." if kind == "PROPOSAL" else "Revisão informativa.")
            lines.append(money(block["price"]))
            for blocker in block.get("blockers", []):
                lines.append("Pendência: " + blocker)
            for coverage in block["coverage"]:
                if coverage["status"] != "COVERED":
                    lines.append("Há participante sem atendimento verificado.")
        elif kind == "OUTCOME":
            lines.append(
                "Resultado de compra fora do fluxo disponível no Ailo; não houve envio por esta interface."
            )
    if collection_only:
        if not lines:
            lines.append("Não há grupo salvo para apresentar. Envie uma mensagem para começar.")
        lines.insert(0, "Vamos continuar de onde paramos? Retomada informativa do grupo salvo.")
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
                "Vocês preferem economia ou rapidez?",
            } or (
                group
                and any(
                    question == f"{p['displayName']} tem alguma alergia ou restrição alimentar?"
                    for p in group["participants"]
                )
            )
            if not routine or not asked:
                lines.append(question)
            asked = asked or bool(routine)
    text = "\n\n".join(lines) or "O grupo continua igual. O que deseja mudar?"
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
