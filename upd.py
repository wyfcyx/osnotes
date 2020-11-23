#!/usr/bin/python

import os
import sys
import time

message = ''
if len(sys.argv) == 1:
    message = 'Update'
else:
    message = sys.argv[1]
pattern = "git add -A && git commit -m \"Update %s %s\" && git push"
os.system(pattern % (message, time.asctime(time.localtime(time.time()))))
