
import base64
import hashlib
import math
import re
import secrets
import time
from html.parser import HTMLParser
from typing import Dict, List, Optional, Sequence, Tuple


EPOCH_SECONDS = 1682924400
DEFAULT_KEYWORD = "obfiowerehiring"
DEFAULT_VERSION = 3
TOTAL_ANIMATION_TIME = 4096


def _js_round(value: float) -> int:
    return math.floor(value + 0.5)


def _float_to_hex(value: float) -> str:
    result: List[str] = []
    quotient = int(value)
    fraction = value - quotient

    while quotient > 0:
        next_quotient = int(quotient / 16)
        remainder = quotient - next_quotient * 16
        result.insert(0, chr(remainder + 55) if remainder > 9 else str(remainder))
        quotient = next_quotient

    if fraction == 0:
        return "".join(result)

    result.append(".")
    while fraction > 0:
        fraction *= 16
        integer = int(fraction)
        fraction -= integer
        result.append(chr(integer + 55) if integer > 9 else str(integer))
    return "".join(result)


class _CubicBezier:
    def __init__(self, curves: Sequence[float]):
        if len(curves) != 4:
            raise ValueError("cubic-bezier requires four control values")
        self.curves = curves

    @staticmethod
    def _calculate(a: float, b: float, m: float) -> float:
        return (
            3.0 * a * (1.0 - m) * (1.0 - m) * m
            + 3.0 * b * (1.0 - m) * m * m
            + m * m * m
        )

    def get_value(self, target: float) -> float:
        x1, y1, x2, y2 = self.curves
        if target <= 0.0:
            if x1 > 0.0:
                gradient = y1 / x1
            elif y1 == 0.0 and x2 > 0.0:
                gradient = y2 / x2
            else:
                gradient = 0.0
            return gradient * target

        if target >= 1.0:
            if x2 < 1.0:
                gradient = (y2 - 1.0) / (x2 - 1.0)
            elif x2 == 1.0 and x1 < 1.0:
                gradient = (y1 - 1.0) / (x1 - 1.0)
            else:
                gradient = 0.0
            return 1.0 + gradient * (target - 1.0)

        start = 0.0
        end = 1.0
        mid = 0.0
        while start < end:
            mid = (start + end) / 2.0
            estimated = self._calculate(x1, x2, mid)
            if abs(target - estimated) < 0.00001:
                return self._calculate(y1, y2, mid)
            if estimated < target:
                start = mid
            else:
                end = mid
        return self._calculate(y1, y2, mid)


class _HomeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.verification: Optional[str] = None
        self.frames: Dict[int, List[str]] = {}
        self._current_frame: Optional[int] = None

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        values = dict(attrs)
        if tag == "meta" and values.get("name") == "twitter-site-verification":
            self.verification = values.get("content")
            return

        if tag == "svg":
            element_id = values.get("id") or ""
            match = re.fullmatch(r"loading-x-anim-(\d+)", element_id)
            if match:
                self._current_frame = int(match.group(1))
                self.frames[self._current_frame] = []
            return

        if tag == "path" and self._current_frame is not None:
            path_data = values.get("d")
            if path_data:
                self.frames[self._current_frame].append(path_data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "svg":
            self._current_frame = None


def _solve(value: float, minimum: float, maximum: float, rounding: bool) -> float:
    result = value * (maximum - minimum) / 255.0 + minimum
    return float(math.floor(result)) if rounding else round(result, 2)


def _interpolate(start: Sequence[float], end: Sequence[float], factor: float) -> List[float]:
    return [left * (1.0 - factor) + right * factor for left, right in zip(start, end)]


def _rotation_matrix(degrees: float) -> List[float]:
    radians = math.radians(degrees)
    return [
        math.cos(radians),
        -math.sin(radians),
        math.sin(radians),
        math.cos(radians),
    ]


def _animate(frame: Sequence[int], target_time: float) -> str:
    start_color = [float(item) for item in [*frame[:3], 1]]
    end_color = [float(item) for item in [*frame[3:6], 1]]
    end_rotation = _solve(float(frame[6]), 60.0, 360.0, True)
    curve_values = [
        _solve(float(value), -1.0 if index % 2 else 0.0, 1.0, False)
        for index, value in enumerate(frame[7:])
    ]

    factor = _CubicBezier(curve_values).get_value(target_time)
    color = _interpolate(start_color, end_color, factor)
    color = [max(0.0, min(255.0, value)) for value in color]
    rotation = _interpolate([0.0], [end_rotation], factor)[0]

    parts = [format(round(value), "x") for value in color[:-1]]
    for value in _rotation_matrix(rotation):
        rounded = abs(round(value, 2))
        hex_value = _float_to_hex(rounded)
        if hex_value.startswith("."):
            hex_value = "0" + hex_value
        parts.append(hex_value.lower() if hex_value else "0")
    parts.extend(["0", "0"])
    return re.sub(r"[.-]", "", "".join(parts))


def _parse_home(html: str) -> Tuple[str, Dict[int, List[str]]]:
    parser = _HomeParser()
    parser.feed(html)
    if not parser.verification:
        raise ValueError("twitter-site-verification meta tag was not found")
    if len(parser.frames) < 4:
        raise ValueError("loading-x-anim SVG frames were not found")
    return parser.verification, parser.frames


def _discover_ondemand_url(html: str) -> str:
    chunk_match = re.search(r",(\d+):[\"']ondemand\.s[\"']", html)
    if not chunk_match:
        raise ValueError("ondemand.s chunk id was not found")
    chunk_id = chunk_match.group(1)
    hash_match = re.search(r",[\"']?" + re.escape(chunk_id) + r"[\"']?:[\"']([0-9a-f]+)[\"']", html)
    if not hash_match:
        raise ValueError("ondemand.s chunk hash was not found")
    return (
        "https://abs.twimg.com/responsive-web/client-web/"
        "ondemand.s." + hash_match.group(1) + "a.js"
    )


def _parse_indices(source: str) -> Tuple[int, List[int]]:
    values = [int(item) for item in re.findall(r"\(\w\[(\d{1,2})\],\s*16\)", source)]
    if len(values) < 2:
        raise ValueError("key-byte indices were not found in ondemand.s")
    return values[0], values[1:]


def _parse_frame_rows(path_data: str) -> List[List[int]]:
    rows = []
    for item in path_data[9:].split("C"):
        values = re.sub(r"[^\d]+", " ", item).strip().split()
        if values:
            rows.append([int(value) for value in values])
    return rows


class XClientTransaction:
    def __init__(
        self,
        verification: str,
        frames: Dict[int, List[str]],
        row_index: int,
        key_indices: Sequence[int],
    ) -> None:
        self.verification = verification
        self.key_bytes = list(base64.b64decode(verification))
        self.frames = frames
        self.row_index = row_index
        self.key_indices = list(key_indices)
        self.animation_key = self._get_animation_key()

    @classmethod
    def from_session(cls, session, home_url: str = "https://x.com/home", timeout: int = 20):
        home_response = session.get(home_url, timeout=timeout)
        home_response.raise_for_status()
        verification, frames = _parse_home(home_response.text)

        ondemand_url = _discover_ondemand_url(home_response.text)
        ondemand_response = session.get(ondemand_url, timeout=timeout)
        ondemand_response.raise_for_status()
        row_index, key_indices = _parse_indices(ondemand_response.text)
        return cls(verification, frames, row_index, key_indices)

    def _get_animation_key(self) -> str:
        frame_id = self.key_bytes[5] % 4
        paths = self.frames.get(frame_id)
        if not paths or len(paths) < 2:
            raise ValueError("selected SVG animation path was not found")

        rows = _parse_frame_rows(paths[1])
        selected_row = self.key_bytes[self.row_index] % 16
        frame_time = math.prod(self.key_bytes[index] % 16 for index in self.key_indices)
        frame_time = _js_round(frame_time / 10.0) * 10
        target_time = float(frame_time) / TOTAL_ANIMATION_TIME
        return _animate(rows[selected_row], target_time)

    def generate(
        self,
        method: str,
        path: str,
        time_now: Optional[int] = None,
        random_byte: Optional[int] = None,
    ) -> str:
        if not path.startswith("/"):
            raise ValueError("path must be a URL path beginning with '/'")
        if time_now is None:
            time_now = math.floor(time.time() - EPOCH_SECONDS)
        if random_byte is None:
            random_byte = secrets.randbelow(256)

        message = (
            f"{method.upper()}!{path}!{time_now}"
            f"{DEFAULT_KEYWORD}{self.animation_key}"
        )
        digest = hashlib.sha256(message.encode("utf-8")).digest()
        time_bytes = [(time_now >> (index * 8)) & 0xFF for index in range(4)]
        plain = [*self.key_bytes, *time_bytes, *digest[:16], DEFAULT_VERSION]
        encoded = bytes([random_byte, *[value ^ random_byte for value in plain]])
        return base64.b64encode(encoded).decode("ascii").rstrip("=")


def decode_transaction_id(value: str) -> Dict[str, object]:
    padded = value + "=" * (-len(value) % 4)
    raw = base64.b64decode(padded)
    if len(raw) != 70:
        raise ValueError(f"unexpected transaction id size: {len(raw)}")
    random_byte = raw[0]
    plain = bytes(byte ^ random_byte for byte in raw[1:])
    relative_time = int.from_bytes(plain[48:52], "little")
    return {
        "random_byte": random_byte,
        "verification_bytes": plain[:48],
        "relative_time": relative_time,
        "unix_time": relative_time + EPOCH_SECONDS,
        "hash_prefix": plain[52:68],
        "version": plain[68],
    }
