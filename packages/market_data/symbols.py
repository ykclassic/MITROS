from dataclasses import dataclass

@dataclass(frozen=True)
class SymbolMapping:
    canonical:str
    provider_symbol:str

class SymbolMapper:
    def __init__(self,mappings:dict[str,dict[str,str]])->None:
        self._mappings=mappings
    def resolve(self,provider:str,canonical:str)->SymbolMapping:
        try: return SymbolMapping(canonical, self._mappings[provider][canonical])
        except KeyError as exc: raise ValueError(f"No symbol mapping for {provider}:{canonical}") from exc
