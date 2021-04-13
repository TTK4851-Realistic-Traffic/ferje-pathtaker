from elasticsearch import Elasticsearch, NotFoundError


def _exists_index(es_client, index_name):
    try:
        es_client.indices.get(index_name)
        return True
    except NotFoundError as err:
        print(f'Index does not already exists: {str(err)}')
        return False


def create_if_not_exists(es_client: Elasticsearch, index_name: str):
    if not _exists_index(es_client, index_name):
        print('Creating index...')
        print(es_client.indices.create(index=index_name))

    request_body = {
        'properties': {
            'timestamp': {'type': 'date', 'index': True},
            # Stores our latitude and longitude
            'location': {'type': 'geo_point'},
            'ferryId': {'type': 'keyword', 'index': True},
            # Originally named 'source', but this name is taken by elasticsearch.
            # Therefore remapped to 'waypointSource' in elasticsearch index
            'waypointSource': {'type': 'keyword', 'index': False},
            'metadata': {'type': 'object', 'enabled': False},
        },
    }

    es_client.indices.put_mapping(index=index_name, body=request_body)
