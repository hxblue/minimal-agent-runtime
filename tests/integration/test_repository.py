from __future__ import annotations

from app.models import AgentRun, Message, SessionMemory, TraceEvent
from app.storage.sqlite import SQLiteRepository


async def test_repository_persists_all_session_state(tmp_path) -> None:
    database = tmp_path / "persistent.db"
    repo = SQLiteRepository(database)
    await repo.initialize()
    session = await repo.create_session("Interview")
    message = Message(session_id=session.id, role="user", content="Remember blue")
    await repo.append_message(message)
    await repo.save_memory(
        SessionMemory(
            session_id=session.id,
            summary="The user chose blue.",
            through_message_id=message.id,
        )
    )
    todo = await repo.add_todo(session.id, "Submit the exercise")
    run = AgentRun(session_id=session.id)
    await repo.create_run(run)
    event = TraceEvent(
        run_id=run.id,
        session_id=session.id,
        event_type="run_started",
        status="started",
    )
    await repo.add_trace_event(event)
    run.status = "completed"
    run.rounds = 1
    await repo.update_run(run)
    await repo.close()

    reopened = SQLiteRepository(database)
    await reopened.initialize()
    try:
        assert (await reopened.get_session(session.id)) == session.model_copy(
            update={"updated_at": (await reopened.get_session(session.id)).updated_at}
        )
        assert (await reopened.list_messages(session.id))[0].content == "Remember blue"
        assert (await reopened.get_memory(session.id)).summary == "The user chose blue."
        assert (await reopened.list_todos(session.id))[0].id == todo.id
        assert (await reopened.get_run(run.id)).status == "completed"
        assert (await reopened.list_trace_events(run.id))[0].event_type == "run_started"
    finally:
        await reopened.close()


async def test_repository_filters_messages_and_todos_by_session(repository) -> None:
    first = await repository.create_session("First")
    second = await repository.create_session("Second")
    await repository.append_message(Message(session_id=first.id, role="user", content="A"))
    await repository.append_message(Message(session_id=second.id, role="user", content="B"))
    await repository.add_todo(first.id, "Only A")

    assert [item.content for item in await repository.list_messages(first.id)] == ["A"]
    assert [item.content for item in await repository.list_messages(second.id)] == ["B"]
    assert [item.content for item in await repository.list_todos(first.id)] == ["Only A"]
    assert await repository.list_todos(second.id) == []


async def test_initialize_is_idempotent(repository) -> None:
    await repository.initialize()
    session = await repository.create_session()
    assert await repository.get_session(session.id) is not None

