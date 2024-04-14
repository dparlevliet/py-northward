import os
import sys
import re
import time
import boto3
import logging
import argparse
import importlib.util


log_format = '%(levelname)s:%(name)s:%(funcName)s: %(message)s'
logging.basicConfig(level=logging.DEBUG, format=log_format)
logging.getLogger('botocore').setLevel(logging.CRITICAL + 1)
logging.getLogger('boto3').setLevel(logging.CRITICAL + 1)
logging.getLogger('urllib3').setLevel(logging.CRITICAL + 1)


class DynamoDBStorageEngine:
    """
        A storage engine that uses DynamoDB to store the state of the migrations.
    """

    _table_exists = None

    def __init__(self, table_name, endpoint_url=None):
        self.table_name = table_name
        self.endpoint_url = endpoint_url

    def _get_table(self):
        dynamodb = boto3.resource('dynamodb', endpoint_url=self.endpoint_url)
        # Make table if non-existant
        if not self._table_exists:
            table_names = [table.name for table in dynamodb.tables.all()]
            if self.table_name not in table_names:
                logging.debug(f"Creating table {self.table_name}")
                table = dynamodb.create_table(
                    TableName=self.table_name,
                    KeySchema=[{'AttributeName': 'filename', 'KeyType': 'HASH'}],
                    AttributeDefinitions=[{'AttributeName': 'filename', 'AttributeType': 'S'}],
                    ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
                )

                logging.debug(f"Waiting for table {self.table_name} to be created")
                table.wait_until_exists()

                logging.debug(f"Table {self.table_name} created")

        self._table_exists = True
        table = dynamodb.Table(self.table_name)
        return table

    def has_run(self, filename):
        table = self._get_table()
        logging.info(f"Checking if {filename} has run")
        response = table.get_item(Key={'filename': filename})

        return 'Item' in response

    def get_last_n(self, n):
        table = self._get_table()
        response = table.scan()
        items = sorted(response.get('Items', []), reverse=True, key=lambda x: x['filename'])
        return [ item['filename'] for item in items[-n:] ]

    def store(self, filename):
        table = self._get_table()
        logging.debug(f"Storing {filename}")
        table.put_item(Item={'filename': filename})

    def delete(self, filename):
        table = self._get_table()
        logging.debug(f"Deleting {filename}")
        table.delete_item(Key={'filename': filename})


class MemoryStorageEngine:
    """
        A simple in-memory storage engine. Useful for testing, but has no persistence.
    """

    data = {}

    def __init__(self, table_name):
        self.table_name = table_name
        self.data = {}

    def has_run(self, filename):
        return filename in self.data

    def store(self, filename):
        logging.debug(f"Storing {filename}")
        self.data[filename] = True

    def delete(self, filename):
        logging.debug(f"Deleting {filename}")
        del self.data[filename]


class MigratorHelpers:

    def _migrate_up(self, filename):
        """
            Load and run a single migration script.
        """

        script_path = os.path.join(self.directory, filename)
        logging.debug(f'Migrating {script_path}')

        script = self._load_script(script_path)
        logging.debug(f'Returned {script}')
        logging.debug(f'Running {script.filename}')

        self.up(script)

    def _load_script(self, path):
        """
            Dynamically load a migration script given its file path. The name of the module
            is derived from the basename of the path to ensure uniqueness and readability.
        """

        logging.debug(f"Loading migration script from path: {path}")

        if not os.path.exists(path):
            raise FileNotFoundError(f"Migration script not found: {path}")

        # Extract a unique module name from the file path
        module_name = os.path.splitext(os.path.basename(path))[0].replace('-', '_').replace(' ', '_')
        logging.debug(f"Module name: {module_name}")

        # build the module path from the directory provided as the base via self.directory.
        # eg/ if given the module to load is at /path/to/app_with_modules/module1/migrations/20240410093757_migration.py
        # the module path would be module1/migrations/20240410093757_migration
        dependency_path = os.path.relpath(path, self.directory).replace('.py', '')
        logging.debug(f"Dependency path: {dependency_path}")

        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            logging.debug(f"Loading module: {module_name}")
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.filename = path.replace('.py', '').replace(self.directory, '').strip('/')
                module.dependency_path = dependency_path
                logging.debug(f"Loaded module: {module_name}")

                return module

            raise Exception(f"Could not read module from path: {path}")
        except Exception as e:
            raise e

    def _find_all_migration_files(self):
        """
            Find and return a list of migration files within the directory.
        """

        migration_files = [os.path.join(self.directory, f) for f in os.listdir(self.directory) if self._is_migration_file(f)]

        if not migration_files:
            if os.path.exists(os.path.join(self.directory, 'migrations')):
                # Assume we need to look for migrations within a migrations folder
                self.directory = os.path.join(self.directory, 'migrations')
                migration_files = [os.path.join(self.directory, f) for f in os.listdir(self.directory) if self._is_migration_file(f)]
            else:
                # Assume we need to look for migrations within modules
                modules = self._find_modules_with_migrations()
                for module_path in modules:
                    migrations_path = os.path.join(module_path, 'migrations')
                    migration_files += [os.path.join(migrations_path, f) for f in os.listdir(migrations_path) if self._is_migration_file(f)]

        # Check if there are any duplicate migration file names. We need all names to be unique.
        migration_names = {}
        migration_timestamps = {}
        for f in migration_files:
            name = os.path.basename(f).replace('.py', '')
            if name in migration_names:
                raise ValueError(f"Duplicate migration file name used: {f}")

            # check if the timestamp is unique
            timestamp = name.split('_')[0]
            if timestamp in migration_timestamps:
                raise ValueError(f"Duplicate migration timestamp used: {f}")

            migration_timestamps[timestamp] = True
            migration_names[name] = True

        return migration_files

    def _resolve_dependency_path(self, dependency):
        """
            Resolve the full path of a dependency script, assuming a format of
            '<modulename>/migrations/<migration_name>.py'. This function translates
            the module and migration name into a path relative to the project's base directory.
        """

        # Split the dependency string on '/' to separate out the module name and migration name
        parts = dependency.split('/')
        if len(parts) == 3 and parts[1] == "migrations":
            # Construct the path by joining the directory with the module name and the migration file name
            module_name, migrations_folder, migration_name = parts
            return os.path.join(self.directory, module_name, migrations_folder, f"{migration_name}.py")

        return os.path.join(self.directory, f"{dependency}.py")

    def _is_migration_file(self, filename):
        """
            Check if a filename matches the expected migration file pattern.
        """

        return re.match(r'\d{14}_.*\.py$', filename) is not None

    def _find_modules_with_migrations(self):
        """
            Find and return a list of paths to modules that contain a migrations folder.
        """

        modules = []
        for item in os.listdir(self.directory):
            module_path = os.path.join(self.directory, item)
            if os.path.isdir(module_path) and os.path.exists(os.path.join(module_path, 'migrations')):
                modules.append(module_path)

        return modules


class Migrator(MigratorHelpers):
    """
        A migration file looks like this:

            ```
            dependencies = [
                '<module>/migrations/20210101000000_create_roles_table',
                '20210101000000_create_permissions_table'
            ]

            def up():
                pass

            def down():
                pass
            ```
    """

    def __init__(self, directory, storage_engine, dry_run=False, migrate_dependencies=True):
        self.directory = directory
        self.storage_engine = storage_engine
        self.dry_run = dry_run
        self.migrate_dependencies = migrate_dependencies

    def up(self, script):
        """
            Run the migration script's up() method if its dependencies are satisfied.
        """

        if self.storage_engine.has_run(script.filename):
            logging.debug(f'{script.filename} has already been run')
            return

        # Handle script dependencies
        if hasattr(script, 'dependencies'):
            for dependency in script.dependencies:
                dependency_path = self._resolve_dependency_path(dependency)
                dependency_script = self._load_script(dependency_path)
                if not self.storage_engine.has_run(dependency_script.dependency_path):
                    if not self.migrate_dependencies:
                        logging.error(f'{script.filename} has not been run because {dependency_script.dependency_path} has not been run')
                        return
                    else:
                        dependency_script = self._load_script(dependency_path)
                        self.up(dependency_script)

        if not self.dry_run:
            logging.info(f'Running up() on {script.filename}')
            script.up()
            self.storage_engine.store(script.dependency_path)
        else:
            logging.debug(f'Would run {script.filename}')

    def down(self, script):
        """
            Run the migration script's down() method and remove it from the storage engine.
        """

        if not self.storage_engine.has_run(script.filename):
            logging.debug(f'{script.filename} has not been run')
            return

        if not self.dry_run:
            logging.info(f'Running down() on {script.filename}')
            script.down()
            self.storage_engine.delete(script.dependency_path)
        else:
            logging.debug(f'Would rollback {script.filename}')

    def migrate(self):
        """
            Dynamically determine if it should scan for migration files directly within the
            given directory or look for migrations folders within modules.
        """

        migration_files = self._find_all_migration_files()
        for full_path in sorted(migration_files):
            self._migrate_up(full_path)

    def rollback(self, n):
        """
            Rollback the last n migrations.
        """

        migration_files = self._find_all_migration_files()
        migrations_map = {os.path.basename(f).replace('.py', ''): f for f in migration_files}
        migration_files = self.storage_engine.get_last_n(n)

        count = 0
        for file in migration_files:
            file = os.path.basename(file).replace('.py', '')
            script = self._load_script(migrations_map[file])
            self.down(script)

            count += 1
            if count == n:
                break

    def status(self):
        """
            Print the status of the migrations.
        """

        files = sorted(os.listdir(self.directory))

        for file in files:
            if file.endswith('.py'):
                script = self._load_script(os.path.join(self.directory, file))
                if self.storage_engine.has_run(script.filename):
                    print(f'{script.filename} has been run')
                else:
                    print(f'{script.filename} has not been run')

    def make_empty(self):
        """
            Create an empty migration file.
        """

        filename = time.strftime('%Y%m%d%H%M%S') + '_migration.py'

        # get the filename of the previous file to add it as a dependency
        files = sorted(os.listdir(self.directory), reverse=True)

        dependency_filename = f"'{files[0].replace('.py', '')}'" if files else ''
        with open(os.path.join(self.directory, filename), 'w') as f:
            f.write(f"""
dependencies = [
    # List of dependencies
    {dependency_filename}
]

def up():
    # Write the migration code here
    pass

def down():
    # Write the rollback code here
    pass
            """.strip())


def main():
    parser = argparse.ArgumentParser(description='Migration script')
    parser.add_argument('--engine', default='dynamodb', help='Storage engine')
    parser.add_argument('--dynamodb-endpoint-url', default=None, help='DynamoDB endpoint URL')
    parser.add_argument('--table', default='migrations', help='Table name')
    parser.add_argument('--directory', default='./migrations', help='Migration directory')
    parser.add_argument('--file', default=None, help='Migration file to run. Takes precidence over directory.')
    parser.add_argument('--dry-run', action='store_true', help='Dry run')
    parser.add_argument('--migrate-dependencies', action='store_true', help='Auto-migrate dependencies')
    parser.add_argument('command', choices=['up', 'down', 'rollback', 'status', 'make'], help='Command')
    parser.add_argument('n', type=int, nargs='?', default=0, help='Number of migrations to rollback')

    args = parser.parse_args()

    if args.engine == 'dynamodb':
        storage_engine = DynamoDBStorageEngine(args.table, endpoint_url=args.dynamodb_endpoint_url)
    elif args.engine == 'memory':
        storage_engine = MemoryStorageEngine(args.table)
    else:
        print('Invalid engine')
        sys.exit(1)

    if args.command == 'rollback' and args.n < 1:
        print('Invalid number of migrations to rollback')
        sys.exit(1)

    # determine the full directory path
    args.directory = os.path.abspath(args.directory)

    migrator = Migrator(
        args.directory,
        storage_engine,
        dry_run=args.dry_run,
        migrate_dependencies=args.migrate_dependencies
    )

    if args.command == 'up':
        if args.file:
            directory = os.path.dirname(args.file)
            migrator.directory = directory
            migrator.migrate_script(args.file)
        else:
            migrator.migrate()
    elif args.command == 'rollback' or args.command == 'down':
        migrator.rollback(args.n)
    elif args.command == 'status':
        migrator.status()
    elif args.command == 'make':
        migrator.make_empty()
    else:
        print('Invalid command')


if __name__ == '__main__':
    main()