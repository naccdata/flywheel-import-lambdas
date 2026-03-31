python_sources(name="function")

python_aws_lambda_function(
    name="lambda",
    runtime="python3.12",
    handler="lambda_function.py:lambda_handler",
    include_requirements=False,
)

python_aws_lambda_layer(
    name="layer",
    runtime="python3.12",
    dependencies=[
        ":function",
        "//common/src/python/s3_import_models:lib",
        "//common/src/python/flywheel_client:lib",
        "//:root#boto3",
        "//:root#pydantic",
        "//:root#fw-client",
        "//:root#aws-lambda-powertools",
    ],
    include_sources=False,
)
