"""The async backbone: SQS (+ DLQs), consumer & scheduler Lambdas, EventBridge
cron, and an IAM user the container API uses to enqueue.

Design notes:
- Lambdas are built from apps/api/Dockerfile.lambda (one image, a different
  handler CMD per function) — container images sidestep the native-wheel pain
  of asyncpg/nh3/cryptography in a zip.
- QUEUE_BACKEND=sqs makes the SAME code that runs in-process locally send to SQS
  in prod; the consumers here run identically to the local asyncio tasks.
- Secrets/config are read from the DEPLOYER'S shell env at synth time and set as
  Lambda env vars, so nothing sensitive is committed.
"""
from __future__ import annotations

import os

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as sources
from aws_cdk import aws_sqs as sqs
from constructs import Construct

# Config the Lambdas need at runtime, pulled from the deployer's environment.
_ENV_KEYS = [
    "DATABASE_URL",
    "REDIS_URL",
    "JWT_SECRET",
    "ENCRYPTION_KEY",
    "GITHUB_APP_ID",
    "GITHUB_APP_PRIVATE_KEY",
    "GITHUB_WEBHOOK_SECRET",
    "EMAIL_BACKEND",
    "RESEND_API_KEY",
    "EMAIL_FROM",
    "APP_URL",
    "API_URL",
    "ROOT_DOMAIN",
]

_API_DIR = "../apps/api"
_LAMBDA_DOCKERFILE = "Dockerfile.lambda"


class ShiplogAsyncStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        env = self._runtime_env()

        # ── SQS: one queue + DLQ per async concern ──────────────────────────
        webhook_dlq = sqs.Queue(self, "WebhookDLQ", retention_period=Duration.days(14))
        email_dlq = sqs.Queue(self, "EmailDLQ", retention_period=Duration.days(14))

        webhook_q = sqs.Queue(
            self,
            "WebhookQueue",
            visibility_timeout=Duration.seconds(180),  # ≥ consumer timeout
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=5, queue=webhook_dlq),
        )
        email_q = sqs.Queue(
            self,
            "EmailQueue",
            visibility_timeout=Duration.seconds(180),
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=5, queue=email_dlq),
        )

        # The consumers/scheduler enqueue via these URLs.
        env["SQS_WEBHOOK_URL"] = webhook_q.queue_url
        env["SQS_EMAIL_URL"] = email_q.queue_url

        # ── Lambdas (one image, per-function handler) ───────────────────────
        def make_fn(name: str, handler: str, timeout: int = 60, memory: int = 512):
            return lambda_.DockerImageFunction(
                self,
                name,
                code=lambda_.DockerImageCode.from_image_asset(
                    directory=_API_DIR,
                    file=_LAMBDA_DOCKERFILE,
                    cmd=[handler],
                ),
                timeout=Duration.seconds(timeout),
                memory_size=memory,
                environment=env,
            )

        webhook_fn = make_fn("WebhookConsumer", "app.lambda_handlers.webhook_consumer")
        email_fn = make_fn("EmailConsumer", "app.lambda_handlers.email_consumer")
        scheduler_fn = make_fn(
            "Scheduler", "app.lambda_handlers.scheduler_handler", timeout=120
        )

        # ── SQS → Lambda (partial-batch failures so only bad msgs retry) ────
        webhook_fn.add_event_source(
            sources.SqsEventSource(webhook_q, batch_size=10, report_batch_item_failures=True)
        )
        email_fn.add_event_source(
            sources.SqsEventSource(email_q, batch_size=10, report_batch_item_failures=True)
        )

        # The scheduler enqueues email broadcasts when it publishes a release.
        email_q.grant_send_messages(scheduler_fn)

        # ── EventBridge cron: publish due scheduled releases every minute ───
        events.Rule(
            self,
            "SchedulerCron",
            schedule=events.Schedule.rate(Duration.minutes(1)),
            targets=[targets.LambdaFunction(scheduler_fn)],
        )

        # ── IAM user for the (off-AWS) container API to enqueue to SQS ───────
        publisher = iam.User(self, "ApiPublisher")
        webhook_q.grant_send_messages(publisher)
        email_q.grant_send_messages(publisher)
        access_key = iam.CfnAccessKey(
            self, "ApiPublisherKey", user_name=publisher.user_name
        )

        # ── Outputs (wire these into the container's env) ───────────────────
        CfnOutput(self, "WebhookQueueUrl", value=webhook_q.queue_url)
        CfnOutput(self, "EmailQueueUrl", value=email_q.queue_url)
        CfnOutput(self, "ApiPublisherAccessKeyId", value=access_key.ref)
        CfnOutput(
            self,
            "ApiPublisherSecretAccessKey",
            value=access_key.attr_secret_access_key,
            description="Sensitive — put in the container env as AWS_SECRET_ACCESS_KEY, then rotate if leaked.",
        )

    def _runtime_env(self) -> dict[str, str]:
        env: dict[str, str] = {"ENV": "prod", "QUEUE_BACKEND": "sqs"}
        for key in _ENV_KEYS:
            value = os.environ.get(key)
            if value:
                env[key] = value
        return env
