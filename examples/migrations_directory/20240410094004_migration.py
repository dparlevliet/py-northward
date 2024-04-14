import boto3

dependencies = [
    # List of dependencies
]

def up():
    """
        Create a DynamoDB table called 'users' with a primary key of 'username'
    """

    dynamodb = boto3.resource('dynamodb', region_name='us-west-2', endpoint_url='http://dynamodb:8000')
    dynamodb.create_table(
        TableName='migrations-directory-users',
        KeySchema=[ {'AttributeName': 'username', 'KeyType': 'HASH'} ],
        AttributeDefinitions=[ {'AttributeName': 'username', 'AttributeType': 'S'} ],
        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
    )


def down():
    """
        Delete the DynamoDB table called 'users'
    """

    dynamodb = boto3.resource('dynamodb', region_name='us-west-2', endpoint_url='http://dynamodb:8000')
    dynamodb.Table('migrations-directory-users').delete()