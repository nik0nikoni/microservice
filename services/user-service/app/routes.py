import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .deps import current_user
from .models import Profile
from .schemas import ProfileOut, ProfileUpdate

logger = logging.getLogger("user-service")
router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=ProfileOut)
def get_my_profile(user: dict = Depends(current_user), db: Session = Depends(get_db)):
    profile = db.get(Profile, user["id"])
    if not profile:
        raise HTTPException(404, "Profile not set")
    return profile


@router.put("/me", response_model=ProfileOut)
def upsert_my_profile(
    data: ProfileUpdate,
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
):
    profile = db.get(Profile, user["id"])
    if profile:
        profile.display_name = data.display_name
        profile.bio = data.bio
    else:
        profile = Profile(
            user_id=user["id"],
            email=user["email"],
            display_name=data.display_name,
            bio=data.bio,
        )
        db.add(profile)
    db.commit()
    db.refresh(profile)
    logger.info("Profile saved: user_id=%s", profile.user_id)
    return profile


# маршрут /me объявлен выше, иначе "me" попало бы в {user_id}
@router.get("/{user_id}", response_model=ProfileOut)
def get_profile(
    user_id: int,
    _: dict = Depends(current_user),
    db: Session = Depends(get_db),
):
    profile = db.get(Profile, user_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    return profile