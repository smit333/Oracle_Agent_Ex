import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


load_dotenv()


@dataclass
class HCMConfig:
    base_url: str
    auth_method: str  # "basic" or "oauth"
    username: Optional[str] = None
    password: Optional[str] = None
    oauth_token: Optional[str] = None


@dataclass
class AppConfig:
    google_api_key: str
    hcm: HCMConfig
    port: int = 8000


def load_config() -> AppConfig:
    google_api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    base_url = os.getenv("HCM_BASE_URL", "").rstrip("/")
    auth_method = os.getenv("HCM_AUTH_METHOD", "basic").strip().lower()
    username = os.getenv("HCM_USERNAME", "").strip() or None
    password = os.getenv("HCM_PASSWORD", "").strip() or None
    oauth_token = os.getenv("HCM_OAUTH_TOKEN", "").strip() or None
    port_str = os.getenv("PORT", "8000").strip()
    try:
        port = int(port_str)
    except ValueError:
        port = 8000

    hcm_config = HCMConfig(
        base_url=base_url,
        auth_method=auth_method,
        username=username,
        password=password,
        oauth_token=oauth_token,
    )
    return AppConfig(google_api_key=google_api_key, hcm=hcm_config, port=port)

