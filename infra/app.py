#!/usr/bin/env python3
"""CDK app: the serverless async backbone for the hybrid deployment.

The always-on API runs on a container (streaming, low latency). THIS stack is
just the async half — SQS queues, the consumer + scheduler Lambdas, and the
EventBridge cron. Deploy with your OWN AWS account:

    cd infra
    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    export CDK_DEFAULT_ACCOUNT=... CDK_DEFAULT_REGION=...
    export DATABASE_URL=... REDIS_URL=... JWT_SECRET=... ENCRYPTION_KEY=... (etc — see README)
    npx cdk bootstrap      # once per account/region
    npx cdk deploy
"""
from __future__ import annotations

import os

import aws_cdk as cdk

from stacks.shiplog_stack import ShiplogAsyncStack

app = cdk.App()

ShiplogAsyncStack(
    app,
    "ShiplogAsync",
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION"),
    ),
)

app.synth()
