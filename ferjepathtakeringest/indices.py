from elasticsearch import Elasticsearch, NotFoundError


def _exists_index(es_client, index_name):
    try:
        es_client.indices.get(index_name)
        return True
    except NotFoundError as err:
        print(f'Index does not already exists: {str(err)}')
        return False


def create_if_not_exists(es_client: Elasticsearch, index_name: str):
    if _exists_index(es_client, 'ferry_waypoings'):
        print('Outdated client with typo is present. Removing...')
        es_client.indices.delete(index='ferry_waypoings')

    if _exists_index(es_client, index_name):
        print('Cleaning up existing index for a fresh setup')
        es_client.indices.delete(index=index_name)

    if not _exists_index(es_client, index_name):
        print('Creating index...')
        print(es_client.indices.create(index=index_name))

    request_body = {
        'properties': {
            'timestamp': {'type': 'date', 'index': True},
            # Stores our latitude and longitude
            'location': {'type': 'geo_point'},
            'ferryId': {'type': 'keyword', 'index': True},
            'waypoint_type': {'type': 'keyword', 'index': False},
            'metadata': {'type': 'object', 'enabled': False},
        },
    }

    es_client.indices.put_mapping(index=index_name, body=request_body)
