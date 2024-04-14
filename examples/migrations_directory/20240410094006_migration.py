import boto3

dependencies = [
    "20240410094004_migration"
]

def up():
    """
        Create a global secondary index on the 'users' table to support querying by email.
    """
    dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
    table = dynamodb.Table('basic-app-users')
    response = table.update(
        AttributeDefinitions=[
            {
                'AttributeName': 'email',
                'AttributeType': 'S'
            }
        ],
        GlobalSecondaryIndexUpdates=[
            {
                'Create': {
                    'IndexName': 'EmailIndex',
                    'KeySchema': [
                        {
                            'AttributeName': 'email',
                            'KeyType': 'HASH'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    },
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                }
            }
        ]
    )
    print(response)

def down():
    """
        Remove the global secondary index named 'EmailIndex' from the 'users' table.
    """
    dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
    table = dynamodb.Table('basic-app-users')
    response = table.update(
        GlobalSecondaryIndexUpdates=[
            {
                'Delete': {
                    'IndexName': 'EmailIndex'
                }
            }
        ]
    )
    print(response)
