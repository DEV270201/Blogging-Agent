from langgraph.checkpoint.postgres import PostgresSaver

from Server.persistence.database import get_pool

_checkpointer: PostgresSaver | None = None


def get_checkpointer() -> PostgresSaver:
    global _checkpointer
    if _checkpointer is None:
        checkpointer = PostgresSaver(get_pool())
        checkpointer.setup()
        _checkpointer = checkpointer
    return _checkpointer


def delete_checkpoint_thread(thread_id: str) -> None:
    get_checkpointer().delete_thread(str(thread_id))
