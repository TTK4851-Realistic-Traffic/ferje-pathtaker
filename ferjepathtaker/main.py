import json


def handler(event, context):
    print(f'Event called: {event}')
    return {
        'statusCode': 200,
        'body': json.dumps({
            'hello': 'world',
        }),
    }
