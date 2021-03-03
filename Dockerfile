# Use
FROM public.ecr.aws/lambda/python:3.8

ARG LAMBDA_PREFIX="ferjepathtakeringest"

COPY $LAMBDA_PREFIX/ ./app
COPY ./requirements-frozen.txt ./requirements-frozen.txt

RUN pip3 install -r requirements-frozen.txt
CMD ["./app/main.handler"]