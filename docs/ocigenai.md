# Use pgai with OCI Gen AI

This page shows you how to:

- [Configure pgai for OCI Gen AI]
- [Add AI functionality to your database](#usage)

## Configure pgai for OCI Gen AI

To authenticate to OCI Gen AI you must setup the [API Key-base authentication](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/sdk_authentication_methods.htm) and install the oci python package with pip install oci

Put your config file under a directory that postgres user has access (usually in ~/.oci), here an example:

```bash
[DEFAULT]
user=ocid1.user.oc1..xxxxx
fingerprint=xxxx
tenancy=ocid1.tenancy.oc1..xxxx
region=us-chicago-1
key_file=~/.oci/key
```

This code supports multiple config profiles (specify it using the _profile parameter)

## Usage

The default region is configured to us-chicago-1 (but you can choose another region using _region variable), and you must supply a compartment id (_compartment=>'ocid1.compartment.oc1..xxxxxx')


- [oci_list_models](#oci_list_models)
- [oci_embed](#oci_embed)

### oci_list_models

This function returns the available model per region/compartment alongside it capabilites.

```sql
SELECT * 
FROM oci_list_models(_region=>'sa-saopaulo-1',_compartment=>'ocid1.compartment.oc1..xxxxxx');
```
  Results:

```text
              name              |     capabilities      | version 
--------------------------------+-----------------------+---------
 meta.llama-3.1-405b-instruct   | ['CHAT']              | 1.0.0
 meta.llama-3.1-70b-instruct    | ['CHAT']              | 1.0.0
 meta.llama-3.1-70b-instruct    | ['CHAT', 'FINE_TUNE'] | 1.0.0
 cohere.command-r-plus          | ['CHAT']              | 1.2
 meta.llama-3-70b-instruct      | ['CHAT', 'FINE_TUNE'] | 1.0.0
 meta.llama-3-70b-instruct      | ['CHAT']              | 1.0.0
 cohere.command-r-16k           | ['CHAT', 'FINE_TUNE'] | 1.2
 cohere.command-r-16k           | ['CHAT']              | 1.2
 cohere.embed-english-v3.0      | ['TEXT_EMBEDDINGS']   | 3.0
 cohere.embed-multilingual-v3.0 | ['TEXT_EMBEDDINGS']   | 3.0
(10 rows)
```


### oci_embed

This fuction receives a text (_input parameter) and returns a vector, you must pass a valid model (_model variable)

```sql
select * from oci_embed(
_model=>'cohere.embed-multilingual-v3.0'
,_region=>'sa-saopaulo-1'
,_compartment=>'ocid1.compartment.oc1..xxxxxx'
,_input=>'teste123'
);
```

  Results:

```text
 [0.030929565,0.06774902,-0.027297974,0.009544373,0.027236938,0.02029419,0.0059394836,-0.053497314,-0.004425049,0.008918762....]
```