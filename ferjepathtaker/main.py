import json
import os
import base64

import boto3
from elasticsearch import Elasticsearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

ELASTICSEARCH_INDEX_NAME = 'ferry_waypoings'


def _get_client_authorizers(headers):
    authorization = headers.get('Authorization', None)

    if authorization is None:
        raise ValueError("Authorization header is not present. Please include it in your request")

    http_basic = authorization.replace("Basic", "")
    if len(http_basic) < 1:
        raise ValueError("Authorization header is missing 'Basic' prefix. Please provide HTTP basic header")

    http_basic_decoded = base64.b64decode(http_basic.encode('ascii')).decode('ascii')
    properties = http_basic_decoded.split(':')

    # First in item is client id and second is client secret
    return properties[0], properties[1]


def _require_authorized_client(http_basic: tuple):
    client_id = os.environ['API_CLIENT_ID']
    client_secret = os.environ['API_CLIENT_SECRET']

    if client_id != http_basic[0] or client_secret != http_basic[1]:
        print(f'Client id or client secret is not correct: Client ID: {client_id != http_basic[0]}, Client Secret: {client_secret != http_basic[1]}')
        raise ValueError('Invalid credentials! Please check they are correctly HTTP basic formated')


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


def _build_response_body(es_hits: dict):
    items = []

    if 'hits' not in es_hits and 'hits' not in es_hits['hits']:
        return items

    for hit in es_hits['hits']['hits']:
        source = hit['_source']
        items.append({
            'ferryId': source['ferryId'],
            'timestamp': source['timestamp'],
            'location': source['location'],
            'metadta': source['metadata']
        })

    return items


def handler(event, context):
    print(f'Event: {event}')

    # Ensure only valid requests are included
    try:
        authorization = _get_client_authorizers(event['headers'])
        _require_authorized_client(authorization)
    except ValueError as err:
        return {
            'statusCode': 401,
            'body': json.dumps({
                'title': 'Unauthorized',
                'detail': str(err),
            }),
        }

    elasticsearch_hostname = os.environ.get("ELASTICSEARCH_HOSTNAME")
    es = _get_es(elasticsearch_hostname)

    body = es.search(index=ELASTICSEARCH_INDEX_NAME, body={
        'size': 10000,
        'query': {
            'match_all': {}
        }
    })
    print(body)
    response = _build_response_body(body)
    print(response)
    return {
        'statusCode': 200,
        'body': json.dumps(response),
    }
