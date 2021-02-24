ferje-pathtaker
===

This project consists of two AWS Lambda functions:

1. **ferje-pathtaker-ingest**
1. **ferje-pathtaker**

### ferje-pathtaker-ingest

Responsible for polling items from our AWS SQS queue, for which ferje-ais-importer pushes data to, 
and store all signals in the database

### ferje-pathtaker

This is our HTTP endpoint that returns a collection of signals based on different query parameters.

> You must be authenticated to access these resources

```http request
GET /v1/waypoints/?lat=xxx&lon=xxx&radius_meter=3000&start=<UNIX timestamp>&end=<UNIX timestamp>
Authorization Bearer <issued token>
Accept text/csv
```

## Local development

The easiest way to test locally is to run the automated tests in `ferjepathtaker/tests/main.py`. 
They try to simulate the real environment. Alternatively run your changes locally and push the changes to AWS, 
and see if it works.

We haven't created any scrambled testdata yet. In the mean time will you have to provide your own.

1. Place the files `2018-07-01.csv` and `2018-07-01_shipdata.csv` inside `ferjeimporter/tests/testdata/`.
   You should have gotten these files from the project earlier.
1. Setup a virtual environment in the root of this project
    1. `pip3 install virtualenv`
    1. `virtualenv venv --python=python3.8`
    1. `source ./venv/bin/activate`
       Windows users may have to use another strategy to successfully activate virtual environments 
       https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/#activating-a-virtual-environment
    1. `pip3 install -r requirements-frozen.txt`
1. Run the tests through PyCharm, VSCode or terminal (whatever you prefer)
   * For terminal users: `python -m unittest` while in root.
   * If you get an boto3 error related to missing credentials, create (for WSL at least) the file `~/.aws/credentials` with the content
      ```
      [default]
      aws_access_key_id=test
      aws_secret_access_key=test
      ```

Our Python tests uses the package [moto](https://pypi.org/project/moto/). It simplifies interactions with AWS when running 
tests by simulating an actual environment, but is in reality only run locally. This allows you as developer to interact with AWS as normal, 
using [boto3](https://boto3.amazonaws.com/). See `ferjeimporter/tests/ test_import_success` for a working example. 