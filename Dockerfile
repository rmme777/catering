FROM python:3.13-slim as base


ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1


RUN apt-get update -y \
    # dependencies for building Python packages && clean apt packages
    && apt-get install -y build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working dir
WORKDIR /app

# Update Project Dependencies
RUN pip install --upgrade pip setuptools pipenv


# Install deps
COPY Pipfile Pipfile.lock ./


# Copy project files
COPY . .



# ==============================================
# MULTI-STAGE BUILDS FOR ENVIRONMENTS
# ==============================================

FROM base AS dev

ENV C_FORCE_ROOT="true"
ENV DJANGO_DEBUG=1

RUN pipenv sync --dev --system

EXPOSE 8000/tcp
ENTRYPOINT [ "python" ]
CMD [ "manage.py", "runserver", "0.0.0.0:8000" ]



FROM base AS prod

ENV DJANGO_DEBUG=
ENV GUNICORN_CMD_ARGS="--bind 0.0.0.0:8000 --reload"

RUN pipenv install --deploy --system

EXPOSE 8000/tcp
ENTRYPOINT [ "python" ]
CMD [ "-m", "gunicorn", "config.wsgi:application"]