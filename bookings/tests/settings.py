SECRET_KEY = "tests-secret-key"
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.admin",
    "bookings",
    "bookings.tests.testapp",
]

DATABASES = {
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
}

USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
ROOT_URLCONF = "bookings.tests.urls"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

BOOKINGS_SERVICE_MODEL = "testapp.Service"
BOOKINGS_PROVIDER_MODEL = "testapp.Provider"
BOOKINGS_ADDON_MODEL = "testapp.ServiceAddon"
BOOKINGS_TENANT_MODEL = None
BOOKINGS_SLOT_VALIDATION_MODE = "NONE"
BOOKINGS_SLOTS_AVAILABLE_FUNC = "bookings.tests.test_services.fake_slots_available"

MIGRATION_MODULES = {"testapp": None}
