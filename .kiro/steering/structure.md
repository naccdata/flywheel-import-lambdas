# Project Structure

## Monorepo Organization

This is a Pants-managed monorepo for AWS Lambda functions. It was created from the `naccdata/lambda-monorepo-template`.

## Repository Layout

```
flywheel-import-lambdas/
├── .devcontainer/              # Dev container configuration
│   ├── devcontainer.json
│   └── Dockerfile
├── .kiro/                      # Kiro settings and steering
│   ├── settings/mcp.json      # Kiro Pants Power config
│   └── steering/              # Steering documents
├── bin/                        # Dev scripts (build, start, stop, terminal, exec)
├── common/                     # Shared code across lambdas
│   ├── src/python/            # Shared source modules
│   │   └── <module_name>/
│   │       ├── BUILD
│   │       └── *.py
│   └── test/python/           # Tests for shared modules
│       ├── BUILD
│       └── test_*.py
├── lambda/                     # Individual Lambda functions
│   └── <lambda_name>/
│       ├── src/python/<lambda_name>_lambda/
│       │   ├── BUILD
│       │   └── lambda_function.py
│       ├── test/python/
│       │   ├── BUILD
│       │   └── test_lambda_function.py
│       └── main.tf            # Terraform for this lambda
├── docs/                       # Documentation
├── examples/                   # Example lambda implementations (for reference)
│   ├── simple-lambda/
│   ├── database-lambda/
│   └── common/
├── BUILD                       # Root Pants BUILD file
├── pants.toml                  # Pants configuration
├── requirements.txt            # Python dependencies
├── ruff.toml                   # Ruff linter config
└── get-pants.sh               # Pants installer
```

## Lambda Structure

Each lambda follows this pattern:

```
lambda/<lambda_name>/
├── src/python/<lambda_name>_lambda/
│   ├── BUILD                  # Pants targets: python_sources, python_aws_lambda_function, python_aws_lambda_layer
│   └── lambda_function.py     # Handler implementation
├── test/python/
│   ├── BUILD                  # python_sources + python_tests targets
│   └── test_lambda_function.py
└── main.tf                    # Terraform configuration
```

### Lambda BUILD File Pattern

```python
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
        "//common/src/python/<module>:lib",
        "//:root#boto3",
        "//:root#pydantic",
    ],
    include_sources=False,
)
```

## Common/Shared Code

Shared modules live under `common/src/python/<module_name>/` with a `BUILD` file containing `python_sources(name="lib")`.

Lambdas reference shared code via Pants dependencies:
```python
"//common/src/python/<module>:lib"
```

## Root BUILD File

```python
python_requirements(name="root")
```

External dependencies from `requirements.txt` are referenced as `//:root#<package>`.

## Source Roots

Pants recognizes these as source roots (from `pants.toml`):
- `src/*` — Source code
- `test/*` — Test code

## Ignored Directories

Pants ignores:
- `.devcontainer/`
- `.vscode/`
