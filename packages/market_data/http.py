from collections.abc import Mapping
from datetime import UTC,datetime
from typing import Any
import httpx

class ProviderHTTPError(RuntimeError): pass

class HTTPProviderBase:
    def __init__(self,*,api_key:str,base_url:str,client:httpx.AsyncClient|None=None)->None:
        self.api_key=api_key
        self.base_url=base_url.rstrip("/")
        self._client=client

    async def _get(self,path:str,params:Mapping[str,str|int|float|bool|None])->dict[str,Any]:
        client=self._client or httpx.AsyncClient(timeout=10.0)
        try:
            response=await client.get(f"{self.base_url}/{path.lstrip('/')}",params=params)
            response.raise_for_status()
            data=response.json()
            if not isinstance(data,dict): raise ProviderHTTPError("Provider returned non-object payload")
            return data
        except (httpx.HTTPError,ValueError) as exc:
            raise ProviderHTTPError(str(exc)) from exc
        finally:
            if self._client is None: await client.aclose()

def utc_from_epoch(value:float)->datetime:
    return datetime.fromtimestamp(value,tz=UTC)
