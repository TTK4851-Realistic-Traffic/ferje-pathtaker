import json
import os
import time
import unittest
from unittest import mock

import boto3
from elasticsearch import Elasticsearch
from testcontainers.elasticsearch import ElasticSearchContainer

from ferjepathtakeringest.main import handler, ELASTICSEARCH_INDEX_NAME

AWS_DEFAULT_REGION = 'us-east-1'


def _build_queue_test_event(messages):
    return {
        'Records': [
            {
                'messageId': '37141a32-7130-4450-992a-e0900fb61ac0',
                'receiptHandle': 'AQEBXbd6h5zumqaPQ/nE+mEErsUePNJmVfSHdLUQP/6Y9zxxGBWJzOkbty+XM8eqxKkvBw8DpkdCu5S9IMEwYA6gDqoUbN2oCfFHqq2kf0gDXhkLZxGocFslCzszT6erOghrVhT7WjT1E1bLIew5V8kmgQSXPRIkbjBSRsNhBDsKlKWCCNI+0tgBTnq3SQinJvL0jhy3OlVTPjy0OrVRp2uP9MQGmEPbAKIrhR6Rbj6z9ySbWaxFTT4RRk5m7PwiAN64/gljdUllpZ3PrL0NBclzoFd0Pfu5xdhHfrACx/3a7dSNN1vyajd+GGkp7oGA6dM9vZi7YuCZnOf+V95H9znOLCO6A0Wp637qxWU+LUFPc1loSGEwFiszfDgPikzj6ikTlqkEzfqv7sJGv0NcdRasUcCbn8RcvtNnVJoE1KuOerk=',
                'body': json.dumps(messages),
                'attributes': {
                    'ApproximateReceiveCount': '2',
                    'SentTimestamp': '1615366514109',
                    'SenderId': '314397620259',
                    'ApproximateFirstReceiveTimestamp': '1615366514114'
                },
                'messageAttributes': {},
                'md5OfBody': 'fe04ac224df61d5a7d7d3749dd357e98',
                'eventSource': 'aws:sqs',
                'eventSourceARN': 'arn:aws:sqs:us-east-1:314397620259:ferje-ais-importer-prod-pathtaker-source',
                'awsRegion': 'us-east-1'
            }
        ]
    }


class TestSignalIngest(unittest.TestCase):
    elasticsearch: Elasticsearch

    def setUp(self) -> None:
        """
        This will initialize a real elasticsearch system using test-containers to give the most realistic
        test-environment (and to not have to bother with mocking. It does however, require Docker to run on your system
        and Windows users might experience some problems with this (because Windows has a tendency to be difficult with containerization).

        It also overwrites any AWS access configurations to ensure that we use non-production values.
        :return:
        """
        # Initialize a local elasticsearch environment
        es_context = ElasticSearchContainer()
        es_context.start()
        self.addCleanup(es_context.stop)

        es_url = es_context.get_url()
        # Extract the components that are actually relevant to connect to our system
        (hostname, port) = tuple(es_url.replace('http://', '').split(':'))

        self.elasticsearch = Elasticsearch(
            hosts=[{'host': hostname, 'port': port}]
        )

        # Ensure test setup uses the correct test credentials
        # os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
        # os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
        # os.environ['AWS_SECURITY_TOKEN'] = 'testing'
        # os.environ['AWS_SESSION_TOKEN'] = 'testing'
        environment_patcher = mock.patch.dict(os.environ, {
            'ELASTICSEARCH_HOSTNAME': f'{hostname}:{port}',
            # Ensure our system looks for resources in the correct region
            'AWS_DEFAULT_REGION': AWS_DEFAULT_REGION,
            # Prevent any use of non-test credentials
            'AWS_ACCESS_KEY_ID': 'testing',
            'AWS_SECRET_ACCESS_KEY': 'testing',
            'AWS_SECURITY_TOKEN': 'testing',
            'AWS_SESSION_TOKEN': 'testing',
        })
        environment_patcher.start()
        self.addCleanup(environment_patcher.stop)

        # Sanity check that AWS uses our test-credentials
        credentials = boto3.Session().get_credentials()
        self.assertEqual('testing', credentials.access_key)
        self.assertEqual('testing', credentials.secret_key)

    def test_successful_write_to_elasticsearch(self):
        test_messages = [
            {
                "timestamp": 1614843750000,
                "lat": 63.6853,
                "lon": 9.668,
                "source": "ais",
                "ferryId": "ef35d14c602e335df133fcf9a8d87ff9d57739f966605d08fde0cce57ed856f8",
                "metadata": {"length": -99, "width": 19},
            },
            {
                "timestamp": 1614843750000,
                "lat": 63.6853,
                "lon": 9.668,
                "source": "ais",
                "ferryId": "ef35d14c602e3322f133fcf9a8d87ff9d57739f966605d08fde0cce57ed856f8",
                "metadata": {"length": -99, "width": 19},
            },
        ]

        handler(_build_queue_test_event(test_messages), {})
        # Give the index some time to process
        time.sleep(1)

        body = self.elasticsearch.search(index=ELASTICSEARCH_INDEX_NAME, body={
            'size': 10000,
            'query': {
                'match_all': {}
            }
        })

        hits = body['hits']['hits']
        self.assertGreaterEqual(len(test_messages), len(hits))

        ferry_ids = [message['ferryId'] for message in test_messages]
        for hit in hits:
            source = hit['_source']['doc']
            self.assertIn(source['ferryId'], ferry_ids)

