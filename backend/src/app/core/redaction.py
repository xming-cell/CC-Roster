"""密钥脱敏: 规则见 `docs/decisions.md` 的 ADR-006。

`redact_secret` 处理单个密钥的三档长度; `redact_text` 在自由文本中定位常见密钥
形态, 再交给 `redact_secret`。错误响应与日志格式化器都必须经过这里。
"""

import re

_MASK = "****"
_SHORT_LENGTH = 8
_MEDIUM_LENGTH = 16

_BEARER_PATTERN = re.compile(r"(?i)(Bearer\s+)([A-Za-z0-9._~+/=-]+)")
_API_KEY_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key\s*[=:]\s*)(?P<quote>['\"]?)([A-Za-z0-9._~+/=-]+)(?P=quote)"
)
# 末尾排除 `*`: 已脱敏的值形如 `sk-l****mnop`, 不再二次替换
_SK_KEY_PATTERN = re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]+(?![A-Za-z0-9_*-])")


def redact_secret(secret: str) -> str:
    """按 ADR-006 的三档长度规则输出脱敏值。"""
    length = len(secret)
    if length <= _SHORT_LENGTH:
        return _MASK
    if length <= _MEDIUM_LENGTH:
        return f"{secret[:2]}{_MASK}{secret[-2:]}"
    return f"{secret[:4]}{_MASK}{secret[-4:]}"


def redact_text(text: str) -> str:
    """替换自由文本中的 `Bearer ...`、`api_key=...` 与 `sk-...`。"""
    text = _BEARER_PATTERN.sub(lambda match: match.group(1) + redact_secret(match.group(2)), text)
    text = _API_KEY_PATTERN.sub(
        lambda match: (
            match.group(1)
            + match.group("quote")
            + redact_secret(match.group(3))
            + match.group("quote")
        ),
        text,
    )
    return _SK_KEY_PATTERN.sub(lambda match: redact_secret(match.group(0)), text)
