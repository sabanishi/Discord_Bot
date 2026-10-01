from bot_jobs import check_page_loop, create_page_loop, link_warning_loop, tactical_challenge_loop


def register_scheduled_tasks(client, state, notifier) -> bool:
    if getattr(state, "tasks_started", False):
        return False

    state.tasks_started = True
    client.loop.create_task(create_page_loop(client, state, notifier))
    client.loop.create_task(check_page_loop(client, state, notifier))
    client.loop.create_task(tactical_challenge_loop(client, state, notifier))
    if state.config.link_warning_enabled:
        client.loop.create_task(link_warning_loop(client, state, notifier))
    return True
