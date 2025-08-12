
def data_to_str(data: bytes | str) -> str:
    if isinstance(data, (bytes, bytearray)):
        return data.decode("utf-8", errors="ignore")
    return data  # type: ignore
