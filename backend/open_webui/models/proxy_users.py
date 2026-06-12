"""Proxy user configuration and usage tracking models."""

from __future__ import annotations

import time
import uuid
from typing import Optional

from open_webui.internal.db import Base, get_async_db_context
from pydantic import BaseModel, ConfigDict
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Integer,
    String,
    Text,
    delete,
    func,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession


####################
# ProxyUserConfig DB Schema
####################


class ProxyUserConfig(Base):
    """Per-user proxy configuration: custom API key and token limits."""

    __tablename__ = 'proxy_user_config'

    user_id = Column(String, primary_key=True)
    api_key = Column(Text, nullable=True)  # NULL = use global default key
    is_active = Column(Boolean, default=True, nullable=False)

    # Token limits per time window (NULL = unlimited)
    hourly_token_limit = Column(BigInteger, nullable=True)
    three_hourly_token_limit = Column(BigInteger, nullable=True)
    daily_token_limit = Column(BigInteger, nullable=True)
    weekly_token_limit = Column(BigInteger, nullable=True)
    monthly_token_limit = Column(BigInteger, nullable=True)

    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


class ProxyUserConfigModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    api_key: Optional[str] = None
    is_active: bool = True

    hourly_token_limit: Optional[int] = None
    three_hourly_token_limit: Optional[int] = None
    daily_token_limit: Optional[int] = None
    weekly_token_limit: Optional[int] = None
    monthly_token_limit: Optional[int] = None

    created_at: Optional[int] = None
    updated_at: Optional[int] = None


class ProxyUserConfigForm(BaseModel):
    api_key: Optional[str] = None
    is_active: bool = True

    hourly_token_limit: Optional[int] = None
    three_hourly_token_limit: Optional[int] = None
    daily_token_limit: Optional[int] = None
    weekly_token_limit: Optional[int] = None
    monthly_token_limit: Optional[int] = None


####################
# ProxyUsageLog DB Schema
####################


class ProxyUsageLog(Base):
    """Records token usage and file counts for each AI request."""

    __tablename__ = 'proxy_usage_log'

    id = Column(String, primary_key=True)
    user_id = Column(String, index=True, nullable=False)
    model = Column(String, nullable=True)

    prompt_tokens = Column(BigInteger, default=0)
    completion_tokens = Column(BigInteger, default=0)
    total_tokens = Column(BigInteger, default=0)

    # Files sent to AI (images, attachments) in this request
    files_sent = Column(Integer, default=0)

    created_at = Column(BigInteger, index=True)


class ProxyUsageLogModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    model: Optional[str] = None

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    files_sent: int = 0

    created_at: int


####################
# ProxyUserConfigs data access
####################


class ProxyUserConfigsTable:
    async def get_config(self, user_id: str, db: AsyncSession | None = None) -> ProxyUserConfigModel | None:
        async with get_async_db_context(db) as session:
            result = await session.execute(
                select(ProxyUserConfig).where(ProxyUserConfig.user_id == user_id)
            )
            row = result.scalar_one_or_none()
            return ProxyUserConfigModel.model_validate(row) if row else None

    async def upsert_config(
        self,
        user_id: str,
        form: ProxyUserConfigForm,
        db: AsyncSession | None = None,
    ) -> ProxyUserConfigModel:
        async with get_async_db_context(db) as session:
            result = await session.execute(
                select(ProxyUserConfig).where(ProxyUserConfig.user_id == user_id)
            )
            row = result.scalar_one_or_none()
            now = int(time.time())
            if row:
                await session.execute(
                    update(ProxyUserConfig)
                    .where(ProxyUserConfig.user_id == user_id)
                    .values(
                        api_key=form.api_key,
                        is_active=form.is_active,
                        hourly_token_limit=form.hourly_token_limit,
                        three_hourly_token_limit=form.three_hourly_token_limit,
                        daily_token_limit=form.daily_token_limit,
                        weekly_token_limit=form.weekly_token_limit,
                        monthly_token_limit=form.monthly_token_limit,
                        updated_at=now,
                    )
                )
            else:
                session.add(
                    ProxyUserConfig(
                        user_id=user_id,
                        api_key=form.api_key,
                        is_active=form.is_active,
                        hourly_token_limit=form.hourly_token_limit,
                        three_hourly_token_limit=form.three_hourly_token_limit,
                        daily_token_limit=form.daily_token_limit,
                        weekly_token_limit=form.weekly_token_limit,
                        monthly_token_limit=form.monthly_token_limit,
                        created_at=now,
                        updated_at=now,
                    )
                )
            await session.commit()

        return await self.get_config(user_id)

    async def delete_config(self, user_id: str, db: AsyncSession | None = None) -> bool:
        async with get_async_db_context(db) as session:
            await session.execute(
                delete(ProxyUserConfig).where(ProxyUserConfig.user_id == user_id)
            )
            await session.commit()
        return True

    async def list_configs(self, db: AsyncSession | None = None) -> list[ProxyUserConfigModel]:
        async with get_async_db_context(db) as session:
            result = await session.execute(select(ProxyUserConfig))
            rows = result.scalars().all()
            return [ProxyUserConfigModel.model_validate(r) for r in rows]


####################
# ProxyUsageLogs data access
####################


class ProxyUsageLogsTable:
    async def create_log(
        self,
        user_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        files_sent: int = 0,
        db: AsyncSession | None = None,
    ) -> ProxyUsageLogModel:
        async with get_async_db_context(db) as session:
            entry = ProxyUsageLog(
                id=str(uuid.uuid4()),
                user_id=user_id,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                files_sent=files_sent,
                created_at=int(time.time()),
            )
            session.add(entry)
            await session.commit()
            await session.refresh(entry)
            return ProxyUsageLogModel.model_validate(entry)

    async def get_total_tokens_since(
        self,
        user_id: str,
        since: int,
        db: AsyncSession | None = None,
    ) -> int:
        """Sum total_tokens for a user since the given epoch timestamp."""
        async with get_async_db_context(db) as session:
            result = await session.execute(
                select(func.coalesce(func.sum(ProxyUsageLog.total_tokens), 0)).where(
                    ProxyUsageLog.user_id == user_id,
                    ProxyUsageLog.created_at >= since,
                )
            )
            return int(result.scalar())

    async def get_oldest_entry_since(
        self,
        user_id: str,
        since: int,
        db: AsyncSession | None = None,
    ) -> int | None:
        """Return created_at of the oldest log entry in the window, or None."""
        async with get_async_db_context(db) as session:
            result = await session.execute(
                select(func.min(ProxyUsageLog.created_at)).where(
                    ProxyUsageLog.user_id == user_id,
                    ProxyUsageLog.created_at >= since,
                )
            )
            return result.scalar()

    async def get_stats(
        self,
        user_id: str,
        since: int,
        db: AsyncSession | None = None,
    ) -> dict:
        """Aggregate usage stats for a user since the given timestamp."""
        async with get_async_db_context(db) as session:
            result = await session.execute(
                select(
                    func.count(ProxyUsageLog.id).label('request_count'),
                    func.coalesce(func.sum(ProxyUsageLog.prompt_tokens), 0).label('prompt_tokens'),
                    func.coalesce(func.sum(ProxyUsageLog.completion_tokens), 0).label('completion_tokens'),
                    func.coalesce(func.sum(ProxyUsageLog.total_tokens), 0).label('total_tokens'),
                    func.coalesce(func.sum(ProxyUsageLog.files_sent), 0).label('files_sent'),
                ).where(
                    ProxyUsageLog.user_id == user_id,
                    ProxyUsageLog.created_at >= since,
                )
            )
            row = result.one()
            return {
                'request_count': int(row.request_count),
                'prompt_tokens': int(row.prompt_tokens),
                'completion_tokens': int(row.completion_tokens),
                'total_tokens': int(row.total_tokens),
                'files_sent': int(row.files_sent),
            }

    async def get_logs(
        self,
        user_id: str,
        since: int | None = None,
        limit: int = 100,
        db: AsyncSession | None = None,
    ) -> list[ProxyUsageLogModel]:
        async with get_async_db_context(db) as session:
            stmt = select(ProxyUsageLog).where(ProxyUsageLog.user_id == user_id)
            if since is not None:
                stmt = stmt.where(ProxyUsageLog.created_at >= since)
            stmt = stmt.order_by(ProxyUsageLog.created_at.desc()).limit(limit)
            result = await session.execute(stmt)
            return [ProxyUsageLogModel.model_validate(r) for r in result.scalars().all()]

    async def get_all_stats(
        self,
        since: int,
        db: AsyncSession | None = None,
    ) -> list[dict]:
        """Aggregate usage stats for all users since the given timestamp."""
        async with get_async_db_context(db) as session:
            result = await session.execute(
                select(
                    ProxyUsageLog.user_id,
                    func.count(ProxyUsageLog.id).label('request_count'),
                    func.coalesce(func.sum(ProxyUsageLog.prompt_tokens), 0).label('prompt_tokens'),
                    func.coalesce(func.sum(ProxyUsageLog.completion_tokens), 0).label('completion_tokens'),
                    func.coalesce(func.sum(ProxyUsageLog.total_tokens), 0).label('total_tokens'),
                    func.coalesce(func.sum(ProxyUsageLog.files_sent), 0).label('files_sent'),
                )
                .where(ProxyUsageLog.created_at >= since)
                .group_by(ProxyUsageLog.user_id)
            )
            return [
                {
                    'user_id': row.user_id,
                    'request_count': int(row.request_count),
                    'prompt_tokens': int(row.prompt_tokens),
                    'completion_tokens': int(row.completion_tokens),
                    'total_tokens': int(row.total_tokens),
                    'files_sent': int(row.files_sent),
                }
                for row in result.all()
            ]


ProxyUserConfigs = ProxyUserConfigsTable()
ProxyUsageLogs = ProxyUsageLogsTable()


####################
# Limit checking
####################

_WINDOW_NAMES = {
    'hourly': 3600,
    'three_hourly': 10800,
    'daily': 86400,
    'weekly': 604800,
    'monthly': 2592000,
}

_WINDOW_LABELS = {
    'hourly': 'hourly',
    'three_hourly': '3-hourly',
    'daily': 'daily',
    'weekly': 'weekly',
    'monthly': 'monthly',
}


def _format_duration(seconds: int) -> str:
    if seconds < 60:
        return f'{seconds}s'
    minutes = seconds // 60
    if minutes < 60:
        return f'{minutes}m'
    hours = minutes // 60
    rem_min = minutes % 60
    if rem_min == 0:
        return f'{hours}h'
    return f'{hours}h {rem_min}m'


async def check_user_token_limits(
    user_id: str,
    config: ProxyUserConfigModel,
) -> tuple[bool, str]:
    """
    Check whether the user is within their configured token limits.

    Returns (allowed, error_message).  error_message is empty when allowed=True.
    """
    if not config.is_active:
        return True, ''

    now = int(time.time())

    checks = [
        ('hourly', config.hourly_token_limit),
        ('three_hourly', config.three_hourly_token_limit),
        ('daily', config.daily_token_limit),
        ('weekly', config.weekly_token_limit),
        ('monthly', config.monthly_token_limit),
    ]

    for window_key, limit in checks:
        if limit is None:
            continue
        duration = _WINDOW_NAMES[window_key]
        since = now - duration
        used = await ProxyUsageLogs.get_total_tokens_since(user_id, since)
        if used >= limit:
            # Find when the oldest entry in the window will expire
            oldest = await ProxyUsageLogs.get_oldest_entry_since(user_id, since)
            if oldest is not None:
                reset_in = (oldest + duration) - now
                reset_in = max(reset_in, 1)
            else:
                reset_in = duration
            label = _WINDOW_LABELS[window_key]
            return (
                False,
                f'Token limit exceeded ({used}/{limit} tokens in {label} window). '
                f'Available again in {_format_duration(reset_in)}.',
            )

    return True, ''
