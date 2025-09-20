install:
	pipenv lock && pipenv sync

installdev:
	pipenv lock && pipenv sync --dev

clean:
	docker image prune -f && \
	docker system prune -a -f && \
	docker builder prune -a -f

run:
	python manage.py runserver

docker:
	docker compose up -d database cache mailing api silpo-mock kfc-mock broker

dockerdown:
	docker compose down

worker_default:
	celery -A config worker -l INFO -Q default --concurrency=4

worker_high:
	celery -A config worker -l INFO -Q high_priority --concurrency=2
