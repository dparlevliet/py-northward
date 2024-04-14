Introduction
============
Welcome to PyNorthward, the versatile and straightforward migration tool designed for any Python project. PyNorthward is built to be unopinionated and adaptable, making it ideal for handling database schema changes across various frameworks and environments. Whether you are setting up a new project or looking to streamline existing database operations, PyNorthward provides a clear and easy path for your database evolution.


Supported directory structures
==============================
See the `examples/` folder for more detailed examples of structures and usages

### example 1
```
app/
| - module1
|   - migrations
|     - 20240410093757_migration.py
| - module 2
|   - migrations
|     - 20240410093809_migration.py
```

### example 2
```
app/
| - migrations
|   - 20240410093757_migration.py
|   - 20240410093809_migration.py
```


Anatomy of a migration file
===========================
```python
dependencies = [
    # List of dependency file names (without .py)
]

def up():
    # do something here, anything you want
    pass


def down():
    # roll back the thing you did
    pass

# don't put any run logic outside of a function, this is an imported module
```


Migration file name formatting
==============================
Migration files must follow the format of `time.strftime('%Y%m%d%H%M%S') + '_<anything>.py'`


Usage examples
==============
Northware is intended to run from anywhere. It can be a stand-along global command which you just point to a directory of supported
migration files.

### Example 1: Running migrate.py with default arguments
```bash
python3 migrate.py up
```

### Example 2: Running migrate.py with custom arguments
```bash
python3 migrate.py --engine dynamodb --table migrations_for_app_with_modules --directory ../examples/app_with_modules up
python3 migrate.py --engine dynamodb --table migrations_for_basic_app --directory ../examples/basic_app up
python3 migrate.py --engine dynamodb --table migrations_for_migrations_directory --directory ../examples/migrations_directory up
```

### Example 3: Running migrate.py with dry run option
```bash
python3 migrate.py --dry-run up
```

### Example 4: Running migrate.py with rollback command and specifying the number of migrations to rollback
```bash
python3 migrate.py rollback 2
```

### Example 5: Running migrate.py with make command to create a new migration file
```bash
python3 migrate.py make
```


Migration memory engines
========================
Currently supported
* DynamoDB
* In-memory (for testing purposes only, not intended for production)


Migration CLI arguments
=======================
| Parameter                   | Default            | Description                                                                                        |
|-----------------------------|--------------------|----------------------------------------------------------------------------------------------------|
| `--engine`                  | `dynamodb`         | Storage engine to use.                                                                             |
| `--dynamodb-endpoint-url`   | `None`             | DynamoDB endpoint URL. This is required if connecting to a custom DynamoDB instance.               |
| `--table`                   | `migrations`       | Name of the table to manage migrations.                                                            |
| `--directory`               | `./migrations`     | Directory where migration files are stored.                                                        |
| `--file`                    | `None`             | Specific migration file to run. Takes precedence over the directory.                               |
| `--dry-run`                 | `False` (flag)     | Perform a dry run (simulate the migration without making any changes).                             |
| `--migrate-dependencies`    | `False` (flag)     | Automatically migrate dependencies.                                                                |
| `command`                   | (required choice)  | Command to execute. Choices are `up`, `down`, `rollback`, `status`, `make`.                        |
| `n`                         | `0`                | Number of migrations to rollback or apply. Only applicable for `rollback` or `down` commands.     |


Dev testing with docker
=======================
```bash
docker-compose run migrate python3 migrate.py
```

Running pytests in docker
=========================
```bash
docker-compose run migrate pytest /src/tests/
```

Running examples
===============
```bash
docker-compose run migrate python3 migrate.py --engine dynamodb --dynamodb-endpoint-url=http://dynamodb:8000 --table migrations_for_app_with_modules --directory /examples/app_with_modules up
docker-compose run migrate python3 migrate.py --engine dynamodb --dynamodb-endpoint-url=http://dynamodb:8000 --table migrations_for_basic_app --directory /examples/basic_app up
docker-compose run migrate python3 migrate.py --engine dynamodb --dynamodb-endpoint-url=http://dynamodb:8000 --table migrations_for_migrations_directory --directory /examples/migrations_directory up
```