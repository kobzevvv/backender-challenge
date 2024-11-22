from datetime import timedelta

import structlog
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from pydantic import BaseModel

from src.common.utils import to_snake_case
from src.logs.ch_client import ClickHouseClient, ClickHouseRow
from src.logs.models import OutboxLog

logger = structlog.get_logger(__name__)


class OutboxLogger:
    @classmethod
    def log(cls, data: list[BaseModel], batch_size: int = 500) -> None:
        """
        Сохраняет логи в базу данных для последующего экспорта в ClickHouse.
        """
        OutboxLog.objects.bulk_create(
            [
                OutboxLog(
                    event_type=to_snake_case(event.__class__.__name__),
                    event_date_time=timezone.now(),
                    environment=settings.ENVIRONMENT,
                    event_context=event.model_dump_json(),
                    metadata_version=settings.METADATA_VERSION,
                )
                for event in data
            ],
            batch_size=batch_size,
        )


class OutboxExporter:
    @classmethod
    def export(cls, batch_size: int | None = None) -> None:
        """
        Экспортирует не экспортированные ранее логи из базы данных в ClickHouse.
        Экспорт выполняется батчами.
        После экспорта помечает логи как экспортированные.
        """
        batch_size = batch_size or settings.CLICKHOUSE_BATCH_SIZE

        while True:
            with transaction.atomic():
                objs = (
                    OutboxLog.objects.filter(exported_at__isnull=True)
                    .select_for_update()
                    .order_by("id")[:batch_size]
                )
                if not objs:
                    logger.info("no data to export, exiting")
                    return

                data = cls._convert_data(objs)
                OutboxLog.objects.filter(id__in=[obj.id for obj in objs]).update(
                    exported_at=timezone.now(),
                )

                client: ClickHouseClient
                with ClickHouseClient.init() as client:
                    client.insert(data)

                logger.info("inserted data to clickhouse", count=len(data))

    @staticmethod
    def _convert_data(
        data: list[OutboxLog],
    ) -> list[ClickHouseRow]:
        return [
            ClickHouseRow(
                event_type=event.event_type,
                event_date_time=event.event_date_time,
                environment=event.environment,
                event_context=event.event_context,
                metadata_version=event.metadata_version,
            )
            for event in data
        ]

    @staticmethod
    def cleanup() -> None:
        """
        Удаляет логи, которые были экспортированы в прошлом, чтобы не захламлять базу данных.
        """
        bound = timezone.now() - timedelta(seconds=settings.CLICKHOUSE_CLEANUP_INTERVAL)
        count, _ = OutboxLog.objects.filter(exported_at__lt=bound).delete()
        logger.info("deleted exported outbox logs", count=count)
