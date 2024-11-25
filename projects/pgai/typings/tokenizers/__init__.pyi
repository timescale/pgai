class Encoding:
    @property
    def tokens(self) -> list[str]: ...

class Tokenizer:
    def encode_batch(
        self,
        input: list[str],
        is_pretokenized: bool = False,
        add_special_tokens: bool = True,
    ) -> list[Encoding]: ...
