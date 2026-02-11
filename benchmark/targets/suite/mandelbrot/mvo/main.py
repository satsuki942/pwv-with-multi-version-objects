import time


# This benchmark has been modified based on the SOM benchmark.
#
# Copyright (C) 2004-2013 Brent Fulgham
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions and the following disclaimer.
#
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions and the following disclaimer in the documentation
#     and/or other materials provided with the distribution.
#
#   * Neither the name of "The Computer Language Benchmarks Game" nor the name
#     of "The Computer Language Shootout Benchmarks" nor the names of its
#     contributors may be used to endorse or promote products derived from this
#     software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# The Computer Language Benchmarks Game
# http://benchmarksgame.alioth.debian.org
#
#  contributed by Karl von Laudermann
#  modified by Jeremy Echols
#  modified by Detlef Reichl
#  modified by Joseph LaFata
#  modified by Peter Zotov

# http://benchmarksgame.alioth.debian.org/u64q/program.php?test=mandelbrot&lang=yarv&id=3

class Mandelbrot__1__:
    def _mandelbrot(self, size):
        _sum = 0
        byte_acc = 0
        bit_num = 0

        y = 0

        while y < size:
            ci = (2.0 * y / size) - 1.0
            x = 0

            while x < size:
                zrzr = 0.0
                zi = 0.0
                zizi = 0.0
                cr = (2.0 * x / size) - 1.5

                z = 0
                not_done = True
                escape = 0
                while not_done and z < 50:
                    zr = zrzr - zizi + cr
                    zi = 2.0 * zr * zi + ci

                    zrzr = zr * zr
                    zizi = zi * zi

                    if zrzr + zizi > 4.0:
                        not_done = False
                        escape = 1
                    z += 1

                byte_acc = (byte_acc << 1) + escape
                bit_num = bit_num + 1

                if bit_num == 8:
                    _sum ^= byte_acc
                    byte_acc = 0
                    bit_num = 0
                elif x == size - 1:
                    byte_acc <<= 8 - bit_num
                    _sum ^= byte_acc
                    byte_acc = 0
                    bit_num = 0
                x += 1
            y += 1

        return _sum

def main():
    start_time = time.perf_counter()
    
    mandelbrot = Mandelbrot()
    mandelbrot._mandelbrot(500)

    end_time = time.perf_counter()
    avg_time = end_time - start_time

    print(avg_time)

main()