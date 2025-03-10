import dataclasses
import math

from typing import Any
from typing import Optional
from typing import Tuple
from typing import Union

from poetry.core.version.pep440.segments import RELEASE_PHASE_ALPHA
from poetry.core.version.pep440.segments import RELEASE_PHASE_DEV
from poetry.core.version.pep440.segments import RELEASE_PHASE_POST
from poetry.core.version.pep440.segments import LocalSegmentType
from poetry.core.version.pep440.segments import Release
from poetry.core.version.pep440.segments import ReleaseTag


# we use the phase "z" to ensure we always sort this after other phases
_INF_TAG = ReleaseTag("z", math.inf)  # noqa
# we use the phase "" to ensure we always sort this before other phases
_NEG_INF_TAG = ReleaseTag("", -math.inf)  # noqa


@dataclasses.dataclass(frozen=True, eq=True, order=True)
class PEP440Version:
    epoch: int = dataclasses.field(default=0, compare=False)
    release: Release = dataclasses.field(default_factory=Release, compare=False)
    pre: Optional[ReleaseTag] = dataclasses.field(default=None, compare=False)
    post: Optional[ReleaseTag] = dataclasses.field(default=None, compare=False)
    dev: Optional[ReleaseTag] = dataclasses.field(default=None, compare=False)
    local: LocalSegmentType = dataclasses.field(default=None, compare=False)
    text: str = dataclasses.field(default=None, compare=False)
    _compare_key: Tuple[
        int, Release, ReleaseTag, ReleaseTag, ReleaseTag, Tuple[Union[int, str], ...]
    ] = dataclasses.field(default=None, init=False, compare=True)

    def __post_init__(self) -> None:
        if self.local is not None and not isinstance(self.local, tuple):
            object.__setattr__(self, "local", (self.local,))

        if isinstance(self.release, tuple):
            object.__setattr__(self, "release", Release(*self.release))

        # we do this here to handle both None and tomlkit string values
        object.__setattr__(
            self, "text", self.to_string() if not self.text else str(self.text)
        )

        object.__setattr__(self, "_compare_key", self._make_compare_key())

    def _make_compare_key(
        self,
    ) -> Tuple[
        int, Release, ReleaseTag, ReleaseTag, ReleaseTag, Tuple[Tuple[float, str], ...]
    ]:
        """
        This code is based on the implementation of packaging.version._cmpkey(..)
        """
        # We need to "trick" the sorting algorithm to put 1.0.dev0 before 1.0a0.
        # We'll do this by abusing the pre segment, but we _only_ want to do this
        # if there is not a pre or a post segment. If we have one of those then
        # the normal sorting rules will handle this case correctly.
        if self.pre is None and self.post is None and self.dev is not None:
            _pre = _NEG_INF_TAG
        # Versions without a pre-release (except as noted above) should sort after
        # those with one.
        elif self.pre is None:
            _pre = _INF_TAG
        else:
            _pre = self.pre

        # Versions without a post segment should sort before those with one.
        _post = _NEG_INF_TAG if self.post is None else self.post

        # Versions without a development segment should sort after those with one.
        _dev = _INF_TAG if self.dev is None else self.dev

        if self.local is None:
            # Versions without a local segment should sort before those with one.
            _local = ((-math.inf, ""),)
        else:
            # Versions with a local segment need that segment parsed to implement
            # the sorting rules in PEP440.
            # - Alpha numeric segments sort before numeric segments
            # - Alpha numeric segments sort lexicographically
            # - Numeric segments sort numerically
            # - Shorter versions sort before longer versions when the prefixes
            #   match exactly
            _local = tuple(
                # We typecast strings that are integers so that they can be compared
                (int(i), "") if str(i).isnumeric() else (-math.inf, i)
                for i in self.local
            )
        return self.epoch, self.release, _pre, _post, _dev, _local

    @property
    def major(self) -> int:
        return self.release.major

    @property
    def minor(self) -> Optional[int]:
        return self.release.minor

    @property
    def patch(self) -> Optional[int]:
        return self.release.patch

    @property
    def non_semver_parts(self) -> Optional[Tuple[int]]:
        return self.release.extra

    def to_string(self, short: bool = False) -> str:
        dash = "-" if not short else ""

        version_string = dash.join(
            filter(
                bool,
                [
                    self.release.to_string(),
                    self.pre.to_string(short) if self.pre else self.pre,
                    self.post.to_string(short) if self.post else self.post,
                    self.dev.to_string(short) if self.dev else self.dev,
                ],
            )
        )

        if self.epoch:
            # if epoch is non-zero we should include it
            version_string = f"{self.epoch}!{version_string}"

        if self.local:
            version_string += "+" + ".".join(map(str, self.local))

        return version_string

    @classmethod
    def parse(cls, value: str) -> "PEP440Version":
        from poetry.core.version.pep440.parser import parse_pep440

        return parse_pep440(value, cls)

    def is_prerelease(self) -> bool:
        return self.pre is not None

    def is_postrelease(self) -> bool:
        return self.post is not None

    def is_devrelease(self) -> bool:
        return self.dev is not None

    def is_local(self) -> bool:
        return self.local is not None

    def is_no_suffix_release(self) -> bool:
        return not (self.pre or self.post or self.dev)

    def is_unstable(self) -> bool:
        return self.is_prerelease() or self.is_devrelease()

    def is_stable(self) -> bool:
        return not self.is_unstable()

    def next_major(self) -> "PEP440Version":
        release = self.release
        if self.is_stable() or Release(self.release.major, 0, 0) < self.release:
            release = self.release.next_major()
        return self.__class__(epoch=self.epoch, release=release)

    def next_minor(self) -> "PEP440Version":
        release = self.release
        if (
            self.is_stable()
            or Release(self.release.major, self.release.minor, 0) < self.release
        ):
            release = self.release.next_minor()
        return self.__class__(epoch=self.epoch, release=release)

    def next_patch(self) -> "PEP440Version":
        return self.__class__(
            epoch=self.epoch,
            release=self.release.next_patch() if self.is_stable() else self.release,
        )

    def next_prerelease(self, next_phase: bool = False) -> "PEP440Version":
        if self.is_prerelease():
            pre = self.pre.next_phase() if next_phase else self.pre.next()
        else:
            pre = ReleaseTag(RELEASE_PHASE_ALPHA)
        return self.__class__(epoch=self.epoch, release=self.release, pre=pre)

    def next_postrelease(self) -> "PEP440Version":
        if self.is_prerelease():
            post = self.post.next()
        else:
            post = ReleaseTag(RELEASE_PHASE_POST)
        return self.__class__(
            epoch=self.epoch,
            release=self.release,
            pre=self.pre,
            dev=self.dev,
            post=post,
        )

    def next_devrelease(self) -> "PEP440Version":
        if self.is_prerelease():
            dev = self.dev.next()
        else:
            dev = ReleaseTag(RELEASE_PHASE_DEV)
        return self.__class__(
            epoch=self.epoch, release=self.release, pre=self.pre, dev=dev
        )

    def first_prerelease(self) -> "PEP440Version":
        return self.__class__(
            epoch=self.epoch, release=self.release, pre=ReleaseTag(RELEASE_PHASE_ALPHA)
        )

    def replace(self, **kwargs: Any) -> "PEP440Version":
        return self.__class__(
            **{
                **{
                    k: getattr(self, k)
                    for k in self.__dataclass_fields__.keys()
                    if k not in ("_compare_key", "text")
                },  # setup defaults with current values, excluding compare keys and text
                **kwargs,  # keys to replace
            }
        )

    def without_local(self) -> "PEP440Version":
        return self.replace(local=None)

    def without_postrelease(self) -> "PEP440Version":
        return self.replace(post=None)
