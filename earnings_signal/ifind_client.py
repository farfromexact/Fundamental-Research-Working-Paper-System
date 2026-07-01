from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

import pandas as pd


class IFindClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class IFindCredentials:
    username: str
    password: str

    @classmethod
    def from_env(cls) -> "IFindCredentials":
        username = os.environ.get("IFIND_USERNAME")
        password = os.environ.get("IFIND_PASSWORD")
        if not username or not password:
            raise IFindClientError("IFIND_USERNAME and IFIND_PASSWORD are required")
        return cls(username=username, password=password)


class IFindClient:
    def __init__(self, credentials: IFindCredentials | None = None) -> None:
        self.credentials = credentials or IFindCredentials.from_env()
        self._api: Any | None = None
        self._logged_in = False

    def __enter__(self) -> "IFindClient":
        self.login()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.logout()

    def login(self) -> None:
        if self._logged_in:
            return
        import iFinDPy  # type: ignore

        result = iFinDPy.THS_iFinDLogin(self.credentials.username, self.credentials.password)
        if result not in (0, "0", None):
            raise IFindClientError(f"iFinD login failed with code {result}")
        self._api = iFinDPy
        self._logged_in = True

    def logout(self) -> None:
        if self._api is not None and self._logged_in:
            try:
                self._api.THS_iFinDLogout()
            finally:
                self._logged_in = False

    def basic_data(self, codes: list[str], indicators: list[str], params: str = "") -> pd.DataFrame:
        self._require_login()
        result = self._api.THS_BasicData(",".join(codes), ",".join(indicators), params)
        return self._to_dataframe(result)

    def data_pool(self, pool_name: str, params: str = "", options: str = "") -> pd.DataFrame:
        self._require_login()
        result = self._api.THS_DataPool(pool_name, params, options)
        return self._to_dataframe(result)

    def iwencai(self, query: str, domain: str = "stock") -> pd.DataFrame:
        self._require_login()
        result = self._api.THS_iwencai(query, domain)
        return self._to_dataframe(result)

    def wc_query(self, query: str, domain: str = "stock") -> pd.DataFrame:
        self._require_login()
        if hasattr(self._api, "THS_WCQuery"):
            result = self._api.THS_WCQuery(query, domain)
            return self._to_dataframe(result)
        return self.iwencai(query, domain=domain)

    def _require_login(self) -> None:
        if self._api is None or not self._logged_in:
            raise IFindClientError("Call login() before querying iFinD")

    def _to_dataframe(self, result: Any) -> pd.DataFrame:
        errorcode = getattr(result, "errorcode", 0)
        if errorcode not in (0, "0", None):
            errmsg = getattr(result, "errmsg", "")
            raise IFindClientError(f"iFinD query failed with code {errorcode}: {errmsg}")
        data = getattr(result, "data", None)
        if isinstance(data, pd.DataFrame):
            return data
        if isinstance(data, list):
            return pd.DataFrame(data)
        if isinstance(result, pd.DataFrame):
            return result
        if hasattr(self._api, "THS_Trans2DataFrame"):
            try:
                frame = self._api.THS_Trans2DataFrame(result)
            except Exception:
                frame = None
            if isinstance(frame, pd.DataFrame):
                return frame
        raise IFindClientError(f"Cannot convert iFinD result to DataFrame: {type(result)!r}")
