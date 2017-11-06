#!/usr/bin/env python3

import markovify
import json
import sys

strings = []
for filename in sys.argv[1:-1]:
    with open(filename, 'r') as f:
        string = f.read()
    strings.append(string)

combined = markovify.combine([markovify.NewlineText.from_json(string)
    for string in strings])

with open(sys.argv[-1], 'w') as f:
    f.write(combined.to_json())
