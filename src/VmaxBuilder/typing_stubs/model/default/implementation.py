from typing import Protocol

from VmaxBuilder.base.enums import ReactionNotation


class DefaultModelConfigProtocol(Protocol):
    reaction_notation: ReactionNotation
    make_copy: bool
    id_type: str
    level: str
    maximum_transcript_ifp_expansion: int
