import os
import sys
import pytest
import logging
import boto3
from io import StringIO
from pathlib import Path
from moto import mock_aws
from migrate import DynamoDBStorageEngine, Migrator

logging.basicConfig(level=logging.DEBUG)


@pytest.fixture(scope="function")
def aws_credentials():
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'


@pytest.fixture(scope="function")
def dynamodb(aws_credentials):
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        table = dynamodb.create_table(
            TableName='test_migrations',
            KeySchema=[{'AttributeName': 'filename', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'filename', 'AttributeType': 'S'}],
            ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
        )
        table.meta.client.get_waiter('table_exists').wait(TableName='test_migrations')
        yield dynamodb
        dynamodb.Table('test_migrations').delete()


@pytest.fixture(params=['app_with_modules', 'basic_app', 'migrations_directory'])
def migration_setup(request):
    # Directly reference the path to the fixtures directory
    base_path = Path(__file__).resolve().parent / "fixtures" / request.param
    yield base_path


@mock_aws
@pytest.mark.filterwarnings("ignore:datetime.datetime.utcnow()")
def test_migration_scenarios(migration_setup, request, dynamodb):
    captured_output = StringIO()
    sys.stdout = captured_output

    directory_path = str(migration_setup)
    storage_engine = DynamoDBStorageEngine('test_migrations')
    migrator = Migrator(directory=directory_path, storage_engine=storage_engine, dry_run=False)
    migrator.migrate()

    sys.stdout = sys.__stdout__

    # Custom assertions based on the parameter ID
    if request.node.callspec.id == 'two_modules':
        # Specific assertions for 'two_modules' scenario
        assert "Hello, running up() from migration 20240410093757" in captured_output.getvalue()
        assert "Hello, running up() from migration 20240410093809" in captured_output.getvalue()
    elif request.node.callspec.id == 'basic_app' or request.node.callspec.id == 'single_dir':
        # Assertions for 'basic_app' and 'single_dir' scenarios
        assert "Hello, running up() from migration 20240410094004" in captured_output.getvalue()
        assert "Hello, running up() from migration 20240410094006" in captured_output.getvalue()

