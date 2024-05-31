"""Config"""

import errno
import os
import tomllib

from dataclasses import dataclass, field
from pathlib import PosixPath
from typing import Any, Final

DEFAULT_CONFIG_PATH: Final[str] = "~/.config/vc-auto-poster.toml"


@dataclass(slots=True)
class Config:
    """Config"""

    url: str
    topic: int
    api_username: str
    api_key: str

    min_delay: int = 20
    min_posts: int = 50
    auto_align: bool = True
    suppress_tags: list[str] = field(default_factory=list)

    pretty: bool = False
    links: bool = False
    game_name: str | None = None

    keep_unknown_votes: bool = False
    unique_voter_substring_match: bool = False
    min_voter_substring_length: int = 3


def load_config(path: str | PosixPath | None = None) -> Config:
    """Loads the configuration"""

    path_: PosixPath
    match path:
        case PosixPath():
            path_ = path
        case str():
            path_ = PosixPath(path)
        case _:
            path_ = PosixPath(DEFAULT_CONFIG_PATH)

    path_ = path_.expanduser().resolve()

    if not path_.exists():
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), path_)

    with open(path_, "rb") as f:
        config: dict[str, Any] = tomllib.load(f)

    return Config(**config)
