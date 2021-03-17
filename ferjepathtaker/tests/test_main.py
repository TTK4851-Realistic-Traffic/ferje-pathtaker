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
                "location": {
                    "lat": 63.6853,
                    "lon": 9.668
                },
                "source": "ais",
                "ferryId": "ef35d14c602e335df133fcf9a8d87ff9d57739f966605d08fde0cce57ed856f8",
                "metadata": {"length": -99, "width": 19},
            },
            {
                "timestamp": 1614843750000,
                "location": {
                    "lat": 63.6853,
                    "lon": 9.668
                },
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

