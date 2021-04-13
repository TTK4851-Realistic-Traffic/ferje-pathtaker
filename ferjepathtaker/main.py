import json
import os
import base64
from typing import List

import boto3
from elasticsearch import Elasticsearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

from ferjepathtaker.search_helper import search_index

ELASTICSEARCH_INDEX_NAME = 'ferry_waypoints'


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
        print(
            f'Client id or client secret is not correct: Client ID: {client_id != http_basic[0]}, Client Secret: {client_secret != http_basic[1]}')
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
            'metadata': source['metadata'],
            # Remap Elasticsearch specific field name,
            # back to our domain specific name
            'source': source['waypointSource'],
        })

    return items


def _convert_response_to_csv(response: List[dict]) -> str:
    rows = [
        ['ferryId', 'timestamp', 'lat', 'lon', 'heading', 'length', 'width', 'source']
    ]

    # The CSV does not know what None is, we call it "null"
    csv_friendly_null = 'null'

    for item in response:
        row = [
            item['ferryId'],
            str(item['timestamp']),
            str(item['location']['lat']),
            str(item['location']['lon']),
            str(item['metadata']['heading']) if 'heading' in item['metadata'] else csv_friendly_null,
            str(item['metadata']['length']) if 'length' in item['metadata'] else csv_friendly_null,
            str(item['metadata']['width']) if 'width' in item['metadata'] else csv_friendly_null,
            str(item['source']) if 'source' in item else csv_friendly_null,
        ]
        rows.append(row)

    csv = []
    for row in rows:
        csv.append(','.join(row))
    return '\n'.join(csv)


def _extract_query_params(event):
    if 'queryStringParameters' not in event:
        raise ValueError('Event did not include any query-string, please include them!')
    raw_query = event["queryStringParameters"]
    start = raw_query['start']
    start = int(start)
    end = raw_query['end']
    end = int(end)
    min_lat = raw_query['min_lat']
    min_lat = float(min_lat)
    min_lon = raw_query['min_lon']
    min_lon = float(min_lon)
    max_lat = raw_query['max_lat']
    max_lat = float(max_lat)
    max_lon = raw_query['max_lon']
    max_lon = float(max_lon)

    source = raw_query.get('source', None)

    return {
        'start': start,
        'end': end,
        'source': source,
        'top_left': {
            'lat': max_lat,
            'lon': min_lon,
        },
        'bottom_right': {
            'lat': min_lat,
            'lon': max_lon,
        },
    }


def _remove_invalid_data(es, es_hits):
    """
    Removes any data that does not follow the expected structure from the Elasticsearch index,
    and the result-set.
    :param es:
    :param es_hits:
    :return:
    """
    if 'hits' not in es_hits and 'hits' not in es_hits['hits']:
        return es_hits

    updated_hits = []
    for hit in es_hits['hits']['hits']:
        source = hit['_source']
        if 'location' not in source:
            print(f'Found invalid hit. Removing... {hit}')
            es.delete(ELASTICSEARCH_INDEX_NAME, hit['_id'])
        else:
            updated_hits.append(hit)

    es_hits['hits']['hits'] = updated_hits
    return es_hits


def handler(event, context):
    print(f'Event: {event}')

    query = event["queryStringParameters"]
    print(f'Query parameters: {query}')

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

    params = {}

    try:
        params = _extract_query_params(event)
    except ValueError as err:
        print(f'Could not extract query parameters from event: {event}. Error: {str(err)}')
        return {
            'statusCode': 400,
            'body': json.dumps({
                'title': 'Invalid parameters',
                'detail': str(err),
            }),
        }

    elasticsearch_hostname = os.environ.get("ELASTICSEARCH_HOSTNAME")
    es = _get_es(elasticsearch_hostname)

    print(f'Request parameters: {params}')

    body = search_index(es, index_name=ELASTICSEARCH_INDEX_NAME, params=params)
    body = _remove_invalid_data(es, body)

    print('Converting elasticsearch to response body...')
    response = _build_response_body(body)
    csv_response = _convert_response_to_csv(response)
    return {
        'statusCode': 200,
        'headers': {
          'content-type': 'text/csv',
        },
        'body': csv_response,
    }
