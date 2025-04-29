# Changelog

## [0.10.1](https://github.com/timescale/pgai/compare/pgai-v0.10.0...pgai-v0.10.1) (2025-04-29)


### Bug Fixes

* change --strict argument of install to flag ([ceaa313](https://github.com/timescale/pgai/commit/ceaa313562e60eb45f976655bbaac4c0f5e37d48))
* support pg15 ([#662](https://github.com/timescale/pgai/issues/662)) ([c7402c0](https://github.com/timescale/pgai/commit/c7402c0110baf180592d2cefab24276853a55f9f))


### Miscellaneous

* add postgres version check to pgai install ([#670](https://github.com/timescale/pgai/issues/670)) ([713e771](https://github.com/timescale/pgai/commit/713e771527e3a659d2943b9ab28413664a81286c))

## [0.10.0](https://github.com/timescale/pgai/compare/pgai-v0.9.2...pgai-v0.10.0) (2025-04-08)


### ⚠ BREAKING CHANGES

* truncate inputs to OpenAI ([#567](https://github.com/timescale/pgai/issues/567))

### Features

* add ai.chunking_none() to skip chunking ([#575](https://github.com/timescale/pgai/issues/575)) ([d84965a](https://github.com/timescale/pgai/commit/d84965af9b09892110e1cd9f989a99e70cd69319))
* add support for generating embeddings for external documents ([#442](https://github.com/timescale/pgai/issues/442)) ([c356ae8](https://github.com/timescale/pgai/commit/c356ae8260c9b5464dcc586af9cc16f66b149f8d))
* truncate inputs to OpenAI ([#567](https://github.com/timescale/pgai/issues/567)) ([ab29dd4](https://github.com/timescale/pgai/commit/ab29dd4b8176fb63aee3f3cde15092e2e1a8a9b7))


### Performance Improvements

* make pgai --help faster ([#605](https://github.com/timescale/pgai/issues/605)) ([00f1eb7](https://github.com/timescale/pgai/commit/00f1eb7d0007f73f6d5bfbea8899cf889e4d6411))
* maximally defer library imports ([#606](https://github.com/timescale/pgai/issues/606)) ([5e3033b](https://github.com/timescale/pgai/commit/5e3033bb236d6bd3fc1dea062a85705e25aac171))


### Miscellaneous

* add missing dep ([#588](https://github.com/timescale/pgai/issues/588)) ([af9d1d3](https://github.com/timescale/pgai/commit/af9d1d33c2ec748e9d88aa5f9d0509ef4d125107))
* add token counts to tracing ([#607](https://github.com/timescale/pgai/issues/607)) ([b75183c](https://github.com/timescale/pgai/commit/b75183cfbbc2a85e3d5fc6fa7d3f604d5c8bf9d2))
* refactor processing logic ([#604](https://github.com/timescale/pgai/issues/604)) ([47bb2ae](https://github.com/timescale/pgai/commit/47bb2ae9e474e01e70002566ef7bfa3589119eee))
* submit plain (not tokenized) input to OpenAI ([#593](https://github.com/timescale/pgai/issues/593)) ([c6a9e6c](https://github.com/timescale/pgai/commit/c6a9e6c5aeb49b4fc2732380f7293bb166efb1b3))
* use basemodel everywhere instead of mixing it with pydantic dataclasses ([#590](https://github.com/timescale/pgai/issues/590)) ([c180627](https://github.com/timescale/pgai/commit/c180627c737a529d6c1605ad872211d06cb43d0d))

## [0.9.2](https://github.com/timescale/pgai/compare/pgai-v0.9.1...pgai-v0.9.2) (2025-03-25)


### Bug Fixes

* force runtime chunk exclusion in fetch_work_query ([#581](https://github.com/timescale/pgai/issues/581)) ([378b18f](https://github.com/timescale/pgai/commit/378b18f528317d2626966da9b47283ba8876e337))

## [0.9.1](https://github.com/timescale/pgai/compare/pgai-v0.9.0...pgai-v0.9.1) (2025-03-21)


### Miscellaneous

* wrap exceptions in a group ([#577](https://github.com/timescale/pgai/issues/577)) ([5118c93](https://github.com/timescale/pgai/commit/5118c930090bd83f2dd2e39626796b5ed7edd3e2))

## [0.9.0](https://github.com/timescale/pgai/compare/pgai-v0.8.4...pgai-v0.9.0) (2025-03-20)


### Features

* add vectorizer.run method ([#572](https://github.com/timescale/pgai/issues/572)) ([635742c](https://github.com/timescale/pgai/commit/635742ca7290854c95225703729810b071e1bff3))
* better worker tracking from the db ([#499](https://github.com/timescale/pgai/issues/499)) ([3768c1c](https://github.com/timescale/pgai/commit/3768c1c0a58e147fbeb6e720d7043f0fa6e0513a))


### Bug Fixes

* do not exit when no extension installed ([82d40d6](https://github.com/timescale/pgai/commit/82d40d6004f2f4b452e73c3807d29b677e48d47e))
* make features more robust ([#573](https://github.com/timescale/pgai/issues/573)) ([9a753f1](https://github.com/timescale/pgai/commit/9a753f1e22f2f945d129b4da6f0b0e08ce152e84))
* **vectorizer:** use table column ordering instead of primary key ordering ([199dabb](https://github.com/timescale/pgai/commit/199dabbec03521fc4cf4dbac8e2c858fd03522ac))

## [0.8.4](https://github.com/timescale/pgai/compare/pgai-v0.8.3...pgai-v0.8.4) (2025-03-10)


### Bug Fixes

* move UUID PK serialization into pgai lib ([#554](https://github.com/timescale/pgai/issues/554)) ([a08f04a](https://github.com/timescale/pgai/commit/a08f04a716fd7d5474e57bbd286414eb24b732e3))

## [0.8.3](https://github.com/timescale/pgai/compare/pgai-v0.8.2...pgai-v0.8.3) (2025-03-10)


### Bug Fixes

* error "Object of type UUID is not JSON serializable" ([#549](https://github.com/timescale/pgai/issues/549)) ([b242d70](https://github.com/timescale/pgai/commit/b242d7049a1c38785c510f0a5a36af31537cb610))

## [0.8.2](https://github.com/timescale/pgai/compare/pgai-v0.8.1...pgai-v0.8.2) (2025-03-05)


### Bug Fixes

* respect OpenAI token limit ([#536](https://github.com/timescale/pgai/issues/536)) ([1afe493](https://github.com/timescale/pgai/commit/1afe49340996a2277bcebf2561dbc4741e571a3b))


### Miscellaneous

* make token count log less verbose ([#539](https://github.com/timescale/pgai/issues/539)) ([6e732ae](https://github.com/timescale/pgai/commit/6e732ae4e128cc7bf8741bdafd765583c83e1bec))

## [0.8.1](https://github.com/timescale/pgai/compare/pgai-v0.8.0...pgai-v0.8.1) (2025-02-28)


### Bug Fixes

* flaky alembic tests ([#515](https://github.com/timescale/pgai/issues/515)) ([7517656](https://github.com/timescale/pgai/commit/7517656413c92614d5a034fa07f9cc45d7ce3a4e))
* fully qualify 'locked' column ([#520](https://github.com/timescale/pgai/issues/520)) ([8a59b21](https://github.com/timescale/pgai/commit/8a59b2184673f56c248fda80f197a9e528970183))
* load target column types' oids to use in binary copy cmd ([5bef4ac](https://github.com/timescale/pgai/commit/5bef4ac56bf349ffb28eeb0ddfc35677c63f9f83))

## [0.8.0](https://github.com/timescale/pgai/compare/pgai-v0.7.0...pgai-v0.8.0) (2025-02-18)


### Features

* add litellm to alembic and python vectorizer creation ([#487](https://github.com/timescale/pgai/issues/487)) ([6bf799d](https://github.com/timescale/pgai/commit/6bf799dfc613e08171ac1d817006d580d56d4178))


### Bug Fixes

* readd version to uv lock ([#463](https://github.com/timescale/pgai/issues/463)) ([f4e8059](https://github.com/timescale/pgai/commit/f4e805941be3b398cf55898f91018cfdf07ab714))
* record exceptions in embedding.setup() ([bc157f2](https://github.com/timescale/pgai/commit/bc157f2a7525f730b25c7f561123e6c42d53390f))


### Miscellaneous

* reorganize the docs ([9bfdc27](https://github.com/timescale/pgai/commit/9bfdc2756a8953019e0df2e5bce95472f255c2c3))

## [0.7.0](https://github.com/timescale/pgai/compare/pgai-v0.6.0...pgai-v0.7.0) (2025-02-05)


### Features

* add vectorizer enable/disable support for ai.scheduling_none ([f3d91a3](https://github.com/timescale/pgai/commit/f3d91a3a774703a46fb88e9b378039eaedb5dcc8))


### Bug Fixes

* remove sqlalchemy warning about conflicts ([#413](https://github.com/timescale/pgai/issues/413)) ([55f89fe](https://github.com/timescale/pgai/commit/55f89fe48779e5bb2ddfd0f4ba7e0e01218f5a76))

## [0.6.0](https://github.com/timescale/pgai/compare/pgai-v0.5.0...pgai-v0.6.0) (2025-01-28)


### Features

* disable OpenAI tokenization when a model does not have a tokenizer match ([#390](https://github.com/timescale/pgai/issues/390)) ([41cb52c](https://github.com/timescale/pgai/commit/41cb52ceb10e484d3051480d17ef0b7f2154bac9))
* add LiteLLM vectorizer integration. Requires a compatible version of the PGAI extension, which is currently under development ([0fb7e46](https://github.com/timescale/pgai/commit/0fb7e46b9eb1f69b0fb67c6a67ff5bf9e96c0cf3))


### Miscellaneous

* get rid of nested parametrization ([#394](https://github.com/timescale/pgai/issues/394)) ([0a399e2](https://github.com/timescale/pgai/commit/0a399e2739096844f4066181be1e8bf686085c16))
* separate test_vectorizer_cli.py into separate files for vectorizer types ([#401](https://github.com/timescale/pgai/issues/401)) ([c64833c](https://github.com/timescale/pgai/commit/c64833c1d616120b8e29863107aa2ffc71b94405))

## [0.5.0](https://github.com/timescale/pgai/compare/pgai-v0.4.0...pgai-v0.5.0) (2025-01-22)


### Features

* add alembic operations for vectorizer ([#266](https://github.com/timescale/pgai/issues/266)) ([b01acfe](https://github.com/timescale/pgai/commit/b01acfeeb7f0472de0337442c3c63a51d6690167))
* allow users to configure a base_url for the vectorizer OpenAI embedder ([#351](https://github.com/timescale/pgai/issues/351)) ([66ceb3d](https://github.com/timescale/pgai/commit/66ceb3dc62712b82f45e2485072595c2f402065b))


### Bug Fixes

* two usability issues with sqlalchemy ([#354](https://github.com/timescale/pgai/issues/354)) ([95fa797](https://github.com/timescale/pgai/commit/95fa797f559adfbaf91ff5198db0d7c45381e1dc))
* vectorizer_relationship for sqlalchemy models with mixins or inheritance ([#357](https://github.com/timescale/pgai/issues/357)) ([cfd5f73](https://github.com/timescale/pgai/commit/cfd5f73606e1a6b88eab00d043bded8d898ab4dd))

## [0.4.0](https://github.com/timescale/pgai/compare/pgai-v0.3.0...pgai-v0.4.0) (2025-01-08)


### Features

* add sqlalchemy vectorizer_relationship ([#265](https://github.com/timescale/pgai/issues/265)) ([0230509](https://github.com/timescale/pgai/commit/0230509a374c472d65280769f92f0baeebb908d7))
* load api keys from db in self hosted vectorizer ([#311](https://github.com/timescale/pgai/issues/311)) ([b7573b7](https://github.com/timescale/pgai/commit/b7573b79711a691a37201e06f6e5ba52631b69b9))
* print unexpected error traceback in debug logs ([#344](https://github.com/timescale/pgai/issues/344)) ([d9bdcd6](https://github.com/timescale/pgai/commit/d9bdcd633fe372fca14dd97d830aeed9789f78ac))
* pull missing ollama models ([#301](https://github.com/timescale/pgai/issues/301)) ([dbac246](https://github.com/timescale/pgai/commit/dbac246b563f10d1704b40bf16038b16529d6888))
* upgrade ollama client to 0.4.5 ([#345](https://github.com/timescale/pgai/issues/345)) ([c579238](https://github.com/timescale/pgai/commit/c57923804532980d8b2bb5e3b47a927c48f55df0))


### Bug Fixes

* handle 'null' value in chunking 'chunk_column' ([#340](https://github.com/timescale/pgai/issues/340)) ([f283b6c](https://github.com/timescale/pgai/commit/f283b6cecd7da42a5197da6219b990598e19f9f0))


### Miscellaneous

* fix broken pgai build by pinning hatchling ([#308](https://github.com/timescale/pgai/issues/308)) ([5441f2d](https://github.com/timescale/pgai/commit/5441f2d3445b1f2afc85ce34b220002b8e4cf08f))
* register postgres_params custom pytest.mark ([#327](https://github.com/timescale/pgai/issues/327)) ([89039b2](https://github.com/timescale/pgai/commit/89039b2181192191dad48dc8206e76b17643e129))
* split embedders in individual files ([#315](https://github.com/timescale/pgai/issues/315)) ([77673ee](https://github.com/timescale/pgai/commit/77673eee81191c7f2c8966010fe8f04d9a929dee))

## [0.3.0](https://github.com/timescale/pgai/compare/pgai-v0.2.1...pgai-v0.3.0) (2024-12-10)


### ⚠ BREAKING CHANGES

* remove `truncate` parameter from Ollama/Voyage APIs ([#284](https://github.com/timescale/pgai/issues/284))

### Features

* add Voyage AI vectorizer integration ([#256](https://github.com/timescale/pgai/issues/256)) ([1b56d62](https://github.com/timescale/pgai/commit/1b56d62295faf996697db75f3a9ac9391869a3bb))
* remove `truncate` parameter from Ollama/Voyage APIs ([#284](https://github.com/timescale/pgai/issues/284)) ([ecda03c](https://github.com/timescale/pgai/commit/ecda03cf5d27f750db534801719413d0abcfa557))


### Bug Fixes

* fail fast when api key is missing and once is set ([#274](https://github.com/timescale/pgai/issues/274)) ([1c2ff20](https://github.com/timescale/pgai/commit/1c2ff2013fd64949a8f5c6374e3134af1b2551f4))

## [0.2.1](https://github.com/timescale/pgai/compare/pgai-v0.2.0...pgai-v0.2.1) (2024-12-02)


### Bug Fixes

* make vectorizer worker robust ([#263](https://github.com/timescale/pgai/issues/263)) ([77c0baf](https://github.com/timescale/pgai/commit/77c0baf57438a837f47c179769bc684edeafbfc8))

## [0.2.0](https://github.com/timescale/pgai/compare/v0.1.0...pgai-v0.2.0) (2024-11-26)


### Features

* add Ollama support to vectorizer ([6a4a449](https://github.com/timescale/pgai/commit/6a4a449e99e2e5e62b5f551206a0b28e5ad40802))


### Bug Fixes

* make vectorizer worker poll for new vectorizers ([0672e7a](https://github.com/timescale/pgai/commit/0672e7a71e2792c984ce9a590a06de9bfd25c8b5))


### Miscellaneous

* a new database for each test ([4ed938b](https://github.com/timescale/pgai/commit/4ed938bd86932bf21340e14007210d8dc6fd72e1))
* add logo to pgai pypi ([3366368](https://github.com/timescale/pgai/commit/336636872b39ce371d801f4ffacd1ea57e67b9f5))
* add test for recursive text splitting ([#207](https://github.com/timescale/pgai/issues/207)) ([4a35fc6](https://github.com/timescale/pgai/commit/4a35fc693395bc4125b9654650043cad5929889e))
* migrate project commands from Make to Just ([42a8f79](https://github.com/timescale/pgai/commit/42a8f795c89bfc7526008dda7c99a3d6a4ecce70))
* migrate to uv and hatch ([#188](https://github.com/timescale/pgai/issues/188)) ([627cf33](https://github.com/timescale/pgai/commit/627cf33e802cac01f2a204aecf994ceb9509a84e))
* refactor test infra ([ac845ca](https://github.com/timescale/pgai/commit/ac845ca8dc834e0359113fd63d30c6ec98e041a7))
* run pgai tests against extension from source ([ffc20d2](https://github.com/timescale/pgai/commit/ffc20d243c2a632d01c5e3476ddbc6c636d994c1))
* scope postgres_container fixture to class ([12c1780](https://github.com/timescale/pgai/commit/12c17809ec235d759e37eaa0898ea3274fea6319))
* separate the dev/test/build between the projects ([183be9e](https://github.com/timescale/pgai/commit/183be9e82632287c35081c4eefd81ff99d4bd4ba))
* test the cli instead of the lambda handler ([#204](https://github.com/timescale/pgai/issues/204)) ([3a48f82](https://github.com/timescale/pgai/commit/3a48f82b103175b83d1036bff31b00f5122606aa))
