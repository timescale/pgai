# Pgai vectorizer S3 integration guide

Pgai vectorizers can be configured to create vector embeddings for documents stored in S3 buckets. We have a [general guide for embedding documents](./document-embeddings.md) that walks you through the steps to configure your vectorizer to load, parse, chunk and embed documents. This guide will focus on issues specific to documents stored in S3.

A simple vectorizer configuration for documents stored in S3 looks like this:

```sql
SELECT ai.create_vectorizer(
    'document'::regclass,
    loading => ai.loading_uri(column_name => 'uri'),
    embedding => ai.embedding_openai('text-embedding-3-small', 768),
    destination => ai.destination_table('document_embeddings')
);
```

Where the `document` table has a column `uri` that contains the S3 URI of the document. Learn more in our [guide for embedding documents](./document-embeddings.md).

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

## Common issues and solutions

**1. S3 Access Issues**

If documents from S3 fail to load:
- Verify AWS credentials are correctly configured
- Check that IAM roles have appropriate permissions
- Ensure S3 bucket names and object keys are correct
