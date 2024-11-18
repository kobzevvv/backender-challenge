import datetime as dt
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, Protocol

import clickhouse_connect
import structlog
from clickhouse_connect.driver.exceptions import DatabaseError
from django.conf import settings

from core.base_model import Model
from events.publisher import PublishedEvent

logger = structlog.get_logger(__name__)

EVENT_LOG_COLUMNS = [
    'event_type',
    'event_date_time',
    'environment',
    'event_context',
]


class EventLogClientProtocol(Protocol):
    """Base event log protocol for any future Clickhouse replacing"""

    @classmethod
    @contextmanager
    def init(cls) -> Generator['EventLogClientProtocol']:
        raise NotImplementedError()

    def insert(self, data: Any) -> None:
        raise NotImplementedError()

    def query(self, query: str) -> Any:
        raise NotImplementedError()


class EventLogClient(EventLogClientProtocol):
    def __init__(self, client: clickhouse_connect.driver.Client) -> None:
        self._client = client

    @classmethod
    @contextmanager
    def init(cls) -> Generator['EventLogClient']:
        client = clickhouse_connect.get_client(
            host=settings.CLICKHOUSE_HOST,
            port=settings.CLICKHOUSE_PORT,
            user=settings.CLICKHOUSE_USER,
            password=settings.CLICKHOUSE_PASSWORD,
            query_retries=2,
            connect_timeout=30,
            send_receive_timeout=10,
        )
        try:
            yield cls(client)
        except Exception as e:
            logger.error('error while executing clickhouse query', error=str(e))
        finally:
            client.close()

    def insert(
        self,
        data: list[PublishedEvent],
    ) -> None:
        try:
            self._client.insert(
                data=self._convert_data(data),
                column_names=EVENT_LOG_COLUMNS,
                database=settings.CLICKHOUSE_SCHEMA,
                table=settings.CLICKHOUSE_EVENT_LOG_TABLE_NAME,
            )
        except DatabaseError as e:
            logger.error('unable to insert data to clickhouse', error=str(e))
            raise

    def query(self, query: str) -> Any:  # noqa: ANN401
        logger.debug('executing clickhouse query', query=query)

        try:
            return self._client.query(query).result_rows
        except DatabaseError as e:
            logger.error('failed to execute clickhouse query', error=str(e))
            return

    def _convert_data(self, data: list[PublishedEvent]) -> list[tuple[str, dt.datetime, str, str]]:
            return [
                (
                    event.event_type,
                    event.event_date_time,
                    event.environment,
                    event.event_context,
                )
                for event in data
            ]
