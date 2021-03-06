from typing import List
import os
import boto3
import json
from datetime import datetime
from elasticsearch import Elasticsearch, RequestsHttpConnection, helpers
from requests_aws4auth import AWS4Auth

from ferjepathtakeringest.indices import create_if_not_exists

ELASTICSEARCH_INDEX_NAME = 'ferry_waypoints'


def chunk(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def _timestamp_as_epoch_milliseconds(timestamp: str) -> int:
    as_datetime = datetime.fromisoformat(timestamp)
    # Epoch Milliseconds is 10^12
    return int(as_datetime.timestamp()) * 1000


def flatten(items: List[list]) -> list:
    """
    Converts a list of lists into a one-dimensional list.
    [[1,2,3], [4], [5,6]] -> [1,2,3,4,5,6]
    """
    flattened = []
    for inner_items in items:
        for item in inner_items:
            flattened.append(item)
    return flattened


def _get_es(server) -> Elasticsearch:
    """
    Setup inspired by:
    https://docs.aws.amazon.com/elasticsearch-service/latest/developerguide/es-request-signing.html#es-request-signing-python

    :return:
    """
    print(f'Connecting to elasticsearch: {server}...')

    # In situations where we are using a local system
    if 'localhost' in server:
        # Assumes that the last part of the server string is only the port number
        # i.e localhost:9200 or localhost:555772
        port = int(server.split(':')[1])
        return Elasticsearch(
            hosts=[{'host': 'localhost', 'port': port}]
        )

    credentials = boto3.Session().get_credentials()
    awsauth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        # Region
        'us-east-1',
        # Service
        'es',
        session_token=credentials.token,
    )

    return Elasticsearch(
        hosts=[{'host': server, 'port': 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )


def _build_id(document) -> str:
    """
    Assign a custom id from the most important fields of our document.
    Reduces risk of duplicated entries, and potential for direct lookups
    :param document:
    :return:
    """
    return f'{str(document["timestamp"])}-{str(document["location"]["lat"])}-{str(document["location"]["lon"])}-{document["ferryId"]}'


def _get_messages_from_event(event: dict) -> List[dict]:
    messages = []

    for record in event['Records']:
        try:
            body = json.loads(record['body'])
            messages.append(body)
        except Exception as err:
            print(f'Failed to parse message, with error {str(err)}. Message: {record["body"]}')

    messages = flatten(messages)
    # Do some additional processing of the data
    for index, message in enumerate(messages):
        # Enforce the correct structure of the persisted data
        updated_message = {
            'ferryId': message['ferryId'],
            'location': {
                'lat': message['lat'],
                'lon': message['lon'],
            },
            'timestamp': _timestamp_as_epoch_milliseconds(message['timestamp']),
            'waypointSource': message['source'],
            'metadata': message['metadata'],
        }
        messages[index] = updated_message

    return messages


def _ferry_messages_to_es_bodies(messages: List[dict]) -> List[dict]:
    bodies = []
    for message in messages:
        bodies.append({
            '_id': _build_id(message),
            **message,
        })
    return bodies


def handler(event, context):
    elasticsearch_hostname = os.environ.get("ELASTICSEARCH_HOSTNAME")
    es = _get_es(elasticsearch_hostname)
    # Ensure the index exists before we try to push data to it
    create_if_not_exists(es, ELASTICSEARCH_INDEX_NAME)

    messages = _get_messages_from_event(event)
    es_upload_entries = _ferry_messages_to_es_bodies(messages)

    # Upload documents in bulk of 100s
    # This allows us to accept quite large bulks of messages from SQS at once,
    # and Elasticsearch should not complain
    chunks = chunk(es_upload_entries, 100)
    for entries in chunks:
        helpers.bulk(
            es,
            entries,
            request_timeout=30,
            index=ELASTICSEARCH_INDEX_NAME,
        )

    return {
        'statusCode': 200,
        'body': {'ok': True},
    }


# Used for local debugging
if __name__ == '__main__':
    handler({}, {})