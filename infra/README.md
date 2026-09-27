# infra — the serverless async backbone (hybrid deploy)

This CDK app deploys **only the async half** of the hybrid: SQS queues (+ DLQs),
the consumer & scheduler Lambdas, and the EventBridge cron. The **API runs on a
container** (see `apps/api/Dockerfile`) because it streams AI drafts (SSE), which
Lambda + API Gateway can't do well.

```
Container API  ──enqueue(boto3)──▶  SQS webhook/email  ──▶  Lambda consumers
(Render/Fly/…)                       EventBridge (1/min) ──▶  Lambda scheduler
```

> ⚠️ Deploy with **your own** AWS account — never a shared/company account.
> Creating these resources costs ~$0 on the free tier at low volume, but it's
> real infrastructure in whatever account you point it at.

## Prerequisites
- An AWS account you own + the AWS CLI configured (`aws configure`) for it.
- **Docker running** (CDK builds the Lambda image at deploy time).
- Node (for the CDK CLI) and Python 3.12.
- Managed data ready: **Neon** Postgres (pooled URL) and **Upstash** Redis.

## 1. Install + bootstrap
```bash
cd infra
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export CDK_DEFAULT_ACCOUNT=<your-account-id>
export CDK_DEFAULT_REGION=<e.g. us-east-1>
npx cdk bootstrap        # once per account/region
```

## 2. Provide config (read from your shell at deploy time — nothing is committed)
```bash
export DATABASE_URL="postgresql+asyncpg://…neon-pooler…/db?ssl=require"
export REDIS_URL="rediss://…upstash…"
export JWT_SECRET=…            # python -c "import secrets;print(secrets.token_urlsafe(48))"
export ENCRYPTION_KEY=…        # python -c "import secrets;print(secrets.token_hex(32))"  (NEVER rotate once live)
export GITHUB_APP_ID=…  GITHUB_APP_PRIVATE_KEY="$(cat key.pem)"  GITHUB_WEBHOOK_SECRET=…
export EMAIL_BACKEND=resend  RESEND_API_KEY=…  EMAIL_FROM="You <updates@yourdomain.com>"
export APP_URL=https://app.yourdomain.com  API_URL=https://api.yourdomain.com  ROOT_DOMAIN=yourdomain.com
```

## 3. Deploy
```bash
npx cdk deploy
```
Note the stack **Outputs**:
- `WebhookQueueUrl`, `EmailQueueUrl`
- `ApiPublisherAccessKeyId`, `ApiPublisherSecretAccessKey` (the IAM user the
  container API uses to enqueue — treat the secret like a password)

## 4. Wire the container API to the queues
Set these on the **container** (Render/Fly/Railway) so its `enqueue()` sends to SQS:
```
QUEUE_BACKEND=sqs
SQS_WEBHOOK_URL=<WebhookQueueUrl output>
SQS_EMAIL_URL=<EmailQueueUrl output>
AWS_ACCESS_KEY_ID=<ApiPublisherAccessKeyId output>
AWS_SECRET_ACCESS_KEY=<ApiPublisherSecretAccessKey output>
AWS_DEFAULT_REGION=<your region>
```
Everything else (DATABASE_URL, secrets, GitHub, email) matches the Lambda env.

## 5. Migrations (run once, separately from runtime)
```bash
cd ../apps/api
DATABASE_URL="postgresql+asyncpg://…neon…" .venv/bin/alembic upgrade head
```

## 6. GitHub App webhook
Point the App's webhook at the **container** API (not Lambda):
`https://api.yourdomain.com/webhooks/github`. The API verifies the HMAC, records
the event, and enqueues to SQS; the Lambda consumer does the rest.

## What runs where
| Concern | Where | Trigger |
|---|---|---|
| REST + SSE AI drafting | Container API | HTTP |
| Webhook processing | `WebhookConsumer` Lambda | SQS |
| Email fan-out | `EmailConsumer` Lambda | SQS |
| Scheduled publishing | `Scheduler` Lambda | EventBridge (1/min) |
| Failed messages | DLQs (14-day retention) | after 5 receives |

## Teardown
```bash
npx cdk destroy
```
