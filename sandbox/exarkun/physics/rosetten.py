width = 600
height = 600

from math import pi, cos, sin

d = 200
n = 6
v = 0.0777 * (n ** 0.5)
m = 1e12 / n
k = (2 * pi) / 1
config = [(m,
           (d * cos(i * (2 * pi) / n + k), d * sin(i * (2 * pi) / n + k), 0),
           (v * sin(i * (2 * pi) / n + k), -v * cos(i * (2 * pi) / n + k), 0))
          for i in range(n)]
