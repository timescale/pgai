# S3 Integration Guide

## Setup for Self-hosted pgai Installations

To integrate with your AWS S3 buckets, pgai needs to authenticate. There are two main methods to authenticate with S3:

**1. Default AWS credentials**

pgai uses the default AWS credential sources, look into the [boto3 docs](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html#configuring-credentials) for details. E.g. you can set the following environment variables where the vectorizer runs:

```
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
```

The user must have appropriate S3 read permissions for the buckets containing your documents.


**2. Assume Role-based Authentication**

You can also use the `aws_role_arn` parameter to assume an IAM role. You can also use the `aws_role_arn` parameter to assume an IAM role. This is what Timescale Cloud uses, but it is usually not necessary if the worker runs on the same AWS account as your AWS S3 buckets::

```sql
SELECT ai.create_vectorizer(
    'document'::regclass,
    loading => ai.loading_uri(
        column_name => 'uri',
        aws_role_arn => 'arn:aws:iam::123456789012:role/S3AccessRole'
    ),
    -- other configuration...
);
```

The role must have appropriate S3 read permissions for the buckets containing your documents.

## Setup for Timescale-cloud-hosted pgai

For Timescale Cloud installations, only role-based authentication via `assume_role_arn` is supported.

### Create a Role for s3 access
First you need to create a role that Timescale can assume:

```bash
aws iam create-role \
  --role-name timescale-vectorizer-s3-access \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Principal": {
          "AWS": "arn:aws:iam::142548018081:role/timescale-pgai-vectorizer"
        },
        "Action": "sts:AssumeRole",
        "Condition": {
          "StringLike": {
            "sts:ExternalId": "projectId/serviceId"
          }
        }
      }
    ]
  }'
```

Note that you need to replace the `projectId/serviceId` in the trust policy with the actual project and service id of your Timescale Cloud installation. You can find this in the Timescale Cloud console. This is a security measure that prevents the [confused deputy problem](https://docs.aws.amazon.com/IAM/latest/UserGuide/confused-deputy.html), which would otherwise allow other Timescale Cloud users to access your buckets if they guessed your role name and accountId.

### Grant permissions to your bucket to the role

```bash
aws iam put-role-policy \
  --role-name timescale-vectorizer-s3-access \
  --policy-name S3AccessPolicy \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Action": [
          "s3:GetObject"
        ],
        "Effect": "Allow",
        "Resource": [
          "arn:aws:s3:::test",
          "arn:aws:s3:::test/*"
        ]
      }
    ]
  }'
```

### Get the role ARN
```bash
aws iam get-role --role-name timescale-s3-role-test --query 'Role.Arn' --output text
```
### Configure it in your ai.loading_uri:

```sql
ai.loading_uri(
    column_name => 'uri',
    aws_role_arn => 'arn:aws:iam::123456789012:role/timescale-vectorizer-s3-access'
)
```


## Syncing S3 to a Documents Table

If your application so far does not handle document uploads which would allow you to update the document table directly. You can instead use s3 events to keep your document table synchronized with S3 when documents are uploaded, modified, or deleted:

```python
# AWS Lambda function to handle S3 events
def handle_s3_event(event, context):
    import psycopg2
    
    # Extract document info from S3 event
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']
    event_name = event['Records'][0]['eventName']
    
    # Connect to PostgreSQL
    conn = psycopg2.connect("postgresql://user:password@host:port/database")
    cursor = conn.cursor()
    
    # Handle different event types
    if 'ObjectCreated' in event_name:
        # Document created or updated
        cursor.execute(
            """
            INSERT INTO document (title, uri, updated_at) 
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (uri) DO UPDATE 
            SET updated_at = CURRENT_TIMESTAMP
            """,
            [key.split('/')[-1], f"s3://{bucket}/{key}"]
        )
    elif 'ObjectRemoved' in event_name:
        # Document deleted
        cursor.execute(
            "DELETE FROM document WHERE uri = %s",
            [f"s3://{bucket}/{key}"]
        )
    
    conn.commit()
    cursor.close()
    conn.close()
```

Configure an [S3 bucket notification](https://docs.aws.amazon.com/AmazonS3/latest/userguide/EventNotifications.html) to trigger this Lambda function on object events (PutObject, DeleteObject).


## Common Issues and Solutions

**1. S3 Access Issues**

If documents from S3 fail to load:
- Verify AWS credentials are correctly configured
- Check that IAM roles have appropriate permissions
- Ensure S3 bucket names and object keys are correct

