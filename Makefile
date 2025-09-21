install:
	pipenv lock && pipenv sync

installdev:
	pipenv lock && pipenv sync --dev

clean:
	docker image prune -f && \
	docker system prune -a -f && \
	docker builder prune -a -f

docker:
	docker compose up -d database cache mailing api silpo-mock kfc-mock uklon-mock broker worker-default worker-high-priority

dockerdown:
	docker compose down
