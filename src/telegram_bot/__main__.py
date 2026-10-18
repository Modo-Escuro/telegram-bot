import argparse
import sqlite3

from .backend import Backend, BackendConfig
from .cart import Carts
from .cart_client import CartClient
from .config import Config
from .connections import Connections
from .conversation import ConversationClient
from .conversation_runner import Conversations, ConversationService, scope_for
from .multiuser import poll_password
from .outbox import Outbox
from .runner import identify, poll
from .state import State, single_instance
from .telegram import Telegram, TelegramError
from .voice import VoiceConfig, VoiceTranscriber


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
        voice_config = VoiceConfig.from_env()
        api = Telegram(config.token, cart_enabled=config.cart_enabled)
        me = api.check()
        if args.check:
            print("Token Telegram válido e webhook ausente. Login iFood não verificado.")
            return 0
        config.state_dir.mkdir(parents=True, exist_ok=True)
        with single_instance(config.state_dir / f"bot-{me['id']}.lock"):
            if args.identify:
                identify(api)
                return 0
            api.configure_name(me)
            if config.access_password:
                # Valida o transporte antes do polling. O ID de cada usuário virá do update autenticado.
                backend_config = BackendConfig.from_env(config.allowed_user_id or 1)
                if config.conversation_enabled and backend_config is None:
                    raise ValueError("Conversa requer BACKEND_BASE_URL e BACKEND_API_TOKEN.")
                state = State(config.state_dir / f"bot-{me['id']}.sqlite3")
                try:
                    print("Bot iniciado com acesso por senha. Uma instância de polling.")
                    poll_password(api, state, config, me["id"], me["username"])
                finally:
                    state.close()
                return 0
            backend_config = BackendConfig.from_env(config.allowed_user_id)
            if config.conversation_enabled and backend_config is None:
                raise ValueError(
                    "Conversa requer BACKEND_BASE_URL e BACKEND_API_TOKEN configurados."
                )
            backend = Backend(backend_config) if backend_config else None
            state = State(config.state_dir / f"bot-{me['id']}.sqlite3")
            box, service, carts = None, None, None
            try:
                conversations = None
                if config.conversation_enabled:
                    path = config.state_dir / f"bot-{me['id']}.sqlite3"
                    scope = scope_for(backend_config, me["id"])
                    client_factory = lambda: ConversationClient(backend_config, me["id"], timeout=5)
                    box = Outbox(path, scope)
                    conversations = Conversations(
                        box, client_factory(), voice_enabled=voice_config is not None
                    )
                    service = ConversationService(
                        path,
                        scope,
                        client_factory,
                        lambda: Telegram(config.token, timeout=5, cart_enabled=config.cart_enabled),
                        config.allowed_user_id,
                        link_status_factory=lambda: (
                            lambda: Backend(backend_config).status(timeout=5)
                        ),
                        transcriber_factory=(
                            lambda: VoiceTranscriber(
                                voice_config, config.state_dir / "voice-budget.sqlite3"
                            )
                        )
                        if voice_config
                        else None,
                    )
                    service.start()
                if config.cart_enabled:
                    carts = Carts(
                        state,
                        CartClient(backend_config),
                        ConversationClient(backend_config, me["id"], timeout=5),
                        Backend(backend_config),
                        me["id"],
                        config.allowed_user_id,
                        scope=scope_for(backend_config, me["id"]),
                    )
                print("Bot iniciado. Abra a conversa privada e envie /start. Ctrl+C encerra.")
                poll(
                    api,
                    state,
                    config.allowed_user_id,
                    me["username"],
                    connections=Connections(
                        backend, state, config.allowed_user_id, conversations=conversations
                    ),
                    conversations=conversations,
                    service=service,
                    carts=carts,
                )
            finally:
                try:
                    if carts:
                        carts.close()
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
