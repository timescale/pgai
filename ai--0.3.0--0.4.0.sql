-------------------------------------------------------------------------------
-- ai 0.4.0

CREATE OR REPLACE FUNCTION @extschema@.oci_list_models(
	_profile text DEFAULT 'DEFAULT'::text,
	_region text DEFAULT 'us-chicago-1'::text,
	_compartment text DEFAULT NULL::text)
    returns table
( "name" text
,"capabilities" text
,"version" text
)
as $func$
_compartment_set = _compartment
if _compartment_set is None:
    plpy.error("Missing compartment id ")

import oci

CONFIG_PROFILE =  _profile
config = oci.config.from_file('~/.oci/config', CONFIG_PROFILE)
endpoint = "https://generativeai."+_region+".oci.oraclecloud.com"
generative_ai_client = oci.generative_ai.GenerativeAiClient(config=config, service_endpoint=endpoint, retry_strategy=oci.retry.NoneRetryStrategy(), timeout=(10,240))

list_models_response = generative_ai_client.list_models(compartment_id=_compartment)
for model in list_models_response.data.items:
 yield (model.display_name,model.capabilities,model.version)

$func$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

CREATE OR REPLACE FUNCTION @extschema@.oci_embed(
	_model text DEFAULT NULL::text,
	_input text DEFAULT NULL::text,
	_input_type text DEFAULT NULL::text,
	_truncate text DEFAULT 'NONE'::text,
	_profile text DEFAULT 'DEFAULT'::text,
	_region text DEFAULT 'us-chicago-1'::text,
	_compartment text DEFAULT NULL::text)
    RETURNS vector
    LANGUAGE 'plpython3u'
    COST 100
    VOLATILE PARALLEL SAFE 
    SET search_path=pg_catalog, pg_temp
AS $BODY$

import oci

CONFIG_PROFILE = _profile
config = oci.config.from_file('~/.oci/config', CONFIG_PROFILE)

endpoint = "https://inference.generativeai."+_region+".oci.oraclecloud.com"
generative_ai_inference_client = oci.generative_ai_inference.GenerativeAiInferenceClient(config=config, service_endpoint=endpoint, retry_strategy=oci.retry.NoneRetryStrategy(), timeout=(10,240))
embed_text_detail = oci.generative_ai_inference.models.EmbedTextDetails()
embed_text_detail.serving_mode = oci.generative_ai_inference.models.OnDemandServingMode(model_id=_model)
embed_text_detail.inputs = [_input]
embed_text_detail.input_type = _input_type
embed_text_detail.truncate = _truncate 
embed_text_detail.compartment_id = _compartment
embed_text_response = generative_ai_inference_client.embed_text(embed_text_detail)

embed_text_response.data
return embed_text_response.data.embeddings[0]
$BODY$;