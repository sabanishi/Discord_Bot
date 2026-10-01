import asyncio
from datetime import datetime, timedelta
from collections.abc import Awaitable, Callable
from zoneinfo import ZoneInfo


JST = ZoneInfo("Asia/Tokyo")


def get_next_scheduled_time(
    now: datetime,
    hour: int,
    minute: int,
) -> datetime:
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return target


async def sleep_until_next_time(hour: int, minute: int) -> datetime:
    now = datetime.now(JST)
    target = get_next_scheduled_time(now, hour, minute)
    await asyncio.sleep((target - now).total_seconds())
    return target


async def run_interval_loop(
    *,
    is_closed: Callable[[], bool],
    interval_seconds: int,
    job: Callable[[], Awaitable[None]],
    on_error: Callable[[Exception], Awaitable[None]],
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    while not is_closed():
        try:
            await job()
        except Exception as error:
            await on_error(error)
        await sleep(interval_seconds)


async def run_daily_loop(
    *,
    client,
    hour: int,
    minute: int,
    job: Callable[[datetime], Awaitable[None]],
    on_error: Callable[[Exception], Awaitable[None]],
    sleep_until: Callable[[int, int], Awaitable[datetime]] = sleep_until_next_time,
) -> None:
    await client.wait_until_ready()
    while not client.is_closed():
        target = await sleep_until(hour, minute)
        try:
            await job(target)
        except Exception as error:
            await on_error(error)
