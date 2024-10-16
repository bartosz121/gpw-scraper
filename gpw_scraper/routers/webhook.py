import secrets
from typing import Annotated

from fastapi import Depends, status
from fastapi.exceptions import HTTPException
from fastapi.responses import Response
from fastapi.routing import APIRouter
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from gpw_scraper.dependencies import WebhookEndpointService, WebhookUserService
from gpw_scraper.models import webhook as webhook_models
from gpw_scraper.schemas import webhook as webhook_schemas

security = HTTPBearer(auto_error=False)


async def get_webhook_user(
    auth: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    service: WebhookUserService,
) -> webhook_models.WebhookUser:
    if auth is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await service.get_one_or_none(api_key=auth.credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


WebhookUser = Annotated[webhook_models.WebhookUser, Depends(get_webhook_user)]


router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post(
    "/endpoints",
    status_code=status.HTTP_201_CREATED,
    response_model=webhook_schemas.WebhhookEndpointCreateResponse,
    responses={"401": {"description": "Unauthorized, expected bearer header"}},
)
async def create_webhook_endpoint(
    data: webhook_schemas.WebookEndpointCreateSchema,
    user: WebhookUser,
    webhook_endpoint_service: WebhookEndpointService,
):
    url_already_exists_for_user = await webhook_endpoint_service.exists(
        user_id=user.id, url=data.url.unicode_string()
    )
    if url_already_exists_for_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"msg": "Webhook endpoint with this url already exists"},
        )

    secret = secrets.token_urlsafe(32)
    webhook_endpoint = webhook_models.WebhookEndpoint(
        user_id=user.id, url=data.url.unicode_string(), secret=secret
    )
    created = await webhook_endpoint_service.create(webhook_endpoint)

    return {"id": created.id, "url": created.url, "secret": secret}


@router.delete(
    "/endpoints/{endpoint_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        "401": {
            "description": "Unauthorized, expected bearer header",
            "403": {"description": "Forbidden"},
        }
    },
)
async def delete_webook_endpoint(
    endpoint_id: int,
    user: WebhookUser,
    webhook_endpoint_service: WebhookEndpointService,
):
    endpoint = await webhook_endpoint_service.get_one_or_none(id=endpoint_id)
    if endpoint is None or endpoint.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    await webhook_endpoint_service.delete(endpoint_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
