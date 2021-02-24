# Use
FROM public.ecr.aws/lambda/python:3.8

ARG LAMBDA_PREFIX="ferjepathtakeringest"

COPY $LAMBDA_PREFIX/ ./$LAMBDA_PREFIX
COPY ./requirements-frozen.txt ./requirements-frozen.txt

RUN pip3 install -r requirements-frozen.txt
CMD ["$LAMBDA_PREFIX/main.handler"]