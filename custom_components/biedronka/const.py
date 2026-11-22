DOMAIN = "biedronka"
AUTH_URL = "https://konto.biedronka.pl/realms/loyalty/protocol/openid-connect/auth"
TOKEN_URL = "https://konto.biedronka.pl/realms/loyalty/protocol/openid-connect/token"
API_URL = "https://api.prod.biedronka.cloud/api/v1/"
CLIENT_ID = "cma20"
REDIRECT_URI = "app://cma20.biedronka.pl"
SCOPE = "email profile forcom-loyalty"  # jak w aplikacji przy odświeżaniu tokenu
USER_AGENT = "okhttp/4.12.0"

CONF_REFRESH_TOKEN = "refresh_token"
CONF_SCAN_MINUTES = "scan_minutes"
DEFAULT_SCAN_MINUTES = 60
MIN_SCAN_MINUTES = 30

EVENT_RECEIPT = "biedronka_paragon"
EVENT_ACTUAL = "biedronka_actual"
CONF_SPLIT = "split_in_actual"
KEEP_RECEIPTS = 400
