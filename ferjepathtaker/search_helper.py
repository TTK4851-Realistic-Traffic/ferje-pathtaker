from elasticsearch import Elasticsearch

VALID_WAYPOINT_TYPES = {'ais', 'radar'}


def search_index(es: Elasticsearch, index_name: str, params: dict):
    matchers = []

    if 'start' in params and 'end' in params:
        # Ensure it is in Epoch millis (We should have received it as epoch seconds)
        start = params['start'] * 1000
        end = params['end'] * 1000

        # Match by time
        matchers.append({
            'range': {
                'timestamp': {
                    'gte': start,
                    'lte': end,
                    'format': 'epoch_millis',
                },
            },
        })

    query_filters = []
    # If we wish to only retrieve 'ais' or 'radar'
    if 'source' in params and params['source'] in VALID_WAYPOINT_TYPES:
        print(f'Filtering by source: {params["source"]}')
        query_filters.append({
            'term': {
                'waypointSource': params["source"],
            }
        })

    if 'top_left' in params and 'top_left' in params:
        query_filters.append({
            'geo_bounding_box': {
                'location': {
                    'top_left': params['top_left'],
                    'bottom_right': params['bottom_right'],
                },
            }
        })

    body = es.search(
        index=index_name,
        request_timeout=30,
        timeout='60s',
        body={
            'size': 10000,
            'query': {
                'bool': {
                    'must': matchers,
                    # Used for query filtering
                    'filter': query_filters,
                },
            },
        },
    )
    return body
