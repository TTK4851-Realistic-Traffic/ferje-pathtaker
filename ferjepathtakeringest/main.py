import boto3
from elasticsearch import Elasticsearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

from ferjepathtakeringest.indices import create_if_not_exists

ELASTICSEARCH_INDEX_NAME = 'ferry_waypoings'

def _get_es() -> Elasticsearch:
    """
    Setup inspired by:
    https://docs.aws.amazon.com/elasticsearch-service/latest/developerguide/es-request-signing.html#es-request-signing-python

    :return:
    """
    print('Conecting to elasticsearch...')
    elasticsearch_base_url = "search-ferjepathtakerprodwaypoints-daqt4o6t55kgljpmaeb3z57l2a.us-east-1.es.amazonaws.com"
    credentials = boto3.Session().get_credentials()
    service = 'es'
    region = 'us-east-1'
    print(f'\tConfiguring elasticsearch AWS authentication: Access Key {credentials.access_key[0:5]}...')
    awsauth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        region,
        service,
        session_token=credentials.token,
    )

    return Elasticsearch(
        hosts=[{'host': elasticsearch_base_url, 'port': 443}],
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


def handler(event, context):
    print('Event')
    print(event)
    print('Context')
    print(context)
    es = _get_es()

    print('Elasticsearch info')
    print(es.info())
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