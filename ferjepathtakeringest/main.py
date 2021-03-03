import boto3
from elasticsearch import Elasticsearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth


def _get_es() -> Elasticsearch:
    """
    Setup inspired by:
    https://docs.aws.amazon.com/elasticsearch-service/latest/developerguide/es-request-signing.html#es-request-signing-python

    :return:
    """
    print('Conecting to elasticsearch...')
    elasticsearch_base_url = "https://search-ferjepathtakerprodwaypoints-daqt4o6t55kgljpmaeb3z57l2a.us-east-1.es.amazonaws.com"
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


def handler(event, context):
    es = _get_es()

    print('Elasticsearch info')
    print(es.info())

    return {
        'statusCode': 200,
        'body': {
            'hello': 'world',
        },
    }
