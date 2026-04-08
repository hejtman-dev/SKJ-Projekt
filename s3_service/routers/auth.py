from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

try:
    from ..schemas import TokenRequest, TokenResponse, UserCreate, UserResponse
    from ..database import get_db
    from ..auth import authenticate_user, create_access_token, hash_password
    from ..models import Bucket, User
except ImportError:
    from schemas import TokenRequest, TokenResponse, UserCreate, UserResponse
    from database import get_db
    from auth import authenticate_user, create_access_token, hash_password
    from models import Bucket, User

router = APIRouter(prefix="/auth", tags=["auth"])


def _raise_validation_error(exc: ValidationError) -> None:
    raise RequestValidationError(exc.errors())


def parse_login_form(
    username: str = Form(...),
    password: str = Form(...),
) -> TokenRequest:
    try:
        return TokenRequest(username=username, password=password)
    except ValidationError as exc:
        _raise_validation_error(exc)


def parse_register_form(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
) -> UserCreate:
    try:
        return UserCreate(username=username, email=email, password=password)
    except ValidationError as exc:
        _raise_validation_error(exc)


@router.post("/token", response_model=TokenResponse)
async def login(
    credentials: TokenRequest = Depends(parse_login_form),
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate user and return JWT token."""
    user = authenticate_user(db, credentials.username, credentials.password)
    if not user:
        raise HTTPException(status_code=401, detail="Neplatné přihlašovací údaje")

    access_token = create_access_token(user_id=user.id)
    return TokenResponse(access_token=access_token, token_type="bearer")


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: UserCreate = Depends(parse_register_form),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Register a new user."""
    existing_user = db.query(User).filter(
        (User.username == payload.username) | (User.email == payload.email)
    ).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Uživatel s tímto jménem nebo emailem již existuje")

    new_user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    db.add(Bucket(user_id=new_user.id, name="default"))
    db.commit()

    return UserResponse.model_validate(new_user)
