AU = 1.5e11
EM = 5.9737e24

config = [
    # The sun
    (3.334e5 * EM, (0, 0, 0), (0, 0, 0)),

    # Mercury
    (6e-2 * EM, (0.38 * AU, 0, 0), (0, 47872.5, 0)),

    # Venus
    (8.2e-1 * EM, (0.72 * AU, 0, 0), (0, 35021.4, 0)),

    # Earth
    (1.0 * EM, (1.0 * AU, 0, 0), (0, 29785.9, 0)),
]

width = height = max([e[1][0] for e in config]) * 2.1
del e
