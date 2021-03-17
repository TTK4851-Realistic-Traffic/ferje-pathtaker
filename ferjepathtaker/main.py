import json
import os

import boto3
from elasticsearch import Elasticsearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

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


def handler(event, context):
    print(f'Event: {event}')
    elasticsearch_hostname = os.environ.get("ELASTICSEARCH_HOSTNAME")
    es = _get_es(elasticsearch_hostname)

    body = es.search(index=ELASTICSEARCH_INDEX_NAME, body={
        'size': 10000,
        'query': {
            'match_all': {}
        }
    })
    print(body)
    return {
        'statusCode': 200,
        'body': json.dumps({
            'hello': 'world',
        }),
    }
