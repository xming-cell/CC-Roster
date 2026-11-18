"""021 新手引导 API。"""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends

from app.adapters.registry import build_registry
from app.core.config import settings
from app.core.paths import resolve_data_dir
from app.repositories.chat import ChatRepository
from app.repositories.onboarding import OnboardingRepository
from app.repositories.profiles import ProfileRepository
from app.repositories.secrets import build_secret_store
from app.schemas.onboarding import OnboardingUpdate, OnboardingView
from app.services.onboarding_service import OnboardingService

router = APIRouter(tags=["onboarding"])


def get_onboarding_service() -> OnboardingService:
    data_dir = Path(resolve_data_dir())
    return OnboardingService(
        OnboardingRepository(data_dir),
        build_registry(),
        ProfileRepository(data_dir),
        build_secret_store(data_dir, mode=settings.secret_backend),
        ChatRepository(data_dir),
    )


OnboardingServiceDep = Annotated[OnboardingService, Depends(get_onboarding_service)]


@router.get("/api/onboarding", response_model=OnboardingView)
def get_onboarding(service: OnboardingServiceDep) -> OnboardingView:
    return service.get()


@router.put("/api/onboarding", response_model=OnboardingView)
def update_onboarding(payload: OnboardingUpdate, service: OnboardingServiceDep) -> OnboardingView:
    return service.update(payload)


@router.post("/api/onboarding/install/check", response_model=OnboardingView)
def check_install(payload: OnboardingUpdate, service: OnboardingServiceDep) -> OnboardingView:
    return service.check_install(payload)


@router.post("/api/onboarding/credentials/check", response_model=OnboardingView)
def check_credentials(payload: OnboardingUpdate, service: OnboardingServiceDep) -> OnboardingView:
    return service.check_credentials(payload)


@router.post("/api/onboarding/first-message/check", response_model=OnboardingView)
def check_first_message(payload: OnboardingUpdate, service: OnboardingServiceDep) -> OnboardingView:
    return service.check_first_message(payload)


@router.post("/api/onboarding/reset", response_model=OnboardingView)
def reset_onboarding(service: OnboardingServiceDep) -> OnboardingView:
    return service.update(OnboardingUpdate(reset=True))
