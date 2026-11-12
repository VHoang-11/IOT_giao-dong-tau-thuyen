"""Deterministic xorshift32 PRNG compatible with the SVMG C implementation."""

import math

UINT32_MASK = 0xFFFFFFFF
UINT32_RANGE = 1 << 32


class XorShift32:
    """Small stateful xorshift32 generator matching ``core/src/sim/generator.c``.

    The C implementation does not remap seed zero, so this class preserves the
    same convention: a zero seed is a valid uint32 state and yields zero forever.
    For ``random()``, each uint32 output is divided by 2**32, giving [0, 1).
    """

    __slots__ = ("_seed", "_state")

    def __init__(self, seed: int) -> None:
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise TypeError("seed must be an integer")
        if not 0 <= seed <= UINT32_MASK:
            raise ValueError("seed must be in [0, 0xFFFFFFFF]")
        self._seed = seed
        self._state = seed

    @property
    def seed(self) -> int:
        """The initial seed, retained for run metadata."""
        return self._seed

    @property
    def state(self) -> int:
        """Current unsigned 32-bit generator state."""
        return self._state

    def next_uint32(self) -> int:
        """Advance once and return the next unsigned 32-bit value.

        Masking after each xor models C's uint32_t assignment truncation, so
        shifts and subsequent operations observe the same state as the C code.
        """
        value = self._state
        value ^= value << 13
        value &= UINT32_MASK
        value ^= value >> 17
        value &= UINT32_MASK
        value ^= value << 5
        value &= UINT32_MASK
        self._state = value
        return value

    def random(self) -> float:
        """Return the next uniform value in [0, 1) using uint32 / 2**32."""
        return self.next_uint32() / float(UINT32_RANGE)

    def normal(self) -> float:
        """Return one standard-normal variate using Box-Muller.

        The first uint32 is mapped to the open interval (0, 1) with
        ``(x + 0.5) / 2**32`` before taking its logarithm, so log(0) cannot
        occur. The second uint32 uses the generator's [0, 1) mapping as the
        uniform angle. The second Box-Muller variate is intentionally discarded
        to keep each call's PRNG consumption simple and predictable.
        """
        first = (self.next_uint32() + 0.5) / float(UINT32_RANGE)
        second = self.random()
        radius = math.sqrt(-2.0 * math.log(first))
        angle = 2.0 * math.pi * second
        return radius * math.cos(angle)
