from elasticsearch import Elasticsearch, NotFoundError


def _exists_index(es_client, index_name):
    try:
        es_client.indices.get(index_name)
        return True
    except NotFoundError as err:
        print(f'Index does not already exists: {str(err)}')
        return False


def create_if_not_exists(es_client: Elasticsearch, index_name: str):

    if _exists_index(es_client, index_name):
        return

    request_body = {
        'settings': {
            'number_of_shards': 1,
            'number_of_replicas': 1,
        },
        'mappings': {
            'waypoints': {
                'properties': {
                    'timestamp': {'type': 'date', 'index': True},
                    # Stores our latitude and longitude
                    'location': {'type': 'geo_point'},
                    'ferryId': {'type': 'keyword', 'index': True},
                    'waypoint_type': {'type': 'keyword', 'index': False},
                    'metadata': {'type': 'object', 'enabled': False},
                }
            }
        }
    }

    print('Creating index...')
    print(es_client.indices.create(index_name, body=request_body))