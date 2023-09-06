"""
Django settings for mocaf project.

Generated by 'django-admin startproject' using Django 3.1.6.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os

import environ
from celery.schedules import crontab
from corsheaders.defaults import default_headers as default_cors_headers  # noqa
from django.utils.translation import gettext_lazy as _

from .sentry_handler import before_send_sentry_handler
from dotenv import load_dotenv

load_dotenv()


root = environ.Path(__file__) - 2  # two folders back

env = environ.Env(
    DEBUG=(bool, True), # changed to True for dev purposes normally False
    SECRET_KEY=(str, ''),
    ALLOWED_HOSTS=(list, ['*']),
    DATABASE_URL=(str, 'sqlite:///db.sqlite3'),
    CACHE_URL=(str, 'locmemcache://'),
    MEDIA_ROOT=(environ.Path(), root('media')),
    STATIC_ROOT=(environ.Path(), root('static')),
    MEDIA_URL=(str, '/media/'),
    STATIC_URL=(str, '/static/'),
    SENTRY_DSN=(str, ''),
    COOKIE_PREFIX=(str, 'mocaf'),
    SERVER_EMAIL=(str, ''),
    DEFAULT_FROM_EMAIL=(str, ''),
    CELERY_BROKER_URL=(str, 'redis://localhost:6379'),
    CELERY_RESULT_BACKEND=(str, 'redis://localhost:6379'),
    CUBEJS_URL=(str, 'http://localhost:4000'),
    GENIEM_NOTIFICATION_API_BASE=(str, ''),
    GENIEM_NOTIFICATION_API_TOKEN=(str, ''),
    GENIEM_PRIZE_API_BASE=(str, ''),
    GENIEM_PRIZE_API_TOKEN=(str, ''),
    INTERNAL_IPS=(list, []),
    PROMETHEUS_METRICS_AUTH_TOKEN=(str, None),
    PROMETHEUS_EXPORT_MIGRATIONS=(bool, False),
    POSTGRES_DB=(str, 'mocaf'),
    POSTGRES_PASSWORD=(str, 'abcdef'),
)
PROMETHEUS_EXPORT_MIGRATIONS = env('PROMETHEUS_EXPORT_MIGRATIONS')

BASE_DIR = root()
PROJECT_DIR = os.path.join(BASE_DIR, 'mocaf')

if os.path.exists(os.path.join(BASE_DIR, '.env')):
    environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')
INTERNAL_IPS = env.list('INTERNAL_IPS',
                        default=(['127.0.0.1'] if DEBUG else []))
DATABASES = {
    'default': env.db(),
}
DATABASES['default']['ATOMIC_REQUESTS'] = True
DATABASES['default']['ENGINE'] = 'django.contrib.gis.db.backends.postgis'

CACHES = {
    'default': env.cache(),
}

SECRET_KEY = env('SECRET_KEY')

TRANSITRT_IMPORTERS = {
    'tampere': {
        'agency_name': 'Nysse',
        'url': 'http://data.itsfactory.fi/siriaccess/vm/json',
        'type': 'siri-rt',
        'frequency': 3,
    },
    'rata': {
        'feed_publisher_name': 'Fintraffic',
        'frequency': 5,
        'type': 'rata',
    }
}

TRANSITRT_TASKS = {'transitrt-import-%s' % key: dict(
    task=f'transitrt.tasks.fetch_live_locations_{key}',
    schedule=val['frequency'],
    options=dict(expires=val['frequency'] - 1),
    args=(key,),
) for key, val in TRANSITRT_IMPORTERS.items()}

CELERY_BROKER_URL = env('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND')

CELERY_BEAT_SCHEDULE = {
    'ingest-received-data': {
        'task': 'trips_ingest.tasks.ingest_events',
        'schedule': 120,
        'options': {
            'expires': 30,
        }
    },
    'generate-new-trips': {
        'task': 'trips.tasks.generate_new_trips',
        'schedule': 240,
        'options': {
            'expires': 30,
        }
    },
    'award-prizes-and-send-notifications': {
        'task': 'notifications.tasks.award_prizes_and_send_notifications',
        'kwargs': {
            'min_active_days': 10,
        },
        'schedule': crontab(hour=6, minute=0, day_of_month=1),
        'options': {
            'expires': 2 * 24 * 60 * 60,  # 2 days
        }
    },
    'send-timed-notifications': {
        'task': 'notifications.tasks.send_notifications',
        'args': ('notifications.tasks.TimedNotificationTask',),
        'schedule': crontab(hour=7, minute=0),
        'options': {
            'expires': 18 * 60 * 60,  # 18 hours
        }
    },
    'send-health-summary-notifications': {
        'task': 'notifications.tasks.send_notifications',
        'args': ('notifications.tasks.HealthSummaryNotificationTask',),
        'schedule': crontab(hour=6, minute=0),
        'options': {
            'expires': 18 * 60 * 60,  # 18 hours
        }
    },
      'send-no-trips-notifications': {
        'task': 'notifications.tasks.send_notifications',
        'args': ('notifications.tasks.NoTripsNotificationTask',),
        'schedule': crontab(hour=10, minute=0),
        'options': {
            'expires': 2 * 24 * 60 * 60,  #  2 days
        }
    },
     'send-survey-notifications': {
        'task': 'notifications.tasks.send_notifications',
        'args': ('notifications.tasks.SurveyNotificationTask',),
        'schedule': crontab(hour=10, minute=0),
        'options': {
            'expires': 23 * 60 * 60,  #  2 days
        }
    },
     'send-survey-start-notifications': {
        'task': 'notifications.tasks.send_notifications',
        'args': ('notifications.tasks.SurveyStartNotificationTask',),
        'schedule': crontab(hour=10, minute=0),
        'options': {
            'expires':  23 * 60 * 60,  #  2 days
        }
    },
    # TODO: Update the following.
    # 'send-welcome-notifications': {
    #     'task': 'notifications.tasks.send_notifications',
    #     'args': ('notifications.tasks.WelcomeNotificationTask',),
    #     'schedule': crontab(hour=9, minute=0),
    #     'options': {
    #         'expires': 2 * 24 * 60 * 60,  # 2 days
    #     }
    # },
    # 'send-no-recent-trips-notifications': {
    #     'task': 'notifications.tasks.send_notifications',
    #     'args': ('notifications.tasks.NoRecentTripsNotificationTask',),
    #     'schedule': crontab(hour=10, minute=0),
    #     'options': {
    #         'expires': 2 * 24 * 60 * 60,  # 2 days
    #     }
    # },
    **TRANSITRT_TASKS,
}
CELERY_TASK_ROUTES = {
    'transitrt.tasks.*': {'queue': 'transitrt'},
    'trips.tasks.*': {'queue': 'trips'},
    'trips_ingest.tasks.*': {'queue': 'trips'},
    'notifications.tasks.*': {'queue': 'notifications'},
}

# Required for Celery exporter: https://github.com/OvalMoney/celery-exporter
# For configuration, see also another exporter: https://github.com/danihodovic/celery-exporter
CELERY_WORKER_SEND_TASK_EVENTS = True
# CELERY_TASK_SEND_SENT_EVENT = True  # required only for danihodovic/celery-exporter

# Application definition

INSTALLED_APPS = [
    'wagtail.contrib.forms',
    'wagtail.contrib.redirects',
    'wagtail.embeds',
    'wagtail.sites',
    'wagtail.users',
    'wagtail.snippets',
    'wagtail.documents',
    'wagtail.images',
    'wagtail.search',
    'wagtail.admin',
    'wagtail.core',
    'wagtail.contrib.modeladmin',

    'modeltrans',
    'modelcluster',
    'taggit',
    'graphene_django',
    'wagtail_localize',
    'wagtail_localize.locales',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.gis',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'django_extensions',
    'django_prometheus',

    'gtfs',
    'transitrt',
    'trips_ingest',
    'trips',
    'budget',
    'feedback',
    'pages',
    'notifications',
    'analytics',
    'poll',
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'django.middleware.gzip.GZipMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'wagtail.contrib.redirects.middleware.RedirectMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

ROOT_URLCONF = 'mocaf.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(PROJECT_DIR, 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'analytics.context_processors.sentry_dsn',
            ],
        },
    },
]

WSGI_APPLICATION = 'mocaf.wsgi.application'

# Password validation
# https://docs.djangoproject.com/en/3.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_HEADERS = list(default_cors_headers) + [
    'sentry-trace',
]

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    )
}

GRAPHENE = {
    'SCHEMA': 'mocaf.schema.schema',
    'MIDDLEWARE': [
        'mocaf.graphql_middleware.APITokenMiddleware',
        'mocaf.graphql_middleware.LocaleMiddleware',
    ],
}


# Internationalization
# https://docs.djangoproject.com/en/3.1/topics/i18n/

LANGUAGES = (
    ('fi', _('Finnish')),
    ('en', _('English')),
    ('sv', _('Swedish')),
)
WAGTAIL_CONTENT_LANGUAGES = LANGUAGES
MODELTRANS_AVAILABLE_LANGUAGES = [x[0] for x in LANGUAGES]
LANGUAGE_CODE = 'fi'
TIME_ZONE = 'Europe/Helsinki'
USE_I18N = True
USE_L10N = True
USE_TZ = True
LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale')
]

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

STATICFILES_DIRS = [
    # os.path.join(PROJECT_DIR, 'static'),
]

# ManifestStaticFilesStorage is recommended in production, to prevent outdated
# JavaScript / CSS assets being served from cache (e.g. after a Wagtail upgrade).
# See https://docs.djangoproject.com/en/3.1/ref/contrib/staticfiles/#manifeststaticfilesstorage
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

STATIC_URL = env('STATIC_URL')
MEDIA_URL = env('MEDIA_URL')
STATIC_ROOT = env('STATIC_ROOT')
MEDIA_ROOT = env('MEDIA_ROOT')

# Reverse proxy stuff
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

SENTRY_DSN = env('SENTRY_DSN')


# Wagtail settings

WAGTAIL_SITE_NAME = "mocaf"
WAGTAIL_ENABLE_UPDATE_CHECK = False
WAGTAIL_PASSWORD_MANAGEMENT_ENABLED = True
WAGTAIL_EMAIL_MANAGEMENT_ENABLED = False
WAGTAIL_PASSWORD_RESET_ENABLED = True
WAGTAIL_I18N_ENABLED = True

# Base URL to use when referring to full URLs within the Wagtail admin backend -
# e.g. in notification emails. Don't include '/admin' or a trailing slash
BASE_URL = 'http://example.com'

LOCAL_SRS = 3067  # ETRS-TM35-FIN

# How many hours a trip leg is editable by the user
ALLOWED_TRIP_UPDATE_HOURS = 3 * 24

# Notification engine
GENIEM_NOTIFICATION_API_BASE = env('GENIEM_NOTIFICATION_API_BASE')
GENIEM_NOTIFICATION_API_TOKEN = env('GENIEM_NOTIFICATION_API_TOKEN')

# Prizes
GENIEM_PRIZE_API_BASE = env('GENIEM_PRIZE_API_BASE')
GENIEM_PRIZE_API_TOKEN = env('GENIEM_PRIZE_API_TOKEN')

# CubeJS
CUBEJS_URL = env('CUBEJS_URL')

# local_settings.py can be used to override environment-specific settings
# like database and email that differ between development and production.
f = os.path.join(BASE_DIR, "local_settings.py")
if os.path.exists(f):
    import sys
    import types
    module_name = "%s.local_settings" % ROOT_URLCONF.split('.')[0]
    module = types.ModuleType(module_name)
    module.__file__ = f
    sys.modules[module_name] = module
    exec(open(f, "rb").read())

if not locals().get('SECRET_KEY', ''):
    secret_file = os.path.join(BASE_DIR, '.django_secret')
    try:
        SECRET_KEY = open(secret_file).read().strip()
    except IOError:
        import random
        system_random = random.SystemRandom()
        try:
            SECRET_KEY = ''.join([system_random.choice('abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)') for i in range(64)])  # noqa
            secret = open(secret_file, 'w')
            import os
            os.chmod(secret_file, 0o0600)
            secret.write(SECRET_KEY)
            secret.close()
        except IOError:
            Exception('Please create a %s file with random characters to generate your secret key!' % secret_file)


if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.utils.MAX_STRING_LENGTH = 2048
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        send_default_pii=True,
        traces_sample_rate=0.1,
        before_send=before_send_sentry_handler,
        integrations=[DjangoIntegration()],
        environment='development' if DEBUG else 'production'
    )

if 'DATABASES' in locals():
    if DATABASES['default']['ENGINE'] in ('django.db.backends.postgresql', 'django.contrib.gis.db.backends.postgis'):
        DATABASES['default']['CONN_MAX_AGE'] = 600

PROMETHEUS_METRICS_AUTH_TOKEN = env('PROMETHEUS_METRICS_AUTH_TOKEN')
#to run local db change values to match your db or can use local_settings with said values

DATABASES = {
    'default': {
        'ATOMIC_REQUESTS': True,
        'CONN_MAX_AGE': 600,
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'HOST': 'db',
        'NAME': env('POSTGRES_DB'),
        'PASSWORD': env('POSTGRES_PASSWORD'),
        'PORT': '',
        'USER': 'mocaf'
    }
}

#GDAL_LIBRARY_PATH=os.getenv('GDAL_LIB_PATH') #needed to run locally
#GEOS_LIBRARY_PATH=os.getenv('GEOS_LIB_PATH') #needed to run locally
