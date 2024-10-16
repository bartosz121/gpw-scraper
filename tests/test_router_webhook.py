from typing import TypedDict

import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from gpw_scraper.models import webhook as webhook_models


class WebhookDbData(TypedDict):
    users: list[webhook_models.WebhookUser]
    endpoints: list[webhook_models.WebhookEndpoint]


@pytest.fixture
async def webhook_db_data(db_session: AsyncSession) -> WebhookDbData:
    users = [
        webhook_models.WebhookUser(name=f"user_{i}", api_key=f"api-key-{i}")
        for i in range(3)
    ]
    db_session.add_all(users)
    await db_session.flush()

    secret = "secret123"
    endpoints = [
        webhook_models.WebhookEndpoint(
            url="http://webhook-endpoint/", secret=secret, user_id=users[0].id
        ),
        webhook_models.WebhookEndpoint(
            url="http://webhook-endpoint/", secret=secret, user_id=users[1].id
        ),
    ]
    db_session.add_all(endpoints)

    await db_session.commit()

    return {"users": users, "endpoints": endpoints}


async def test_router_webhook_create_endpoint(webhook_db_data, api_client):
    data = {"url": "http://localhost/"}

    response = await api_client.post(
        "/api/v1/webhooks/endpoints",
        json=data,
        headers={"Authorization": f"Bearer {webhook_db_data['users'][0].api_key}"},
    )
    assert response.status_code == status.HTTP_201_CREATED

    response_data = response.json()
    assert response_data["url"] == data["url"]


async def test_router_webhook_create_endpoint_no_authorization_header(
    api_client,
):
    data = {"url": "http://localhost/"}

    response = await api_client.post(
        "/api/v1/webhooks/endpoints",
        json=data,
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize(
    "header",
    ["Bearer", "bearer", "bearer apsdkkasjd", "bearerasd123123", "", "9124u8rn"],
)
async def test_router_webhook_create_endpoint_wrong_authorization_header(
    header,
    webhook_db_data,
    api_client,
):
    data = {"url": "http://localhost/"}

    response = await api_client.post(
        "/api/v1/webhooks/endpoints",
        json=data,
        headers={"Authorization": header},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_router_webhook_create_endpoint_url_already_exists_in_db(
    webhook_db_data, api_client
):
    data = {"url": "http://webhook-endpoint/"}

    response = await api_client.post(
        "/api/v1/webhooks/endpoints",
        json=data,
        headers={"Authorization": f"Bearer {webhook_db_data['users'][0].api_key}"},
    )
    assert response.status_code == status.HTTP_409_CONFLICT

    response = await api_client.post(
        "/api/v1/webhooks/endpoints",
        json=data,
        headers={"Authorization": f"Bearer {webhook_db_data['users'][2].api_key}"},
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["url"] == data["url"]


async def test_router_webhook_delete_endpoint(webhook_db_data, api_client):
    response = await api_client.delete(
        f"/api/v1/webhooks/endpoints/{webhook_db_data['endpoints'][0].id}",
        headers={"Authorization": f"Bearer {webhook_db_data['users'][0].api_key}"},
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_router_webhook_delete_endpoint_no_authorization_header(
    api_client,
):
    response = await api_client.delete(
        "/api/v1/webhooks/endpoints/1",
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize(
    "header",
    ["Bearer", "bearer", "bearer apsdkkasjd", "bearerasd123123", "", "9124u8rn"],
)
async def test_router_webhook_delete_endpoint_wrong_authorization_header(
    header,
    webhook_db_data,
    api_client,
):
    response = await api_client.delete(
        "/api/v1/webhooks/endpoints/1",
        headers={"Authorization": header},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_router_webhook_delete_endpoint_403_if_not_found(
    webhook_db_data, api_client
):
    response = await api_client.delete(
        "/api/v1/webhooks/endpoints/111",
        headers={"Authorization": f"Bearer {webhook_db_data['users'][0].api_key}"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_router_webhook_delete_endpoint_403_if_not_owner(
    webhook_db_data, api_client
):
    response = await api_client.delete(
        f"/api/v1/webhooks/endpoints/{webhook_db_data['endpoints'][1].id}",
        headers={"Authorization": f"Bearer {webhook_db_data['users'][0].api_key}"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
