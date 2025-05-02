# Pgai vectorizer S3 integration guide

Pgai vectorizers can be configured to create vector embeddings for documents stored in S3 buckets. We have a [general guide for embedding documents](./README.md#document-embedding) that walks you through the steps to configure your vectorizer to load, parse, chunk and embed documents. This guide will focus on issues specific to documents stored in S3.

A simple vectorizer configuration for documents stored in S3 looks like this:

```sql
SELECT ai.create_vectorizer(
    'document'::regclass,
    loading => ai.loading_uri(column_name => 'uri'),
    embedding => ai.embedding_openai('text-embedding-3-small', 768),
    destination => ai.destination_table('document_embeddings')
);
```

Where the `document` table has a column `uri` that contains the S3 URI of the document. Learn more in our [guide for embedding documents](./README.md#document-embedding).
If you do not have a documents table yet, we provide you an example of how you can sync your s3 buckets to such a table [further down in this document](#syncing-s3-to-a-documents-table).

But how do you configure the vectorizer to get access to your S3 buckets if they are not publicly accessible? This is the focus of the rest of this guide.

- [Setup for self-hosted pgai installations](#setup-for-self-hosted-pgai-installations)
- [Setup for Timescale Cloud](#setup-for-timescale-cloud)
- [Common issues and solutions](#common-issues-and-solutions)

## Setup for self-hosted pgai installations

To integrate with your AWS S3 buckets, pgai needs to authenticate. There are two main methods to authenticate with S3:

**1. Default AWS credentials**

pgai uses the default AWS credential sources, look into the [boto3 docs](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html#configuring-credentials) for details. E.g. you can set the following environment variables where the vectorizer runs:

```
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
```

The user must have appropriate S3 read permissions for the buckets containing your documents.


**2. Assume Role-based Authentication**

 You can also use the `aws_role_arn` parameter to assume an IAM role. This is what Timescale Cloud uses, but it is usually not necessary if the worker runs on the same AWS account as your AWS S3 buckets::

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

## Setup for Timescale Cloud

For Timescale Cloud installations, only role-based authentication via `assume_role_arn` is supported.

### Create a role for s3 access
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

If your application treats s3 as the source of truth for documents and therefore doesn't keep track of files in postgres, you can configure [s3 event notifications](https://docs.aws.amazon.com/AmazonS3/latest/userguide/EventNotifications.html) to keep your document table synchronized with S3 when documents are uploaded, modified, or deleted.

The easiest way to handle s3 changes is to create a new AWS lambda function to listen to s3 notifications. AWS will take care of calling your function whenever the bucket content changes. The lambda function can then update the document table in your postgres instance accordingly.

### 1. Create a new lambda function
Create a new AWS Lambda function, in this example we are using Python 3.13 as our runtime. You can use the AWS console or the AWS CLI to create the function.
![Create Lambda](/docs/images/s3_sync/create_lambda.png)

### 2. Configure the trigger

Next up add a trigger to your lambda function, choose s3 as the trigger type and select the bucket you want to listen to.
For event types just make sure you include all object create and delete events. S3 does not differentiate between creates and updates.
![Configure Trigger](/docs/images/s3_sync/trigger_config.png)

### 3. Implement the lambda function
Your lambda function then needs to [handle s3 events](https://docs.aws.amazon.com/lambda/latest/dg/with-s3.html) and update the document table accordingly. Here is a simple example of a lambda function that does this for a table that has `uri` and `updated_at` columns:
```python
import json
import psycopg2

# You might want to load this from env vars or your secret manager instead
CONN_STRING = "postgresql://tsdbadmin:my-host-name:5432/postgres"


def lambda_handler(event, context):
    conn = psycopg2.connect(CONN_STRING)
    # Process each record in the event
    for record in event['Records']:
        # Extract S3 event details
        event_name = record['eventName']
        bucket_name = record['s3']['bucket']['name']
        object_key = record['s3']['object']['key']
        s3_uri = f"s3://{bucket_name}/{object_key}"
        cur = conn.cursor()
        # Determine if this is a create/update or delete event
        if event_name.startswith('ObjectCreated'): # An update is also an ObjectCreated event
            print(f"Creating or updating document for {s3_uri}")
            cur.execute(
                "INSERT INTO s3_documents (file_uri) VALUES (%s) ON CONFLICT (file_uri) DO UPDATE SET updated_at = CURRENT_TIMESTAMP",
                [s3_uri]
            )

        elif event_name.startswith('ObjectRemoved'):
            print(f"Deleting document for {s3_uri}")
            cur.execute("Delete from s3_documents where file_uri=%s;", [s3_uri])
        conn.commit()
        cur.close()
    conn.close()
    return {
        'statusCode': 200,
        'body': json.dumps('S3 event processing completed successfully')
    }
```

This lambda function requires the `psycopg2` library to connect to postgres. You can either include it in your [deployment package](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html#python-package-create-dependencies) or use a [custom docker image](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html) to include it.

> [!NOTE]
> If you are working on an ARM Mac installing the right binary version of psycopg2 needs some fiddling with pip. [This guide](https://aws.plainenglish.io/installing-psycopg2-on-aws-lambda-when-developing-on-arm-macs-f1453199f516) might help.

That's it: Save and deploy the function. The lambda function will be triggered whenever a file is created, updated or deleted in the S3 bucket. It will then insert or delete the corresponding document in the `s3_documents` table or update the `updated_at` timestamp if the document already exists. This will in turn inform any configured vectorizer to reprocess the document.


## Common issues and solutions

**1. S3 Access Issues**

If documents from S3 fail to load:
- Verify AWS credentials are correctly configured
- Check that IAM roles have appropriate permissions
- Ensure S3 bucket names and object keys are correct
