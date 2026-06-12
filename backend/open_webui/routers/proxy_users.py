"""Admin API for proxy user configuration and usage metrics."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request
from open_webui.models.proxy_users import (
    ProxyUserConfigForm,
    ProxyUserConfigModel,
    ProxyUsageLogs,
    ProxyUserConfigs,
)
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.models.users import UserModel

router = APIRouter()


# ---------------------------------------------------------------------------
# Admin: proxy user config CRUD
# ---------------------------------------------------------------------------


@router.get('/configs', response_model=list[ProxyUserConfigModel])
async def list_proxy_user_configs(user=Depends(get_admin_user)):
    """List all proxy user configs."""
    return await ProxyUserConfigs.list_configs()


@router.get('/configs/{user_id}', response_model=ProxyUserConfigModel)
async def get_proxy_user_config(user_id: str, user=Depends(get_admin_user)):
    config = await ProxyUserConfigs.get_config(user_id)
    if not config:
        raise HTTPException(status_code=404, detail='Proxy user config not found')
    return config


@router.post('/configs/{user_id}', response_model=ProxyUserConfigModel)
async def upsert_proxy_user_config(
    user_id: str,
    form: ProxyUserConfigForm,
    user=Depends(get_admin_user),
):
    """Create or update a proxy user config for the given user_id."""
    return await ProxyUserConfigs.upsert_config(user_id, form)


@router.delete('/configs/{user_id}')
async def delete_proxy_user_config(user_id: str, user=Depends(get_admin_user)):
    await ProxyUserConfigs.delete_config(user_id)
    return {'deleted': True}


# ---------------------------------------------------------------------------
# Admin: usage metrics
# ---------------------------------------------------------------------------


def _since_epoch(period: str) -> int:
    """Return epoch seconds for the start of the requested period."""
    now = int(time.time())
    periods = {
        'hour': 3600,
        '3hours': 10800,
        'day': 86400,
        'week': 604800,
        'month': 2592000,
    }
    return now - periods.get(period, 86400)


@router.get('/metrics')
async def get_all_metrics(
    period: str = 'day',
    user=Depends(get_admin_user),
):
    """
    Return aggregated usage stats for all users.

    period: hour | 3hours | day | week | month
    """
    since = _since_epoch(period)
    return await ProxyUsageLogs.get_all_stats(since)


@router.get('/metrics/{user_id}')
async def get_user_metrics(
    user_id: str,
    period: str = 'day',
    user=Depends(get_admin_user),
):
    """Return aggregated usage stats for a single user."""
    since = _since_epoch(period)
    return await ProxyUsageLogs.get_stats(user_id, since)


@router.get('/metrics/{user_id}/logs')
async def get_user_logs(
    user_id: str,
    period: str = 'day',
    limit: int = 100,
    user=Depends(get_admin_user),
):
    """Return individual usage log entries for a user."""
    since = _since_epoch(period)
    return await ProxyUsageLogs.get_logs(user_id, since=since, limit=limit)


# ---------------------------------------------------------------------------
# Self-service: current user's own stats
# ---------------------------------------------------------------------------


@router.get('/me/metrics')
async def get_my_metrics(
    period: str = 'day',
    user: UserModel = Depends(get_verified_user),
):
    """Return the current user's usage stats."""
    since = _since_epoch(period)
    return await ProxyUsageLogs.get_stats(user.id, since)
