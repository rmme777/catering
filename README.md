##### RUN APPLICATION
- `make docker` - start application in docker
- `make run` - start application with debug

**Choose 'dev or prod' in compose.yml to start API**

##### OTHER MAKEFILE COMMANDS
- `make clean` - fully clean docker
- `make dockerdown` - docker compose down
- `make install` - install dependencies from pipfile
- `make installdev` - install development dependencies 

##### CONFIGURATION
You can create .enf file for configuring django setting module. By default .env file is created and added to compose.yml.
