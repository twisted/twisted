width = 1600
height = 1600

from math import pi, cos, sin

d = 100
n = 8
v = 0.0777 * n
m = 1e12 / n
k = (2 * pi) / 1
config = [(m,
           (d * cos(i * (2 * pi) / n + k), d * sin(i * (2 * pi) / n + k), 0),
           (v * sin(i * (2 * pi) / n + k), -v * cos(i * (2 * pi) / n + k), 0))
          for i in range(n)]
