from typing import List
import os
import boto3
import json
from elasticsearch import Elasticsearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

from ferjepathtakeringest.indices import create_if_not_exists

ELASTICSEARCH_INDEX_NAME = 'ferry_waypoings'


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
        region='us-east-1',
        service='es',
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
    return [json.loads(record['body']) for record in event['Records']]


def handler(event, context):
    elasticsearch_hostname = os.environ.get("ELASTICSEARCH_HOSTNAME")
    print(f'Event: {event}')
    es = _get_es(elasticsearch_hostname)
    print(f'Elasticsearch info: {es.info()}')
    # Ensure the index exists before we try to push data to it
    create_if_not_exists(es, ELASTICSEARCH_INDEX_NAME)

    documents = [
        {
            "timestamp": 1614843750000,
            "location": {
                'lat': 63.6853,
                'lon': 9.668,
            },
            'ferryId': 'ef35d14c602e335df133fcf9a8d87ff9d57739f966605d08fde0cce57ed856f8',
            'metadata': {
                'length': -99,
                'width': 19,
            },
        },
    ]

    for document in documents:
        es.index(index=ELASTICSEARCH_INDEX_NAME, id=_build_id(document), body=document)

    body = es.search(index=ELASTICSEARCH_INDEX_NAME, body={
        'size': 10000,
        'query': {
            'match_all': {}
        }
    })

    print('Stored items in index')
    print(body)

    return {
        'statusCode': 200,
        'body': {
            'hello': 'world',
        },
    }


# Used for local debugging
if __name__ == '__main__':
    handler({}, {})