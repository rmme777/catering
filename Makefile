install:
	pipenv lock && pipenv sync

installdev:
	pipenv lock && pipenv sync --dev

build:
	docker build -t catering-api .

clean:
	docker image prune -f && \
	docker system prune -a -f && \
	docker builder prune -a -f


run:
	python manage.py runserver

docker:
	docker compose up -d database cache mailing api

dockerdown:
	docker compose down