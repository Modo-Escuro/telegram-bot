import argparse
import sqlite3

from .backend import Backend, BackendConfig
from .config import Config
from .connections import Connections
from .conversation import ConversationClient
from .conversation_runner import Conversations, ConversationService, scope_for
from .outbox import Outbox
from .runner import identify, poll
from .state import State, single_instance
from .telegram import Telegram, TelegramError


def main():
    parser = argparse.ArgumentParser(description="Bot privado Compra com Contexto.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="Verifica token e ausência de webhook.")
    group.add_argument(
        "--identify", action="store_true", help="Descobre seu ID por desafio privado."
    )
    args = parser.parse_args()
    try:
        config = Config.from_env(identify=args.identify)
        api = Telegram(config.token)
        me = api.check()
        if args.check:
            print("Token Telegram válido e webhook ausente. Login iFood não verificado.")
            return 0
        config.state_dir.mkdir(parents=True, exist_ok=True)
        with single_instance(config.state_dir / f"bot-{me['id']}.lock"):
            if args.identify:
                identify(api)
                return 0
            backend_config = BackendConfig.from_env(config.allowed_user_id)
            if config.conversation_enabled and backend_config is None:
                raise ValueError(
                    "Conversa requer BACKEND_BASE_URL e BACKEND_API_TOKEN configurados."
                )
            backend = Backend(backend_config) if backend_config else None
            state = State(config.state_dir / f"bot-{me['id']}.sqlite3")
            box, service = None, None
            try:
                conversations = None
                if config.conversation_enabled:
                    path = config.state_dir / f"bot-{me['id']}.sqlite3"
                    scope = scope_for(backend_config, me["id"])
                    client_factory = lambda: ConversationClient(backend_config, me["id"], timeout=5)
                    box = Outbox(path, scope)
                    conversations = Conversations(box, client_factory())
                    service = ConversationService(
                        path,
                        scope,
                        client_factory,
                        lambda: Telegram(config.token, timeout=5),
                        config.allowed_user_id,
                    )
                    service.start()
                print("Bot iniciado. Abra a conversa privada e envie /start. Ctrl+C encerra.")
                poll(
                    api,
                    state,
                    config.allowed_user_id,
                    me["username"],
                    connections=Connections(backend, state, config.allowed_user_id),
                    conversations=conversations,
                    service=service,
                )
            finally:
                try:
                    if service:
                        service.stop()
                finally:
                    if box:
                        box.close()
                    state.close()
    except KeyboardInterrupt:
        print("\nBot encerrado.")
        return 0
    except TelegramError as exc:
        if exc.code == 401:
            print("Token Telegram recusado. Confira a configuração local.")
        elif exc.code == 409:
            print("Conflito de polling/webhook. Encerre a outra instância antes de reiniciar.")
        else:
            print(str(exc))
        return 1
    except ValueError as exc:
        print(str(exc))
        return 1
    except (OSError, sqlite3.Error):
        print("Não foi possível acessar o estado local ou concluir a operação.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
