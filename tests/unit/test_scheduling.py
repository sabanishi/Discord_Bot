import asyncio
import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.scheduling import get_next_scheduled_time, sleep_until_next_time


class SchedulingTests(unittest.TestCase):
    def test_next_time_is_tomorrow_after_schedule(self):
        now = datetime(2026, 10, 1, 8, 0, tzinfo=ZoneInfo("Asia/Tokyo"))

        result = get_next_scheduled_time(now, 7, 0)

        self.assertEqual(result, datetime(2026, 10, 2, 7, 0, tzinfo=ZoneInfo("Asia/Tokyo")))

    def test_next_time_is_today_before_schedule(self):
        now = datetime(2026, 10, 1, 6, 0, tzinfo=ZoneInfo("Asia/Tokyo"))

        result = get_next_scheduled_time(now, 7, 0)

        self.assertEqual(result, datetime(2026, 10, 1, 7, 0, tzinfo=ZoneInfo("Asia/Tokyo")))

    def test_sleep_returns_scheduled_time_after_waiting(self):
        target = datetime(2026, 10, 1, 7, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
        with patch("app.scheduling.datetime") as datetime_mock:
            datetime_mock.now.return_value = datetime(2026, 10, 1, 6, 59, tzinfo=ZoneInfo("Asia/Tokyo"))
            with patch("app.scheduling.asyncio.sleep", new=unittest.mock.AsyncMock()) as sleep_mock:
                result = asyncio.run(sleep_until_next_time(7, 0))

        self.assertEqual(result, target)
        sleep_mock.assert_awaited_once()

    def test_interval_loop_runs_job_then_waits_until_closed(self):
        events = []
        closed = False

        async def job():
            events.append("job")

        async def on_error(error):
            events.append(f"error:{error}")

        async def sleep(seconds):
            nonlocal closed
            events.append(f"sleep:{seconds}")
            closed = True

        def is_closed():
            return closed

        asyncio.run(
            __import__("app.scheduling", fromlist=["run_interval_loop"]).run_interval_loop(
                is_closed=is_closed,
                interval_seconds=30,
                job=job,
                on_error=on_error,
                sleep=sleep,
            )
        )

        self.assertEqual(events, ["job", "sleep:30"])

    def test_interval_loop_reports_job_error_before_waiting(self):
        events = []
        closed = False

        async def job():
            raise ValueError("failed")

        async def on_error(error):
            events.append(f"error:{error}")

        async def sleep(seconds):
            nonlocal closed
            events.append(f"sleep:{seconds}")
            closed = True

        asyncio.run(
        __import__("app.scheduling", fromlist=["run_interval_loop"]).run_interval_loop(
                is_closed=lambda: closed,
                interval_seconds=30,
                job=job,
                on_error=on_error,
                sleep=sleep,
            )
        )

        self.assertEqual(events, ["error:failed", "sleep:30"])

    def test_daily_loop_waits_for_ready_then_runs_job(self):
        events = []
        closed = False

        class Client:
            async def wait_until_ready(self):
                events.append("ready")

            def is_closed(self):
                return closed

        async def job(target):
            events.append(f"job:{target}")

        async def on_error(error):
            events.append(f"error:{error}")

        async def sleep_until(hour, minute):
            nonlocal closed
            events.append(f"sleep:{hour}:{minute}")
            closed = True
            return "target"

        asyncio.run(
        __import__("app.scheduling", fromlist=["run_daily_loop"]).run_daily_loop(
                client=Client(),
                hour=7,
                minute=0,
                job=job,
                on_error=on_error,
                sleep_until=sleep_until,
            )
        )

        self.assertEqual(events, ["ready", "sleep:7:0", "job:target"])

    def test_daily_loop_does_not_run_when_client_is_already_closed(self):
        events = []

        class Client:
            async def wait_until_ready(self):
                events.append("ready")

            def is_closed(self):
                return True

        async def job(target):
            events.append("job")

        asyncio.run(
        __import__("app.scheduling", fromlist=["run_daily_loop"]).run_daily_loop(
                client=Client(),
                hour=7,
                minute=0,
                job=job,
                on_error=lambda error: asyncio.sleep(0),
                sleep_until=lambda hour, minute: asyncio.sleep(0),
            )
        )

        self.assertEqual(events, ["ready"])


if __name__ == "__main__":
    unittest.main()
