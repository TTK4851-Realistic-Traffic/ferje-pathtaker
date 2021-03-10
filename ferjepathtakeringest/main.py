from typing import List
import os
import boto3
import json
from elasticsearch import Elasticsearch, RequestsHttpConnection, helpers
from requests_aws4auth import AWS4Auth

from ferjepathtakeringest.indices import create_if_not_exists

ELASTICSEARCH_INDEX_NAME = 'ferry_waypoings'


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
    return f'{document["timestamp"]}-{document["location"]["lat"]}-{document["location"]["lon"]}-{document["ferryId"]}'


def _get_messages_from_event(event: dict) -> List[dict]:
    return flatten([json.loads(record['body']) for record in event['Records']])


def _ferry_messages_to_es_bodies(messages: List[dict]) -> List[dict]:
    bodies = []
    for message in messages:
        bodies.append({
            '_id': _build_id(message),
            'doc_type': 'waypoint',
            'doc': message,
        })
    return bodies


def handler(event, context):
    elasticsearch_hostname = os.environ.get("ELASTICSEARCH_HOSTNAME")
    print(f'Event: {event}')
    es = _get_es(elasticsearch_hostname)
    # Ensure the index exists before we try to push data to it
    create_if_not_exists(es, ELASTICSEARCH_INDEX_NAME)

    messages = _get_messages_from_event(event)
    es_upload_entries = _ferry_messages_to_es_bodies(messages)

    helpers.bulk(es, es_upload_entries, index=ELASTICSEARCH_INDEX_NAME)

    return {
        'statusCode': 200,
        'body': {'ok': True},
    }


# Used for local debugging
if __name__ == '__main__':
    handler({}, {})