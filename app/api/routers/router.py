from fastapi import APIRouter

from app.api.routers import auth, employee, invite, organization, statutory_rules
from app.core.config import get_settings

SETTINGS = get_settings()

router = APIRouter(prefix=SETTINGS.API_PREFIX)
router.include_router(auth.router, tags=["Auth"])
router.include_router(invite.router, tags=["Invite"])
router.include_router(employee.router, tags=["Employee"])
router.include_router(organization.router, tags=["Organization"])
router.include_router(statutory_rules.router, tags=["Statutory Rules"])
