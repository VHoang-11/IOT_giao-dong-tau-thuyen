#!/usr/bin/env python3
"""Đáp án tham chiếu độc lập cho test M1-02 (không dùng core/src/filter.c).

Chạy:  python tests/firmware/tools/ref_filter.py
Chỉ dùng thư viện chuẩn (math) với số thực 64 bit; các hằng in ra được dán vào
tests/firmware/test/test_filter/test_filter.c cùng dung sai nêu trong file đó.
"""
import cmath
import math

G = 9.80665


def butter2_lp(fc, fs):
    """Butterworth bậc 2, biến đổi song tuyến tính có prewarp."""
    k = math.tan(math.pi * fc / fs)
    norm = 1.0 / (1.0 + math.sqrt(2) * k + k * k)
    b0 = k * k * norm
    return (b0, 2 * b0, b0, 2 * (k * k - 1) * norm, (1 - math.sqrt(2) * k + k * k) * norm)


def gain(coef, f, fs):
    b0, b1, b2, a1, a2 = coef
    z = cmath.exp(-1j * 2 * math.pi * f / fs)
    return abs((b0 + b1 * z + b2 * z * z) / (1 + a1 * z + a2 * z * z))


def run_biquad(coef, xs, x0_state=0.0):
    b0, b1, b2, a1, a2 = coef
    z1 = z2 = x0_state
    out = []
    for x in xs:
        y = b0 * x + z1
        z1 = b1 * x - a1 * y + z2
        z2 = b2 * x - a2 * y
        out.append(y)
    return out


def main():
    c = butter2_lp(0.5, 20.0)
    print("C1 coef b0,b1,b2,a1,a2 =", ["%.8f" % v for v in c])
    s = run_biquad(c, [1.0] * 5)
    print("C3 step y0..y2        =", ["%.8f" % v for v in s[:3]])
    for f in (0.05, 0.5, 1.5, 5.0):
        print("C4 |H(%.2f Hz)|       = %.6f" % (f, gain(c, f, 20.0)))

    a = 0.95
    print("B2 alpha=0.95: n=1,2,20 ->",
          ["%.8f" % (math.pi / 4 * (1 - a ** n)) for n in (1, 2, 20)])
    # Equilibrium with gyro bias: e = alpha*(e + b*dt) -> e = alpha*b*dt/(1-alpha) = tau*b  (tau = alpha*dt/(1-alpha))
    dt, b = 0.05, 0.01
    tau_eff = a * dt / (1 - a)
    print("B4 equilibrium = %.6f rad (tau_eff=%.4f s)" % (tau_eff * b, tau_eff))
    print("B6 alpha=0.9: %.8f" % ((1 - 0.9) * math.pi / 4))

    # Nhóm E: roll 10 deg, T=20 s ; RMS ngõ ra trên số nguyên chu kỳ sau 60 s
    amp = 10.0
    print("E1 RMS input = %.4f deg" % (amp / math.sqrt(2)))
    # E4: bias gyro 0.1 deg/s, tau = 7.5 s (alpha tính theo dt=0.05)
    alpha = 7.5 / (7.5 + 0.05)
    e = alpha * 0.1 * 0.05 / (1 - alpha)
    print("E4 equilibrium = %.5f deg (tau=7.5 s -> tau*bias=%.3f)" % (e, 7.5 * 0.1))


if __name__ == "__main__":
    main()
